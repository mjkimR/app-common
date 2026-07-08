from app_helper.cli import cli
from click.testing import CliRunner


def test_commit_copies_prompt_and_reports(mocker):
    mocker.patch("app_helper.prompts.build_prompt", return_value="PROMPT")
    copy = mocker.patch("app_helper.prompts.copy_to_clipboard")

    result = CliRunner().invoke(cli, ["prompt", "commit", "-l", "Korean"])

    assert result.exit_code == 0
    assert "copied to clipboard" in result.output
    copy.assert_called_once_with("PROMPT")


def test_commit_error_becomes_click_exception(mocker):
    mocker.patch("app_helper.prompts.build_prompt", side_effect=ValueError("No staged changes found."))

    result = CliRunner().invoke(cli, ["prompt", "commit"])

    assert result.exit_code != 0
    assert "No staged changes found." in result.output


def test_review_passes_staged_flag_and_language(mocker):
    build = mocker.patch("app_helper.prompts.build_review_prompt", return_value="R")
    mocker.patch("app_helper.prompts.copy_to_clipboard")

    result = CliRunner().invoke(cli, ["prompt", "review", "--staged", "-l", "English"])

    assert result.exit_code == 0
    build.assert_called_once_with(language="English", staged_only=True)


def test_review_defaults_to_head_and_korean(mocker):
    build = mocker.patch("app_helper.prompts.build_review_prompt", return_value="R")
    mocker.patch("app_helper.prompts.copy_to_clipboard")

    result = CliRunner().invoke(cli, ["prompt", "review"])

    assert result.exit_code == 0
    build.assert_called_once_with(language="Korean", staged_only=False)
