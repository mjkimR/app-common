import subprocess

import pytest
from app_helper.clipboard import copy_text


class TestCopyText:
    def test_darwin_uses_pbcopy(self, mocker):
        mocker.patch("sys.platform", "darwin")
        run = mocker.patch("subprocess.run")

        copy_text("hello")

        assert run.call_args.args[0] == ["pbcopy"]
        assert run.call_args.kwargs["input"] == b"hello"

    def test_win32_uses_clip(self, mocker):
        mocker.patch("sys.platform", "win32")
        run = mocker.patch("subprocess.run")

        copy_text("hi")

        assert run.call_args.args[0] == ["clip"]

    def test_linux_uses_xclip(self, mocker):
        mocker.patch("sys.platform", "linux")
        mocker.patch("builtins.open", mocker.mock_open(read_data="Linux version 6.0 generic"))
        run = mocker.patch("subprocess.run")

        copy_text("hi")

        assert run.call_args.args[0] == ["xclip", "-selection", "clipboard"]

    def test_linux_falls_back_to_xsel_when_xclip_missing(self, mocker):
        mocker.patch("sys.platform", "linux")
        mocker.patch("builtins.open", mocker.mock_open(read_data="Linux"))

        def run_side_effect(cmd, **kwargs):
            if cmd[0] == "xclip":
                raise FileNotFoundError
            return subprocess.CompletedProcess(cmd, 0)

        run = mocker.patch("subprocess.run", side_effect=run_side_effect)

        copy_text("hi")

        assert run.call_args.args[0] == ["xsel", "--clipboard", "--input"]

    def test_linux_raises_when_no_clipboard_tool(self, mocker):
        mocker.patch("sys.platform", "linux")
        mocker.patch("builtins.open", mocker.mock_open(read_data="Linux"))
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)

        with pytest.raises(RuntimeError, match="Clipboard tool not found"):
            copy_text("hi")

    def test_wsl_uses_clip_exe_with_utf16le(self, mocker):
        mocker.patch("sys.platform", "linux")
        mocker.patch("builtins.open", mocker.mock_open(read_data="Linux version microsoft-standard-WSL2"))
        mocker.patch("shutil.which", return_value="/mnt/c/clip.exe")
        run = mocker.patch("subprocess.run")

        copy_text("héllo")

        assert run.call_args.args[0] == ["/mnt/c/clip.exe"]
        assert run.call_args.kwargs["input"] == "héllo".encode("utf-16le")

    def test_unsupported_platform_raises(self, mocker):
        mocker.patch("sys.platform", "sunos5")

        with pytest.raises(RuntimeError, match="Unsupported platform"):
            copy_text("hi")

    def test_called_process_error_is_wrapped(self, mocker):
        mocker.patch("sys.platform", "darwin")
        mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["pbcopy"]))

        with pytest.raises(RuntimeError, match="Failed to copy to clipboard"):
            copy_text("hi")
