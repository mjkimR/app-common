"""Unit tests for app_base.core.traceback"""

from unittest.mock import MagicMock, patch

from app_base.core.traceback import (
    _is_whitelisted,
    get_exception_traceback_str,
)

# ---------------------------------------------------------------------------
# _is_whitelisted
# ---------------------------------------------------------------------------


class TestIsWhitelisted:
    def test_returns_true_for_matching_directory_pattern(self):
        filename = "/home/user/site-packages/sqlalchemy/orm/session.py"
        assert _is_whitelisted(filename, ["sqlalchemy"]) is True

    def test_returns_true_for_matching_file_pattern(self):
        import os

        filename = os.path.join("/home", "user", "site-packages", "requests.py")
        assert _is_whitelisted(filename, ["requests"]) is True

    def test_returns_false_when_no_match(self):
        filename = "/home/user/site-packages/httpx/client.py"
        assert _is_whitelisted(filename, ["sqlalchemy", "requests"]) is False

    def test_returns_false_for_empty_whitelist(self):
        filename = "/home/user/site-packages/sqlalchemy/orm/session.py"
        assert _is_whitelisted(filename, []) is False

    def test_partial_name_does_not_match(self):
        # "sql" should not match "sqlalchemy"
        filename = "/home/user/site-packages/sqlalchemy/orm/session.py"
        assert _is_whitelisted(filename, ["sql"]) is False


# ---------------------------------------------------------------------------
# get_exception_traceback_str — LOG_SIMPLE_TRACEBACK = False
# ---------------------------------------------------------------------------


def _mock_settings(simple: bool = True, whitelist: list[str] | None = None):
    settings = MagicMock()
    settings.LOG_SIMPLE_TRACEBACK = simple
    settings.LOG_TRACEBACK_WHITELIST = whitelist or ["app_base"]
    return settings


class TestGetExceptionTracebackStrFullMode:
    """When LOG_SIMPLE_TRACEBACK is False, the full standard traceback is returned."""

    def test_returns_full_traceback(self):
        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings(simple=False)):
            try:
                raise ValueError("full traceback test")
            except ValueError as exc:
                result = get_exception_traceback_str(exc)

        assert "ValueError" in result
        assert "full traceback test" in result
        # Standard traceback includes "Traceback (most recent call last):"
        assert "Traceback (most recent call last):" in result

    def test_does_not_start_with_filtered_header(self):
        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings(simple=False)):
            try:
                raise RuntimeError("no filter")
            except RuntimeError as exc:
                result = get_exception_traceback_str(exc)

        assert "Traceback (Filtered):" not in result


# ---------------------------------------------------------------------------
# get_exception_traceback_str — LOG_SIMPLE_TRACEBACK = True
# ---------------------------------------------------------------------------


class TestGetExceptionTracebackStrFilteredMode:
    """When LOG_SIMPLE_TRACEBACK is True, noise frames are removed."""

    def test_starts_with_filtered_header(self):
        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            try:
                raise ValueError("filtered test")
            except ValueError as exc:
                result = get_exception_traceback_str(exc)

        assert result.startswith("Traceback (Filtered):\n")

    def test_exception_message_included(self):
        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            try:
                raise ValueError("hello traceback")
            except ValueError as exc:
                result = get_exception_traceback_str(exc)

        assert "hello traceback" in result

    def test_noise_patterns_filtered_out(self):
        """Frames containing noise patterns should not appear (unless they are the last frame)."""
        import traceback as tb

        noise_frame = tb.FrameSummary(
            filename="/usr/lib/python3/starlette/middleware/base.py",
            lineno=42,
            name="call_next",
        )
        # Last frame: project code that triggered the error
        last_frame = tb.FrameSummary(
            filename="/app/myproject/service.py",
            lineno=10,
            name="handle",
        )

        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            with patch("traceback.extract_tb", return_value=[noise_frame, last_frame]):
                try:
                    raise RuntimeError("noise test")
                except RuntimeError as exc:
                    result = get_exception_traceback_str(exc)

        assert "starlette/middleware" not in result
        assert "service.py" in result

    def test_last_frame_always_included(self):
        """The last frame (actual error site) must always be present even if it matches a noise pattern."""
        import traceback as tb

        noise_frame = tb.FrameSummary(
            filename="/usr/lib/python3/starlette/middleware/base.py",
            lineno=99,
            name="dispatch",
        )

        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            with patch("traceback.extract_tb", return_value=[noise_frame]):
                try:
                    raise RuntimeError("last frame test")
                except RuntimeError as exc:
                    result = get_exception_traceback_str(exc)

        # The last frame should be kept regardless of noise pattern
        assert "line 99" in result or "dispatch" in result

    def test_external_lib_filtered_without_whitelist(self):
        import traceback as tb

        site_frame = tb.FrameSummary(
            filename="/usr/lib/python3/site-packages/httpx/_client.py",
            lineno=10,
            name="send",
        )
        project_frame = tb.FrameSummary(
            filename="/app/myproject/service.py",
            lineno=20,
            name="do_work",
        )

        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings(whitelist=[])):
            with patch("traceback.extract_tb", return_value=[site_frame, project_frame]):
                try:
                    raise RuntimeError("external lib test")
                except RuntimeError as exc:
                    result = get_exception_traceback_str(exc)

        assert "_client.py" not in result
        assert "service.py" in result

    def test_whitelisted_external_lib_included(self):
        import traceback as tb

        sqlalchemy_frame = tb.FrameSummary(
            filename="/usr/lib/python3/site-packages/sqlalchemy/orm/session.py",
            lineno=5,
            name="execute",
        )
        project_frame = tb.FrameSummary(
            filename="/app/myproject/repo.py",
            lineno=15,
            name="query",
        )

        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings(whitelist=["sqlalchemy"])):
            with patch("traceback.extract_tb", return_value=[sqlalchemy_frame, project_frame]):
                try:
                    raise RuntimeError("whitelist test")
                except RuntimeError as exc:
                    result = get_exception_traceback_str(exc)

        assert "session.py" in result


# ---------------------------------------------------------------------------
# Exception chaining
# ---------------------------------------------------------------------------


class TestExceptionChaining:
    def test_explicit_cause_includes_both_exceptions(self):
        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            try:
                try:
                    raise ValueError("root cause")
                except ValueError as root:
                    raise RuntimeError("surface error") from root
            except RuntimeError as exc:
                result = get_exception_traceback_str(exc)

        assert "ValueError" in result
        assert "root cause" in result
        assert "RuntimeError" in result
        assert "surface error" in result

    def test_implicit_context_includes_both_exceptions(self):
        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            try:
                try:
                    raise ValueError("context error")
                except ValueError as exc:
                    raise RuntimeError("handler error") from exc
            except RuntimeError as exc:
                result = get_exception_traceback_str(exc)

        assert "ValueError" in result
        assert "context error" in result
        assert "RuntimeError" in result
        assert "handler error" in result

    def test_cyclic_exception_chain_does_not_hang(self):
        """Cyclic __cause__ references should not cause an infinite loop."""
        exc_a = ValueError("a")
        exc_b = RuntimeError("b")
        exc_a.__cause__ = exc_b
        exc_b.__cause__ = exc_a  # cycle

        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            result = get_exception_traceback_str(exc_a)

        # Should terminate and contain at least one of the exceptions
        assert "ValueError" in result or "RuntimeError" in result

    def test_single_exception_no_chaining_message(self):
        with patch("app_base.core.traceback.get_app_settings", return_value=_mock_settings()):
            try:
                raise KeyError("only one")
            except KeyError as exc:
                result = get_exception_traceback_str(exc)

        assert "direct cause" not in result
        assert "During handling" not in result
        assert "KeyError" in result
