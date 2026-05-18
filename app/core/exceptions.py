"""
app/core/exceptions.py

WHY: Decouple domain logic from HTTP. Service layer raises
     domain exceptions; the handler layer maps them to HTTP responses.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# ── Base ────────────────────────────────────────────────────

class AppException(Exception):
    def __init__(self, message: str, code: str = "error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


# ── Auth ─────────────────────────────────────────────────────

class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, code="authentication_error")


class InvalidTokenError(AppException):
    def __init__(self, message: str = "Invalid or expired token") -> None:
        super().__init__(message, code="invalid_token")


class PermissionDeniedError(AppException):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message, code="permission_denied")


# ── Resources ────────────────────────────────────────────────

class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", code="not_found")


class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, code="conflict")


# ── Files ────────────────────────────────────────────────────

class FileTooLargeError(AppException):
    def __init__(self, max_mb: int) -> None:
        super().__init__(
            f"File exceeds maximum size of {max_mb}MB",
            code="file_too_large",
        )


class InvalidFileTypeError(AppException):
    def __init__(self, allowed: list[str]) -> None:
        super().__init__(
            f"Invalid file type. Allowed: {', '.join(allowed)}",
            code="invalid_file_type",
        )


# ── Transcription ────────────────────────────────────────────

class TranscriptionError(AppException):
    def __init__(self, message: str = "Transcription failed") -> None:
        super().__init__(message, code="transcription_error")


# ── HTTP Handler Registration ────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(InvalidTokenError)
    async def invalid_token_handler(request: Request, exc: InvalidTokenError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(PermissionDeniedError)
    async def permission_handler(request: Request, exc: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(FileTooLargeError)
    async def file_too_large_handler(request: Request, exc: FileTooLargeError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(InvalidFileTypeError)
    async def invalid_file_type_handler(request: Request, exc: InvalidFileTypeError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(TranscriptionError)
    async def transcription_error_handler(request: Request, exc: TranscriptionError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": exc.code, "message": exc.message},
        )