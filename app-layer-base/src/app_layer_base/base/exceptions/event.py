from http import HTTPStatus

from app_layer_base.base.exceptions.base import CustomException


class EventProcessingException(CustomException):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    message = "Event processing failed"


class EventHandlerNotFoundException(CustomException):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    message = "Event handler not found for the given event type"


class InvalidEventPayloadException(CustomException):
    status_code = HTTPStatus.BAD_REQUEST
    message = "Invalid event payload"
