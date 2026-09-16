"""Keep complete logs on disk and return bounded output to the caller."""

from __future__ import annotations

import contextlib
import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import click

from app_tools.runner.planning import Step

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
MAX_OUTPUT = 16_000


def execute(step: Step, log_dir: Path, raw: bool = False) -> int:
    started = time.monotonic()
    with tempfile.NamedTemporaryFile(prefix="command-", suffix=".log", dir=log_dir, delete=False) as log:
        log_path = Path(log.name)
        try:
            process = subprocess.Popen(
                step.argv, cwd=step.cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )
        except OSError as error:
            log.write(str(error).encode())
            code = 127 if isinstance(error, FileNotFoundError) else 126
        else:
            try:
                code = process.wait()
            except KeyboardInterrupt:
                # npm/uv often have children; stop the entire command group on cancellation.
                if os.name == "posix":
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait()
                click.echo(f"INTERRUPTED {step.label}; log: {log_path}", err=True)
                raise
            if code < 0:
                code = 128 - code
    if raw:
        with log_path.open(errors="replace") as stream:
            while chunk := stream.read(8192):
                click.echo(chunk, nl=False)
    elif code:
        size = log_path.stat().st_size
        with log_path.open("rb") as stream:
            if size <= MAX_OUTPUT:
                output = stream.read().decode(errors="replace")
            else:
                head = stream.read(MAX_OUTPUT // 2).decode(errors="replace")
                stream.seek(-MAX_OUTPUT // 2, 2)
                tail = stream.read().decode(errors="replace")
                output = f"{head}\n... output omitted; full log: {log_path} ...\n{tail}"
        click.echo(ANSI.sub("", output), nl=not output.endswith("\n"))
    status = "PASS" if code == 0 else f"FAIL({code})"
    click.echo(f"{status} {step.label} [{step.cwd}] ({time.monotonic() - started:.1f}s) log: {log_path}")
    return code
