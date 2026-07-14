import shutil
import subprocess
import sys
from pathlib import Path


def _is_wsl() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except FileNotFoundError:
        return False


def copy_text(text: str) -> None:
    try:
        if _is_wsl():
            # clip.exe is the Windows utility that copies stdin to the Windows clipboard.
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


def copy_file(path: Path) -> None:
    """Put the file itself on the clipboard, so it can be pasted as an attachment.

    Only macOS exposes a file-object clipboard we can drive from the shell; elsewhere the
    caller should fall back to handing the user the path.
    """
    if sys.platform != "darwin":
        raise RuntimeError(f"Copying a file to the clipboard is only supported on macOS (got {sys.platform}).")

    script = f'set the clipboard to (POSIX file "{path}" as «class furl»)'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to copy file to clipboard: {e.stderr.decode(errors='replace').strip()}") from e
