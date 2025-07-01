# database/firestore_manager.py

import os
import logging
from typing import Dict, Any, Optional, List, Tuple
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_document import DocumentSnapshot

# Import the ConfigManager
from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class FirestoreManager:
    _instance = None
    _db = None
    _is_initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirestoreManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._is_initialized:
            self._initialize_firestore()
            self._is_initialized = True

    def _initialize_firestore(self):
        """
        Initializes the Firebase Admin SDK.
        It tries to load credentials from Streamlit secrets first,
        then from a service account file specified by an environment variable,
        and finally from Google Cloud's default application credentials.
        """
        config_manager = ConfigManager()
        
        # Try to load credentials from Streamlit secrets
        firestore_config = config_manager.get('firestore')

        if firestore_config and all(k in firestore_config for k in ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']):
            try:
                cred_dict = {
                    "type": firestore_config['type'],
                    "project_id": firestore_config['project_id'],
                    "private_key_id": firestore_config['private_key_id'],
                    "private_key": firestore_config['private_key'].replace('\\n', '\n'), # Handle newline characters
                    "client_email": firestore_config['client_email'],
                    "client_id": firestore_config.get('client_id'),
                    "auth_uri": firestore_config.get('auth_uri'),
                    "token_uri": firestore_config.get('token_uri'),
                    "auth_provider_x509_cert_url": firestore_config.get('auth_provider_x509_cert_url'),
                    "client_x509_cert_url": firestore_config.get('client_x509_cert_url'),
                    "universe_domain": firestore_config.get('universe_domain', 'googleapis.com')
                }
                cred = credentials.Certificate(cred_dict)
                logger.info("Initializing Firebase from Streamlit secrets.")
                firebase_admin.initialize_app(cred)
                self._db = firestore.client()
                logger.info("Firestore initialized successfully from secrets.")
                return
            except Exception as e:
                logger.error(f"Error initializing Firebase from secrets: {e}")
                st.error(f"Configuration Error: Could not initialize database from secrets. Details: {e}")
                # Fall through to other methods if secrets fail

        # Fallback 1: Try service account file via environment variable (e.g., for local dev or traditional deployments)
        if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            try:
                cred = credentials.ApplicationDefault()
                logger.info("Initializing Firebase using GOOGLE_APPLICATION_CREDENTIALS environment variable.")
                firebase_admin.initialize_app(cred)
                self._db = firestore.client()
                logger.info("Firestore initialized successfully using GOOGLE_APPLICATION_CREDENTIALS.")
                return
            except Exception as e:
                logger.error(f"Error initializing Firebase from GOOGLE_APPLICATION_CREDENTIALS: {e}")
                st.error(f"Configuration Error: Could not initialize database from GOOGLE_APPLICATION_CREDENTIALS. Details: {e}")
                # Fall through

        # Fallback 2: Implicitly try default application credentials (e.g., GKE, Cloud Run)
        try:
            logger.info("Initializing Firebase using default application credentials.")
            firebase_admin.initialize_app()
            self._db = firestore.client()
            logger.info("Firestore initialized successfully using default credentials.")
        except Exception as e:
            logger.critical(f"FATAL: Could not initialize Firebase from any source: {e}")
            st.error(f"Critical Error: Database could not be initialized. Please check backend configuration. Details: {e}")
            st.stop() # Stop the Streamlit app if DB cannot be initialized

    def get_db(self):
        """Returns the Firestore client."""
        if self._db is None:
            # Attempt re-initialization if somehow not initialized on first call
            self._initialize_firestore()
            if self._db is None:
                raise RuntimeError("Firestore database client is not initialized.")
        return self._db

    def _get_collection(self, collection_name: str):
        """Helper to get a collection reference."""
        return self.get_db().collection(collection_name)

    # === User Management ===
    def add_user(self, user_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Adds a new user to the 'users' collection."""
        try:
            doc_ref = self._get_collection('users').document(user_data['user_id'])
            doc_ref.set(user_data)
            logger.info(f"User '{user_data.get('email')}' added successfully to Firestore.")
            return True, "User added successfully."
        except Exception as e:
            logger.error(f"Error adding user to Firestore: {e}")
            return False, f"Failed to add user: {e}"

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user by their user_id from the 'users' collection."""
        try:
            doc_ref = self._get_collection('users').document(user_id)
            doc: DocumentSnapshot = doc_ref.get()
            if doc.exists:
                user_data = doc.to_dict()
                # Ensure user_id is part of the dictionary if not already
                if 'user_id' not in user_data:
                    user_data['user_id'] = doc.id
                return user_data
            return None
        except Exception as e:
            logger.error(f"Error getting user '{user_id}' from Firestore: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user by their email from the 'users' collection."""
        try:
            # Firestore doesn't allow direct query by email for single document get,
            # so we query the collection for the email.
            docs = self._get_collection('users').where('email', '==', email).limit(1).stream()
            for doc in docs:
                user_data = doc.to_dict()
                if 'user_id' not in user_data:
                    user_data['user_id'] = doc.id
                return user_data
            return None
        except Exception as e:
            logger.error(f"Error getting user by email '{email}' from Firestore: {e}")
            return None

    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
        """Updates an existing user's data."""
        try:
            doc_ref = self._get_collection('users').document(user_id)
            doc_ref.update(updates)
            logger.info(f"User '{user_id}' updated successfully in Firestore.")
            return True, "User updated successfully."
        except Exception as e:
            logger.error(f"Error updating user '{user_id}' in Firestore: {e}")
            return False, f"Failed to update user: {e}"

    def delete_user(self, user_id: str) -> Tuple[bool, str]:
        """Deletes a user by their user_id."""
        try:
            self._get_collection('users').document(user_id).delete()
            logger.info(f"User '{user_id}' deleted successfully from Firestore.")
            return True, "User deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting user '{user_id}' from Firestore: {e}")
            return False, f"Failed to delete user: {e}"
            
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Retrieves all users from the 'users' collection."""
        users = []
        try:
            docs = self._get_collection('users').stream()
            for doc in docs:
                user_data = doc.to_dict()
                user_data['user_id'] = doc.id # Ensure user_id is always present
                users.append(user_data)
            return users
        except Exception as e:
            logger.error(f"Error retrieving all users from Firestore: {e}")
            return []

    # === Reset Tokens Management ===
    def add_reset_token(self, token_id: str, token_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Adds a new password reset token."""
        try:
            doc_ref = self._get_collection('reset_tokens').document(token_id)
            doc_ref.set(token_data)
            logger.info(f"Reset token '{token_id}' added successfully to Firestore.")
            return True, "Token added successfully."
        except Exception as e:
            logger.error(f"Error adding reset token to Firestore: {e}")
            return False, f"Failed to add token: {e}"

    def get_reset_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a password reset token."""
        try:
            doc_ref = self._get_collection('reset_tokens').document(token_id)
            doc: DocumentSnapshot = doc_ref.get()
            if doc.exists:
                token_data = doc.to_dict()
                if 'token_id' not in token_data: # Ensure token_id is part of the dictionary
                    token_data['token_id'] = doc.id
                return token_data
            return None
        except Exception as e:
            logger.error(f"Error getting reset token '{token_id}' from Firestore: {e}")
            return None

    def delete_reset_token(self, token_id: str) -> Tuple[bool, str]:
        """Deletes a password reset token."""
        try:
            self._get_collection('reset_tokens').document(token_id).delete()
            logger.info(f"Reset token '{token_id}' deleted successfully from Firestore.")
            return True, "Token deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting reset token '{token_id}' from Firestore: {e}")
            return False, f"Failed to delete token: {e}"

    def clean_expired_reset_tokens(self) -> int:
        """Deletes all expired password reset tokens."""
        cleaned_count = 0
        try:
            now = firestore.SERVER_TIMESTAMP # Use server timestamp for consistency
            expired_tokens_query = self._get_collection('reset_tokens').where('expires_at', '<', now).stream()
            
            for doc in expired_tokens_query:
                doc.reference.delete()
                cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired reset tokens from Firestore.")
            return cleaned_count
        except Exception as e:
            logger.error(f"Error cleaning expired reset tokens from Firestore: {e}")
            return 0
            
    # === OTP Management ===
    def add_otp(self, identifier: str, otp_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Adds a new OTP entry."""
        try:
            doc_ref = self._get_collection('otps').document(identifier) # Using identifier (email) as doc ID
            doc_ref.set(otp_data)
            logger.info(f"OTP for '{identifier}' added successfully to Firestore.")
            return True, "OTP added successfully."
        except Exception as e:
            logger.error(f"Error adding OTP for '{identifier}' to Firestore: {e}")
            return False, f"Failed to add OTP: {e}"

    def get_otp(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Retrieves an OTP entry."""
        try:
            doc_ref = self._get_collection('otps').document(identifier)
            doc: DocumentSnapshot = doc_ref.get()
            if doc.exists:
                otp_data = doc.to_dict()
                return otp_data
            return None
        except Exception as e:
            logger.error(f"Error getting OTP for '{identifier}' from Firestore: {e}")
            return None

    def update_otp(self, identifier: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
        """Updates an existing OTP entry."""
        try:
            doc_ref = self._get_collection('otps').document(identifier)
            doc_ref.update(updates)
            logger.info(f"OTP for '{identifier}' updated successfully in Firestore.")
            return True, "OTP updated successfully."
        except Exception as e:
            logger.error(f"Error updating OTP for '{identifier}' in Firestore: {e}")
            return False, f"Failed to update OTP: {e}"

    def delete_otp(self, identifier: str) -> Tuple[bool, str]:
        """Deletes an OTP entry."""
        try:
            self._get_collection('otps').document(identifier).delete()
            logger.info(f"OTP for '{identifier}' deleted successfully from Firestore.")
            return True, "OTP deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting OTP for '{identifier}' from Firestore: {e}")
            return False, f"Failed to delete OTP: {e}"

    def clean_expired_otps(self) -> int:
        """Deletes all expired OTP entries."""
        cleaned_count = 0
        try:
            now = firestore.SERVER_TIMESTAMP # Use server timestamp for consistency
            expired_otps_query = self._get_collection('otps').where('expires_at', '<', now).stream()
            
            for doc in expired_otps_query:
                doc.reference.delete()
                cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired OTPs from Firestore.")
            return cleaned_count
        except Exception as e:
            logger.error(f"Error cleaning expired OTPs from Firestore: {e}")
            return 0
