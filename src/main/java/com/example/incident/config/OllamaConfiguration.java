package com.example.incident.config;

import dev.langchain4j.model.chat.ChatLanguageModel;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.ollama.OllamaChatModel;
import dev.langchain4j.model.ollama.OllamaEmbeddingModel;

import java.time.Duration;

/** Creates LangChain4j clients for the local Ollama server. */
public final class OllamaConfiguration {
    private final String baseUrl = environment("OLLAMA_BASE_URL", "http://localhost:11434");
    private final String embeddingModel = environment("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest");
    private final String chatModel = environment("OLLAMA_CHAT_MODEL", "mistral:latest");

    public EmbeddingModel embeddingModel() {
        return OllamaEmbeddingModel.builder().baseUrl(baseUrl).modelName(embeddingModel)
                .timeout(Duration.ofSeconds(90)).build();
    }

    public ChatLanguageModel chatModel() {
        return OllamaChatModel.builder().baseUrl(baseUrl).modelName(chatModel)
                .temperature(0.1).timeout(Duration.ofSeconds(120)).build();
    }

    public String embeddingModelName() { return embeddingModel; }
    public String chatModelName() { return chatModel; }

    private static String environment(String name, String defaultValue) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? defaultValue : value;
    }
}
