import hashlib
import os
import re
import secrets
import stat
from pathlib import Path

from django.conf import settings


class PrivateStorageError(Exception):
    pass


class PrivateDocumentStorage:
    key_pattern = re.compile(r'^[a-f0-9]{64}\.(pdf|jpg|jpeg|png)$')
    temporary_pattern = re.compile(r'^\.[a-f0-9]{64}\.tmp$')

    def _root(self):
        root = Path(settings.PRIVATE_DOCUMENT_ROOT)
        if root.is_symlink():
            raise PrivateStorageError('Private storage root cannot be a symbolic link.')
        resolved = root.resolve()
        public_roots = [Path(settings.MEDIA_ROOT).resolve()]
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if static_root:
            public_roots.append(Path(static_root).resolve())
        if any(resolved == public_root or resolved.is_relative_to(public_root) for public_root in public_roots):
            raise PrivateStorageError('Private document storage cannot be inside a public media or static root.')
        resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(resolved, 0o700)
        except OSError:
            pass
        return resolved

    def _path(self, key):
        if not isinstance(key, str) or not self.key_pattern.fullmatch(key):
            raise PrivateStorageError('Invalid private storage identifier.')
        root = self._root()
        path = root / key
        if path.parent != root or path.is_symlink():
            raise PrivateStorageError('Unsafe private storage path.')
        return path

    def root_path(self):
        return self._root()

    def candidate_files(self):
        root = self._root()
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file():
                continue
            if self.key_pattern.fullmatch(path.name) or self.temporary_pattern.fullmatch(path.name):
                yield path

    def save(self, upload):
        suffix = Path(upload.filename).suffix.lower()
        key = f'{secrets.token_hex(32)}{suffix}'
        destination = self._path(key)
        temporary = self._root() / f'.{secrets.token_hex(32)}.tmp'
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(upload.content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
            try:
                os.chmod(destination, 0o600)
            except OSError:
                pass
            return key
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            finally:
                raise

    def open(self, key):
        path = self._path(key)
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        try:
            descriptor = os.open(path, flags)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                os.close(descriptor)
                raise PrivateStorageError('Stored document is not a regular file.')
            return os.fdopen(descriptor, 'rb')
        except OSError as error:
            raise PrivateStorageError('Stored document is unavailable.') from error

    def delete(self, key):
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as error:
            raise PrivateStorageError('Unable to remove the unreferenced file.') from error

    def checksum(self, key):
        digest = hashlib.sha256()
        try:
            with self.open(key) as source:
                for chunk in iter(lambda: source.read(64 * 1024), b''):
                    digest.update(chunk)
        except OSError as error:
            raise PrivateStorageError('Stored document could not be read.') from error
        return digest.hexdigest()


private_document_storage = PrivateDocumentStorage()