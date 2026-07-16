"""In-memory incident vectors and cosine-similarity search."""
from dataclasses import dataclass
from math import sqrt
from domain.models import Incident, SimilarIncident
from services.ollama import OllamaClient

@dataclass(frozen=True, slots=True)
class VectorizedIncident:
    incident: Incident
    vector: list[float]

class InMemoryIncidentVectorStore:
    def __init__(self, ollama: OllamaClient, entries: list[VectorizedIncident]) -> None:
        self._ollama, self._entries = ollama, entries
    @classmethod
    async def build(cls, incidents: list[Incident], ollama: OllamaClient) -> "InMemoryIncidentVectorStore":
        entries = [VectorizedIncident(incident, await ollama.embed(incident.searchable_text())) for incident in incidents]
        return cls(ollama, entries)
    async def search(self, incident: Incident, limit: int) -> list[SimilarIncident]:
        query_vector = await self._ollama.embed(incident.searchable_text())
        matches = [SimilarIncident(incident=entry.incident, similarity=cosine_similarity(query_vector, entry.vector)) for entry in self._entries]
        return sorted(matches, key=lambda match: match.similarity, reverse=True)[:limit]
    @property
    def count(self) -> int:
        return len(self._entries)

def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions do not match.")
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    if denominator == 0:
        raise ValueError("Cannot compare a zero-length embedding.")
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator
