from app_base.base.exceptions.base import CustomException


class FilterDependencyError(CustomException):
    """Base exception for all filter dependency related errors."""

    pass


class ConfigurationError(FilterDependencyError):
    """
    Raised for errors in filter configuration during development.

    This category of exceptions indicates a problem with how the filter
    dependencies are defined in the code, rather than an issue with runtime
    user input.
    """

    pass


class InvalidValueError(FilterDependencyError):
    """
    Raised when a value provided to a filter is invalid.

    This can occur in two scenarios:

    1.  **Configuration Time**: An invalid value is used when defining a filter,
        such as an incorrect enum value for a `match_type`.
    2.  **Runtime**: An invalid value is provided by an API user, such as a
        field name for ordering that is not in the allowed `whitelist`.
    """

    pass
