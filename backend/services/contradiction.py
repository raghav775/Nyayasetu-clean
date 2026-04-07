from services.llm import call_llm
import json
import re


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes add despite instructions."""
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text.strip())
    return text.strip()


def _extract_json(raw: str) -> dict | None:
    """Try multiple strategies to extract a valid JSON object from raw LLM output."""
    if not raw:
        return None

    # Strategy 1: Strip markdown fences, then parse
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Strategy 2: Direct parse of original
    try:
        return json.loads(raw.strip())
    except Exception:
        pass

    # Strategy 3: Find the outermost { ... } block
    try:
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass

    # Strategy 4: Regex for JSON block
    try:
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass

    return None


def find_contradictions(document_a: str, document_b: str) -> dict:
    system_prompt = """You are an expert Indian legal analyst specializing in contract review.
Compare two legal documents and identify every contradiction, conflict, or incompatibility.

CRITICAL: Respond with a raw JSON object and nothing else.
No markdown, no code fences (no ```), no explanation, no preamble.
Start your response with { and end with }.

Use exactly this structure:
{
  "total_contradictions": 2,
  "overall_compatibility": "Low - multiple conflicts found",
  "contradictions": [
    {
      "clause": "Termination Notice Period",
      "party_a_position": "30 days written notice required",
      "party_b_position": "90 days notice required per addendum",
      "suggested_resolution": "Adopt the longer 90-day period to protect both parties"
    }
  ]
}

If no contradictions exist, return exactly:
{"total_contradictions": 0, "overall_compatibility": "High - documents are compatible", "contradictions": []}"""

    user_message = f"""Analyze these two legal documents and return a JSON object listing all contradictions.

=== DOCUMENT A ===
{document_a[:2000]}

=== DOCUMENT B ===
{document_b[:2000]}

Start your response with {{ and end with }}. Raw JSON only."""

    raw = call_llm(system_prompt, user_message, json_mode=True)
    print(f"[Contradiction] Raw LLM response: {raw[:500]}")

    result = _extract_json(raw)

    if result is not None and all(k in result for k in ("total_contradictions", "overall_compatibility", "contradictions")):
        return result

    # All strategies failed — never dump raw LLM text into UI fields
    print(f"[Contradiction] All parse strategies failed. Full raw response: {raw}")
    return {
        "total_contradictions": 0,
        "overall_compatibility": "Analysis error - please try again",
        "contradictions": [],
        "_error": "The AI returned an unexpected response format. Please re-run the analysis."
    }