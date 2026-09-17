"""
Integration Tests for Flask API endpoints and sensitive key redaction.
"""
import pytest
import json
from app import app
from services.log_service import redact_sensitive_data, audit_logger

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_api_key_redaction():
    payload = {
        "api_key": "AIzaSyD-secret1234567890abcdefghijklm",
        "authorization": "Bearer sec_abcdef1234567890",
        "query": "Hello world with key AIzaSyD-secret1234567890abcdefghijklm embedded in text"
    }
    redacted = redact_sensitive_data(payload)
    assert redacted["api_key"] == "****"
    assert redacted["authorization"] == "****"
    assert "AIzaSyD" not in redacted["query"]
    assert "****" in redacted["query"]

def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert "status" in data
    assert "agent" in data
    assert "ollama" in data

def test_models_endpoint(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.get_json()
    assert "models" in data
    assert any(m["id"] == "custom" for m in data["models"])

def test_vector_status_endpoint(client):
    res = client.get("/api/vector/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "total_chunks" in data
    assert "total_documents" in data
    assert "db_size_mb" in data

def test_ollama_models_endpoint(client):
    res = client.get("/api/ollama/models")
    assert res.status_code == 200
    data = res.get_json()
    assert "models" in data
    assert len(data["models"]) > 0
    # Check that model characteristics include dimensions, context_window, size, description, status
    first = data["models"][0]
    assert "dimensions" in first
    assert "context_window" in first
    assert "size" in first
    assert "description" in first
    assert "status" in first

def test_telemetry_endpoint(client):
    res = client.get("/api/telemetry?model=All+Models&time_range=1+day&interval=15+min")
    assert res.status_code == 200
    data = res.get_json()
    assert "totals" in data
    assert "charts" in data

def test_logs_endpoint(client):
    res = client.get("/api/logs")
    assert res.status_code == 200
    data = res.get_json()
    assert "statistics" in data
    assert "conversations" in data

def test_chat_endpoint(client):
    res = client.post(
        "/api/chat",
        json={
            "query": "What is the weather in Tokyo?",
            "model": "gemini-2.5-flash",
            "temperature": 0.5,
            "max_tokens": 1024,
            "max_rag_chunks": 3
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "answer" in data["data"]
    assert "retrieved_evidence" in data["data"]

def test_component_logging(client):
    # Perform chat inquiry that triggers weather skill, vector search, and model
    res = client.post(
        "/api/chat",
        json={
            "query": "What is the weather in London right now?",
            "model": "gemini-2.5-flash"
        }
    )
    assert res.status_code == 200
    conv_id = res.get_json()["data"]["conversation_id"]

    # Query logs for this conversation
    log_res = client.get(f"/api/logs?conversation_id={conv_id}")
    assert log_res.status_code == 200
    log_data = log_res.get_json()

    events = log_data.get("events", [])
    assert len(events) > 0

    invokers = {e.get("invoker") for e in events}
    targets = {e.get("target") for e in events}

    # Verify component interactions logged per specification
    assert "user" in invokers or "user" in targets
    assert "agent" in invokers
    assert "skill" in invokers or "skill" in targets
    assert "tool" in invokers or "tool" in targets
    assert "vector database" in invokers or "vector database" in targets
    assert "ollamavector model" in invokers or "ollamavector model" in targets

    # Verify conversation list displays Number of Events
    convs = log_data.get("conversations", [])
    matching_conv = next((c for c in convs if c["conversation_id"] == conv_id), None)
    assert matching_conv is not None
    assert matching_conv["total_events"] > 0
