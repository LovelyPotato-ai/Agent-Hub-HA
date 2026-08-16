# chromadb.api.types stub
# Provides all types that crewai imports from chromadb.api.types
# Based on the real chromadb api/types.py structure.

from typing import Any, Dict, List, Optional, Protocol, TypeVar, runtime_checkable

L = TypeVar("L")
T = TypeVar("T")

# Basic type aliases
URI = str
URIs = List[URI]
ID = str
IDs = List[ID]
Document = str
Documents = List[Document]
Metadata = Dict[str, Any]
Metadatas = List[Metadata]
CollectionMetadata = Optional[Dict[str, Any]]
Embedding = List[float]
Embeddings = List[Embedding]

# Where clause types
Where = Dict[str, Any]
WhereDocument = Dict[str, Any]

# Include type
Include = List[str]

# Loadable — used as DataLoader[Loadable]
Loadable = Any


# DataLoader must be a generic Protocol (subscriptable with [T])
# crewai uses DataLoader[Loadable] as a type annotation in TypedDict
@runtime_checkable
class DataLoader(Protocol[L]):
    """Generic DataLoader protocol — stub for chromadb.api.types.DataLoader."""
    def __call__(self, uris: URIs) -> L:
        ...


# EmbeddingFunction protocol
@runtime_checkable
class EmbeddingFunction(Protocol[T]):
    """Generic EmbeddingFunction protocol stub."""
    def __call__(self, input: Any) -> Any:
        ...


# QueryResult TypedDict stub
class QueryResult(Dict[str, Any]):
    pass


# GetResult TypedDict stub
class GetResult(Dict[str, Any]):
    pass
