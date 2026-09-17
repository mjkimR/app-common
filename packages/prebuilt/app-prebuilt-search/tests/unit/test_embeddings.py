from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from app_prebuilt_search import FastEmbedProvider


async def test_lazy_provider_separates_query_and_passage(monkeypatch):
    model = Mock()
    model.passage_embed.return_value = [np.array([1.0, 0.0])]
    model.query_embed.return_value = [np.array([0.0, 1.0])]
    constructor = Mock(return_value=model)
    loader = Mock(return_value=SimpleNamespace(TextEmbedding=constructor))
    monkeypatch.setattr("app_prebuilt_search.embeddings.importlib.import_module", loader)
    provider = FastEmbedProvider(model_name="example", dimension=2, embedding_id="pinned-v1")
    loader.assert_not_called()
    assert await provider.embed_documents([]) == []
    loader.assert_not_called()
    assert await provider.embed_documents(["doc"]) == [[1.0, 0.0]]
    assert await provider.embed_query("query") == [0.0, 1.0]
    constructor.assert_called_once()
    model.passage_embed.assert_called_once_with(["doc"])
    model.query_embed.assert_called_once_with(["query"])
