"""
app/storage/validation.py

Deep file validation beyond MIME type.

WHY magic bytes?
Content-Type header is user-supplied and trivially spoofed.
e.g. rename malware.exe to audio.mp3 — MIME check passes.
Magic bytes are the actual file signature — much harder to fake.

We read the first 12 bytes and compare against known audio/video signatures.
"""

from app.core.exceptions import InvalidFileTypeError

# Magic byte signatures for allowed audio/video formats
# Format: (offset, bytes_to_match)
MAGIC_SIGNATURES: list[tuple[int, bytes, str]] = [
    # (offset, signature, format_name)
    (0,  b"ID3",                   "mp3"),
    (0,  b"\xff\xfb",              "mp3"),
    (0,  b"\xff\xf3",              "mp3"),
    (0,  b"\xff\xf2",              "mp3"),
    (0,  b"RIFF",                  "wav"),    # WAV uses RIFF container
    (0,  b"fLaC",                  "flac"),
    (0,  b"OggS",                  "ogg"),
    (4,  b"ftyp",                  "mp4"),    # MP4/M4A
    (0,  b"\x1a\x45\xdf\xa3",     "webm"),   # WebM/MKV
    (0,  b"\x00\x00\x00",         "mp4"),    # Some MP4 variants
]

ALLOWED_MIME_TYPES_VALIDATION = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav",
    "audio/webm", "audio/ogg", "audio/flac",
    "video/mp4", "video/webm", "video/quicktime",
}


def validate_file_magic(file_bytes: bytes, filename: str) -> None:
    """
    Validate file magic bytes against known audio/video signatures.
    Raises InvalidFileTypeError if file doesn't match any known format.
    """
    header = file_bytes[:12]

    for offset, signature, fmt in MAGIC_SIGNATURES:
        if header[offset:offset + len(signature)] == signature:
            return  # Valid — matches a known signature

    # Special case: WAV files need RIFF + WAVE check
    if len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WAVE":
        return

    raise InvalidFileTypeError(
        allowed=["mp3", "wav", "flac", "ogg", "mp4", "webm", "m4a"]
    )


def sanitize_filename(filename: str) -> str:
    """
    Remove path traversal attempts and dangerous characters.
    Keep only alphanumeric, dash, underscore, dot.
    """
    import re
    # Strip path separators
    filename = filename.replace("/", "").replace("\\", "").replace("..", "")
    # Keep safe characters only
    safe = re.sub(r"[^\w\.\-]", "_", filename)
    # Limit length
    if len(safe) > 255:
        name, _, ext = safe.rpartition(".")
        safe = name[:250] + "." + ext
    return safe or "upload"