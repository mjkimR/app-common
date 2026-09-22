from app_layer_base.base.exceptions.base import CustomException


class InvalidApiKey(CustomException):
    status_code = 401
    code = "INVALID_API_KEY"
    message = "Invalid or missing API key"
    trace = False


class ApiKeyPermissionDenied(CustomException):
    status_code = 403
    code = "API_KEY_PERMISSION_DENIED"
    message = "The credential does not grant this operation"
    trace = False
