# src/aitoolkit/backend/agents/sql_agent.py
from typing import Optional, AsyncGenerator
from aitoolkit.backend.llm import BaseLLM, EmbeddingLLM # Import EmbeddingLLM
from aitoolkit.backend.db import SchemaManager # Import SchemaManager
from aitoolkit.config import configs
from pathlib import Path
import re
import logging

log = logging.getLogger(__name__)

class SQLAgent:
    """
    Agent responsible for generating SQL queries from natural language questions
    based on provided database schemas, utilizing semantic search for context retrieval.
    """
    # CORRECTED __init__ signature
    def __init__(self, llm: BaseLLM, embedding_llm: EmbeddingLLM, schema_manager: SchemaManager):
        self.llm = llm
        self.embedding_llm = embedding_llm # Store the embedding LLM
        self.schema_manager = schema_manager # Store the schema manager
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Loads the default prompt template for the SQL Agent."""
        template_path = Path(configs.get('sql_agent_settings').get('default_prompt_template'))
        if not template_path.exists():
            log.error(f"SQL Agent prompt template not found at: {template_path}")
            raise FileNotFoundError(f"SQL Agent prompt template not found at: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()

    async def generate_sql_query(self, natural_language_question: str, selected_schema_name: str) -> str:
        """
        Generates a SQL query from a natural language question and a selected schema,
        using semantic search to retrieve relevant schema parts.
        """
        # 1. Generate embedding for the question
        try:
            query_embedding = self.embedding_llm.get_embedding(natural_language_question)
        except Exception as e:
            log.error(f"Failed to generate embedding for query: {e}")
            return f"Error: Failed to process query for embedding: {e}"

        # 2. Retrieve relevant schema fragments from the vector store for the selected schema
        # Filter by schema_name namespace if your vector_db_manager supports it, or pass as filter
        relevant_schema_docs = self.schema_manager.vector_db_manager.search(
            query_embedding=query_embedding,
            k=5, # Retrieve top 5 relevant schema fragments
            filters={"schema_name": selected_schema_name} # Filter by the specific schema
        )
        
        # Consolidate relevant DDL fragments
        pruned_schema_definition = ""
        unique_ddl_fragments = set() # Use a set to avoid duplicate DDLs
        for doc in relevant_schema_docs:
            if 'raw_ddl_fragment' in doc['metadata']:
                unique_ddl_fragments.add(doc['metadata']['raw_ddl_fragment'])
        
        if unique_ddl_fragments:
            pruned_schema_definition = "\n\n".join(sorted(list(unique_ddl_fragments))) # Sort for consistent order
        else:
            # Fallback: if no specific fragments are retrieved, use the full schema definition
            # This can happen if embeddings are not perfectly aligned or if schema is very small
            pruned_schema_definition = self.schema_manager.get_schema(selected_schema_name)
            log.warning(f"No specific schema fragments found for '{selected_schema_name}'. Using full schema as fallback.")
            if not pruned_schema_definition:
                return f"Error: Schema '{selected_schema_name}' not found or empty."


        # 3. Construct the prompt for the LLM using the pruned schema
        prompt = self.prompt_template.format(
            schema_definition=pruned_schema_definition,
            question=natural_language_question
        )
        log.info(f"--- SQL Agent Prompt (Pruned Schema) --- \n{prompt[:1000]}...\n--- End Prompt ---") # Log partial prompt

        # 4. Use the LLM to generate the SQL query
        response = await self.llm.generate_response(prompt, temperature=0.1)
        return self._extract_sql_from_response(response)

    async def stream_sql_query(self, natural_language_question: str, selected_schema_name: str) -> AsyncGenerator[str, None]:
        """
        Generates a SQL query from a natural language question and a selected schema, with streaming,
        using semantic search for context retrieval.
        """
        # 1. Generate embedding for the question
        try:
            query_embedding = self.embedding_llm.get_embedding(natural_language_question)
        except Exception as e:
            log.error(f"Failed to generate embedding for query during streaming: {e}")
            yield f"Error: Failed to process query for embedding: {e}"
            return # Stop the generator

        # 2. Retrieve relevant schema fragments
        relevant_schema_docs = self.schema_manager.vector_db_manager.search(
            query_embedding=query_embedding,
            k=5, # Retrieve top 5 relevant schema fragments
            filters={"schema_name": selected_schema_name}
        )
        
        pruned_schema_definition = ""
        unique_ddl_fragments = set()
        for doc in relevant_schema_docs:
            if 'raw_ddl_fragment' in doc['metadata']:
                unique_ddl_fragments.add(doc['metadata']['raw_ddl_fragment'])
        
        if unique_ddl_fragments:
            pruned_schema_definition = "\n\n".join(sorted(list(unique_ddl_fragments)))
        else:
            pruned_schema_definition = self.schema_manager.get_schema(selected_schema_name)
            if not pruned_schema_definition:
                yield f"Error: Schema '{selected_schema_name}' not found or empty."
                return

        # 3. Construct the prompt for the LLM
        prompt = self.prompt_template.format(
            schema_definition=pruned_schema_definition,
            question=natural_language_question
        )
        log.info(f"--- SQL Agent Streaming Prompt (Pruned Schema) --- \n{prompt[:1000]}...\n--- End Prompt ---")

        full_response_content = ""
        async for chunk in self.llm.stream_response(prompt, temperature=0.1):
            full_response_content += chunk
            yield chunk # Yield raw chunks as they come

        # After streaming is complete, ensure final extraction for robust display
        # The UI should ideally handle presenting the extracted part.
        # This function aims to just stream what the LLM generates.
        # The _extract_sql_from_response is then used by the UI on the full_response_content.

    def _extract_sql_from_response(self, llm_response: str) -> str:
        """
        Extracts the SQL query from the LLM's response.
        Assumes the LLM will wrap SQL in triple backticks (```sql ... ```)
        """
        # This is a basic regex to find SQL code blocks
        match = re.search(r"```sql\n(.*?)```", llm_response, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # If no code block found, check for specific fallback indicators or return as is
        # You can add more sophisticated fallback logic if LLM often doesn't use triple backticks
        log.warning("No ````sql``` block found in LLM response. Returning full response as SQL (may be incorrect).")
        return llm_response.strip()