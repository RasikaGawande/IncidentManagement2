"""Environment-based application settings."""
from dataclasses import dataclass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True, slots=True)
class Settings:
    ollama_base_url: str
    ollama_chat_model: str
    ollama_embedding_model: str
    similarity_threshold: float
    data_directory: Path
    github_repository: str | None
    github_token: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
            ollama_chat_model=os.getenv("OLLAMA_CHAT_MODEL", "mistral:latest"),
            ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.85")),
            data_directory=Path(os.getenv("DATA_DIRECTORY", PROJECT_ROOT / "data")),
            github_repository=os.getenv("GITHUB_REPOSITORY"),
            github_token=os.getenv("GITHUB_TOKEN"),
        )
