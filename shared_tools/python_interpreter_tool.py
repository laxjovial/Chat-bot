# shared_tools/python_interpreter_tool.py

import logging
from typing import Optional, Dict, Any
from langchain_core.tools import tool
from langchain_community.tools.python.tool import PythonREPLTool

# Import user_manager for RBAC checks
from utils.user_manager import get_user_tier_capability

logger = logging.getLogger(__name__)

# Initialize the underlying Python REPL tool
_python_repl_instance = PythonREPLTool()

@tool
def python_interpreter_with_rbac(code: str, user_token: Optional[str] = None) -> str:
    """
    Executes Python code. This tool is designed for complex data analysis, calculations,
    and programmatic logic on structured data. Access is controlled by user tier.

    Args:
        code (str): The Python code string to execute.
        user_token (str, optional): The unique identifier for the user, used for RBAC checks.
                                   Required for tier-based access control.

    Returns:
        str: The result of the code execution (stdout/stderr) or an access denied message.
    """
    logger.info(f"Tool: python_interpreter_with_rbac called for user: '{user_token}'")

    # --- RBAC Enforcement for Data Analysis ---
    # Check if data analysis is enabled for the user's tier
    is_data_analysis_enabled = get_user_tier_capability(user_token, 'data_analysis_enabled', False)
    if not is_data_analysis_enabled:
        return "Access Denied: Data analysis capabilities (Python interpreter) are not enabled for your current tier. Please upgrade your plan."

    # Optionally, you could also check for 'time_series_analysis_enabled' here
    # if you want to differentiate access to specific types of analysis within the interpreter.
    # For now, 'data_analysis_enabled' will cover all interpreter usage.

    try:
        # Execute the code using the underlying PythonREPLTool instance
        result = _python_repl_instance.run(code)
        return result
    except Exception as e:
        logger.error(f"Error executing Python code for user '{user_token}': {e}", exc_info=True)
        return f"An error occurred during Python code execution: {e}"

# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import os
    from unittest.mock import MagicMock
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            # Mock user tokens for testing RBAC
            self.user_tokens = {
                "free_user_token": "mock_free_token",
                "basic_user_token": "mock_basic_token",
                "pro_user_token": "mock_pro_token",
                "elite_user_token": "mock_elite_token",
                "admin_user_token": "mock_admin_token"
            }
        def get(self, key, default=None):
            parts = key.split('.')
            val = self
            for part in parts:
                if hasattr(val, part):
                    val = getattr(val, part)
                elif isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return default
            return val

    # Mock user_manager.find_user_by_token and get_user_tier_capability for testing RBAC
    class MockUserManager:
        _mock_users = {
            "mock_free_token": {"username": "FreeUser", "email": "free@example.com", "tier": "free", "roles": ["user"]},
            "mock_basic_token": {"username": "BasicUser", "email": "basic@example.com", "tier": "basic", "roles": ["user"]},
            "mock_pro_token": {"username": "ProUser", "email": "pro@example.com", "tier": "pro", "roles": ["user"]},
            "mock_elite_token": {"username": "EliteUser", "email": "elite@example.com", "tier": "elite", "roles": ["user"]},
            "mock_admin_token": {"username": "AdminUser", "email": "admin@example.com", "tier": "admin", "roles": ["user", "admin"]},
            "nonexistent_token": None
        }
        def find_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
            return self._mock_users.get(token)

        def get_user_tier_capability(self, user_token: Optional[str], capability_key: str, default_value: Any = None) -> Any:
            user = self.find_user_by_token(user_token)
            user_tier = user.get('tier', 'free') if user else 'free'
            user_roles = user.get('roles', []) if user else []

            if 'admin' in user_roles:
                if isinstance(default_value, bool): return True
                if isinstance(default_value, (int, float)): return float('inf')
                return default_value
            
            mock_tier_configs = {
                "free": {
                    "data_analysis_enabled": False,
                    "time_series_analysis_enabled": False
                },
                "basic": {
                    "data_analysis_enabled": False,
                    "time_series_analysis_enabled": False
                },
                "pro": {
                    "data_analysis_enabled": True,
                    "time_series_analysis_enabled": True
                },
                "elite": {
                    "data_analysis_enabled": True,
                    "time_series_analysis_enabled": True
                },
                "premium": {
                    "data_analysis_enabled": True,
                    "time_series_analysis_enabled": True
                }
            }
            tier_config = mock_tier_configs.get(user_tier, {})
            return tier_config.get(capability_key, default_value)


    # Patch the actual imports for testing
    import sys
    sys.modules['utils.user_manager'] = MockUserManager()
    # Mock config_manager (not strictly needed for this tool's RBAC, but good practice)
    class MockConfigManager:
        _instance = None
        _is_loaded = False
        def __init__(self):
            if MockConfigManager._instance is not None:
                raise Exception("ConfigManager is a singleton. Use get_instance().")
            MockConfigManager._instance = self
            self._config_data = {} # No specific config needed for this test beyond tiers
            self._is_loaded = True
        
        def get(self, key, default=None):
            parts = key.split('.')
            val = self._config_data
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return default
            return val
        
        def get_secret(self, key, default=None):
            return st.secrets.get(key, default)

    # Replace the actual config_manager with the mock
    sys.modules['config.config_manager'].config_manager = MockConfigManager()
    sys.modules['config.config_manager'].ConfigManager = MockConfigManager # Also replace the class for singleton check

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")

    print("\n--- Testing python_interpreter_with_rbac ---")
    
    test_code = "print(1 + 1)"
    test_data_analysis_code = "import pandas as pd; df = pd.DataFrame({'col': [1,2,3]}); print(df.mean())"

    # Test with free user (should be denied)
    print("\n--- Free User (Access Denied) ---")
    free_user_token = st.secrets.user_tokens["free_user_token"]
    result_free = python_interpreter_with_rbac(code=test_code, user_token=free_user_token)
    print(f"Free User Result:\n{result_free}")
    assert "Access Denied" in result_free

    # Test with basic user (should be denied)
    print("\n--- Basic User (Access Denied) ---")
    basic_user_token = st.secrets.user_tokens["basic_user_token"]
    result_basic = python_interpreter_with_rbac(code=test_code, user_token=basic_user_token)
    print(f"Basic User Result:\n{result_basic}")
    assert "Access Denied" in result_basic

    # Test with pro user (should be allowed)
    print("\n--- Pro User (Allowed) ---")
    pro_user_token = st.secrets.user_tokens["pro_user_token"]
    result_pro = python_interpreter_with_rbac(code=test_data_analysis_code, user_token=pro_user_token)
    print(f"Pro User Result:\n{result_pro}")
    assert "Access Denied" not in result_pro
    assert "2.0" in result_pro # Expected output from pandas mean

    # Test with elite user (should be allowed)
    print("\n--- Elite User (Allowed) ---")
    elite_user_token = st.secrets.user_tokens["elite_user_token"]
    result_elite = python_interpreter_with_rbac(code=test_data_analysis_code, user_token=elite_user_token)
    print(f"Elite User Result:\n{result_elite}")
    assert "Access Denied" not in result_elite
    assert "2.0" in result_elite

    # Test with admin user (should be allowed)
    print("\n--- Admin User (Allowed) ---")
    admin_user_token = st.secrets.user_tokens["admin_user_token"]
    result_admin = python_interpreter_with_rbac(code=test_data_analysis_code, user_token=admin_user_token)
    print(f"Admin User Result:\n{result_admin}")
    assert "Access Denied" not in result_admin
    assert "2.0" in result_admin

    print("\n--- RBAC tests for python_interpreter_with_rbac completed. ---")

    # Clean up dummy config files (if created by this test script)
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        for f in dummy_data_dir.iterdir():
            if f.is_file():
                os.remove(f)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
