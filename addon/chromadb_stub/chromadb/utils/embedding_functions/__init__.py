# chromadb.utils.embedding_functions stub


class EmbeddingFunction:
    """Base stub for embedding functions."""
    def __call__(self, input):
        raise NotImplementedError("chromadb is not installed — embedding functions unavailable")


class OpenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, *args, **kwargs):
        pass


class SentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, *args, **kwargs):
        pass


class DefaultEmbeddingFunction(EmbeddingFunction):
    def __init__(self, *args, **kwargs):
        pass
