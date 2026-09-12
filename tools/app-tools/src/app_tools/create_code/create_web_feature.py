import re
from pathlib import Path
from string import Template

from app_error import Actor, AppError, Retry

WEB_FEATURE_TEMPLATES_DIR = Path(__file__).parent / "templates" / "web_feature"


class WebFeatureAlreadyExistsError(AppError):
    code = "WEB_FEATURE_ALREADY_EXISTS"
    actor = Actor.USER
    retry = Retry.AFTER_FIX

    def __init__(self, feature_name: str, feature_dir: Path) -> None:
        super().__init__(
            f"Web Feature '{feature_name}' already exists at {feature_dir}.",
            target_files=[str(feature_dir)],
            fix=f"rm -rf {feature_dir}",
            what_to_report=f"Web Feature '{feature_name}' already exists.",
        )


def pluralize(name: str) -> str:
    """A simple pluralizer."""
    if name.endswith("y"):
        return name[:-1] + "ies"
    if name.endswith("s"):
        return name + "es"
    return name + "s"


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def detect_default_prefix(base_dir: Path) -> str:
    """Detects whether running inside web/ or root."""
    if (base_dir / "src/lib").exists() and (base_dir / "package.json").exists():
        return "src/lib/features"
    if (base_dir / "web/src/lib").exists():
        return "web/src/lib/features"
    return "src/lib/features"


def create_web_feature(
    name: str,
    plural: str | None = None,
    base_dir: Path | None = None,
    feature_prefix: str | None = None,
) -> Path:
    """
    Generates a new Svelte 5 web feature module.

    :param name: The name of the feature in CamelCase (e.g., "Project").
    :param plural: The plural name of the feature in snake_case (e.g., "projects").
    :param base_dir: Base directory of the project.
    :param feature_prefix: Target directory prefix. Defaults to auto-detected src/lib/features.
    """
    if base_dir is None:
        base_dir = Path.cwd()

    class_name = name
    singular_name = to_snake_case(class_name)
    plural_name = plural if plural else pluralize(singular_name)
    prefix = feature_prefix if feature_prefix else detect_default_prefix(base_dir)

    feature_dir = base_dir / f"{prefix}/{singular_name}"

    if feature_dir.exists():
        raise WebFeatureAlreadyExistsError(singular_name, feature_dir)

    print(f"Creating Svelte 5 web feature '{class_name}' in '{feature_dir}'...")

    mapping = {
        "class_name": class_name,
        "singular_name": singular_name,
        "plural_name": plural_name,
    }

    for template_path in sorted(WEB_FEATURE_TEMPLATES_DIR.rglob("*.tmpl")):
        relative_path_str = str(template_path.relative_to(WEB_FEATURE_TEMPLATES_DIR).with_suffix(""))
        # Replace variable tokens in filenames
        target_relative_str = relative_path_str.replace("__singular_name__", singular_name).replace(
            "__class_name__", class_name
        )

        content = Template(template_path.read_text()).substitute(mapping)
        output_path = feature_dir / target_relative_str
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content.strip() + "\n")
        print(f"  - Created {output_path}")

    print(f"\nWeb feature '{class_name}' created successfully!")
    print("\nNext steps:")
    print(f"1. Review generated state and components in '{feature_dir}'.")
    print(f"2. Mount <{class_name}View /> inside your desired route (e.g. 'src/routes/{plural_name}/+page.svelte').")
    return feature_dir
