from app_error import (
    ActionMode,
    Actor,
    Advisory,
    AppError,
    ExitCode,
    Retry,
)


def test_advisory_mode_derivations():
    # 1. Guardrail blocked
    adv_guardrail = Advisory(guardrail=True, actor=Actor.TOOL, retry=Retry.SAFE)
    assert adv_guardrail.mode == ActionMode.BLOCKED

    # 2. Developer maintenance
    adv_dev = Advisory(actor=Actor.DEVELOPER, retry=Retry.AFTER_FIX)
    assert adv_dev.mode == ActionMode.MAINTENANCE

    # 3. Unsafe retry halts
    adv_halt = Advisory(actor=Actor.TOOL, retry=Retry.UNSAFE)
    assert adv_halt.mode == ActionMode.HALT

    # 4. Tool auto-fix
    adv_tool = Advisory(actor=Actor.TOOL, retry=Retry.SAFE, fix="uv run test")
    assert adv_tool.mode == ActionMode.AUTO

    # 5. User interaction
    adv_user = Advisory(actor=Actor.USER, retry=Retry.AFTER_FIX)
    assert adv_user.mode == ActionMode.INTERACTION

    # 6. Defer (safe retry, no actor specified)
    adv_defer = Advisory(actor=Actor.NONE, retry=Retry.SAFE, retry_after="60s")
    assert adv_defer.mode == ActionMode.DEFER


def test_advisory_lines():
    adv = Advisory(
        code="CONFIG_INVALID",
        actor=Actor.TOOL,
        retry=Retry.SAFE,
        fix="uv run setup",
        target_files=("config.json",),
        details=("Missing key 'api_url'",),
    )
    lines = adv.lines(message="Invalid configuration")
    rendered = "\n".join(lines)

    assert "[ERROR]  (CONFIG_INVALID) Invalid configuration" in rendered
    assert "[ACTION] AUTO" in rendered
    assert "[TARGET] config.json" in rendered
    assert "[FIX]    uv run setup" in rendered
    assert "[DETAIL] Missing key 'api_url'" in rendered


def test_app_error_defaults():
    err = AppError("Something went wrong")
    assert str(err) == "Something went wrong"
    assert err.code == "GENERAL_ERROR"
    assert err.exit_code == ExitCode.FAILED
    assert err.actor == Actor.NONE
    assert err.retry == Retry.UNSAFE
    assert err.mode == ActionMode.HALT

    lines = err.lines()
    assert any("[ERROR]  (GENERAL_ERROR) Something went wrong" in line for line in lines)
    assert any("[ACTION] HALT" in line for line in lines)


def test_app_error_custom_attributes():
    err = AppError(
        "File not found",
        "Check directory path",
        code="FILE_NOT_FOUND",
        actor=Actor.USER,
        retry=Retry.AFTER_FIX,
        target_files=["/tmp/test.txt"],
        fix="touch /tmp/test.txt",
        what_to_report="File is missing",
    )
    assert err.code == "FILE_NOT_FOUND"
    assert err.actor == Actor.USER
    assert err.mode == ActionMode.INTERACTION
    assert err.target_files == ["/tmp/test.txt"]

    mcp_text = err.render_mcp()
    assert "[ERROR]  (FILE_NOT_FOUND) File not found" in mcp_text
    assert "[ACTION] INTERACTION" in mcp_text
    assert "[TARGET] /tmp/test.txt" in mcp_text
    assert "[FIX]    touch /tmp/test.txt" in mcp_text
    assert "[REPORT] File is missing" in mcp_text
    assert "[DETAIL] Check directory path" in mcp_text


def test_serialization():
    err = AppError(
        "Invalid token",
        code="AUTH_FAILED",
        actor=Actor.USER,
        retry=Retry.AFTER_FIX,
    )
    dict_full = err.to_dict(include_advisory=True)
    assert dict_full["code"] == "AUTH_FAILED"
    assert dict_full["message"] == "Invalid token"
    assert "advisory" in dict_full
    assert dict_full["advisory"]["mode"] == "INTERACTION"
    assert dict_full["advisory"]["actor"] == "USER"

    dict_no_adv = err.to_dict(include_advisory=False)
    assert "advisory" not in dict_no_adv
