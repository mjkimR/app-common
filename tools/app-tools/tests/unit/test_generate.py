import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from app_tools.create_code.create_feature import create_feature

# app-common workspace root: .../app-common/tools/app-tools/tests/unit/test_generate.py
REPO_ROOT = Path(__file__).resolve().parents[4]

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
        "extraPaths": [str(REPO_ROOT / "packages" / "base" / "app-layer-base" / "src"), "."],
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


def test_feature_already_exists_raises_app_error(tmp_path):
    from app_tools.create_code.create_feature import FeatureAlreadyExistsError

    _generate(tmp_path, name="Widget", prefix="genpkg")
    with pytest.raises(FeatureAlreadyExistsError) as exc_info:
        create_feature(name="Widget", plural=None, base_dir=tmp_path, feature_prefix="genpkg")

    err = exc_info.value
    assert err.code == "FEATURE_ALREADY_EXISTS"
    assert "rm -rf" in (err.fix or "")
    assert "[ERROR]  (FEATURE_ALREADY_EXISTS)" in "\n".join(err.lines())


def test_creates_web_feature_expected_files(tmp_path):
    from app_tools.create_code.create_web_feature import create_web_feature

    feature_dir = create_web_feature(name="Widget", plural=None, base_dir=tmp_path, feature_prefix="src/lib/features")
    assert (feature_dir / "widget.svelte.ts").is_file()
    assert (feature_dir / "WidgetView.svelte").is_file()
    assert (feature_dir / "components" / "WidgetDialog.svelte").is_file()
    assert (feature_dir / "index.ts").is_file()

    # Verify content placeholders replaced properly
    state_content = (feature_dir / "widget.svelte.ts").read_text()
    assert "export class WidgetState" in state_content
    assert "$state<WidgetItem[]>" in state_content
    assert "components['schemas']['WidgetRead']" in state_content
    assert "Array.isArray(data) ? data : ((data as any)?.items ?? [])" in state_content
    assert "/api/v1/widgets" in state_content

    index_content = (feature_dir / "index.ts").read_text()
    assert "export { default as WidgetView } from './WidgetView.svelte';" in index_content


def test_web_feature_already_exists_raises_app_error(tmp_path):
    from app_tools.create_code.create_web_feature import WebFeatureAlreadyExistsError, create_web_feature

    create_web_feature(name="Widget", plural=None, base_dir=tmp_path, feature_prefix="src/lib/features")
    with pytest.raises(WebFeatureAlreadyExistsError) as exc_info:
        create_web_feature(name="Widget", plural=None, base_dir=tmp_path, feature_prefix="src/lib/features")

    err = exc_info.value
    assert err.code == "WEB_FEATURE_ALREADY_EXISTS"
    assert "rm -rf" in (err.fix or "")
