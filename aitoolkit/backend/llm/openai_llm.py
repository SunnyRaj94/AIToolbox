# src/aitoolkit/backend/llm/openai_llm.py
from typing import AsyncGenerator, Dict, Any, Optional
from openai import AsyncOpenAI # Use AsyncOpenAI for async operations
from aitoolkit.backend.llm.base import BaseLLM
from aitoolkit.config import env, configs # For API key and default models

class OpenAI_LLM(BaseLLM):
    """
    OpenAI LLM integration.
    """
    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None, **kwargs):
        # Prioritize provided api_key, then environment variable, then None
        super().__init__(
            model_name=model_name or configs.get('llm_settings').get("openai_default_model"),
            api_key=api_key or env.get("OPENAI_API_KEY"),
            **kwargs
        )
        if not self.api_key:
            raise ValueError("OpenAI API key is not provided. Please set OPENAI_API_KEY environment variable or pass it during initialization.")
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate_response(self, prompt: str, temperature: float = 0.7, **kwargs) -> str:
        """
        Generates a single, non-streaming response from OpenAI.
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
            return f"Error generating OpenAI response: {e}"

    async def stream_response(self, prompt: str, temperature: float = 0.7, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generates a streaming response from OpenAI.
        """
        try:
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
            yield f"Error streaming OpenAI response: {e}"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": "OpenAI",
            "model_name": self.model_name,
            "api_key_set": bool(self.api_key),
            "type": "cloud_api"
        }