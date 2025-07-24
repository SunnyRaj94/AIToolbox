# src/aitoolkit/backend/llm/groq_llm.py
from typing import AsyncGenerator, Dict, Any, Optional
from groq import AsyncGroq
from .base import BaseLLM
from aitoolkit.config import env, configs # For API key and default models

class Groq_LLM(BaseLLM):
    """
    Groq LLM integration.
    """
    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None, **kwargs):
        super().__init__(
            model_name=model_name or configs.get('llm_settings').get('groq_default_model'),
            api_key=api_key or env.get("GROQ_API_KEY"),
            **kwargs
        )
        if not self.api_key:
            raise ValueError("Groq API key is not provided. Please set GROQ_API_KEY environment variable or pass it during initialization.")
        # FIX: Instantiate AsyncGroq
        self.client = AsyncGroq(api_key=self.api_key)

    async def generate_response(self, prompt: str, temperature: float = 0.7, **kwargs) -> str:
        """
        Generates a single, non-streaming response from Groq.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                stream=False,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating Groq response: {e}"

    async def stream_response(self, prompt: str, temperature: float = 0.7, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generates a streaming response from Groq.
        """
        try:
            # This line remains without await, as it returns an async iterator directly
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                stream=True,
                **kwargs
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error streaming Groq response: {e}"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": "Groq",
            "model_name": self.model_name,
            "api_key_set": bool(self.api_key),
            "type": "cloud_api"
        }