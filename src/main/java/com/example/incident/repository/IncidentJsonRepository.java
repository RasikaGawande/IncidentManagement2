package com.example.incident.repository;

import com.example.incident.model.Incident;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

/** Reads the independently managed historical and incoming incident JSON files. */
public final class IncidentJsonRepository {
    private final ObjectMapper objectMapper = new ObjectMapper();

    public List<Incident> loadHistoricalIncidents() throws IOException {
        try (InputStream stream = resource("/historical-incidents.json")) {
            return objectMapper.readValue(stream, new TypeReference<>() { });
        }
    }

    public List<Incident> loadNewIncidents() throws IOException {
        try (InputStream stream = resource("/new-incident.json")) {
            return objectMapper.readValue(stream, new TypeReference<>() { });
        }
    }

    private InputStream resource(String name) {
        InputStream stream = IncidentJsonRepository.class.getResourceAsStream(name);
        if (stream == null) throw new IllegalStateException("Missing classpath resource: " + name);
        return stream;
    }
}
