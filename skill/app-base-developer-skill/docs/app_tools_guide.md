# app-tools Developer Guide

This guide provides expert guidance for utilizing the `app-tools` CLI to streamline development workflows for FastAPI applications built on the modular workspace packages. It focuses on generating new feature modules and understanding the conventions used by the `app-tools` CLI.

## Core Philosophy & Usage

The `app-tools` CLI is designed to accelerate development by generating boilerplate code for common patterns, adhering to the architectural guidelines of the `app-layer-base` package.

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

### Utility Commands: Environment Specification

The `app-tools` CLI also provides utility commands to help inspect the environment configuration for `app-base` applications.

#### `app-tools get-env-spec`

This command lists the environment variables and their specifications for different `app-base` configurations. It's useful for understanding what environment variables are expected and their types/defaults.

**Command:**
```bash
app-tools get-env-spec --type <config_type>
```

**Options:**
-   `--type`: **(Required)** The type of configuration to inspect.
    -   Choices include: `auth`, `app`, `file_storage`, `file_storage_none`, `file_storage_local`, `file_storage_s3`, `vector_db`, `vector_db_none`, `vector_db_qdrant`.

**Example:**

To see the environment variables for `file_storage_s3` configuration:

```bash
app-tools get-env-spec --type file_storage_s3
```

**Output Example:**

```
--- Environment Variables for File Storage S3 ---
APP_BASE_S3_ACCESS_KEY_ID: Type: SecretStr. Default: '<hidden>'
APP_BASE_S3_BUCKET_NAME: Type: str. Default: None
APP_BASE_S3_ENDPOINT_URL: Type: str. Default: None
APP_BASE_S3_REGION_NAME: Type: str. Default: None
APP_BASE_S3_SECRET_ACCESS_KEY: Type: SecretStr. Default: '<hidden>'
APP_BASE_FILE_STORAGE_PROVIDER: Type: str. Default: 's3'
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
-   `app-tools/src/app_tools/commands/get_env_spec.py`: The core logic for listing environment variable specifications.
-   `app-tools/src/app_tools/utils/config.py`: Utility functions, including how `app-tools` determines the project root.