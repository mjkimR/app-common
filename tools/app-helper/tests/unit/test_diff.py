import subprocess

import pytest
from app_helper import git
from app_helper.cli import cli
from app_helper.diff import write_diff_file
from click.testing import CliRunner


@pytest.fixture
def tmp_gettempdir(mocker, tmp_path):
    mocker.patch("tempfile.gettempdir", return_value=str(tmp_path))
    return tmp_path


class TestWriteDiffFile:
    def test_stages_then_writes_staged_diff(self, mocker, tmp_gettempdir):
        mocker.patch("app_helper.git.ensure_repo")
        stage = mocker.patch("app_helper.git.stage_all")
        diff = mocker.patch("app_helper.git.get_diff", return_value="MY DIFF")

        path = write_diff_file()

        stage.assert_called_once()
        diff.assert_called_once_with(git.STAGED)
        assert path.read_text() == "MY DIFF\n"

    def test_no_add_skips_staging(self, mocker, tmp_gettempdir):
        mocker.patch("app_helper.git.ensure_repo")
        stage = mocker.patch("app_helper.git.stage_all")
        mocker.patch("app_helper.git.get_diff", return_value="D")

        write_diff_file(stage=False)

        stage.assert_not_called()

    def test_default_filename_is_content_hash(self, mocker, tmp_gettempdir):
        mocker.patch("app_helper.git.ensure_repo")
        mocker.patch("app_helper.git.stage_all")
        mocker.patch("app_helper.git.get_diff", return_value="MY DIFF")

        path = write_diff_file()

        assert path.name.startswith("diff-")
        assert path.suffix == ".txt"
        # Same content must land on the same filename.
        assert write_diff_file().name == path.name

    def test_extensionless_filename_gets_txt_suffix(self, mocker, tmp_gettempdir):
        mocker.patch("app_helper.git.ensure_repo")
        mocker.patch("app_helper.git.stage_all")
        mocker.patch("app_helper.git.get_diff", return_value="D")

        assert write_diff_file(filename="feature").name == "feature.txt"

    def test_filename_with_extension_is_left_alone(self, mocker, tmp_gettempdir):
        mocker.patch("app_helper.git.ensure_repo")
        mocker.patch("app_helper.git.stage_all")
        mocker.patch("app_helper.git.get_diff", return_value="D")

        assert write_diff_file(filename="feature.patch").name == "feature.patch"

    def test_outside_repo_raises(self, mocker):
        mocker.patch("app_helper.git.ensure_repo", side_effect=RuntimeError("Not a git repository."))

        with pytest.raises(RuntimeError, match="Not a git repository"):
            write_diff_file()

    def test_empty_diff_raises(self, mocker, tmp_gettempdir):
        mocker.patch("app_helper.git.ensure_repo")
        mocker.patch("app_helper.git.stage_all")
        mocker.patch("app_helper.git.get_diff", side_effect=ValueError("No changes found."))

        with pytest.raises(ValueError, match="No staged changes found"):
            write_diff_file()


class TestCopyDiffCommand:
    def test_copies_file_and_reports_path(self, mocker, tmp_path):
        path = tmp_path / "diff-abc1234.txt"
        mocker.patch("app_helper.diff.write_diff_file", return_value=path)
        copy = mocker.patch("app_helper.diff.copy_file")

        result = CliRunner().invoke(cli, ["copy-diff"])

        assert result.exit_code == 0
        assert "Copied diff file to clipboard" in result.output
        assert str(path) in result.output
        copy.assert_called_once_with(path)

    def test_passes_filename_and_no_add(self, mocker, tmp_path):
        write = mocker.patch("app_helper.diff.write_diff_file", return_value=tmp_path / "f.txt")
        mocker.patch("app_helper.diff.copy_file")

        result = CliRunner().invoke(cli, ["copy-diff", "feature", "--no-add"])

        assert result.exit_code == 0
        write.assert_called_once_with(filename="feature", stage=False)

    def test_unsupported_platform_still_reports_path(self, mocker, tmp_path):
        path = tmp_path / "d.txt"
        mocker.patch("app_helper.diff.write_diff_file", return_value=path)
        mocker.patch("app_helper.diff.copy_file", side_effect=RuntimeError("only supported on macOS"))

        result = CliRunner().invoke(cli, ["copy-diff"])

        assert result.exit_code == 0
        assert "only supported on macOS" in result.output
        assert str(path) in result.output

    def test_error_becomes_click_exception(self, mocker):
        mocker.patch("app_helper.diff.write_diff_file", side_effect=RuntimeError("Not a git repository."))

        result = CliRunner().invoke(cli, ["copy-diff"])

        assert result.exit_code != 0
        assert "Not a git repository." in result.output


class TestCopyFile:
    def test_darwin_uses_osascript(self, mocker, tmp_path):
        from app_helper.clipboard import copy_file

        mocker.patch("sys.platform", "darwin")
        run = mocker.patch("subprocess.run")

        copy_file(tmp_path / "d.txt")

        assert run.call_args.args[0][0] == "osascript"
        assert str(tmp_path / "d.txt") in run.call_args.args[0][2]

    def test_non_darwin_raises(self, mocker, tmp_path):
        from app_helper.clipboard import copy_file

        mocker.patch("sys.platform", "linux")

        with pytest.raises(RuntimeError, match="only supported on macOS"):
            copy_file(tmp_path / "d.txt")

    def test_osascript_failure_is_wrapped(self, mocker, tmp_path):
        from app_helper.clipboard import copy_file

        mocker.patch("sys.platform", "darwin")
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["osascript"], stderr=b"boom"),
        )

        with pytest.raises(RuntimeError, match="Failed to copy file to clipboard"):
            copy_file(tmp_path / "d.txt")
