from http import HTTPStatus

from app_layer_base.base.exceptions.base import CustomException
from app_layer_base.base.exceptions.basic import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)


class IncorrectEmailOrPasswordException(BadRequestException):
    message = "Incorrect email or password"
    trace = False


class InvalidCredentialsException(CustomException):
    """The token is missing, malformed, expired, or no longer valid.

    401, not 403: a client refreshes or signs in again on this, and must be able to tell it from a request it is
    simply not allowed to make (`PermissionDeniedException`).
    """

    status_code = HTTPStatus.UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    title = "Unauthorized"
    message = "Could not validate credentials"
    trace = False


class TooManyLoginAttemptsException(CustomException):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "TOO_MANY_LOGIN_ATTEMPTS"
    title = "Too Many Requests"
    message = "Too many failed login attempts; try again later"
    trace = False


class PermissionDeniedException(ForbiddenException):
    message = "The user doesn't have enough privileges"
    trace = False


class UserCantDeleteItselfException(ForbiddenException):
    message = "User can't delete itself"
    trace = False


class UserNotFoundException(NotFoundException):
    message = "User not found"
    trace = False


class UserAlreadyExistsException(ConflictException):
    message = "The user with this username already exists in the system"
    trace = False
