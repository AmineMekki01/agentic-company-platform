from cryptography.fernet import Fernet

from app.core.config import settings


class EncryptionService:
    """
    Encrypt/decrypt strings using Fernet. Requires FERNET_KEY env var.
    
    Args:
        key: Fernet key (optional, will use settings.fernet_key if not provided)
    """
    def __init__(self, key: str | None = None) -> None:
        """
        Initialize with a Fernet key.
        
        Args:
            key: Fernet key (optional, will use settings.fernet_key if not provided)
        """
        raw = key or settings.fernet_key or ""
        if not raw:
            raise RuntimeError(
                "FERNET_KEY is required for credential encryption. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        self._fernet = Fernet(raw.encode())

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The plaintext string to encrypt
            
        Returns:
            The encrypted string
        """
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: The encrypted string to decrypt
            
        Returns:
            The decrypted string
        """
        return self._fernet.decrypt(ciphertext.encode()).decode()
