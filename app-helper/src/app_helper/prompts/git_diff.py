import shutil
import subprocess
import sys

from app_helper.prompts.templates import CODE_REVIEW_PROMPT_TEMPLATE, COMMIT_MESSAGE_PROMPT_TEMPLATE


def _get_git_diff_output(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")

    diff = result.stdout.strip()
    if not diff:
        raise ValueError("No changes found.")

    return diff


def build_prompt(language: str = "English") -> str:
    try:
        diff = _get_git_diff_output(["git", "diff", "--cached"])
    except ValueError as e:
        raise ValueError("No staged changes found. Please stage your changes with `git add` first.") from e

    return COMMIT_MESSAGE_PROMPT_TEMPLATE.format(language=language, diff=diff)


def build_review_prompt(language: str = "English", staged_only: bool = False) -> str:
    args = ["git", "diff", "--cached"] if staged_only else ["git", "diff", "HEAD"]
    try:
        diff = _get_git_diff_output(args)
    except ValueError as e:
        hint = "staged changes" if staged_only else "changes (HEAD)"
        raise ValueError(f"No {hint} found.") from e

    return CODE_REVIEW_PROMPT_TEMPLATE.format(language=language, diff=diff)


def copy_to_clipboard(text: str) -> None:
    try:
        # Check if running in WSL (Windows Subsystem for Linux)
        if sys.platform.startswith("linux"):
            is_wsl = False
            try:
                with open("/proc/version") as f:
                    if "microsoft" in f.read().lower():
                        is_wsl = True
            except FileNotFoundError:
                pass

            if is_wsl:
                # clip.exe is the Windows utility that copies stdin to the Windows clipboard
                clip_path = shutil.which("clip.exe") or "/mnt/c/Windows/System32/clip.exe"
                try:
                    # Windows clip.exe handles UTF-16LE input perfectly for all characters
                    subprocess.run([clip_path], input=text.encode("utf-16le"), check=True)
                    return
                except (subprocess.SubprocessError, FileNotFoundError):
                    # Fallback to standard Linux tools if clip.exe fails or is not found
                    pass

        encoded = text.encode("utf-8")
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=encoded, check=True)
        elif sys.platform.startswith("linux"):
            try:
                subprocess.run(["xclip", "-selection", "clipboard"], input=encoded, check=True)
            except FileNotFoundError:
                try:
                    subprocess.run(["xsel", "--clipboard", "--input"], input=encoded, check=True)
                except FileNotFoundError as exc:
                    raise RuntimeError(
                        "Clipboard tool not found. Please install xclip or xsel.\n"
                        "  Ubuntu/Debian: sudo apt install xclip\n"
                        "  Fedora/RHEL:   sudo dnf install xclip"
                    ) from exc
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=encoded, check=True)
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to copy to clipboard: {e}") from e
