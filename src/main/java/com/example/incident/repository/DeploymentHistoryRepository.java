package com.example.incident.repository;

import com.example.incident.model.DeploymentRecord;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

/** Temporary file-backed deployment backend; replace this adapter with a CI/CD API later. */
public final class DeploymentHistoryRepository {
    private final ObjectMapper objectMapper = new ObjectMapper();

    public List<DeploymentRecord> findByService(String service) throws IOException {
        try (InputStream stream = DeploymentHistoryRepository.class.getResourceAsStream("/deployment-history.json")) {
            if (stream == null) throw new IllegalStateException("Missing classpath resource: /deployment-history.json");
            return objectMapper.readValue(stream, new TypeReference<List<DeploymentRecord>>() { }).stream()
                    .filter(deployment -> deployment.service().equalsIgnoreCase(service))
                    .toList();
        }
    }
}
