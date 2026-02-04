---
name: app-tools-developer
description: Expert assistant for generating boilerplate code and managing project structure
  using the `app-tools` CLI. Specializes in automating the creation of new features
  (models, schemas, repos, services, usecases, API endpoints) for `app-base` based
  FastAPI projects.
---
# app-tools Developer Skill

This skill provides expert guidance for utilizing the `app-tools` CLI to streamline development workflows, particularly for `app-base` based FastAPI applications. It focuses on generating new feature modules and understanding the conventions used by the `app-tools` CLI.

## Core Philosophy & Usage

The `app-tools` CLI is designed to accelerate development by generating boilerplate code for common patterns, adhering to the architectural guidelines of the `app-base` package.

### Primary Workflow: Creating a New Feature

The main command allows you to generate a complete new CRUD (Create, Read, Update, Delete) feature module, including SQLAlchemy models, Pydantic schemas, repositories, services, use cases, and API routers.

#### `app-tools create-code feature`

This command generates a new feature module with all necessary boilerplate files.

**Command:**
```bash
app-tools create-code feature --name <FeatureName> [--plural <plural_name>]
```

**Options:**
-   `--name`: **(Required)** The name of the feature in `CamelCase` (e.g., `Article`, `UserProfile`). This will be used to name classes and generate singular forms.
-   `--plural`: **(Optional)** The plural name of the feature in `snake_case` (e.g., `articles`, `user_profiles`). If omitted, it will be automatically generated (e.g., `Article` -> `articles`). This is used for directory names, table names, and API route prefixes.

**Example:**

To create a new feature named `Task`:

```bash
app-tools create-code feature --name Task
```

This will generate a directory structure and files similar to this (assuming `base_dir` is the project root):

```
app/features/tasks/
├── __init__.py
├── models.py       # SQLAlchemy model for Task
├── schemas.py      # Pydantic schemas (TaskCreate, TaskUpdate, TaskRead)
├── repos.py        # TaskRepository
├── services.py     # TaskService
├── usecases/
│   ├── __init__.py
│   └── crud.py     # CRUD UseCases (GetTaskUseCase, CreateTaskUseCase, etc.)
└── api/
    ├── __init__.py
    └── v1.py       # FastAPI router with CRUD endpoints for /tasks
```

Additionally, it will attempt to update the `app/router.py` file to include the newly generated API router.

**Output:**

The CLI will provide feedback on the files created and, if applicable, indicate that the main router has been updated.

```
Creating feature 'Task' in '/Users/mj/workspace/playground/app-common/app/features/tasks'...
  - Created app/features/tasks/__init__.py
  - Created app/features/tasks/models.py
  - Created app/features/tasks/schemas.py
  - Created app/features/tasks/repos.py
  - Created app/features/tasks/services.py
  - Created app/features/tasks/usecases/__init__.py
  - Created app/features/tasks/usecases/crud.py
  - Created app/features/tasks/api/__init__.py
  - Created app/features/tasks/api/v1.py

Feature 'Task' created successfully!
  - Updated app/router.py

Next steps:
1. Review the generated files in 'app/features/tasks'.
2. Add the new model to 'alembic' and run migrations.
```

## Next Steps after Feature Generation

After using `create-code feature`, you should:
1.  **Review and Customize**: Examine the generated files. They provide a basic CRUD structure, but you'll likely need to customize `models.py`, `schemas.py`, `services.py` (to add business logic via hooks), and `api/v1.py` (to adjust dependencies, add authorization, etc.) to fit your specific requirements.
2.  **Database Migrations**: If you've modified `models.py`, you'll need to update your database schema using `alembic` (or your chosen migration tool).
    -   Generate a new migration script.
    -   Apply the migration.
3.  **Implement Business Logic**: Add specific business rules and validations within the service hooks (`_context_*`, `_prepare_*`, `_post_*` methods) in `services.py`.
4.  **Testing**: Write unit and integration tests for your new feature.

## Available Resources

When performing tasks related to `app-tools`, you may want to refer to these files:

-   `app-tools/README.md`: High-level overview and basic usage.
-   `app-tools/src/app_tools/cli.py`: The main CLI entry point.
-   `app-tools/src/app_tools/create_code/create_feature.py`: The core logic for generating feature files.
-   `app-tools/src/app_tools/create_code/__init__.py`: The `create-code` command definition.
-   `app-tools/src/app_tools/utils/config.py`: Utility functions, including how `app-tools` determines the project root.