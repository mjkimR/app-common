# app-common

A personal monorepo containing common modules and CLI tools designed to accelerate and standardize development across various FastAPI-based projects.

## Core Packages

This repository consists of two main packages:

### 1. [app-base](./app-base/README.md)
The core library containing common modules and utilities for application development.
- **Features**: CRUD service/repository base classes, layered architecture patterns, adapters (S3, Qdrant, AI via LangChain), and configuration management.

### 2. [app-tools](./app-tools/README.md)
A CLI utility to enhance developer productivity.
- **Features**: Scaffolding and boilerplate code generation tailored for the `app-base` architecture (e.g., automatically generating Models, Repositories, Services, and Controllers).

## Architecture Overview

Projects built with these tools follow a strict layered architecture to ensure maintainability and clean separation of concerns:

- **API/Router**: Handles HTTP requests, manages dependency injection, and delegates execution to UseCases.
- **UseCase**: Orchestrates workflows and manages database transaction boundaries.
- **Service**: Contains the core business logic. Built with a mixin-based approach and customized via **Service Hooks** (e.g., `UserAwareHooksMixin`).
- **Repository**: Provides a generic data access layer (CRUD) for SQLAlchemy models.
- **Model/Schema**: Defines database structures (SQLAlchemy) and data transfer objects (Pydantic).

## Quick Installation

You can install each package directly from GitHub using `uv`.

```bash
# Install the core app-base library
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-base"

# Install the app-tools CLI (recommended for development only)
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-tools" --dev
```

## Documentation & Developer Skills

Comprehensive architecture guides, API references, and development workflows are maintained as **Developer Skills**. These serve as a unified knowledge base for both human developers and AI coding assistants.

- **[app-base Developer Skill & Docs](./skill/app-base-developer-skill/SKILL.md)**: Contains the architectural philosophy, guides on using Service Hooks, and detailed component references.
- **[app-tools Developer Skill](./skill/app-tools-developer-skill/SKILL.md)**: Contains guides on code generation and viewing environment specifications via the CLI.
