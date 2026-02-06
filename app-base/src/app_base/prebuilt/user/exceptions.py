from app_base.base.exceptions.basic import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)


class IncorrectEmailOrPasswordException(BadRequestException):
    message = "Incorrect email or password"
    trace = False


class InvalidCredentialsException(ForbiddenException):
    message = "Could not validate credentials"
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
