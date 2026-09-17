from app_error import Actor, AppError, Retry


class SearchConfigurationError(AppError, ValueError):
    code = "SEARCH_CONFIGURATION_INVALID"
    actor = Actor.DEVELOPER
    retry = Retry.AFTER_FIX


class SearchInputError(AppError, ValueError):
    code = "SEARCH_INPUT_INVALID"
    actor = Actor.USER
    retry = Retry.AFTER_FIX


class SearchSourceError(AppError, ValueError):
    code = "SEARCH_SOURCE_INVALID"
    actor = Actor.DEVELOPER
    retry = Retry.AFTER_FIX
