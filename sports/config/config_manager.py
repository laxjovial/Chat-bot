# sports/config/config_manager.py

import os
import yaml
from pathlib import Path

# === Default paths ===
CONFIG_FILE = Path("sports/data/config.yml")
USER_CONFIG_DIR = Path("sports/data/users")

# === Defaults ===
DEFAULT_CONFIG = {
    "llm_model": "llama3",
    "temperature": 0.3,
    "embedding_mode": "openai",
    "embedding_model": "text-embedding-ada-002",
    "tier": "free",
    "api_keys": {
        "openai": "",
        "serpapi": "",
        "contextualweb": "",
        "huggingface": ""
    }
}


def load_global_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f)
    return DEFAULT_CONFIG


def load_user_config(user_id: str) -> dict:
    user_file = USER_CONFIG_DIR / f"{user_id}.yml"
    if user_file.exists():
        with open(user_file, "r") as f:
            return yaml.safe_load(f)
    return {}


def get_config(user_id: str = "default") -> dict:
    """Returns merged global + user config."""
    config = load_global_config()
    user_config = load_user_config(user_id)

    # Merge user values
    for key, val in user_config.items():
        if isinstance(val, dict) and key in config:
            config[key].update(val)
        else:
            config[key] = val

    return config


def get_api_key(service: str, user_id: str = "default") -> str:
    config = get_config(user_id)
    return config.get("api_keys", {}).get(service, "")


def get_model_settings(user_id: str = "default") -> dict:
    config = get_config(user_id)
    return {
        "llm_model": config.get("llm_model", "llama3"),
        "temperature": config.get("temperature", 0.3),
    }


def get_embedding_config(user_id: str = "default") -> dict:
    config = get_config(user_id)
    return {
        "mode": config.get("embedding_mode", "openai"),
        "model": config.get("embedding_model", "text-embedding-ada-002"),
    }


def get_user_tier(user_id: str = "default") -> str:
    return get_config(user_id).get("tier", "free")


# === Example CLI test ===
if __name__ == "__main__":
    print(get_model_settings("admin"))
    print(get_api_key("openai", "admin"))
    print(get_embedding_config("admin"))
    print(get_user_tier("admin"))
