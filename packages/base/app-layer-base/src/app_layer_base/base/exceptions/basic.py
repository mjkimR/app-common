from http import HTTPStatus

from app_layer_base.base.exceptions.base import CustomException


class BadRequestException(CustomException):
    status_code = HTTPStatus.BAD_REQUEST
    code = "BAD_REQUEST"
    title = "Bad Request"
    message = "Bad Request"


class ForbiddenException(CustomException):
    status_code = HTTPStatus.FORBIDDEN
    code = "FORBIDDEN"
    title = "Forbidden"
    message = "Forbidden"


class NotFoundException(CustomException):
    status_code = HTTPStatus.NOT_FOUND
    code = "NOT_FOUND"
    title = "Resource Not Found"
    message = "Not Found"
    trace = False


class ConflictException(CustomException):
    status_code = HTTPStatus.CONFLICT
    code = "CONFLICT"
    title = "Conflict"
    message = "Conflict"
