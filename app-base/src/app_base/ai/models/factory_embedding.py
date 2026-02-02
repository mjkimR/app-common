import logging
from typing import TYPE_CHECKING

from app_base.ai.models.schemas import AIModelItem

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings


class EmbeddingFactory:
    def create_model(self, config: AIModelItem) -> "Embeddings":
        provider = config.provider
        args = config.args

        try:
            match provider:
                case "openai-compatible" | "openai":
                    from langchain_openai import OpenAIEmbeddings  # type: ignore

                    return OpenAIEmbeddings(**args)
                case "google":
                    from langchain_google_genai import GoogleGenerativeAIEmbeddings  # type: ignore

                    if "api_key" in args:
                        args["google_api_key"] = args.pop("api_key")
                    return GoogleGenerativeAIEmbeddings(**args)
                case _:
                    raise ValueError(f"Unsupported Embedding provider: {provider}")
        except ImportError as e:
            raise ImportError(
                f"Failed to import dependencies for provider '{provider}'. Please install the required package."
            ) from e

    def get_dimension(self, config: "AIModelItem") -> int:
        """
        Returns the vector size.
        1. If defined in config (yaml), returns it.
        2. If not, loads the actual model and calculates/returns it.
        """
        # 1. Check YAML config first
        if config.dimension is not None:
            return config.dimension

        # 2. Calculate at runtime
        dimension = self._calculate_dimension_dynamically(config)
        config.dimension = dimension  # cache for future use
        return dimension

    def _calculate_dimension_dynamically(self, config: "AIModelItem") -> int:
        """Actually performs embedding to check the dimension"""
        try:
            model = self.create_model(config)
            # Test with a very short word
            dummy_vector = model.embed_query("test")
            logging.info(f"Determined embedding dimension for '{config.name}': {len(dummy_vector)}")
            return len(dummy_vector)
        except Exception as e:
            raise RuntimeError(f"Failed to determine embedding dimension for '{config.name}': {e}") from e
