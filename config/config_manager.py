# config/config_manager.py
import os
import yaml
import streamlit as st
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    _instance = None
    _config_data = {}
    _is_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._is_loaded:
            self._load_config()
            self._is_loaded = True

    def _load_config(self):
        """
        Loads configurations from YAML files and Streamlit secrets.
        Prioritizes Streamlit secrets for sensitive information.
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(os.path.dirname(base_dir), 'data')

        # Load general config.yml
        config_path = os.path.join(data_dir, 'config.yml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self._config_data.update(yaml.safe_load(f) or {})
            logger.info(f"Loaded config from {config_path}")
        else:
            logger.warning(f"config.yml not found at {config_path}")

        # Load sports_apis.yaml
        sports_apis_path = os.path.join(data_dir, 'sports_apis.yaml')
        if os.path.exists(sports_apis_path):
            with open(sports_apis_path, 'r') as f:
                self._config_data.update(yaml.safe_load(f) or {})
            logger.info(f"Loaded sports APIs config from {sports_apis_path}")
        else:
            logger.warning(f"sports_apis.yaml not found at {sports_apis_path}")

        # Load media_apis.yaml (NEW)
        media_apis_path = os.path.join(data_dir, 'media_apis.yaml')
        if os.path.exists(media_apis_path):
            with open(media_apis_path, 'r') as f:
                self._config_data.update(yaml.safe_load(f) or {})
            logger.info(f"Loaded media APIs config from {media_apis_path}")
        else:
            logger.warning(f"media_apis.yaml not found at {media_apis_path}")


        # Override with Streamlit secrets (for sensitive keys like LLM API keys)
        # Secrets are accessed via st.secrets.section.key
        if hasattr(st, 'secrets'):
            for key, value in st.secrets.items():
                if isinstance(value, dict):
                    # Merge nested dictionaries from secrets
                    if key not in self._config_data:
                        self._config_data[key] = {}
                    self._config_data[key].update(value)
                else:
                    self._config_data[key] = value
            logger.info("Loaded/overrode config with Streamlit secrets.")
        else:
            logger.warning("Streamlit secrets not available. Ensure app is run via 'streamlit run'.")

    def get(self, key, default=None):
        """Retrieves a configuration value."""
        # Support nested access like 'section.key'
        keys = key.split('.')
        value = self._config_data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def __getitem__(self, key):
        """Allows dictionary-like access: config['section']['key'] or config['top_level_key']"""
        return self.get(key)

# Global instance to be imported by other modules
config_manager = ConfigManager()

if __name__ == '__main__':
    # Example usage for testing (this block won't run directly in Streamlit context without modifications)
    # To test, run: python -m your_project.config.config_manager
    # You might need to mock st.secrets for local execution without Streamlit
    print("Testing ConfigManager (requires streamlit.secrets context for full test):")

    # Example of how to use it in a Streamlit app or test file
    # with a mock for st.secrets if running standalone:

    # Temporarily mock st.secrets if not running in a Streamlit context
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key"}
            self.app = {"name": "Test App"}
            self.themoviedb = {"api_key": "mock-tmdb-key"} # Added for media testing

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")

    cm = ConfigManager()

    print(f"App Name: {cm.get('app.name', 'Default App')}")
    print(f"LLM Provider: {cm.get('llm.provider', 'OpenAI')}")
    print(f"OpenAI API Key (should be from secrets): {cm.get('openai.api_key', 'Not Set')}")
    print(f"Sports API URL: {cm.get('sports_api.football_data.base_url', 'Not Set')}") # Updated key
    print(f"TheMovieDB API Key: {cm.get('themoviedb.api_key', 'Not Set')}") # New key

    # Test dictionary-like access
    if 'app' in cm:
        print(f"App section config: {cm['app']}")
    if 'openai' in cm and 'api_key' in cm['openai']:
        print(f"OpenAI API Key (dict access): {cm['openai']['api_key']}")
    if 'themoviedb' in cm and 'api_key' in cm['themoviedb']:
        print(f"TheMovieDB API Key (dict access): {cm['themoviedb']['api_key']}")
