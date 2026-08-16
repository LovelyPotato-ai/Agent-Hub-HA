# chromadb stub — satisfies crewai imports without installing real chromadb
# crewai imports chromadb at startup even when memory/RAG features are not used.
# This stub provides no-op implementations of the required classes.

__version__ = "1.1.0"


class Client:
    def __init__(self, *args, **kwargs):
        pass


class EphemeralClient:
    def __init__(self, *args, **kwargs):
        pass


class PersistentClient:
    def __init__(self, *args, **kwargs):
        pass


class HttpClient:
    def __init__(self, *args, **kwargs):
        pass


def client(*args, **kwargs):
    return Client()
