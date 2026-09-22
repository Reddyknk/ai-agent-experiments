from __future__ import annotations

import argparse
import atexit

from flask import Flask, jsonify, render_template, request

from config import DEFAULT_LLM_MODEL, GEMINI_MODEL, PORT
from services.agent_service import AgentService
from services.ollama_service import OllamaManager
from services.vector_service import VectorService

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["JSON_SORT_KEYS"] = False

vector_service = VectorService()
ollama_manager = OllamaManager()
agent_service = AgentService(vector_service=vector_service, ollama_manager=ollama_manager)


@app.context_processor
def inject_defaults():
    return {
        "default_model": GEMINI_MODEL or DEFAULT_LLM_MODEL,
        "port": PORT,
    }


@app.get("/")
def index():
    return render_template("index.html", default_model=GEMINI_MODEL or DEFAULT_LLM_MODEL)


@app.get("/api/health")
def health():
    status = agent_service.health_status()
    return jsonify(status)


@app.get("/api/models")
def model_list():
    return jsonify({"models": agent_service.available_models()})


@app.get("/api/vector/stats")
def vector_stats():
    return jsonify(vector_service.get_stats())


@app.get("/api/vector/documents")
def vector_documents():
    return jsonify({"documents": vector_service.list_documents()})


@app.post("/api/vector/populate")
def populate_vector_db():
    payload = request.get_json(silent=True) or {}
    source = payload.get("source") or "sample_docs"
    try:
        results = vector_service.populate_from_source(
            source,
            chunk_size=int(payload.get("chunk_size") or 1200),
            overlap=int(payload.get("chunk_overlap") or 150),
        )
        return jsonify({"success": True, "results": results})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required"}), 400

    response = agent_service.process_message(
        message=message,
        agent_name=(payload.get("agent") or "Custom Agent"),
        skill_selector=(payload.get("skill_selector") or "vector_store"),
        model=(payload.get("model") or GEMINI_MODEL or DEFAULT_LLM_MODEL),
        max_turns=int(payload.get("max_turns") or 3),
        temp=float(payload.get("temperature") or 0.7),
        max_tokens=int(payload.get("max_tokens") or 256),
        doc_threshold=float(payload.get("doc_threshold") or 0.3),
        rag_chunks=int(payload.get("rag_chunks") or 5),
        skill_threshold=float(payload.get("skill_threshold") or 0.2),
        custom_endpoint=(payload.get("custom_endpoint") or "").strip(),
    )
    return jsonify(response)


@app.get("/api/telemetry")
def telemetry():
    return jsonify(agent_service.telemetry_summary(request.args.get("model")))


@app.get("/api/audit")
def audit():
    return jsonify(agent_service.audit_summary())


@app.get("/api/audit/events")
def audit_events():
    conversation_id = request.args.get("conversation_id")
    return jsonify({"events": agent_service.get_events(conversation_id)})


@app.get("/api/conversations")
def conversations():
    return jsonify({"conversations": agent_service.get_conversations()})


@app.get("/api/logs")
def logs():
    return jsonify({"logs": agent_service.get_logs()})


@app.post("/api/logs/clear")
def clear_logs():
    agent_service.clear_logs()
    return jsonify({"success": True})


@app.get("/api/skills")
def skills():
    return jsonify({"skills": vector_service.list_skill_records()})


@app.post("/api/skills/update")
def update_skills():
    result = agent_service.sync_skills()
    return jsonify(result)


@app.post("/api/vector/reset")
def vector_reset():
    vector_service.reset_all()
    return jsonify({"success": True})


@app.post("/api/vector/delete")
def vector_delete():
    payload = request.get_json(silent=True) or {}
    doc_id = payload.get("doc_id")
    if doc_id is None:
        return jsonify({"success": False, "error": "doc_id required"}), 400
    vector_service.delete_document(doc_id)
    return jsonify({"success": True})


@app.get("/api/embedding-models")
def embedding_models():
    installed = ollama_manager.list_models()
    return jsonify({
        "models": [
            {"name": "nomic-embed-text", "dimensions": 768, "context": 2048, "size_mb": 274, "status": "Installed" if "nomic-embed-text:latest" in installed else "Available to Pull"},
            {"name": "all-minilm", "dimensions": 384, "context": 512, "size_mb": 46, "status": "Installed" if "all-minilm:latest" in installed else "Available to Pull"},
            {"name": "mxbai-embed-large", "dimensions": 1024, "context": 512, "size_mb": 435, "status": "Installed" if "mxbai-embed-large:latest" in installed else "Available to Pull"},
        ],
        "active": installed[0] if installed else None,
    })


@app.post("/api/embedding-models/change")
def change_embedding_model():
    payload = request.get_json(silent=True) or {}
    model = (payload.get("model") or "").strip()
    if not model or payload.get("confirm") != "Change the embedding model":
        return jsonify({"success": False, "error": "Model and exact confirmation are required"}), 400
    vector_service.reset_all()
    pulled = ollama_manager.pull_model(model)
    agent_service.sync_skills()
    return jsonify({"success": pulled, "model": model, "message": "Embedding model changed and skills reindexed."})


@app.post("/api/shutdown")
def shutdown():
    payload = request.get_json(silent=True) or {}
    confirm = payload.get("confirm")
    if confirm != "Shutdown the service":
        return jsonify({"success": False, "error": "Confirmation text is incorrect"}), 400
    ollama_manager.stop_if_started_by_app()
    return jsonify({"success": True, "message": "Shutdown acknowledged."})


def run_app():
    parser = argparse.ArgumentParser(description="Agent with RAG app")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    vector_service.ensure_initialized()
    agent_service.sync_skills()
    ollama_manager.ensure_running()
    atexit.register(ollama_manager.stop_if_started_by_app)
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    run_app()
