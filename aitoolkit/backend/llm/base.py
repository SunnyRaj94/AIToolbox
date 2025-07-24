# src/aitoolkit/backend/llm/base.py
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional

class BaseLLM(ABC):
    """
    Abstract Base Class for all Large Language Model integrations.
    Defines the common interface for interacting with different LLM providers.
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None, **kwargs):
        self.model_name = model_name
        self.api_key = api_key
        self.kwargs = kwargs # To capture any additional LLM-specific parameters

    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generates a single, non-streaming response from the LLM.
        Implementations should handle their specific API calls.
        """
        pass

    @abstractmethod
    async def stream_response(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generates a streaming response from the LLM.
        Implementations should yield chunks of text as they become available.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Returns information about the configured LLM model.
        """
        pass

    # Optional: Add methods for token counting, cost estimation, etc. if needed later