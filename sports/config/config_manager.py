# sports/config/config_manager.py

import os
import yaml
from pathlib import Path
from utils.user_manager import lookup_user_by_token

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


def load_user_config(user_token: str) -> dict:
    user_file = USER_CONFIG_DIR / f"{user_token}.yml"
    if user_file.exists():
        with open(user_file, "r") as f:
            return yaml.safe_load(f)
    return {}


def get_config(user_token: str = "default") -> dict:
    """Returns merged global + user config. Auto-creates user config if missing."""
    user_file = USER_CONFIG_DIR / f"{user_token}.yml"
    if not user_file.exists():
        create_user_config(user_token)  # 🔁 Auto-create user config on first use

    config = load_global_config()
    user_config = load_user_config(user_token)

    for key, val in user_config.items():
        if isinstance(val, dict) and key in config:
            config[key].update(val)
        else:
            config[key] = val

    return config


def get_api_key(service: str, user_token: str = "default") -> str:
    config = get_config(user_token)
    return config.get("api_keys", {}).get(service, "")


def get_model_settings(user_token: str = "default") -> dict:
    config = get_config(user_token)
    return {
        "llm_model": config.get("llm_model", "llama3"),
        "temperature": config.get("temperature", 0.3),
    }


def get_embedding_config(user_token: str = "default") -> dict:
    config = get_config(user_token)
    return {
        "mode": config.get("embedding_mode", "openai"),
        "model": config.get("embedding_model", "text-embedding-ada-002"),
    }


def get_user_tier(user_token: str = "default") -> str:
    return get_config(user_token).get("tier", "free")


def create_user_config(user_token: str, config: dict = None) -> bool:
    user_file = USER_CONFIG_DIR / f"{user_token}.yml"
    if not user_file.exists():
        user_file.parent.mkdir(parents=True, exist_ok=True)
        with open(user_file, "w") as f:
            yaml.dump(config or DEFAULT_CONFIG, f)
        return True
    return False


def set_api_key(service: str, key_value: str, user_token: str = "default") -> None:
    user_file = USER_CONFIG_DIR / f"{user_token}.yml"
    config = load_user_config(user_token)
    if "api_keys" not in config:
        config["api_keys"] = {}
    config["api_keys"][service] = key_value
    user_file.parent.mkdir(parents=True, exist_ok=True)
    with open(user_file, "w") as f:
        yaml.dump(config, f)


# CLI example test
if __name__ == "__main__":
    from utils.user_manager import create_user
    token = create_user("Victor", "victor@gmail.com")
    print(get_model_settings(token))
    print(get_api_key("openai", token))
    print(get_embedding_config(token))
    print(get_user_tier(token))
    create_user_config(token)
    set_api_key("openai", "new-key-123", token)


