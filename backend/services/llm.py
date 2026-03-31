import os

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def call_groq(system_prompt: str, user_message: str) -> str:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return response.choices[0].message.content.strip()


def call_ollama(system_prompt: str, user_message: str) -> str:
    import ollama
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response["message"]["content"].strip()


def call_llm(system_prompt: str, user_message: str) -> str:
    groq_key = os.getenv("GROQ_API_KEY", "")
    use_groq = groq_key and groq_key != "your_groq_api_key_here"

    if use_groq:
        try:
            return call_groq(system_prompt, user_message)
        except Exception as e:
            print(f"[LLM] Groq failed: {e}")
            raise RuntimeError(f"Groq failed: {e}. Please try again later.")

    raise RuntimeError("No LLM configured. Set GROQ_API_KEY environment variable.")