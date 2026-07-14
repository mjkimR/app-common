from app_helper.cli import cli
from click.testing import CliRunner


def test_commit_copies_prompt_and_reports(mocker):
    mocker.patch("app_helper.prompts.build_prompt", return_value="PROMPT")
    copy = mocker.patch("app_helper.prompts.copy_text")

    result = CliRunner().invoke(cli, ["prompt", "commit", "-l", "English"])

    assert result.exit_code == 0
    assert "copied to clipboard" in result.output
    copy.assert_called_once_with("PROMPT")


def test_commit_defaults_to_english(mocker):
    build = mocker.patch("app_helper.prompts.build_prompt", return_value="PROMPT")
    mocker.patch("app_helper.prompts.copy_text")

    result = CliRunner().invoke(cli, ["prompt", "commit"])

    assert result.exit_code == 0
    build.assert_called_once_with(language="English")


def test_commit_error_becomes_click_exception(mocker):
    mocker.patch("app_helper.prompts.build_prompt", side_effect=ValueError("No staged changes found."))

    result = CliRunner().invoke(cli, ["prompt", "commit"])

    assert result.exit_code != 0
    assert "No staged changes found." in result.output


def test_review_passes_staged_flag_and_language(mocker):
    build = mocker.patch("app_helper.prompts.build_review_prompt", return_value="R")
    mocker.patch("app_helper.prompts.copy_text")

    result = CliRunner().invoke(cli, ["prompt", "review", "--staged", "-l", "English"])

    assert result.exit_code == 0
    build.assert_called_once_with(language="English", staged_only=True, last_commit=False)
    assert "target: staged" in result.output


def test_review_last_commit(mocker):
    build = mocker.patch("app_helper.prompts.build_review_prompt", return_value="R")
    mocker.patch("app_helper.prompts.copy_text")

    result = CliRunner().invoke(cli, ["prompt", "review", "--last"])

    assert result.exit_code == 0
    build.assert_called_once_with(language="English", staged_only=False, last_commit=True)
    assert "target: last commit" in result.output


def test_review_defaults_to_head_and_english(mocker):
    build = mocker.patch("app_helper.prompts.build_review_prompt", return_value="R")
    mocker.patch("app_helper.prompts.copy_text")

    result = CliRunner().invoke(cli, ["prompt", "review"])

    assert result.exit_code == 0
    build.assert_called_once_with(language="English", staged_only=False, last_commit=False)
    assert "target: HEAD" in result.output
