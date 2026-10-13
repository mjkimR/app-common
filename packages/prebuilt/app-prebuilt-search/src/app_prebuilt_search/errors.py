from devkit.advisory import Actor, AdvisoryError, Retry


class SearchConfigurationError(AdvisoryError, ValueError):
    code = "SEARCH_CONFIGURATION_INVALID"
    actor = Actor.DEVELOPER
    retry = Retry.AFTER_FIX


class SearchInputError(AdvisoryError, ValueError):
    code = "SEARCH_INPUT_INVALID"
    actor = Actor.USER
    retry = Retry.AFTER_FIX


class SearchSourceError(AdvisoryError, ValueError):
    code = "SEARCH_SOURCE_INVALID"
    actor = Actor.DEVELOPER
    retry = Retry.AFTER_FIX
