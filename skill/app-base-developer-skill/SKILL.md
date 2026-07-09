---
name: app-base-developer-skill
description: Expert assistant for developing FastAPI applications using the modular workspace
  packages and `app-tools` CLI. Specializes in layered architecture, code generation,
  and implementing business logic with service hooks.
---
# App Base Developer Skill

This skill is an expert assistant for building FastAPI applications using our common modular workspace packages and the `app-tools` code generation CLI.

It can guide you through creating new features, implementing business logic, understanding the decoupled layered architecture, and managing your application's configuration.

## Task Router

-   **If you want to create a new CRUD feature from scratch...**
    -   Use the `app-tools` code generator. See the [Quick Reference](#quick-reference) for the command.
    -   For a detailed walkthrough, see the [app-tools Developer Guide](./docs/app_tools_guide.md).

-   **If you want to understand our layered architecture (Services, Repositories, UseCases)...**
    -   Read the [app-base Developer Guide](./docs/app_base_guide.md#core-philosophy--architecture).

-   **If you want to add business logic (e.g., uniqueness checks, user awareness)...**
    -   Use Service Hooks.
    -   See the guide on [Using Service Hooks](./docs/app_base_guide.md#using-service-hooks).

-   **If you want to interact with File Storage, a Vector Store, an HTTP Client, or an AI Model...**
    -   Each adapter is a standalone package; its canonical reference is its own README. See the [Adapter Module Reference](./docs/reference_adapter.md) for the index.

-   **If you need to check environment variables for configuration...**
    -   Use the `app-tools get-env-spec` command.
    -   See the [app-tools Developer Guide](./docs/app_tools_guide.md#utility-commands-environment-specification).

## Keyword Router

-   **`app-layer-base`**: Refers to the core domain framework. See the [app-base Developer Guide](./docs/app_base_guide.md).
-   **`app-tools`**: Refers to the CLI for code generation. See the [app-tools Developer Guide](./docs/app_tools_guide.md).
-   **Code Scaffolding**: See [Creating a New Feature](./docs/app_tools_guide.md#primary-workflow-creating-a-new-feature).
-   **Service, Repository, UseCase, Model, Schema**: Core layers of the architecture. See the [app-base Developer Guide](./docs/app_base_guide.md#core-philosophy--architecture).
-   **Hooks, Business Logic**: Customized service flows. See [Using Service Hooks](./docs/app_base_guide.md#using-service-hooks).
-   **Configuration, Settings**: See [Managing Application Configuration](./docs/app_base_guide.md#managing-application-configuration-environment-variables).
-   **Adapters (File Storage, Vector Store, HTTP Client)**: See the [Adapter Module Reference](./docs/reference_adapter.md).

## Reference Documentation

For detailed API-level information on each workspace module's classes and configurations:

-   **[Base Module Reference](./docs/reference_base.md)**: Models (Mixins), Repositories, Services (Hooks), UseCases, Dependencies, Exceptions inside `app-layer-base`.
-   **[Adapter Module Reference](./docs/reference_adapter.md)**: File Storage (S3, Local), Vector Store (Qdrant), HTTP Client — each links to its standalone package README.
-   **[Core, Config, AI & Utils Reference](./docs/reference_core_config.md)**: Middlewares, Pydantic Settings, LangChain AI Factories, Time/Type Utilities.

## Quick Reference

### Code Generation

To generate a new feature (e.g., `Book`):
```bash
uv run app-tools create-code feature --name Book
```

### Get Environment Spec

To list required environment variables for a specific configuration (e.g., `file_storage_s3`):
```bash
uv run app-tools get-env-spec --type file_storage_s3
```
