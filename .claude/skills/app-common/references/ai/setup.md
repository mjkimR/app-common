# app-ai-catalog Setup & Configuration

## Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-ai-catalog"
```

## Configuration (`catalog.yml`)

Place `catalog.yml` in your project root (or provide custom path to `AIClient`).
Values support environment variable substitution with `${ENV_VAR}` or `${ENV_VAR:-default}`:

```yaml
models:
  - name: gpt-4o
    type: llm
    litellm_params:
      model: openai/gpt-4o
      api_key: ${OPENAI_API_KEY}

  - name: text-embedding-3-small
    type: text-embedding
    litellm_params:
      model: openai/text-embedding-3-small
      api_key: ${OPENAI_API_KEY}
    model_info:
      dimension: 1536

aliases:
  - name: default-llm
    type: llm
    target: gpt-4o
```
