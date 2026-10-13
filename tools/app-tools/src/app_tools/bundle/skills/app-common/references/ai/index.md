# app-ai-catalog

Typed client interface for LLM completions, embeddings, and LangChain adapters driven by a centralized `catalog.yml`.

> For package installation and `catalog.yml` configuration schema, see [setup.md](./setup.md).

## Usage

```python
from app_ai_catalog import AIClient

ai = AIClient()  # loads catalog.yml from project root

# Chat completion via LiteLLM router
response = await ai.chat_completion(
    model="default-llm",
    messages=[{"role": "user", "content": "Hello!"}],
)

# LangChain Embeddings adapter (used by vector stores or RAG chains)
embeddings = ai.get_langchain_embeddings("text-embedding-3-small")
```
