"""Small, explicit HTTP client for Ollama's local API."""

import httpx


class OllamaClient:
    def __init__(self, base_url: str, embedding_model: str, chat_model: str) -> None:
        self._base_url = base_url
        self._embedding_model = embedding_model
        self._chat_model = chat_model

    async def embed(self, text: str) -> list[float]:
        response = await self._request(
            "/api/embed", {"model": self._embedding_model, "input": text}, timeout=90
        )
        embeddings = response.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings or not isinstance(embeddings[0], list):
            raise RuntimeError("Ollama returned an invalid embedding response.")
        return embeddings[0]

    async def generate(self, prompt: str) -> str:
        response = await self._request(
            "/api/generate",
            {
                "model": self._chat_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=120,
        )
        recommendation = response.get("response")
        if not isinstance(recommendation, str) or not recommendation.strip():
            raise RuntimeError("Ollama returned an empty recommendation.")
        return recommendation.strip()

    async def _request(self, path: str, payload: dict, timeout: float) -> dict:
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
                response = await client.post(path, json=payload)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError(f"Ollama request failed: {error}") from error
