from fastapi import status

from app_base.base.exceptions.base import CustomException


class EventProcessingException(CustomException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Event processing failed"


class EventHandlerNotFoundException(CustomException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Event handler not found for the given event type"


class InvalidEventPayloadException(CustomException):
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Invalid event payload"
