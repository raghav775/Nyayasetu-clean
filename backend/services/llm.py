import os
import json

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # was llama-3.1-8b-instant
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def call_groq(system_prompt: str, user_message: str, json_mode: bool = False) -> str:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=2048,  # raised from 1500 — JSON was being truncated mid-object
        # response_format removed — llama-3.3-70b ignores the schema in json_object
        # mode and returns a generic dummy object instead of following your structure
    )
    return response.choices[0].message.content.strip()


def call_ollama(system_prompt: str, user_message: str, json_mode: bool = False) -> str:
    import ollama

    kwargs = dict(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    if json_mode:
        kwargs["format"] = "json"  # safe to keep for Ollama, it respects the schema

    response = ollama.chat(**kwargs)
    return response["message"]["content"].strip()


def call_llm(system_prompt: str, user_message: str, json_mode: bool = False) -> str:
    groq_key = os.getenv("GROQ_API_KEY", "")
    use_groq = groq_key and groq_key != "your_groq_api_key_here"

    if use_groq:
        try:
            return call_groq(system_prompt, user_message, json_mode=json_mode)
        except Exception as e:
            print(f"[LLM] Groq failed: {e}")

    try:
        return call_ollama(system_prompt, user_message, json_mode=json_mode)
    except Exception as e:
        print(f"[LLM] Ollama failed: {e}")

    return json.dumps({
        "error": "AI service temporarily unavailable. Please try again."
    }) if json_mode else "⚠️ AI service temporarily unavailable. Please try again."