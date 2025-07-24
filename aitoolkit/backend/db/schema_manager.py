# src/aitoolkit/backend/db/schema_manager.py
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

class SchemaManager:
    """
    Manages the storage and retrieval of user-defined database schemas.
    Schemas are stored in a JSON file.
    """
    def __init__(self, storage_path: Union[str, Path]):
        self.storage_path = Path(storage_path)
        self._ensure_storage_path_exists()
        self._schemas: Dict[str, Dict[str, Any]] = self._load_schemas()

    def _ensure_storage_path_exists(self):
        """Ensures the directory for the storage path exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Loads all schemas from the JSON storage file."""
        if not self.storage_path.exists():
            return {}
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not decode SQL schemas file. Starting with empty schemas. Error: {e}")
            return {}
        except Exception as e:
            print(f"An unexpected error occurred loading schemas: {e}")
            return {}

    def _save_schemas(self):
        """Saves the current state of schemas to the JSON storage file."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self._schemas, f, indent=4)
        except Exception as e:
            print(f"Error saving SQL schemas: {e}")

    def add_schema(self, schema_name: str, schema_definition: str) -> bool:
        """
        Adds or updates a database schema.
        schema_definition can be DDL (CREATE TABLE statements) or a descriptive text.
        Returns True if added/updated, False if schema_name already exists and definition is identical.
        """
        if schema_name in self._schemas and self._schemas[schema_name]['definition'] == schema_definition:
            return False # No change needed
        self._schemas[schema_name] = {"definition": schema_definition}
        self._save_schemas()
        return True

    def get_schema(self, schema_name: str) -> Optional[str]:
        """Retrieves a schema definition by its name."""
        return self._schemas.get(schema_name, {}).get("definition")

    def get_all_schema_names(self) -> List[str]:
        """Returns a list of all stored schema names."""
        return sorted(list(self._schemas.keys()))

    def delete_schema(self, schema_name: str) -> bool:
        """Deletes a schema by its name. Returns True if deleted, False if not found."""
        if schema_name in self._schemas:
            del self._schemas[schema_name]
            self._save_schemas()
            return True
        return False