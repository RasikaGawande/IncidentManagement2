package com.example.incident.vector;

import com.example.incident.model.Incident;
import com.example.incident.model.SimilarIncident;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.model.embedding.EmbeddingModel;

import java.util.Comparator;
import java.util.List;

/** Stores only for this process lifetime; vectors are rebuilt when the application starts. */
public final class InMemoryIncidentVectorStore {
    private final EmbeddingModel embeddingModel;
    private final List<VectorizedIncident> entries;

    private InMemoryIncidentVectorStore(EmbeddingModel embeddingModel, List<VectorizedIncident> entries) {
        this.embeddingModel = embeddingModel;
        this.entries = entries;
    }

    public static InMemoryIncidentVectorStore from(List<Incident> incidents, EmbeddingModel embeddingModel) {
        List<VectorizedIncident> entries = incidents.stream()
                .map(incident -> new VectorizedIncident(incident, embed(embeddingModel, incident.searchableText())))
                .toList();
        return new InMemoryIncidentVectorStore(embeddingModel, entries);
    }

    public List<SimilarIncident> search(Incident incomingIncident, int limit) {
        float[] queryVector = embed(embeddingModel, incomingIncident.searchableText());
        return entries.stream()
                .map(entry -> new SimilarIncident(entry.incident(), cosineSimilarity(queryVector, entry.vector())))
                .sorted(Comparator.comparingDouble(SimilarIncident::similarity).reversed())
                .limit(limit)
                .toList();
    }

    private static float[] embed(EmbeddingModel model, String text) {
        Embedding embedding = model.embed(text).content();
        return embedding.vector();
    }

    private static double cosineSimilarity(float[] left, float[] right) {
        if (left.length != right.length) throw new IllegalArgumentException("Embedding dimensions do not match");
        double dot = 0, leftMagnitude = 0, rightMagnitude = 0;
        for (int i = 0; i < left.length; i++) {
            dot += left[i] * right[i];
            leftMagnitude += left[i] * left[i];
            rightMagnitude += right[i] * right[i];
        }
        return dot / (Math.sqrt(leftMagnitude) * Math.sqrt(rightMagnitude));
    }

    private record VectorizedIncident(Incident incident, float[] vector) { }
}
