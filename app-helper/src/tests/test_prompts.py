import subprocess

import pytest
from app_helper.prompts import git_diff
from app_helper.prompts.git_diff import _get_git_diff_output, build_prompt, build_review_prompt


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr=stderr)


class TestGetGitDiffOutput:
    def test_returns_stripped_diff(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(stdout="  diff --git a b\n  "))

        assert _get_git_diff_output(["git", "diff"]) == "diff --git a b"

    def test_raises_on_nonzero_returncode(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(returncode=1, stderr="fatal: not a repo"))

        with pytest.raises(RuntimeError, match="git diff failed"):
            _get_git_diff_output(["git", "diff"])

    def test_raises_on_empty_diff(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(stdout="   "))

        with pytest.raises(ValueError, match="No changes found"):
            _get_git_diff_output(["git", "diff"])


class TestBuildPrompt:
    def test_formats_commit_template_from_staged_diff(self, mocker):
        diff_mock = mocker.patch.object(git_diff, "_get_git_diff_output", return_value="MY DIFF")

        result = build_prompt(language="Korean")

        assert "MY DIFF" in result
        assert "Korean" in result
        diff_mock.assert_called_once_with(["git", "diff", "--cached"])

    def test_empty_staged_raises_helpful_error(self, mocker):
        mocker.patch.object(git_diff, "_get_git_diff_output", side_effect=ValueError("No changes found."))

        with pytest.raises(ValueError, match="stage your changes"):
            build_prompt()


class TestBuildReviewPrompt:
    def test_uses_head_diff_by_default(self, mocker):
        diff_mock = mocker.patch.object(git_diff, "_get_git_diff_output", return_value="REVIEW DIFF")

        result = build_review_prompt(language="English")

        assert "REVIEW DIFF" in result
        assert "English" in result
        diff_mock.assert_called_once_with(["git", "diff", "HEAD"])

    def test_staged_only_uses_cached_diff(self, mocker):
        diff_mock = mocker.patch.object(git_diff, "_get_git_diff_output", return_value="D")

        build_review_prompt(staged_only=True)

        diff_mock.assert_called_once_with(["git", "diff", "--cached"])

    def test_empty_raises(self, mocker):
        mocker.patch.object(git_diff, "_get_git_diff_output", side_effect=ValueError("No changes found."))

        with pytest.raises(ValueError, match=r"No .* found"):
            build_review_prompt()
