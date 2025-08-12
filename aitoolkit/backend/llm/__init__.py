# src/aitoolkit/backend/llm/__init__.py
from .base import BaseLLM
from .openai_llm import OpenAI_LLM
from .groq_llm import Groq_LLM
from .embedding import EmbeddingLLM, EMBEDDING_LLM_REGISTRY 
# from .ollama_llm import Ollama_LLM # Add when implemented
# from .google_gemini_llm import GoogleGemini_LLM # Add when implemented

# A dictionary to map provider names to their respective LLM classes
LLM_REGISTRY = {
    "OpenAI": OpenAI_LLM,
    "Groq": Groq_LLM,
    # "Ollama": Ollama_LLM,
    # "Google Gemini": GoogleGemini_LLM,
}