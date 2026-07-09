# app-ai-catalog

A YAML-driven catalog over a [LiteLLM](https://github.com/BerriAI/litellm) `Router` that gives an application one typed entry point for LLM completion, embeddings and image generation — plus a LangChain `Embeddings` adapter. Models, routes, aliases and collections are declared in a `catalog.yml`.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-ai-catalog"
```

## Configuration

The catalog is defined in a `catalog.yml` at your project root (or a path you pass to `AIClient`). Values support `${ENV_VAR}` and `${ENV_VAR:-default}` substitution, so secrets stay in the environment:

```yaml
# catalog.yml
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

# Optional: aliases, routes (load-balanced deployments) and collections
aliases:
  - name: default-llm
    type: llm
    target: gpt-4o
```

## Usage

Wire the lifespan into your FastAPI app, then resolve the singleton client:

```python
from fastapi import FastAPI
from app_ai_catalog import get_ai_client, lifespan_ai_client

app = FastAPI(lifespan=lifespan_ai_client)


async def summarize(text: str) -> str:
    client = get_ai_client()
    resp = await client.acompletion("default-llm", messages=[{"role": "user", "content": text}])
    return resp.choices[0].message.content


async def embed(text: str) -> list[float]:
    client = get_ai_client()
    return await client.aembedding("text-embedding-3-small", input=text)
```

For LangChain integrations, `client.get_embedding("text-embedding-3-small")` returns an `Embeddings` object, and `client.get_embedding_dimension(name)` resolves the vector size (used by [`app-vector-store`](../app-vector-store/README.md)).

## Public API

- `AIClient` — facade: `completion`/`acompletion`, `embedding`/`aembedding`, `image_generation`/`aimage_generation`, `get_embedding`, `get_embedding_dimension`, `reload`
- `get_ai_client`, `setup_ai_client`, `set_ai_client`, `reload_ai_client`, `close_ai_client` — singleton lifecycle
- `lifespan_ai_client` — FastAPI lifespan
- `LiteLLMEmbeddingsAdapter` — LangChain `Embeddings` implementation

> AI/RAG features that are still being iterated (prompt registry, agent/graph orchestration, retrieval) live in a separate proving-ground project and are absorbed here only once stable; this package is intentionally the stable model-access substrate.

## See also

- [Core, Config, AI & Utils Reference](../skill/app-base-developer-skill/docs/reference_core_config.md) — AI factory usage in context.
- [Architecture & Service Hooks Guide](../skill/app-base-developer-skill/docs/app_base_guide.md) — how this package fits the layered app.
