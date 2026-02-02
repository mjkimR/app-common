from fastapi import status

from app_base.base.exceptions.base import CustomException


class BadRequestException(CustomException):
    status_code = status.HTTP_400_BAD_REQUEST
    title = "Bad Request"
    message = "Bad Request"


class ForbiddenException(CustomException):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Forbidden"
    message = "Forbidden"


class NotFoundException(CustomException):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Resource Not Found"
    message = "Not Found"
    trace = False


class ConflictException(CustomException):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"
    message = "Conflict"
