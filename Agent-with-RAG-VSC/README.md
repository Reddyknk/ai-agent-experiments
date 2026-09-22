# Agent With RAG

This Flask application provides a browser interface for a retrieval-augmented agent. It maintains separate ChromaDB collections for skills and document chunks, invokes local skill tools, calls Google Gemini through `google-genai`, supports a Google ADK `LlmAgent`, and records component-level audit events in `database/log.json`.

## Installation

Create or activate a Python environment, then install all dependencies:

```bash
pip install -r requirements.txt
```

Install Ollama separately and make sure it is available on `PATH`. Ollama is used for vector embeddings. The application starts Ollama if it was not already running and only stops it when the application started it.

Create `.env` with a Google AI Studio key:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
PORT=5000
```

## Start

```bash
python app.py
```

The default URL is `http://127.0.0.1:5000`. Override the port with `python app.py --port 5002`.

## User Guide

1. Open the application in a browser.
2. In Chat & Knowledge Synthesis, choose the model, agent, skill selector, thresholds, and RAG chunk limit, then send a question.
3. Inspect grouped skill/document evidence in Retrieved Context Evidence. Expand Show Logs to inspect execution steps.
4. In Vector DB Ingestion, choose a local directory, URL, or sample source. Configure chunk size/overlap and populate the database. Existing chunks are deduplicated.
5. Use Vector Storage Status to inspect document names, chunk counts, character totals, and delete individual documents.
6. Use Telemetry to filter model activity, refresh summaries, and inspect throughput/token charts.
7. Use Audit Log & Event to inspect the five newest conversations. Scroll the table for older records, select a conversation to load its events, and click an event for its complete JSON payload.

## Logs and shutdown

Every request and response between the agent, skill/document vector stores, tools, Google GenAI, Google ADK, and custom endpoints is written as a separate JSON event in `database/log.json`. Credential fields are redacted as `****`. The Audit page can clear the log after confirmation.

To stop services, use the red Shutdown button and type exactly `Shutdown the service`. Supporting services that were already running before app startup are not stopped.
