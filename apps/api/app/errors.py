"""Typed API errors -> the contract's error envelope."""
from fastapi import HTTPException, status


class ApiError(HTTPException):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(status_code=http_status, detail=message)
        self.code = code


class NotFound(ApiError):
    def __init__(self, message: str = "Not found"):
        super().__init__("NOT_FOUND", message, status.HTTP_404_NOT_FOUND)


class Forbidden(ApiError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


class Unauthorized(ApiError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__("UNAUTHORIZED", message, status.HTTP_401_UNAUTHORIZED)


class Conflict(ApiError):
    def __init__(self, message: str = "Conflict"):
        super().__init__("CONFLICT", message, status.HTTP_409_CONFLICT)


class Unprocessable(ApiError):
    def __init__(self, message: str):
        super().__init__("VALIDATION_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class TooLarge(ApiError):
    def __init__(self, message: str = "Upload exceeds 25 MB limit"):
        super().__init__("PAYLOAD_TOO_LARGE", message, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


class BadRequest(ApiError):
    def __init__(self, message: str):
        super().__init__("BAD_REQUEST", message, status.HTTP_400_BAD_REQUEST)
