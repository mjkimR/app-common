import subprocess

import pytest
from app_helper import git


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr=stderr)


class TestGetDiff:
    def test_returns_stripped_diff(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(stdout="  diff --git a b\n  "))

        assert git.get_diff(git.HEAD) == "diff --git a b"

    def test_excludes_lock_file_from_diff(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_completed(stdout="d"))

        git.get_diff(git.STAGED)

        assert run.call_args.args[0] == ["git", "diff", "--cached", "--", ".", ":(exclude)uv.lock"]

    def test_last_commit_revision_range(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_completed(stdout="d"))

        git.get_diff(git.LAST_COMMIT)

        assert run.call_args.args[0][:4] == ["git", "diff", "HEAD~1", "HEAD"]

    def test_raises_on_nonzero_returncode(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(returncode=1, stderr="fatal: not a repo"))

        with pytest.raises(RuntimeError, match="git diff failed"):
            git.get_diff(git.HEAD)

    def test_raises_on_empty_diff(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(stdout="   "))

        with pytest.raises(ValueError, match="No changes found"):
            git.get_diff(git.HEAD)


class TestEnsureRepo:
    def test_passes_inside_work_tree(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(stdout="true"))

        git.ensure_repo()

    def test_raises_outside_repo(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(returncode=128, stderr="fatal:"))

        with pytest.raises(RuntimeError, match="Not a git repository"):
            git.ensure_repo()


class TestStageAll:
    def test_runs_git_add(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_completed())

        git.stage_all()

        assert run.call_args.args[0] == ["git", "add", "."]

    def test_raises_on_failure(self, mocker):
        mocker.patch("subprocess.run", return_value=_completed(returncode=1, stderr="permission denied"))

        with pytest.raises(RuntimeError, match="git add failed"):
            git.stage_all()
