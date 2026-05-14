# app-base Documentation

Welcome to the `app-base` documentation! This directory contains detailed guides for the `app-base` package, separated by module.

`app-base` is a foundational package providing a layered architecture (Repository, Service, UseCase), SQLAlchemy Mixins, various Data/Storage Adapters, and AI integration factories.

## Table of Contents

1. [Base Module (`app_base/base`)](./01-base-module.md)
   - Models (Mixins), Repositories, Services (Hooks), UseCases, Dependencies, Exceptions.
2. [Adapter Module (`app_base/adapter`)](./02-adapter-module.md)
   - Event Broker, File Storage (S3, Local), NoSQL Database (MongoDB, Firestore), Vector Store (Qdrant), HTTP Client.
3. [Core, Config, AI & Utils Modules (`app_base/core`, `config`, `ai`, `utils`)](./03-core-config-ai-utils-module.md)
   - Middlewares, Pydantic Settings, LangChain AI Factories, Time/Type Utilities.