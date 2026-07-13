# Incident Management Similarity Demo

This Java application loads historical and incoming incidents from separate JSON files, generates embeddings through LangChain4j and Ollama, stores the historical vectors in memory at startup, retrieves the closest incidents for the new one, and asks Mistral to verify the comparison and propose safe next steps.

When the closest historical incident scores below 85% similarity, the Deployment Check Agent reads the latest successful deployment from `deployment-history.json` and includes that evidence in the Mistral prompt.

## Prerequisites

Run an Ollama server with a chat model and an embedding-capable model:

```bash
ollama pull nomic-embed-text
ollama pull mistral
ollama serve
```

## Run

```bash
mvn compile exec:java
```

Configuration is through environment variables:

- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_CHAT_MODEL` (default `mistral:latest`)
- `OLLAMA_EMBEDDING_MODEL` (default `nomic-embed-text:latest`)

Update `src/main/resources/historical-incidents.json` to add historical cases and `src/main/resources/new-incident.json` to add one or more incoming incidents.

`INC-NEW-06` is an intentional low-similarity example. Because `reporting-api` has no historical incidents, it activates the Deployment Check Agent, which finds deployment `DEP-9005` and provides its timestamp-format change to Mistral as investigation evidence.
