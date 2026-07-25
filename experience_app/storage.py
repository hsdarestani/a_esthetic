import io
import os
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage


class EncryptedPrivateStorage(FileSystemStorage):
    """Encrypt sensitive files before they touch disk and decrypt only after authorization."""

    def __init__(self, *args, **kwargs):
        location = kwargs.pop("location", getattr(settings, "PRIVATE_MEDIA_ROOT", settings.BASE_DIR / "private_media"))
        super().__init__(location=location, base_url=None, *args, **kwargs)

    def _fernet(self):
        raw = os.environ.get("PRIVATE_FILE_ENCRYPTION_KEYS", "")
        keys = [item.strip().encode() for item in raw.split(",") if item.strip()]
        if not keys:
            raise ImproperlyConfigured("PRIVATE_FILE_ENCRYPTION_KEYS ist nicht konfiguriert.")
        try:
            return MultiFernet([Fernet(key) for key in keys])
        except Exception as exc:
            raise ImproperlyConfigured("Ungültiger Schlüssel für private Dateien.") from exc

    def _save(self, name, content):
        plaintext = content.read()
        encrypted = self._fernet().encrypt(plaintext)
        saved_name = super()._save(name + ".enc", ContentFile(encrypted))
        try:
            os.chmod(self.path(saved_name), 0o600)
        except OSError:
            pass
        return saved_name

    def _open(self, name, mode="rb"):
        encrypted_file = super()._open(name, "rb")
        encrypted = encrypted_file.read()
        encrypted_file.close()
        plaintext = self._fernet().decrypt(encrypted)
        return ContentFile(plaintext, name=Path(name).name.removesuffix(".enc"))

    def url(self, name):
        raise ValueError("Private Dateien haben keine öffentliche URL.")


private_storage = EncryptedPrivateStorage()
