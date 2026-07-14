import pytest
from app_helper import git
from app_helper.prompts.git_diff import build_prompt, build_review_prompt


class TestBuildPrompt:
    def test_formats_commit_template_from_staged_diff(self, mocker):
        diff_mock = mocker.patch("app_helper.git.get_diff", return_value="MY DIFF")

        result = build_prompt(language="Korean")

        assert "MY DIFF" in result
        assert "Korean" in result
        diff_mock.assert_called_once_with(git.STAGED)

    def test_empty_staged_raises_helpful_error(self, mocker):
        mocker.patch("app_helper.git.get_diff", side_effect=ValueError("No changes found."))

        with pytest.raises(ValueError, match="stage your changes"):
            build_prompt()


class TestBuildReviewPrompt:
    def test_uses_head_diff_by_default(self, mocker):
        diff_mock = mocker.patch("app_helper.git.get_diff", return_value="REVIEW DIFF")

        result = build_review_prompt(language="English")

        assert "REVIEW DIFF" in result
        assert "English" in result
        diff_mock.assert_called_once_with(git.HEAD)

    def test_staged_only_uses_cached_diff(self, mocker):
        diff_mock = mocker.patch("app_helper.git.get_diff", return_value="D")

        build_review_prompt(staged_only=True)

        diff_mock.assert_called_once_with(git.STAGED)

    def test_last_commit_uses_revision_range(self, mocker):
        diff_mock = mocker.patch("app_helper.git.get_diff", return_value="D")

        build_review_prompt(last_commit=True)

        diff_mock.assert_called_once_with(git.LAST_COMMIT)

    def test_staged_and_last_together_raise(self, mocker):
        mocker.patch("app_helper.git.get_diff", return_value="D")

        with pytest.raises(ValueError, match="mutually exclusive"):
            build_review_prompt(staged_only=True, last_commit=True)

    def test_empty_raises_with_target_hint(self, mocker):
        mocker.patch("app_helper.git.get_diff", side_effect=ValueError("No changes found."))

        with pytest.raises(ValueError, match="No last commit found"):
            build_review_prompt(last_commit=True)
