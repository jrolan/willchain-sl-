import base64
import hashlib
import json
import secrets

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class IntegrityCryptoError(Exception):
    pass


def canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')


def sha256_hex(value):
    return hashlib.sha256(value).hexdigest()


def commitment_for(record_reference, content_digest, salt):
    record_id = bytes.fromhex(record_reference)
    digest = bytes.fromhex(content_digest)
    if len(record_id) != 32 or len(digest) != 32 or len(salt) != 32:
        raise IntegrityCryptoError('Integrity commitment inputs must be 32 bytes.')
    return hashlib.sha256(record_id + digest + salt).hexdigest()


def new_record_reference():
    return secrets.token_hex(32)


def new_salt():
    return secrets.token_bytes(32)


def _fernet():
    configured_key = getattr(settings, 'INTEGRITY_ENCRYPTION_KEY', '')
    if configured_key:
        key = configured_key.encode('ascii')
    else:
        key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
        )
    try:
        return Fernet(key)
    except (TypeError, ValueError) as error:
        raise IntegrityCryptoError('Integrity encryption key is invalid.') from error


def encrypt_secret(purpose, value):
    return _fernet().encrypt(purpose.encode('ascii') + b':' + value).decode('ascii')


def decrypt_secret(purpose, token):
    try:
        value = _fernet().decrypt(token.encode('ascii'))
    except (InvalidToken, UnicodeEncodeError, ValueError) as error:
        raise IntegrityCryptoError('Protected integrity material could not be decrypted.') from error
    prefix = purpose.encode('ascii') + b':'
    if not value.startswith(prefix):
        raise IntegrityCryptoError('Protected integrity material has an invalid purpose.')
    return value[len(prefix):]
