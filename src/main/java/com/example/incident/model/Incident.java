package com.example.incident.model;

/** The common schema used for historical and incoming incidents. */
public record Incident(String id, String title, String service, String severity, String symptoms,
                       String rootCause, String resolution) {
    public String searchableText() {
        return "title: " + title + "; service: " + service + "; severity: " + severity
                + "; symptoms: " + symptoms;
    }
}
