from contextlib import asynccontextmanager

from fastapi import status
from sqlalchemy.exc import (
    DataError,
    DBAPIError,
    IntegrityError,
    NoResultFound,
    OperationalError,
)

from app_base.base.exceptions.base import CustomException


class IntegrityException(CustomException):
    status_code = status.HTTP_409_CONFLICT
    title = "Data integrity violation"
    message = "Data integrity violation (e.g., Duplicate key or Foreign Key violation)"


class NoResultFoundException(CustomException):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Resource not found"
    message = "The requested resource was not found."


class InvalidDataException(CustomException):
    status_code = status.HTTP_400_BAD_REQUEST
    title = "Invalid data"
    message = "The provided data is invalid."


class DatabaseException(CustomException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    title = "Database error"
    message = "An unexpected database error occurred."


@asynccontextmanager
async def database_exception_handler():
    try:
        yield
    except NoResultFound as e:
        raise NoResultFoundException() from e
    except IntegrityError as e:
        raise IntegrityException() from e
    except DataError as e:
        raise InvalidDataException() from e
    except OperationalError as e:
        raise DatabaseException() from e
    except DBAPIError as e:
        raise DatabaseException() from e
