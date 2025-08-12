# aitoolkit/backend/db/schema_manager.py
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
import re
import logging

from aitoolkit.backend.llm.embedding import EmbeddingLLM
from aitoolkit.backend.db.vector_db_manager import FAISSVectorDBManager

log = logging.getLogger(__name__)

class SchemaManager:
    """
    Manages database schemas, including loading, saving, and generating/retrieving
    semantic embeddings for schema parts to facilitate intelligent context provisioning
    to the LLM. Now supports both CREATE TABLE DDL format and structured schema format.
    """
    
    def __init__(self, schema_storage_path: str, vector_db_persist_path: str, embedding_llm: EmbeddingLLM):
        self.schema_file = Path(schema_storage_path)
        self.schemas: Dict[str, Union[str, dict]] = self._load_schemas()
        self.embedding_llm = embedding_llm
        # Initialize the FAISS vector database manager
        self.vector_db_manager = FAISSVectorDBManager(vector_db_persist_path, embedding_llm)

    def _load_schemas(self) -> Dict[str, Union[str, dict]]:
        """Loads schemas from the configured JSON file."""
        if self.schema_file.exists():
            try:
                with open(self.schema_file, 'r', encoding='utf-8') as f:
                    schemas = json.load(f)
                    log.info(f"Loaded {len(schemas)} schemas from {self.schema_file}")
                    return schemas
            except json.JSONDecodeError as e:
                log.error(f"Error decoding JSON from schema file {self.schema_file}: {e}")
                return {}
        log.info(f"Schema file not found at {self.schema_file}. Starting with empty schemas.")
        return {}

    def _save_schemas(self):
        """Saves current schemas to the configured JSON file."""
        self.schema_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.schema_file, 'w', encoding='utf-8') as f:
                json.dump(self.schemas, f, indent=4)
            log.info(f"Saved {len(self.schemas)} schemas to {self.schema_file}")
        except IOError as e:
            log.error(f"Error saving schemas to {self.schema_file}: {e}")

    def _is_structured_schema(self, schema_definition: Union[str, dict]) -> bool:
        """Check if the schema is in structured format (dict) or DDL format (string)."""
        return isinstance(schema_definition, dict) and 'database_name' in schema_definition

    def _extract_table_info_from_ddl(self, schema_definition: str) -> List[Dict]:
        """
        Parses CREATE TABLE statements from the schema definition
        to extract table names, column names, and data types.
        This is a simplified parser and might need robust error handling for real-world DDLs.
        """
        tables_info = []
        # Regex to find CREATE TABLE statements, including potential backticks around table/column names
        table_matches = re.findall(r"CREATE TABLE\s+`?(\w+)`?\s*\((.*?)\);", schema_definition, re.DOTALL | re.IGNORECASE)

        for table_name, columns_str in table_matches:
            columns = []
            # Regex to find column name and type within the columns_str
            column_matches = re.findall(r"`?(\w+)`?\s+(\w+)(?:[^,;()]*(?:\([^)]*\))?[^,;()]*)?(?:,|\s*$)", columns_str)
            
            for col_name, col_type in column_matches:
                columns.append({"name": col_name.strip(), "type": col_type.strip()})
            
            # Reconstruct the DDL fragment for exact representation
            raw_ddl = f"CREATE TABLE {table_name} ({columns_str});"
            
            tables_info.append({
                "table_name": table_name.strip(),
                "columns": columns,
                "raw_ddl_fragment": raw_ddl.strip()
            })
        
        if not tables_info and schema_definition:
            # If no CREATE TABLE statements are found, treat the entire definition as a general schema description
            tables_info.append({
                "table_name": "General_Schema_Description",
                "columns": [],
                "raw_ddl_fragment": schema_definition.strip()
            })
            log.warning("No explicit CREATE TABLE statements found. Treating schema as a single descriptive block.")

        return tables_info

    def _extract_table_info_from_structured(self, schema_definition: dict) -> List[Dict]:
        """
        Extracts table information from structured schema format.
        """
        tables_info = []
        
        database_name = schema_definition.get('database_name', 'Unknown')
        sql_language = schema_definition.get('sql_language', 'SQL')
        description = schema_definition.get('description', '')
        
        tables = schema_definition.get('tables', [])
        
        for table in tables:
            table_name = table.get('table_name', 'Unknown')
            table_description = table.get('description', '')
            columns = table.get('columns', [])
            
            # Extract column information
            column_info = []
            ddl_columns = []
            
            for col in columns:
                col_name = col.get('column_name', 'unknown')
                col_type = col.get('type', 'VARCHAR')
                col_desc = col.get('description', '')
                is_pk = col.get('is_pk', False)
                
                column_info.append({
                    "name": col_name,
                    "type": col_type,
                    "description": col_desc,
                    "is_pk": is_pk
                })
                
                # Build DDL fragment
                ddl_col = f"{col_name} {col_type}"
                if is_pk:
                    ddl_col += " PRIMARY KEY"
                ddl_columns.append(ddl_col)
            
            # Generate DDL fragment
            raw_ddl = f"CREATE TABLE {table_name} (\n    " + ",\n    ".join(ddl_columns) + "\n);"
            
            tables_info.append({
                "table_name": table_name,
                "table_description": table_description,
                "columns": column_info,
                "raw_ddl_fragment": raw_ddl,
                "database_name": database_name,
                "sql_language": sql_language,
                "database_description": description
            })
        
        return tables_info

    def add_schema(self, name: str, definition: Union[str, dict]) -> bool:
        """
        Adds or updates a schema and generates/updates its embeddings in the vector store.
        Now supports both string (DDL) and dict (structured) formats.
        Returns True if schema was added/updated, False if no change.
        """
        # Convert definition to string for comparison if it's a dict
        definition_str = json.dumps(definition, sort_keys=True) if isinstance(definition, dict) else definition
        existing_str = json.dumps(self.schemas.get(name), sort_keys=True) if isinstance(self.schemas.get(name), dict) else self.schemas.get(name)
        
        if name in self.schemas and existing_str == definition_str:
            log.info(f"Schema '{name}' already exists with the same definition. No update needed.")
            return False

        self.schemas[name] = definition
        self._save_schemas()

        # Update embeddings for this schema
        self._update_schema_embeddings(name, definition)
        return True

    def add_schema_from_text(self, schema_text: str) -> Optional[str]:
        """
        Tries to parse schema text as JSON (structured format) first, 
        then falls back to treating it as DDL.
        Returns the schema name if successful, None otherwise.
        """
        try:
            # Try to parse as JSON first
            schema_dict = json.loads(schema_text)
            if self._is_structured_schema(schema_dict):
                schema_name = schema_dict.get('database_name', 'Unknown_Schema')
                if self.add_schema(schema_name, schema_dict):
                    log.info(f"Added structured schema: {schema_name}")
                    return schema_name
                else:
                    log.info(f"Schema {schema_name} already exists with same definition")
                    return schema_name
        except json.JSONDecodeError:
            # Not valid JSON, treat as DDL
            pass
        
        # Fallback: treat as DDL string
        # Extract a reasonable name from the DDL or use a default
        table_matches = re.findall(r"CREATE TABLE\s+`?(\w+)`?", schema_text, re.IGNORECASE)
        if table_matches:
            schema_name = f"Schema_{table_matches[0]}"
        else:
            schema_name = "Custom_Schema"
        
        if self.add_schema(schema_name, schema_text):
            log.info(f"Added DDL schema: {schema_name}")
            return schema_name
        else:
            log.info(f"Schema {schema_name} already exists with same definition")
            return schema_name

    def _update_schema_embeddings(self, schema_name: str, schema_definition: Union[str, dict]):
        """Processes schema definition to create and store embeddings."""
        if self._is_structured_schema(schema_definition):
            table_infos = self._extract_table_info_from_structured(schema_definition)
        else:
            table_infos = self._extract_table_info_from_ddl(schema_definition)
        
        if not table_infos:
            log.warning(f"No table information extracted for schema '{schema_name}'. Cannot create embeddings.")
            return

        documents_to_add = []
        metadatas_to_add = []

        # Delete existing embeddings for this schema before adding new ones
        self.vector_db_manager.delete_namespace(schema_name)

        for table_info in table_infos:
            table_name = table_info['table_name']
            columns = table_info['columns']
            
            # Create columns description
            if columns and len(columns) > 0 and isinstance(columns[0], dict) and 'description' in columns[0]:
                # Structured format with descriptions
                columns_description = ", ".join([
                    f"{col['name']} ({col['type']})" + 
                    (f" - {col['description']}" if col.get('description') else "") +
                    (" [PRIMARY KEY]" if col.get('is_pk') else "")
                    for col in columns
                ])
            else:
                # DDL format or simple format
                columns_description = ", ".join([f"{col['name']} ({col['type']})" for col in columns])
            
            # Create a rich description for embedding
            doc_content_parts = [
                f"Database schema: '{schema_name}'",
                f"Table: `{table_name}`"
            ]
            
            # Add table description if available
            if table_info.get('table_description'):
                doc_content_parts.append(f"Table description: {table_info['table_description']}")
            
            # Add database info if available (structured format)
            if table_info.get('database_description'):
                doc_content_parts.append(f"Database description: {table_info['database_description']}")
            
            if table_info.get('sql_language'):
                doc_content_parts.append(f"SQL Language: {table_info['sql_language']}")
            
            doc_content_parts.extend([
                f"Columns: {columns_description}",
                f"DDL: {table_info['raw_ddl_fragment']}"
            ])
            
            doc_content = ". ".join(doc_content_parts)
            
            documents_to_add.append(doc_content)
            
            metadata = {
                "schema_name": schema_name,
                "table_name": table_name,
                "raw_ddl_fragment": table_info['raw_ddl_fragment']
            }
            
            # Add additional metadata for structured schemas
            if table_info.get('database_name'):
                metadata['database_name'] = table_info['database_name']
            if table_info.get('sql_language'):
                metadata['sql_language'] = table_info['sql_language']
            if table_info.get('table_description'):
                metadata['table_description'] = table_info['table_description']
                
            metadatas_to_add.append(metadata)
        
        if documents_to_add:
            try:
                self.vector_db_manager.add_documents(documents_to_add, metadatas_to_add, namespace=schema_name)
                log.info(f"Generated and stored embeddings for schema '{schema_name}' with {len(documents_to_add)} table/schema fragments.")
            except Exception as e:
                log.error(f"Failed to add embeddings for schema '{schema_name}': {e}")
        else:
            log.info(f"No documents to add for schema '{schema_name}' after extraction.")

    def get_schema(self, name: str) -> Optional[Union[str, dict]]:
        """Retrieves a schema definition by name."""
        return self.schemas.get(name)

    def get_schema_as_string(self, name: str) -> Optional[str]:
        """
        Retrieves a schema definition by name and converts it to string format.
        For structured schemas, converts to DDL format.
        """
        schema = self.schemas.get(name)
        if not schema:
            return None
        
        if self._is_structured_schema(schema):
            # Convert structured schema to DDL string
            table_infos = self._extract_table_info_from_structured(schema)
            ddl_parts = []
            ddl_parts.append(f"-- Database: {schema.get('database_name', 'Unknown')}")
            ddl_parts.append(f"-- Language: {schema.get('sql_language', 'SQL')}")
            if schema.get('description'):
                ddl_parts.append(f"-- Description: {schema['description']}")
            ddl_parts.append("")
            
            for table_info in table_infos:
                if table_info.get('table_description'):
                    ddl_parts.append(f"-- Table: {table_info['table_name']} - {table_info['table_description']}")
                ddl_parts.append(table_info['raw_ddl_fragment'])
                ddl_parts.append("")
            
            return "\n".join(ddl_parts)
        else:
            # Already a string (DDL format)
            return schema

    def get_all_schema_names(self) -> List[str]:
        """Returns a list of all stored schema names."""
        return list(self.schemas.keys())

    def delete_schema(self, name: str) -> bool:
        """
        Deletes a schema and its associated embeddings.
        """
        if name in self.schemas:
            del self.schemas[name]
            self._save_schemas()
            # Also delete embeddings associated with this schema
            self.vector_db_manager.delete_namespace(name)
            log.info(f"Schema '{name}' deleted.")
            return True
        log.warning(f"Attempted to delete non-existent schema: '{name}'")
        return False

    def get_schema_info(self, name: str) -> Optional[Dict]:
        """
        Returns summary information about a schema.
        """
        schema = self.schemas.get(name)
        if not schema:
            return None
        
        info = {"name": name, "type": "structured" if self._is_structured_schema(schema) else "ddl"}
        
        if self._is_structured_schema(schema):
            info.update({
                "database_name": schema.get('database_name', 'Unknown'),
                "sql_language": schema.get('sql_language', 'SQL'),
                "description": schema.get('description', ''),
                "table_count": len(schema.get('tables', []))
            })
            tables = schema.get('tables', [])
            info["tables"] = [{"name": t.get('table_name', 'Unknown'), 
                             "column_count": len(t.get('columns', []))} for t in tables]
        else:
            # DDL format - extract basic info
            table_matches = re.findall(r"CREATE TABLE\s+`?(\w+)`?", str(schema), re.IGNORECASE)
            info["table_count"] = len(table_matches)
            info["tables"] = [{"name": table_name, "column_count": "unknown"} for table_name in table_matches]
        
        return info