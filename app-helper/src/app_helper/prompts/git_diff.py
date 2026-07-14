from app_helper import git
from app_helper.prompts.templates import CODE_REVIEW_PROMPT_TEMPLATE, COMMIT_MESSAGE_PROMPT_TEMPLATE


def build_prompt(language: str = "English") -> str:
    try:
        diff = git.get_diff(git.STAGED)
    except ValueError as e:
        raise ValueError("No staged changes found. Please stage your changes with `git add` first.") from e

    return COMMIT_MESSAGE_PROMPT_TEMPLATE.format(language=language, diff=diff)


def build_review_prompt(language: str = "English", staged_only: bool = False, last_commit: bool = False) -> str:
    if staged_only and last_commit:
        raise ValueError("--staged and --last are mutually exclusive.")

    if last_commit:
        revision, hint = git.LAST_COMMIT, "last commit"
    elif staged_only:
        revision, hint = git.STAGED, "staged changes"
    else:
        revision, hint = git.HEAD, "changes (HEAD)"

    try:
        diff = git.get_diff(revision)
    except ValueError as e:
        raise ValueError(f"No {hint} found.") from e

    return CODE_REVIEW_PROMPT_TEMPLATE.format(language=language, diff=diff)
