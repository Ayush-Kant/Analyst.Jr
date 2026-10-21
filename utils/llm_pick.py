import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()


def pick_llm(level: str) -> ChatGroq:
    """
    Return the configured Groq model for the requested complexity level.

    The low, medium, high, and legacy claude levels are preserved for
    compatibility with the existing agents. All levels intentionally use
    the same Groq model.
    """
    level = level.lower()
    model_by_level = {
        "low": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        "medium": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        "high": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        "claude": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
    }

    if level not in model_by_level:
        raise ValueError(f"Unsupported level: {level}")

    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to your .env file."
        )

    return ChatGroq(
        model=model_by_level[level],
        temperature=0,
    )


if __name__ == "__main__":
    llm_obj = pick_llm("low")
    print(llm_obj.invoke("What is the capital of France?"))
