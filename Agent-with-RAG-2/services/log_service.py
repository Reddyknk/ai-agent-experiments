"""
Audit and Event Logging Service.
Stores all invocations, requests, responses, and errors in database/log.json.
Provides query, aggregation, conversation tracking, and sensitive API key redaction.
"""
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from config import LOG_FILE

_log_lock = threading.Lock()

# Common API key regex patterns to redact
API_KEY_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key["\']?\s*[:=]\s*["\'])([^"\']{6,})(["\'])'), r'\g<1>****\g<3>'),
    (re.compile(r'(?i)(bearer\s+)([A-Za-z0-9_\-\.]{15,})'), r'\g<1>****'),
    (re.compile(r'(?i)(token["\']?\s*[:=]\s*["\'])([^"\']{6,})(["\'])'), r'\g<1>****\g<3>'),
    (re.compile(r'AIza[0-9A-Za-z_\-]{25,45}'), '****'),
    (re.compile(r'sk-[0-9A-Za-z]{20,60}'), '****'),
]

def redact_sensitive_data(data: Any) -> Any:
    """
    Recursively redact API keys, tokens, and secret credentials with '****'.
    """
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(secret_term in k.lower() for secret_term in ["key", "secret", "token", "password", "authorization"]):
                if isinstance(v, str) and len(v) > 0:
                    redacted[k] = "****"
                else:
                    redacted[k] = v
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        text = data
        for regex, repl in API_KEY_PATTERNS:
            text = regex.sub(repl, text)
        return text
    return data

class LogService:
    def __init__(self, log_path=LOG_FILE):
        self.log_path = log_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        with _log_lock:
            if not os.path.exists(self.log_path):
                with open(self.log_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)

    def log_event(
        self,
        event_type: str,
        invoker: str,
        target: str,
        payload: Any,
        response: Any,
        description: str = "",
        conversation_id: Optional[str] = None,
        latency_ms: float = 0.0,
        status: str = "success"
    ) -> Dict[str, Any]:
        """
        Record an invocation event between user, agent, skill, tool, or external service.
        """
        now_utc = datetime.now(timezone.utc)
        entry = {
            "id": f"log-{int(now_utc.timestamp() * 1000)}-{os.urandom(3).hex()}",
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "invoker": invoker,
            "target": target,
            "description": description or f"{event_type}: {invoker} -> {target}",
            "payload": redact_sensitive_data(payload),
            "response": redact_sensitive_data(response),
            "conversation_id": conversation_id or "system",
            "latency_ms": round(latency_ms, 2),
            "status": status
        }

        with _log_lock:
            try:
                logs = []
                if os.path.exists(self.log_path) and os.path.getsize(self.log_path) > 0:
                    with open(self.log_path, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                logs.append(entry)
                with open(self.log_path, "w", encoding="utf-8") as f:
                    json.dump(logs, f, indent=2)
            except Exception as e:
                print(f"[LogService Error] Failed to write log: {e}")

        return entry

    def get_all_logs(self) -> List[Dict[str, Any]]:
        with _log_lock:
            if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
                return []
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []

    def clear_logs(self) -> bool:
        with _log_lock:
            try:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
                return True
            except Exception as e:
                print(f"[LogService Error] Failed to clear logs: {e}")
                return False

    def get_conversations(self) -> List[Dict[str, Any]]:
        """
        Extract unique conversation sessions with first user query and final agent response.
        """
        logs = self.get_all_logs()
        conversations = {}

        for entry in logs:
            cid = entry.get("conversation_id")
            if not cid or cid == "system":
                continue

            if cid not in conversations:
                conversations[cid] = {
                    "conversation_id": cid,
                    "timestamp": entry.get("timestamp"),
                    "user_query": "",
                    "agent_response": "",
                    "total_events": 0,
                    "model_used": "unknown",
                    "status": "completed"
                }

            conversations[cid]["total_events"] += 1

            if entry.get("event_type") == "User Prompt":
                if not conversations[cid]["user_query"]:
                    if isinstance(entry.get("payload"), dict):
                        conversations[cid]["user_query"] = entry.get("payload", {}).get("query", "")
                    else:
                        conversations[cid]["user_query"] = str(entry.get("payload", ""))

            if entry.get("event_type") in ["Agent Response", "LLM Synthesis"]:
                if isinstance(entry.get("response"), dict):
                    conversations[cid]["agent_response"] = entry.get("response", {}).get("content", "")
                else:
                    conversations[cid]["agent_response"] = str(entry.get("response", ""))

            if entry.get("event_type") == "LLM Synthesis":
                if isinstance(entry.get("payload"), dict):
                    conversations[cid]["model_used"] = entry.get("payload", {}).get("model", "unknown")

        # Sort conversations reverse chronologically
        conv_list = list(conversations.values())
        conv_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return conv_list

    def get_conversation_logs(self, conversation_id: str) -> List[Dict[str, Any]]:
        logs = self.get_all_logs()
        return [l for l in logs if l.get("conversation_id") == conversation_id]

    def get_statistics(self) -> Dict[str, Any]:
        logs = self.get_all_logs()
        total_user_prompts = sum(1 for l in logs if l.get("event_type") == "User Prompt")
        total_model_calls = sum(1 for l in logs if "LLM" in l.get("event_type", ""))
        total_ollama_embeds = sum(1 for l in logs if "Ollama" in l.get("event_type", "") or "Embed" in l.get("event_type", ""))

        latencies = [l.get("latency_ms", 0) for l in logs if l.get("latency_ms", 0) > 0]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

        return {
            "total_user_prompts": total_user_prompts,
            "total_model_calls": total_model_calls,
            "total_ollama_embeds": total_ollama_embeds,
            "avg_latency_ms": avg_latency,
            "total_logs": len(logs)
        }

# Global singleton
audit_logger = LogService()
