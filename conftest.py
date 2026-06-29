import os

from cryptography.fernet import Fernet

os.environ.setdefault("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
