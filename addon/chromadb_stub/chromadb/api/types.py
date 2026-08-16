# chromadb.api.types stub
# Provides all types that crewai imports from chromadb.api.types

from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Union

# Type aliases
CollectionMetadata = Optional[Dict[str, Any]]
Include = List[str]
Where = Dict[str, Any]
WhereDocument = Dict[str, Any]
Loadable = Any
DataLoader = Optional[Callable]

# QueryResult type
QueryResult = Dict[str, Any]


class EmbeddingFunction(Protocol):
    """Protocol stub for chromadb EmbeddingFunction."""
    def __call__(self, input: Any) -> Any:
        ...
