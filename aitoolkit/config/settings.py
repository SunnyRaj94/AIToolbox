# src/aitoolkit/config/settings.py
import yaml
import os
from pathlib import Path
import logging

log = logging.getLogger(__name__)

class Config:
    _instance = None
    _configs = {}
    _env_vars = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_configs()
            cls._instance._load_env_vars()
        return cls._instance

    def _load_configs(self):
        config_file_path = Path(__file__).parent / 'configs.yaml'
        # print(f"Attempting to load config from: {config_file_path}") # Debug print
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                self._configs = yaml.safe_load(f)
            # print(f"Configs loaded successfully: {self._configs.keys()}") # Debug print
            # print(f"Value for 'sql_agent_settings.schema_storage_path': {self.get('sql_agent_settings.schema_storage_path')}") # Debug print
        except FileNotFoundError:
            log.error(f"Error: Config file not found at {config_file_path}")
            self._configs = {} # Initialize empty to avoid errors
        except yaml.YAMLError as e:
            log.error(f"Error parsing config file: {e}")
            self._configs = {}
        except Exception as e: # Catch any other unexpected errors during load
            log.error(f"An unexpected error occurred during config loading: {e}")
            self._configs = {}

    def _load_env_vars(self):
        # Load specific environment variables
        self._env_vars = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
            "GOOGLE_GEMINI_API_KEY": os.getenv("GOOGLE_GEMINI_API_KEY"),
            "COHERE_API_KEY": os.getenv("COHERE_API_KEY"), # For future Cohere embedding
            # Add other API keys or sensitive variables here
        }
        # Handle JWT secret key from environment if available
        if "JWT_SECRET_KEY" in os.environ:
            if 'jwt' not in self._configs:
                self._configs['jwt'] = {}
            self._configs['jwt']['secret_key'] = os.getenv("JWT_SECRET_KEY")

        # Automatically update API keys in _configs if env vars are present
        # This allows configs.get to retrieve them as well
        if "OPENAI_API_KEY" in self._env_vars and self._env_vars["OPENAI_API_KEY"] is not None:
            if 'llm_settings' not in self._configs: self._configs['llm_settings'] = {}
            self._configs['llm_settings']['OPENAI_API_KEY'] = self._env_vars["OPENAI_API_KEY"]
            if 'embedding_settings' not in self._configs: self._configs['embedding_settings'] = {}
            self._configs['embedding_settings']['OPENAI_API_KEY'] = self._env_vars["OPENAI_API_KEY"]

        if "GOOGLE_GEMINI_API_KEY" in self._env_vars and self._env_vars["GOOGLE_GEMINI_API_KEY"] is not None:
            if 'llm_settings' not in self._configs: self._configs['llm_settings'] = {}
            self._configs['llm_settings']['GOOGLE_GEMINI_API_KEY'] = self._env_vars["GOOGLE_GEMINI_API_KEY"]
            if 'embedding_settings' not in self._configs: self._configs['embedding_settings'] = {}
            self._configs['embedding_settings']['GOOGLE_GEMINI_API_KEY'] = self._env_vars["GOOGLE_GEMINI_API_KEY"]

        if "GROQ_API_KEY" in self._env_vars and self._env_vars["GROQ_API_KEY"] is not None:
            if 'llm_settings' not in self._configs: self._configs['llm_settings'] = {}
            self._configs['llm_settings']['GROQ_API_KEY'] = self._env_vars["GROQ_API_KEY"]


    def get(self, key: str, default=None):
        """
        Get a configuration value using dot notation (e.g., 'app.project_name').
        Prioritizes environment variables for certain keys if they are explicitly loaded.
        """
        parts = key.split('.')
        current_config = self._configs

        # Direct environment variable check for explicitly named keys
        if key == "OPENAI_API_KEY": return self._env_vars.get("OPENAI_API_KEY", default)
        if key == "GROQ_API_KEY": return self._env_vars.get("GROQ_API_KEY", default)
        if key == "GOOGLE_GEMINI_API_KEY": return self._env_vars.get("GOOGLE_GEMINI_API_KEY", default)
        if key == "COHERE_API_KEY": return self._env_vars.get("COHERE_API_KEY", default)


        for part in parts:
            if isinstance(current_config, dict):
                current_config = current_config.get(part)
            else:
                return default # Part not found or not a dictionary
            if current_config is None:
                return default # Key not found at this level
        return current_config if current_config is not None else default

    def get_all(self):
        return self._configs

    def get_env(self, key: str, default=None):
        """Get an environment variable directly."""
        return self._env_vars.get(key, default)

# Instantiate the Config class as a singleton
# configs = Config()
# env = configs.get_env # Alias for direct environment variable access