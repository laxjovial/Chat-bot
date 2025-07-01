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
                sports_apis_config = yaml.safe_load(f) or {}
                if 'apis' in sports_apis_config:
                    self._config_data['sports_apis'] = sports_apis_config['apis']
                if 'search_apis' in sports_apis_config: # If there are shared search APIs
                    if 'search_apis' not in self._config_data:
                        self._config_data['search_apis'] = []
                    self._config_data['search_apis'].extend(sports_apis_config['search_apis'])
            logger.info(f"Loaded sports APIs from {sports_apis_path}")
        else:
            logger.warning(f"sports_apis.yaml not found at {sports_apis_path}")

        # Load media_apis.yaml
        media_apis_path = os.path.join(data_dir, 'media_apis.yaml')
        if os.path.exists(media_apis_path):
            with open(media_apis_path, 'r') as f:
                media_apis_config = yaml.safe_load(f) or {}
                if 'apis' in media_apis_config:
                    self._config_data['media_apis'] = media_apis_config['apis']
                if 'search_apis' in media_apis_config: # If there are shared search APIs
                    if 'search_apis' not in self._config_data:
                        self._config_data['search_apis'] = []
                    self._config_data['search_apis'].extend(media_apis_config['search_apis'])
            logger.info(f"Loaded media APIs from {media_apis_path}")
        else:
            logger.warning(f"media_apis.yaml not found at {media_apis_path}")
        
        # Load smtp_config.yml
        smtp_config_path = os.path.join(data_dir, 'smtp_config.yml')
        if os.path.exists(smtp_config_path):
            with open(smtp_config_path, 'r') as f:
                smtp_config = yaml.safe_load(f) or {}
                self._config_data['email'] = self._config_data.get('email', {})
                self._config_data['email'].update(smtp_config)
            logger.info(f"Loaded SMTP config from {smtp_config_path}")
        else:
            logger.warning(f"smtp_config.yml not found at {smtp_config_path}")

        # Load Streamlit secrets (for sensitive API keys)
        # st.secrets is only available when running with `streamlit run`
        if hasattr(st, 'secrets'):
            for section, keys in st.secrets.items():
                # For direct API keys like openai.api_key
                if isinstance(keys, dict):
                    if section not in self._config_data:
                        self._config_data[section] = {}
                    self._config_data[section].update(keys)
                # For top-level secrets, e.g., 'API_KEY_NAME' = 'value'
                else:
                    self._config_data[section] = keys
            logger.info("Loaded configurations from Streamlit secrets.")
        else:
            logger.warning("Streamlit secrets not available (not running in Streamlit context or st.secrets is not initialized).")
            # Fallback to environment variables if not in Streamlit context and secrets are needed
            # This is a common pattern for deployment where secrets are env vars
            if os.getenv('OPENAI_API_KEY'):
                self._config_data['openai'] = {'api_key': os.getenv('OPENAI_API_KEY')}
            if os.getenv('GOOGLE_API_KEY'):
                self._config_data['google'] = {'api_key': os.getenv('GOOGLE_API_KEY')}
            if os.getenv('SERPAPI_API_KEY'):
                if 'search_apis' not in self._config_data:
                    self._config_data['search_apis'] = []
                # Check if SerpAPI config already exists before adding
                if not any(api.get('name') == 'SerpAPI' for api in self._config_data['search_apis']):
                    self._config_data['search_apis'].append({
                        'name': 'SerpAPI',
                        'type': 'search',
                        'endpoint': 'https://serpapi.com/search',
                        'key_name': 'api_key',
                        'key_value': os.getenv('SERPAPI_API_KEY')
                    })
            # Add other env var fallbacks as needed for specific APIs


    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value using a dot-notation key (e.g., 'app.name').
        """
        keys = key.split('.')
        val = self._config_data
        try:
            for k in keys:
                if isinstance(val, dict):
                    val = val[k]
                else:
                    return default # Key path invalid mid-way
            return val
        except KeyError:
            return default

    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Specifically retrieves a secret, prioritizing st.secrets, then environment variables.
        Expected format in secrets.toml:
        [section]
        key = "value"
        Or top-level:
        key = "value"
        """
        # First, try to get from loaded config (which includes st.secrets if available)
        value = self.get(key)
        if value is not None:
            # If the value is a string like "load_from_secrets.section_key", resolve it
            if isinstance(value, str) and value.startswith("load_from_secrets."):
                secret_path = value.split("load_from_secrets.")[1]
                # Try to resolve from st.secrets directly if possible
                if hasattr(st, 'secrets'):
                    secrets_keys = secret_path.split('.')
                    secret_val = st.secrets
                    try:
                        for sk in secrets_keys:
                            secret_val = secret_val[sk]
                        return secret_val
                    except KeyError:
                        logger.warning(f"Secret key '{secret_path}' not found in st.secrets.")
                        # Fallback to environment variable if not found in st.secrets for a loaded_from_secrets key
                        env_var_name = secret_path.replace('.', '_').upper()
                        return os.getenv(env_var_name, default)
                else:
                    # If st.secrets not available, directly try environment variable
                    env_var_name = secret_path.replace('.', '_').upper()
                    return os.getenv(env_var_name, default)
            return value
        
        # If not found in loaded config, try environment variables directly for the given key
        # Convert dot-notation to common env var format (e.g., OPENAI_API_KEY)
        env_var_name = key.replace('.', '_').upper()
        env_value = os.getenv(env_var_name)
        if env_value is not None:
            return env_value

        return default

    def __getitem__(self, key: str) -> Any:
        """Allows dictionary-like access: config_manager['app']['name']"""
        return self._config_data[key]

    def __contains__(self, key: str) -> bool:
        """Allows checking for key existence: 'app' in config_manager"""
        return key in self._config_data

# Instantiate the ConfigManager immediately upon import
config_manager = ConfigManager()


# --- Test function (for standalone testing) ---
if __name__ == "__main__":
    import sys
    import shutil
    from pathlib import Path

    # Create dummy config files for testing
    dummy_data_dir = Path("data")
    dummy_data_dir.mkdir(exist_ok=True)

    dummy_config_path = dummy_data_dir / "config.yml"
    dummy_sports_path = dummy_data_dir / "sports_apis.yaml"
    dummy_media_path = dummy_data_dir / "media_apis.yaml"
    dummy_smtp_path = dummy_data_dir / "smtp_config.yml"
    dummy_secrets_file = Path(".streamlit") / "secrets.toml"
    Path(".streamlit").mkdir(exist_ok=True) # Ensure .streamlit directory exists

    with open(dummy_config_path, "w") as f:
        f.write("""
app:
  name: "Test App"
  version: "1.0.0"
llm:
  provider: "ollama"
  model: "llama2"
""")

    with open(dummy_sports_path, "w") as f:
        f.write("""
apis:
  - name: "TheSportsDB"
    type: "sports"
    endpoint: "https://www.thesportsdb.com/"
    key_name: "api_key"
    key_value: "load_from_secrets.thesportsdb_api_key"
search_apis:
  - name: "SerpAPI"
    type: "search"
    endpoint: "https://serpapi.com/"
    key_name: "api_key"
    key_value: "load_from_secrets.serpapi_api_key"
""")
    with open(dummy_media_path, "w") as f:
        f.write("""
apis:
  - name: "TheMovieDB"
    type: "media"
    endpoint: "https://api.themoviedb.org/"
    key_name: "api_key"
    key_value: "load_from_secrets.themoviedb_api_key"
search_apis:
  - name: "GoogleCustomSearch"
    type: "search"
    endpoint: "https://www.googleapis.com/customsearch/v1"
    key_name: "key"
    key_value: "load_from_secrets.google_custom_search_api_key"
""")
    
    with open(dummy_smtp_path, "w") as f:
        f.write("""
smtp_server: smtp.testmail.com
smtp_port: 587
smtp_user: test@example.com
from_email: app@example.com
""")

    with open(dummy_secrets_file, "w") as f:
        f.write("""
[openai]
api_key = "sk-test-openai-key"

[google]
api_key = "AIzaSy-test-google-key"

[thesportsdb]
api_key = "test-sportsdb-key"

[serpapi]
api_key = "test-serpapi-key"

[themoviedb]
api_key = "test-tmdb-key"

[google_custom_search]
api_key = "test-gcs-key"

[email_smtp_user]
# This simulates how a top-level secret for email user might be stored if not nested
# Or it could be under [email] section in secrets.toml: [email] smtp_user = "secret_user"
value = "secret_smtp_user@example.com"

[email_smtp_password]
value = "secret_smtp_password"
""")

    # Temporarily mock st.secrets for standalone execution
    class MockSecrets:
        def __init__(self):
            # Simulate sections directly
            self.openai = {"api_key": "sk-mock-openai-key"}
            self.google = {"api_key": "AIzaSy-mock-google-key"}
            self.thesportsdb = {"api_key": "mock-thesportsdb-key"}
            self.serpapi = {"api_key": "mock-serpapi-key"}
            self.themoviedb = {"api_key": "mock-themoviedb-key"}
            self.google_custom_search = {"api_key": "mock-gcs-key"}
            # Simulate top-level secrets
            self.email_smtp_user = "mock_smtp_user@example.com"
            self.email_smtp_password = "mock_smtp_password"

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")

    # Re-instantiate ConfigManager to reload with dummy files and mocked secrets
    ConfigManager._instance = None # Reset the singleton
    ConfigManager._is_loaded = False
    cm = ConfigManager()

    print("\n--- ConfigManager Test Results ---")
    print(f"App Name: {cm.get('app.name', 'Default App')}")
    print(f"LLM Provider: {cm.get('llm.provider', 'OpenAI')}")
    print(f"LLM Model: {cm.get('llm.model', 'default-model')}")

    print(f"OpenAI API Key (from mocked secrets): {cm.get_secret('openai.api_key', 'Not Set')}")
    print(f"Google API Key (from mocked secrets): {cm.get_secret('google.api_key', 'Not Set')}")
    
    print("\n--- Sports API Config ---")
    sports_apis = cm.get('sports_apis', [])
    for api in sports_apis:
        print(f"  - {api['name']} Endpoint: {api['endpoint']}")
        # Test loading key from 'load_from_secrets'
        if "load_from_secrets" in api.get('key_value', ''):
            resolved_key = cm.get_secret(api['key_value'].split("load_from_secrets.")[1])
            print(f"    Key for {api['name']}: {resolved_key}")
    
    print("\n--- Media API Config ---")
    media_apis = cm.get('media_apis', [])
    for api in media_apis:
        print(f"  - {api['name']} Endpoint: {api['endpoint']}")
        if "load_from_secrets" in api.get('key_value', ''):
            resolved_key = cm.get_secret(api['key_value'].split("load_from_secrets.")[1])
            print(f"    Key for {api['name']}: {resolved_key}")

    print("\n--- Search API Config (Shared) ---")
    search_apis = cm.get('search_apis', [])
    for api in search_apis:
        print(f"  - {api['name']} Endpoint: {api['endpoint']}")
        if "load_from_secrets" in api.get('key_value', ''):
            resolved_key = cm.get_secret(api['key_value'].split("load_from_secrets.")[1])
            print(f"    Key for {api['name']}: {resolved_key}")

    print("\n--- Email Config ---")
    print(f"SMTP Server: {cm.get('email.smtp_server', 'Not Set')}")
    print(f"SMTP Port: {cm.get('email.smtp_port', 'Not Set')}")
    print(f"SMTP User (from smtp_config.yml, overridden by secrets): {cm.get('email.smtp_user', 'Not Set')}")
    print(f"SMTP User (resolved from secrets): {cm.get_secret('email_smtp_user', 'Not Set')}")
    print(f"SMTP Password (resolved from secrets): {cm.get_secret('email_smtp_password', 'Not Set')}")
    print(f"From Email: {cm.get('email.from_email', 'Not Set')}")

    # Test environment variable fallback
    print("\n--- Environment Variable Test ---")
    os.environ['TEST_ENV_KEY'] = 'value_from_env'
    print(f"TEST_ENV_KEY (from env var): {cm.get('test_env_key', 'Not Found')}")
    print(f"TEST_ENV_KEY (from get_secret, uppercase conversion): {cm.get_secret('test.env.key', 'Not Found')}")
    del os.environ['TEST_ENV_KEY'] # Clean up

    # Test dictionary-like access
    print(f"App config using dict access: {cm['app']}")
    print(f"'llm' in config_manager: {'llm' in cm}")
    print(f"'non_existent_key' in config_manager: {'non_existent_key' in cm}")

    # Clean up dummy files
    if dummy_data_dir.exists():
        shutil.rmtree(dummy_data_dir)
    if dummy_secrets_file.parent.exists(): # .streamlit directory
        shutil.rmtree(dummy_secrets_file.parent)
    
    print("\nCleaned up dummy config files and directories.")
