"""
Credential Security and Encryption
Supports Windows DPAPI (Data Protection API) with Fernet AES-256 fallback.
Ensures API secrets are never logged or sent to LLMs or UI.
"""
import os
import sys
import base64
import ctypes
from typing import Optional
from cryptography.fernet import Fernet
from pathlib import Path

# Windows DPAPI structs
if sys.platform == "win32":
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

class CredentialVault:
    def __init__(self, key_file_path: Optional[Path] = None):
        self.is_windows = sys.platform == "win32"
        self._fallback_key_file = key_file_path or (Path(__file__).resolve().parent.parent.parent / "data" / ".vault.key")
        self._fernet: Optional[Fernet] = None
        self._init_fallback_fernet()

    def _init_fallback_fernet(self):
        try:
            self._fallback_key_file.parent.mkdir(parents=True, exist_ok=True)
            if self._fallback_key_file.exists():
                key = self._fallback_key_file.read_bytes().strip()
            else:
                key = Fernet.generate_key()
                self._fallback_key_file.write_bytes(key)
                if self.is_windows:
                    # Hide file on windows
                    try:
                        ctypes.windll.kernel32.SetFileAttributesW(str(self._fallback_key_file), 0x02)  # FILE_ATTRIBUTE_HIDDEN
                    except Exception:
                        pass
            self._fernet = Fernet(key)
        except Exception as e:
            # Generate in-memory key if filesystem access fails
            key = Fernet.generate_key()
            self._fernet = Fernet(key)

    def protect(self, plaintext: str) -> str:
        """Encrypt sensitive plaintext string using Windows DPAPI or Fernet."""
        if not plaintext:
            return ""
        
        data_bytes = plaintext.encode("utf-8")
        
        if self.is_windows:
            try:
                blob_in = DATA_BLOB(len(data_bytes), ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte)))
                blob_out = DATA_BLOB()
                if ctypes.windll.crypt32.CryptProtectData(
                    ctypes.byref(blob_in),
                    "ABTC_SECURE_VAULT",
                    None,
                    None,
                    None,
                    0,
                    ctypes.byref(blob_out)
                ):
                    encrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                    return "DPAPI:" + base64.b64encode(encrypted_bytes).decode("ascii")
            except Exception:
                pass  # Fallback to Fernet
        
        # Fallback to Fernet
        return "FERNET:" + self._fernet.encrypt(data_bytes).decode("ascii")

    def unprotect(self, ciphertext: str) -> str:
        """Decrypt sensitive ciphertext."""
        if not ciphertext:
            return ""
        
        try:
            if ciphertext.startswith("DPAPI:") and self.is_windows:
                raw_b64 = ciphertext[6:]
                encrypted_bytes = base64.b64decode(raw_b64)
                blob_in = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)))
                blob_out = DATA_BLOB()
                if ctypes.windll.crypt32.CryptUnprotectData(
                    ctypes.byref(blob_in),
                    None,
                    None,
                    None,
                    None,
                    0,
                    ctypes.byref(blob_out)
                ):
                    decrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                    return decrypted_bytes.decode("utf-8")
            elif ciphertext.startswith("FERNET:"):
                raw_b64 = ciphertext[7:].encode("ascii")
                return self._fernet.decrypt(raw_b64).decode("utf-8")
            else:
                # Plaintext legacy/fallback
                return ciphertext
        except Exception:
            return ""

def mask_secret(secret: Optional[str]) -> str:
    """Masks a secret string so it can be safely sent to frontend or logs."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "********"
    return f"{secret[:4]}...{secret[-4:]}"

vault = CredentialVault()
