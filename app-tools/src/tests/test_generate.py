import importlib
import json
import subprocess
import sys
from pathlib import Path

from app_tools.create_code.create_feature import create_feature

# app-common workspace root: .../app-common/app-tools/src/tests/test_generate.py
REPO_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_FILES = [
    "__init__.py",
    "models.py",
    "schemas.py",
    "repos.py",
    "services.py",
    "usecases/__init__.py",
    "usecases/crud.py",
    "api/__init__.py",
    "api/v1.py",
]


def _generate(base_dir: Path, name: str = "Widget", prefix: str = "genpkg") -> Path:
    create_feature(name=name, plural=None, base_dir=base_dir, feature_prefix=prefix)
    (base_dir / prefix / "__init__.py").write_text("")
    return base_dir / prefix / "widgets"


def test_creates_expected_files(tmp_path):
    feature_dir = _generate(tmp_path)
    for rel in EXPECTED_FILES:
        assert (feature_dir / rel).is_file(), f"generated feature missing {rel}"


def test_generated_feature_imports_against_current_layer_base(tmp_path):
    """Golden test: the generated code must import cleanly against the CURRENT
    app-layer-base. Catches renamed/moved symbols, generic-arity changes
    (e.g. BaseRepository[...] param count), and syntax errors at import time."""
    _generate(tmp_path)

    sys.path.insert(0, str(tmp_path))
    try:
        v1 = importlib.import_module("genpkg.widgets.api.v1")

        paths = {route.path for route in v1.router.routes}
        assert paths == {"/widgets", "/widgets/{widget_id}"}
        # 6 CRUD endpoints: create, list, get, patch, put, delete
        assert len(v1.router.routes) == 6
    finally:
        sys.path.remove(str(tmp_path))
        for mod in [m for m in sys.modules if m == "genpkg" or m.startswith("genpkg.")]:
            del sys.modules[mod]


def test_generated_feature_typechecks_with_pyright(tmp_path):
    """Golden test: the generated code must pass pyright against the CURRENT
    app-layer-base. Catches type-level drift the import test cannot (e.g. a mixin
    property whose type changed)."""
    feature_dir = _generate(tmp_path)

    config = {
        "typeCheckingMode": "basic",
        "extraPaths": [str(REPO_ROOT / "app-layer-base" / "src"), "."],
        "venvPath": str(REPO_ROOT),
        "venv": ".venv",
        "include": ["genpkg"],
    }
    (tmp_path / "pyrightconfig.json").write_text(json.dumps(config))

    result = subprocess.run(
        ["uv", "run", "pyright", "--project", str(tmp_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"pyright reported issues on generated code:\n{result.stdout}\n{result.stderr}"
    assert feature_dir.exists()
