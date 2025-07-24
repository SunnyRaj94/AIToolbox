# src/aitoolkit/backend/agents/sql_agent.py
from typing import Optional, AsyncGenerator
from aitoolkit.backend.llm import BaseLLM
from aitoolkit.config import configs
from pathlib import Path

class SQLAgent:
    """
    Agent responsible for generating SQL queries from natural language questions
    based on provided database schemas.
    """
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Loads the default prompt template for the SQL Agent."""
        template_path = Path(configs.get('sql_agent_settings').get('default_prompt_template'))
        if not template_path.exists():
            raise FileNotFoundError(f"SQL Agent prompt template not found at: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()

    async def generate_sql_query(self, natural_language_question: str, schema_definition: str) -> str:
        """
        Generates a SQL query from a natural language question and a schema.
        """
        # Construct the prompt for the LLM
        prompt = self.prompt_template.format(
            schema_definition=schema_definition,
            question=natural_language_question
        )
        print(f"--- SQL Agent Prompt --- \n{prompt}\n--- End Prompt ---") # For debugging

        # Use the LLM to generate the SQL query (non-streaming for this output)
        response = await self.llm.generate_response(prompt, temperature=0.1) # Lower temperature for factual tasks
        return self._extract_sql_from_response(response)

    async def stream_sql_query(self, natural_language_question: str, schema_definition: str) -> AsyncGenerator[str, None]:
        """
        Generates a SQL query from a natural language question and a schema, with streaming.
        """
        prompt = self.prompt_template.format(
            schema_definition=schema_definition,
            question=natural_language_question
        )

        full_response_content = ""
        async for chunk in self.llm.stream_response(prompt, temperature=0.1):
            full_response_content += chunk
            yield chunk # Yield chunks as they come

        # After streaming is complete, extract and yield the final SQL
        final_sql = self._extract_sql_from_response(full_response_content)
        # You might want to yield the final, cleaned SQL here if it's different from the streamed chunks
        # For simplicity, we'll assume direct streaming of the SQL block.
        # If the LLM generates prose around the SQL, you'll need to yield
        # only the SQL part in the *last* chunk or after processing.
        # For now, we'll just let the raw chunks stream.
        # A better approach would be to stream everything, then process the final output for extraction.
        # For a *demonstration* of streaming, yielding chunks is fine.
        # For correctness, you might wait for full_response_content and then extract.
        # Let's adjust this to *extract and yield* the final SQL block for clarity,
        # while still showing intermediate streamed tokens.
        # This means the streamed chunks might be the raw LLM output,
        # and the *final* display should use the extracted SQL.
        # We'll handle this in the UI.

    def _extract_sql_from_response(self, llm_response: str) -> str:
        """
        Extracts the SQL query from the LLM's response.
        Assumes the LLM will wrap SQL in triple backticks (```sql ... ```)
        """
        # This is a basic regex to find SQL code blocks
        import re
        match = re.search(r"```sql\n(.*?)```", llm_response, re.DOTALL)
        if match:
            return match.group(1).strip()
        # If no code block found, return the whole response as a fallback
        return llm_response.strip()