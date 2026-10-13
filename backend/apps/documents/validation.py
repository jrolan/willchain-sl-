import hashlib
import io
import os
import re
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError
from django.utils.text import get_valid_filename
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rest_framework.exceptions import ValidationError


MAX_DOCUMENT_SIZE_BYTES = 10_000_000
ALLOWED_FORMATS = {
    '.pdf': ('application/pdf', 'PDF'),
    '.jpg': ('image/jpeg', 'JPEG'),
    '.jpeg': ('image/jpeg', 'JPEG'),
    '.png': ('image/png', 'PNG'),
}


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    extension: str
    media_type: str
    content: bytes
    checksum_sha256: str

    @property
    def file_size(self):
        return len(self.content)


def _safe_filename(raw_name):
    if not isinstance(raw_name, str) or '\x00' in raw_name:
        raise ValidationError({'file': 'The filename is invalid.'})
    basename = raw_name.replace('\\', '/').rsplit('/', 1)[-1]
    basename = ''.join(char for char in basename if char >= ' ' and char != '\x7f')
    safe_name = get_valid_filename(basename)[:255]
    if not safe_name or safe_name in {'.', '..'}:
        raise ValidationError({'file': 'The filename is invalid.'})
    return safe_name


def validate_upload(upload):
    if upload is None:
        raise ValidationError({'file': 'A document file is required.'})
    if upload.size <= 0:
        raise ValidationError({'file': 'Empty files are not accepted.'})
    if upload.size > MAX_DOCUMENT_SIZE_BYTES:
        raise ValidationError({'file': f'Files must not exceed {MAX_DOCUMENT_SIZE_BYTES} bytes.'})

    filename = _safe_filename(upload.name)
    extension = os.path.splitext(filename)[1].lower()
    allowed = ALLOWED_FORMATS.get(extension)
    if not allowed:
        raise ValidationError({'file': 'Only PDF, JPEG, and PNG documents are supported.'})
    expected_type, expected_format = allowed
    claimed_type = (getattr(upload, 'content_type', '') or '').lower()
    if claimed_type not in {expected_type, 'application/octet-stream'}:
        raise ValidationError({'file': 'The claimed media type does not match the file extension.'})

    upload.seek(0)
    content = upload.read(MAX_DOCUMENT_SIZE_BYTES + 1)
    upload.seek(0)
    if not content:
        raise ValidationError({'file': 'Empty files are not accepted.'})
    if len(content) > MAX_DOCUMENT_SIZE_BYTES:
        raise ValidationError({'file': f'Files must not exceed {MAX_DOCUMENT_SIZE_BYTES} bytes.'})

    if expected_format == 'PDF':
        if not content.startswith(b'%PDF-') or not re.search(rb'%%EOF\s*$', content[-2048:]):
            raise ValidationError({'file': 'The PDF content is malformed or does not match its extension.'})
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted or len(reader.pages) == 0:
                raise ValidationError({'file': 'Encrypted or empty PDFs are not accepted.'})
        except (PdfReadError, ValueError, OSError):
            raise ValidationError({'file': 'The PDF content is malformed or unreadable.'}) from None
    else:
        signatures_match = (
            content.startswith(b'\xff\xd8\xff')
            if expected_format == 'JPEG'
            else content.startswith(b'\x89PNG\r\n\x1a\n')
        )
        if not signatures_match:
            raise ValidationError({'file': 'The file signature does not match its extension.'})
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format != expected_format:
                    raise ValidationError({'file': 'The file content does not match its extension.'})
                if image.width * image.height > 40_000_000:
                    raise ValidationError({'file': 'The image dimensions exceed the allowed limit.'})
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValidationError({'file': 'The image content is malformed.'}) from None

    return ValidatedUpload(
        filename=filename,
        extension=extension,
        media_type=expected_type,
        content=content,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
    )