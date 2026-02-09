---
name: app-base-developer-skill
description: Expert assistant for developing FastAPI applications using the `app-base`
  library and `app-tools` CLI. Specializes in layered architecture, code generation,
  and implementing business logic with service hooks.
---
# App Base Developer Skill

This skill is an expert assistant for building FastAPI applications using the `app-base` common personal library and the `app-tools` code generation CLI.

It can guide you through creating new features, implementing business logic, understanding the architecture, and managing your application's configuration.

## Task Router

-   **If you want to create a new CRUD feature from scratch...**
    -   Use the `app-tools` code generator. See the [Quick Reference](#quick-reference) for the command.
    -   For a detailed walkthrough, see the [app-tools Developer Guide](./docs/app_tools_guide.md).

-   **If you want to understand the `app-base` architecture (Services, Repositories, UseCases)...**
    -   Read the [app-base Developer Guide](./docs/app_base_guide.md#core-philosophy--architecture).

-   **If you want to add business logic (e.g., uniqueness checks, user awareness)...**
    -   Use Service Hooks.
    -   See the guide on [Using Service Hooks](./docs/app_base_guide.md#using-service-hooks).

-   **If you want to interact with File Storage (S3, local), a Vector Store, or an AI Model...**
    -   See the guide on [Using Adapters & AI](./docs/app_base_guide.md#using-adapters--ai).

-   **If you need to check environment variables for configuration...**
    -   Use the `app-tools get-env-spec` command.
    -   See the [app-tools Developer Guide](./docs/app_tools_guide.md#utility-commands-environment-specification).

## Keyword Router

-   **`app-base`**: Refers to the core application library. See the [app-base Developer Guide](./docs/app_base_guide.md).
-   **`app-tools`**: Refers to the CLI for code generation. See the [app-tools Developer Guide](./docs/app_tools_guide.md).
-   **Code Generation, Boilerplate, Scaffolding**: See the guide for [Creating a New Feature](./docs/app_tools_guide.md#primary-workflow-creating-a-new-feature).
-   **CRUD**: Stands for Create, Read, Update, Delete. The base pattern for new features. See the [app-base guide](./docs/app_base_guide.md#primary-workflow-creating-a-new-crud-endpoint) or the [app-tools guide](./docs/app_tools_guide.md#primary-workflow-creating-a-new-feature).
-   **Service, Repository, UseCase, Model, Schema**: These are the core layers of the `app-base` architecture. See the [app-base Developer Guide](./docs/app_base_guide.md#core-philosophy--architecture).
-   **Hooks, Business Logic**: Refers to customizing service behavior. See [Using Service Hooks](./docs/app_base_guide.md#using-service-hooks).
-   **Configuration, Environment Variables, Settings**: See [Managing Application Configuration](./docs/app_base_guide.md#managing-application-configuration-environment-variables).
-   **File Storage, S3, Vector Store, AI, LLM**: See [Using Adapters & AI](./docs/app_base_guide.md#using-adapters--ai).

## Quick Reference

### Code Generation

To generate a new feature (e.g., `Book`):
```bash
app-tools create-code feature --name Book
```
> See the [app-tools Developer Guide](./docs/app_tools_guide.md) for more details.

### Get Environment Spec

To list required environment variables for a specific configuration (e.g., `file_storage_s3`):
```bash
app-tools get-env-spec --type file_storage_s3
```
> See the [app-tools Developer Guide](./docs/app_tools_guide.md#utility-commands-environment-specification) for all available types.
