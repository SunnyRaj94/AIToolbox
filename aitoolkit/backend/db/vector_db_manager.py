# aitoolkit/backend/db/vector_db_manager.py
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import logging
from pathlib import Path
import os

log = logging.getLogger(__name__)

class BaseVectorDBManager(ABC):
    @abstractmethod
    def add_documents(self, texts: List[str], metadatas: List[Dict], namespace: Optional[str] = None):
        """Adds documents (texts and their metadata) to the vector database."""
        pass

    @abstractmethod
    def search(self, query_embedding: List[float], k: int = 5, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Searches the vector database for the most similar documents.
        Returns a list of dictionaries, each containing 'content' and 'metadata'.
        """
        pass

    @abstractmethod
    def delete_namespace(self, namespace: str):
        """Deletes all documents within a given namespace (e.g., for a specific schema)."""
        pass

class FAISSVectorDBManager(BaseVectorDBManager):
    """
    FAISS Vector Database Manager.
    Handles persistence and search for schema embeddings.
    """
    def __init__(self, persist_directory: str, embedding_function):
        try:
            import faiss
            from langchain_community.vectorstores import FAISS
            from langchain_core.embeddings import Embeddings as LangchainEmbeddings
            
            # Helper to wrap our EmbeddingLLM for LangChain's Embeddings interface
            class CustomLangchainEmbeddings(LangchainEmbeddings):
                def __init__(self, embedding_llm_instance):
                    self.embedding_llm = embedding_llm_instance

                def embed_documents(self, texts: List[str]) -> List[List[float]]:
                    # Batch embedding (if supported by LLM, else loop)
                    return [self.embedding_llm.get_embedding(text) for text in texts]

                def embed_query(self, text: str) -> List[float]:
                    return self.embedding_llm.get_embedding(text)

            self._langchain_embeddings_wrapper = CustomLangchainEmbeddings(embedding_function)
            self.FAISS = FAISS
            self.faiss = faiss # For direct FAISS operations if needed

        except ImportError as e:
            log.error(f"Missing FAISS or LangChain dependencies: {e}. Please install them (e.g., `poetry add faiss-cpu langchain-community`).")
            raise ImportError(f"Missing FAISS or LangChain dependencies: {e}")

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.embedding_function = embedding_function # Our EmbeddingLLM instance
        self._db: Optional[FAISS] = None
        self._load_db() # Attempt to load existing DB on init

    def _load_db(self):
        """Loads the FAISS index from the persist directory."""
        index_file = self.persist_directory / "index.faiss"
        pkl_file = self.persist_directory / "index.pkl"

        if index_file.exists() and pkl_file.exists():
            log.info(f"Loading FAISS index from {self.persist_directory}")
            try:
                self._db = self.FAISS.load_local(
                    folder_path=str(self.persist_directory),
                    embeddings=self._langchain_embeddings_wrapper,
                    allow_dangerous_deserialization=True # Necessary for some pickled objects
                )
            except Exception as e:
                log.error(f"Error loading FAISS index from {self.persist_directory}: {e}. Starting fresh.")
                self._db = None # Reset if loading fails
        else:
            log.info(f"No FAISS index found at {self.persist_directory}. Starting fresh.")
            self._db = None # Will be initialized on first add_documents

    def _persist_db(self):
        """Persists the FAISS index to disk."""
        if self._db:
            try:
                self._db.save_local(folder_path=str(self.persist_directory))
                log.info(f"FAISS index saved to {self.persist_directory}")
            except Exception as e:
                log.error(f"Error saving FAISS index to {self.persist_directory}: {e}")

    def add_documents(self, texts: List[str], metadatas: List[Dict], namespace: Optional[str] = None):
        """Adds documents to the FAISS index."""
        if not texts:
            log.warning("No texts provided to add to FAISS.")
            return

        # Ensure metadatas also have the namespace if provided
        for metadata in metadatas:
            if namespace:
                metadata['namespace'] = namespace

        if self._db is None:
            # Initialize the FAISS database with the first batch of documents
            self._db = self.FAISS.from_texts(
                texts=texts,
                embedding=self._langchain_embeddings_wrapper,
                metadatas=metadatas
            )
        else:
            self._db.add_texts(
                texts=texts,
                metadatas=metadatas
            )
        self._persist_db()
        log.info(f"Added {len(texts)} documents to FAISS.")

    def search(self, query_embedding: List[float], k: int = 5, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Searches the FAISS index for the most similar documents.
        Filters are applied *after* retrieval if FAISS itself doesn't support them natively.
        """
        if self._db is None:
            log.warning("FAISS DB not initialized. Cannot perform search.")
            return []

        # LangChain's similarity_search_by_vector (or with_score_by_vector) is preferred.
        # It typically returns Langchain Document objects.
        # Note: Direct pre-filtering by metadata in FAISS.similarity_search is not standard.
        # We perform post-filtering here.
        docs_with_scores = self._db.similarity_search_with_score_by_vector(query_embedding, k=k*2) # Retrieve more to allow for filtering
        
        results = []
        for doc, score in docs_with_scores:
            is_match = True
            if filters:
                for key, value in filters.items():
                    if doc.metadata.get(key) != value:
                        is_match = False
                        break
            if is_match:
                results.append({"content": doc.page_content, "metadata": doc.metadata, "score": score})
            if len(results) >= k: # Stop once we have 'k' filtered results
                break
        
        log.info(f"FAISS search returned {len(results)} results (filtered to k={k}).")
        return results

    def delete_namespace(self, namespace: str):
        """
        Deletes documents associated with a specific namespace.
        Note: Basic FAISS does not have a direct 'delete by metadata' feature.
        This typically requires rebuilding the index from scratch with the desired documents,
        or managing separate indices. For this implementation, we will simulate by marking
        and warning, or if a new index is built, it will naturally exclude them.
        """
        log.warning(f"Deletion of documents by namespace '{namespace}' is not directly supported by basic FAISS. "
                    "For a full delete, the index should be rebuilt, or use a vector DB that supports deletions.")
        # To truly remove, you'd typically filter out documents belonging to this namespace
        # from your source data and re-add them to a *new* FAISS index.
        # This implementation mainly ensures that if add_schema is called, it overwrites.