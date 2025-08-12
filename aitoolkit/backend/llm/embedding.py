# aitoolkit/backend/llm/embedding.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import os
import logging

log = logging.getLogger(__name__)

class EmbeddingLLM(ABC):
    """Abstract base class for Language Model services that provide embeddings."""

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding vector for the given text.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict:
        """
        Returns information about the embedding model, including API key status.
        """
        pass

# --- Concrete Implementations ---

class OpenAIEmbeddingLLM(EmbeddingLLM):
    """OpenAI Embedding LLM implementation."""

    def __init__(self, model_name: str = "text-embedding-ada-002"):
        super().__init__(model_name=model_name, api_key=os.getenv("OPENAI_API_KEY"))
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "The 'openai' library is not installed. Please install it with `poetry add openai`."
            )
        
        if not self.api_key:
            raise ValueError("OpenAI API key is not set. Please set OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=self.api_key)

    def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding vector for the given text using OpenAI.
        """
        try:
            # OpenAI's embedding API is synchronous in the standard client.
            response = self.client.embeddings.create(
                input=text,
                model=self.model_name
            )
            return response.data[0].embedding
        except Exception as e:
            log.error(f"Error generating OpenAI embedding: {e}")
            raise ValueError(f"Failed to generate embedding with OpenAI: {e}")

    def get_model_info(self) -> Dict:
        """
        Returns information about the OpenAI embedding model.
        """
        return {
            "provider": "OpenAI Embeddings",
            "model_name": self.model_name,
            "api_key_set": bool(self.api_key)
        }

class GoogleGeminiEmbeddingLLM(EmbeddingLLM):
    """Google Gemini Embedding LLM implementation."""

    def __init__(self, model_name: str = "text-embedding-004"):
        super().__init__(model_name=model_name, api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("The 'google-generativeai' library is not installed. Please install it with `poetry add google-generativeai`.")
        
        if not self.api_key:
            raise ValueError("Google Gemini API key is not set. Please set GOOGLE_GEMINI_API_KEY environment variable.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)

    def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding vector for the given text using Google Gemini.
        """
        try:
            response = self.model.embed_content(
                model=self.model_name,
                content=text
            )
            return response['embedding'] # Access the embedding from the response structure
        except Exception as e:
            log.error(f"Error generating Google Gemini embedding: {e}")
            raise ValueError(f"Failed to generate embedding with Google Gemini: {e}")

    def get_model_info(self) -> Dict:
        """
        Returns information about the Google Gemini embedding model.
        """
        return {
            "provider": "Google Gemini Embeddings",
            "model_name": self.model_name,
            "api_key_set": bool(self.api_key)
        }

class OllamaEmbeddingLLM(EmbeddingLLM):
    """Ollama Embedding LLM implementation."""

    def __init__(self, model_name: str = "nomic-embed-text"):
        super().__init__(model_name=model_name) # Ollama typically runs locally and doesn't use API keys
        try:
            from ollama import Client # Ollama client library
        except ImportError:
            raise ImportError("The 'ollama' library is not installed. Please install it with `poetry add ollama`.")
        self.client = Client() # Assumes Ollama server is running locally

    def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding vector for the given text using Ollama.
        """
        try:
            response = self.client.embeddings(model=self.model_name, prompt=text)
            return response['embedding']
        except Exception as e:
            log.error(f"Error generating Ollama embedding: {e}. Is Ollama server running and model '{self.model_name}' pulled?")
            raise ValueError(f"Failed to generate embedding with Ollama: {e}")

    def get_model_info(self) -> Dict:
        """
        Returns information about the Ollama embedding model.
        """
        return {
            "provider": "Ollama Embeddings",
            "model_name": self.model_name,
            "api_key_set": False # No API key needed for Ollama
        }
    
class SentenceTransformersEmbeddingLLM(EmbeddingLLM):
    """
    Local embedding LLM implementation using the sentence-transformers library.
    This allows loading models directly from Hugging Face.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        super().__init__(model_name=model_name) # No API key needed for local models
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "The 'sentence-transformers' library is not installed. Please install it with `poetry add sentence-transformers`."
            )
        try:
            # Load the model directly from Hugging Face
            self.model = SentenceTransformer(self.model_name)
            log.info(f"Successfully loaded local embedding model: {self.model_name}")
        except Exception as e:
            log.error(f"Error loading SentenceTransformer model '{self.model_name}': {e}")
            raise ValueError(f"Failed to load local embedding model '{self.model_name}': {e}")

    def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding vector for the given text using the loaded local model.
        """
        try:
            # Encode the text to get the embedding vector
            embedding = self.model.encode(text, convert_to_numpy=False).tolist()
            return embedding
        except Exception as e:
            log.error(f"Error generating embedding with local model '{self.model_name}': {e}")
            raise ValueError(f"Failed to generate embedding with local model: {e}")

    def get_model_info(self) -> Dict:
        """
        Returns information about the local embedding model.
        """
        return {
            "provider": "Local (Sentence Transformers)",
            "model_name": self.model_name,
            "api_key_set": False # No API key needed
        }

EMBEDDING_LLM_REGISTRY = {
    "OpenAI": OpenAIEmbeddingLLM,
    "Google Gemini": GoogleGeminiEmbeddingLLM,
    "Ollama": OllamaEmbeddingLLM,
    "Local (Sentence Transformers)": SentenceTransformersEmbeddingLLM,
}