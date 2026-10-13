import pytest
from app_tools.create_code.feature import register_router
from app_tools.create_code.naming import pluralize, to_snake_case


class TestPluralize:
    @pytest.mark.parametrize(
        "word,expected",
        [
            ("article", "articles"),  # default: + s
            ("category", "categories"),  # y -> ies
            ("bus", "buses"),  # s -> es
        ],
    )
    def test_pluralize_rules(self, word, expected):
        assert pluralize(word) == expected


class TestToSnakeCase:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Article", "article"),
            ("BlogPost", "blog_post"),
            ("HTTPServer", "http_server"),
            ("UserID", "user_id"),
        ],
    )
    def test_camel_to_snake(self, name, expected):
        assert to_snake_case(name) == expected


ROUTER_WITH_FEATURES = """\
from fastapi import APIRouter

from app.core.database.deps import get_session
from app.features.articles.api.v1 import router as v1_articles_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(v1_articles_router)

router = APIRouter()
router.include_router(v1_router)
"""

ROUTER_NO_FEATURES = """\
from fastapi import APIRouter

from app.core.database.deps import get_session

v1_router = APIRouter(prefix="/api/v1")

router = APIRouter()
router.include_router(v1_router)
"""


def _write_router(tmp_path, content):
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    router_path = app_dir / "router.py"
    router_path.write_text(content)
    return router_path


class TestUpdateRouter:
    def test_inserts_import_and_include(self, tmp_path):
        router_path = _write_router(tmp_path, ROUTER_WITH_FEATURES)

        register_router(tmp_path, "widgets", "app.features", dry_run=False)

        text = router_path.read_text()
        assert "from app.features.widgets.api.v1 import router as v1_widgets_router" in text
        assert "v1_router.include_router(v1_widgets_router)" in text

    def test_is_idempotent(self, tmp_path):
        router_path = _write_router(tmp_path, ROUTER_WITH_FEATURES)

        register_router(tmp_path, "widgets", "app.features", dry_run=False)
        register_router(tmp_path, "widgets", "app.features", dry_run=False)

        text = router_path.read_text()
        assert text.count("import router as v1_widgets_router") == 1
        assert text.count("v1_router.include_router(v1_widgets_router)") == 1

    def test_uses_fallback_anchors_when_no_feature_routes(self, tmp_path):
        router_path = _write_router(tmp_path, ROUTER_NO_FEATURES)

        register_router(tmp_path, "widgets", "app.features", dry_run=False)

        lines = router_path.read_text().splitlines()
        # import goes right after the get_session anchor
        get_session_idx = lines.index("from app.core.database.deps import get_session")
        assert lines[get_session_idx + 1] == "from app.features.widgets.api.v1 import router as v1_widgets_router"
        # include goes right before the top-level router.include_router(v1_router)
        include_idx = lines.index("router.include_router(v1_router)")
        assert lines[include_idx - 1] == "v1_router.include_router(v1_widgets_router)"

    def test_missing_router_file_is_a_warning(self, tmp_path):
        status, problem = register_router(tmp_path, "widgets", "app.features", dry_run=False)
        assert status == "skipped"
        assert problem is not None and problem.code == "APP_SCAFFOLD_ROUTER_NOT_UPDATED"

    def test_reports_whether_it_changed_the_router(self, tmp_path):
        _write_router(tmp_path, ROUTER_WITH_FEATURES)
        assert register_router(tmp_path, "widgets", "app.features", dry_run=False) == ("updated", None)
        assert register_router(tmp_path, "widgets", "app.features", dry_run=False) == ("unchanged", None)
