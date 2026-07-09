import re
from pathlib import Path
from string import Template

FEATURE_TEMPLATES_DIR = Path(__file__).parent / "templates" / "feature"


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


def update_router(plural_name: str, base_dir: Path, import_prefix: str):
    """
    Updates backend/app/router.py to include the new feature's router.
    """
    router_path = base_dir / "app/router.py"
    try:
        lines = router_path.read_text().splitlines()
        if not lines:
            print(f"Warning: {router_path} is empty. Skipping update.")
            return

        # Add import
        last_feature_import_index = -1
        for i, line in enumerate(lines):
            if line.startswith(f"from {import_prefix}."):
                last_feature_import_index = i

        import_statement = f"from {import_prefix}.{plural_name}.api.v1 import router as v1_{plural_name}_router"
        if any(import_statement in line for line in lines):
            print(f"  - Import statement already exists in {router_path}")
        elif last_feature_import_index != -1:
            lines.insert(last_feature_import_index + 1, import_statement)
        else:
            # Fallback if no feature imports are found
            after_line = "from app.core.database.deps import get_session"
            try:
                index = lines.index(after_line)
                lines.insert(index + 1, import_statement)
            except ValueError:
                lines.insert(0, import_statement)  # Add at the beginning if anchor not found

        # Add include_router
        last_include_router_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("v1_router.include_router("):
                last_include_router_index = i

        include_statement = f"v1_router.include_router(v1_{plural_name}_router)"
        if any(include_statement in line for line in lines):
            print(f"  - Router include statement already exists in {router_path}")
        elif last_include_router_index != -1:
            lines.insert(last_include_router_index + 1, include_statement)
        else:
            # Fallback for include router
            before_line = "router.include_router(v1_router)"
            try:
                index = lines.index(before_line)
                lines.insert(index, include_statement)
            except ValueError:
                lines.append(include_statement)  # Add at the end if anchor not found

        router_path.write_text("\n".join(lines) + "\n")
        print(f"  - Updated {router_path}")

    except FileNotFoundError:
        print(f"Warning: Could not find {router_path} to update.")
    except Exception as e:
        print(f"An error occurred while updating {router_path}: {e}")


def create_feature(
    name: str,
    plural: str | None,
    base_dir: Path | None = None,
    feature_prefix: str | None = None,
):
    """
    Generates a new CRUD feature.

    :param name: The name of the feature in CamelCase (e.g., "Article").
    :param plural: The plural name of the feature in snake_case.
    :param base_dir: The base directory of the project.
    :param feature_prefix: The prefix path for the feature directory (e.g., "app/features"). Defaults to "app/features".
    """
    if base_dir is None:
        base_dir = Path.cwd()

    class_name = name
    singular_name = to_snake_case(class_name)
    plural_name = plural if plural else pluralize(singular_name)
    prefix = feature_prefix if feature_prefix else "app/features"
    import_prefix = prefix.replace("/", ".")

    feature_dir = base_dir / f"{prefix}/{plural_name}"

    if feature_dir.exists():
        print(f"Error: Feature '{plural_name}' already exists at {feature_dir}.")
        return

    print(f"Creating feature '{class_name}' in '{feature_dir}'...")

    mapping = {
        "class_name": class_name,
        "singular_name": singular_name,
        "plural_name": plural_name,
        "import_prefix": import_prefix,
    }

    # Render every template under templates/feature/ into the feature directory,
    # mirroring its layout. That directory IS the feature skeleton: add or remove a
    # *.tmpl file to change what gets generated — no code change needed here.
    # Templates use string.Template ($placeholders), so literal braces in the
    # generated Python (e.g. route paths like "/{book_id}") need no escaping.
    for template_path in sorted(FEATURE_TEMPLATES_DIR.rglob("*.tmpl")):
        relative_output = template_path.relative_to(FEATURE_TEMPLATES_DIR).with_suffix("")
        content = Template(template_path.read_text()).substitute(mapping)

        output_path = feature_dir / relative_output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content.strip())
        print(f"  - Created {output_path}")

    print(f"\nFeature '{class_name}' created successfully!")
    update_router(plural_name, base_dir, import_prefix)

    print("\nNext steps:")
    print(f"1. Review the generated files in '{feature_dir}'.")
    print("2. Add the new model to 'alembic' and run migrations.")
