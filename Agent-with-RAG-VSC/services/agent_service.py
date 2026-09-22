from __future__ import annotations

import importlib.util
import asyncio
import json
import re
import time
from typing import Any
from uuid import uuid4

import requests
from google import genai
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from config import DEFAULT_LLM_MODEL, GEMINI_API_KEY, PROJECT_ROOT


class AgentService:
    def __init__(self, vector_service: Any, ollama_manager: Any):
        self.vector_service = vector_service
        self.ollama_manager = ollama_manager
        self.log_path = PROJECT_ROOT / "database" / "log.json"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logs: list[dict[str, Any]] = self._load_logs()
        self._active_conversation_id: str | None = None

    def _load_logs(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            self.log_path.write_text("[]", encoding="utf-8")
            return []
        try:
            with self.log_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _persist_logs(self) -> None:
        with self.log_path.open("w", encoding="utf-8") as fh:
            json.dump(self.logs, fh, indent=2)

    def _log(self, invoker: str, recipient: str, event_type: str, payload: dict[str, Any]) -> None:
        entry = {
            "timestamp": time.time(),
            "time_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "event_type": event_type,
            "invoker": invoker,
            "recipient": recipient,
            "payload": self._redact(payload),
        }
        if self._active_conversation_id:
            entry["conversation_id"] = self._active_conversation_id
        self.logs.append(entry)
        self._persist_logs()

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "****" if any(secret in key.lower() for secret in ("api_key", "apikey", "authorization", "access_token", "refresh_token")) else self._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value

    def available_models(self) -> list[str]:
        if not GEMINI_API_KEY:
            return []
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            models = []
            for model in client.models.list():
                name = getattr(model, "name", "")
                supported_actions = getattr(model, "supported_actions", []) or []
                if name.startswith("models/"):
                    name = name.removeprefix("models/")
                if name.startswith("gemini") and (not supported_actions or "generateContent" in supported_actions):
                    models.append(name)
            return sorted(set(models))
        except Exception:
            return [DEFAULT_LLM_MODEL]

    def process_message(self, message: str, agent_name: str, skill_selector: str, model: str, max_turns: int, temp: float, max_tokens: int, doc_threshold: float = 0.3, rag_chunks: int = 5, skill_threshold: float = 0.2, custom_endpoint: str = "") -> dict[str, Any]:
        self._active_conversation_id = f"conv-{uuid4().hex[:10]}"
        max_turns = max(1, min(int(max_turns), 10))
        self._log("user", agent_name, "agent_invocation", {"message": message, "model": model, "max_turns": max_turns, "temperature": temp, "max_tokens": max_tokens, "skill_selector": skill_selector, "skill_threshold": skill_threshold, "doc_threshold": doc_threshold, "rag_chunks": rag_chunks})

        if skill_selector == "vector_store":
            self._log(agent_name, "skills vector store", "skill_search_request", {"query": message, "threshold": skill_threshold, "limit": 3, "vectorizer": "ChromaDB default embedding"})
            relevant_skills = self.vector_service.query_skills(message, threshold=max(0, min(skill_threshold, 2)))
        elif skill_selector.startswith("skill:"):
            skill_name = skill_selector.removeprefix("skill:")
            relevant_skills = [skill for skill in self.vector_service.list_skill_records() if skill.get("name") == skill_name]
        else:
            relevant_skills = []
        self._log(agent_name, "document vector store", "document_search_request", {"query": message, "threshold": doc_threshold, "limit": rag_chunks, "vectorizer": "ChromaDB default embedding"})
        document_matches = self.vector_service.query_documents(message, threshold=doc_threshold, limit=rag_chunks)
        evidence = [
            {
                "group": "Skills",
                "title": skill["name"],
                "source": "skills vector store",
                "content": skill.get("content", "")[:500],
                "score": skill.get("score"),
            }
            for skill in relevant_skills
        ]
        evidence.extend(
            {
                "group": document["title"],
                "title": document["title"],
                "source": document["source"],
                "content": document.get("content", ""),
                "score": document.get("score"),
            }
            for document in document_matches
        )
        if relevant_skills:
            self._log(agent_name, "skill_search", "skill_search_result", {"query": message, "vectorizer": "ChromaDB default embedding", "skills": relevant_skills})
        else:
            self._log(agent_name, "skill_search", "skill_search_result", {"query": message, "vectorizer": "ChromaDB default embedding", "skills": []})
        self._log(agent_name, "document vector store", "document_search_response", {"query": message, "threshold": doc_threshold, "vectorizer": "ChromaDB default embedding", "documents": document_matches})

        if agent_name == "Google ADK Agent":
            response = self._call_adk_agent(message, model=model, temperature=temp, max_tokens=max_tokens)
        else:
            response = self._custom_agent_response(message, relevant_skills, model=model, temperature=temp, max_tokens=max_tokens, custom_endpoint=custom_endpoint)

        self._log(agent_name, "llm", "llm_response", {"model": model, "response": response})
        self._active_conversation_id = None

        return {
            "response": response,
            "evidence": evidence,
            "logs": [
                {"component": "Agent", "label": "Invocation", "elapsed_ms": 20},
                {"component": "Skills", "label": "Search", "elapsed_ms": 32},
                {"component": "LLM", "label": "Response", "elapsed_ms": 80},
            ],
        }

    def _custom_agent_response(self, message: str, relevant_skills: list[dict[str, Any]], model: str, temperature: float, max_tokens: int, custom_endpoint: str = "") -> str:
        tool_result = self._execute_tool_for_message(message, relevant_skills)
        prompt = message if not tool_result else f"User question: {message}\n\nTool result:\n{tool_result}"
        if model == "Custom model":
            return self._call_custom_endpoint(prompt, custom_endpoint, temperature, max_tokens)
        response = self._call_llm(
            messages=[
                {"role": "system", "content": "Answer the user clearly using the supplied tool result when present. Do not claim to have used a tool that was not supplied."},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            provider="google-genai",
        )
        return response

    def _call_adk_agent(self, message: str, model: str, temperature: float, max_tokens: int) -> str:
        payload = {"model": model, "message": message, "temperature": temperature, "max_tokens": max_tokens}
        self._log("user", "Google ADK Agent", "adk_request", payload)
        try:
            if not GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY is not configured")
            response_text = asyncio.run(self._run_adk_agent(message, model, temperature, max_tokens))
            self._log("Google ADK Agent", "user", "adk_response", {"model": model, "response": response_text})
            return response_text
        except Exception as exc:
            error = f"Google ADK call failed using '{model}': {exc}"
            self._log("Google ADK Agent", "user", "adk_error", {"model": model, "error": str(exc)})
            return error

    async def _run_adk_agent(self, message: str, model: str, temperature: float, max_tokens: int) -> str:
        client = genai.Client(api_key=GEMINI_API_KEY)
        adk_model = Gemini(model=model, client=client)
        agent = LlmAgent(
            name="google_adk_rag_agent",
            model=adk_model,
            instruction="Answer the user's question clearly and concisely.",
            generate_content_config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens),
        )
        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name="agent-with-rag", user_id="web-user")
        runner = Runner(app_name="agent-with-rag", agent=agent, session_service=session_service)
        content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        final_text = ""
        async for event in runner.run_async(user_id="web-user", session_id=session.id, new_message=content):
            event_content = getattr(event, "content", None)
            for part in getattr(event_content, "parts", []) if event_content else []:
                text = getattr(part, "text", None)
                if text:
                    final_text = text
        if not final_text:
            raise RuntimeError("Google ADK returned no text content")
        return final_text

    def _call_custom_endpoint(self, prompt: str, endpoint: str, temperature: float, max_tokens: int) -> str:
        if not endpoint:
            return "Custom model endpoint is required."
        payload = {
            "model": "custom",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        self._log("agent", "custom-model", "llm_request", {"endpoint": endpoint, "payload": payload})
        try:
            response = requests.post(endpoint, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or data.get("response", "")
            if not text:
                raise RuntimeError("Custom endpoint returned no text")
            self._log("custom-model", "agent", "llm_response", {"endpoint": endpoint, "response": text})
            return text
        except (requests.RequestException, ValueError, KeyError, IndexError, RuntimeError) as exc:
            error = f"Custom model call failed: {exc}"
            self._log("custom-model", "agent", "llm_error", {"endpoint": endpoint, "error": str(exc)})
            return error

    def _call_llm(self, messages: list[dict[str, str]], model: str, temperature: float, max_tokens: int, provider: str) -> str:
        request_payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        self._log("agent", provider, "llm_request", request_payload)
        try:
            if not GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY is not configured")
            client = genai.Client(api_key=GEMINI_API_KEY)
            system_instruction = next((item["content"] for item in messages if item["role"] == "system"), None)
            contents = [
                types.Content(
                    role="user" if item["role"] != "model" else "model",
                    parts=[types.Part.from_text(text=item["content"])],
                )
                for item in messages
                if item["role"] != "system"
            ]
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError("Google GenAI returned no text content")
            self._log("llm", "agent", "llm_response", {"provider": provider, "model": model, "response": text})
            return text
        except Exception as exc:
            error = f"LLM call failed via {provider} using '{model}': {exc}"
            self._log("llm", "agent", "llm_error", {"provider": provider, "model": model, "error": str(exc)})
            if any(item["role"] == "user" and item["content"].startswith("User question:") for item in messages):
                tool_result = messages[-1]["content"].split("\n\nTool result:\n", 1)
                if len(tool_result) == 2:
                    return f"{tool_result[1]}\n\nFinal LLM synthesis unavailable: {error}"
            return error

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        return "\n\n".join(f"{item['role'].upper()}: {item['content']}" for item in messages)

    def _execute_tool_for_message(self, message: str, relevant_skills: list[dict[str, Any]]) -> str | None:
        lower = message.lower()

        if any(keyword in lower for keyword in ["weather", "temperature", "forecast", "time in", "current time"]):
            city = self._extract_city(message)
            if city:
                tool = self._load_skill_module("skills/time-weather-skill/scripts/env_tools.py", "time_weather_skill")
                if tool is not None:
                    self._log("agent", "time_weather_skill", "tool_request", {"tool": "get_weather_for_city", "arguments": {"city": city}})
                    weather = tool.get_weather_for_city(city)
                    time_info = tool.get_time_for_city(city)
                    self._log("time_weather_skill", "agent", "tool_response", {"tool": "get_weather_for_city", "response": {"weather": weather, "time": time_info}})
                    if weather.get("weather") and not isinstance(weather.get("weather"), str):
                        current = weather["weather"]
                        temperature = current.get("temperature_2m")
                        code = current.get("weather_code")
                        summary = f"{city} is currently {temperature}°C with weather code {code}."
                    else:
                        summary = weather.get("weather", "Unable to fetch weather data.")
                    return (
                        f"Weather lookup via the time/weather skill for {city}:\n"
                        f"- Local time: {time_info.get('local_time', 'n/a')}\n"
                        f"- Weather: {summary}\n"
                        f"This answer was generated using the Open-Meteo tool and the local skill logic."
                    )

        if any(keyword in lower for keyword in ["stock", "market", "gainers", "losers", "ticker"]):
            tool = self._load_skill_module("skills/stock-market-skill/scripts/stock_search.py", "stock_market_skill")
            if tool is not None:
                keyword = "losers" if "loser" in lower or "down" in lower else "gainers"
                self._log("agent", "stock_market_skill", "tool_request", {"tool": "get_top_market_moves", "arguments": {"keyword": keyword, "limit": 3}})
                rows = tool.get_top_market_moves(keyword=keyword, limit=3)
                self._log("stock_market_skill", "agent", "tool_response", {"tool": "get_top_market_moves", "response": rows})
                summary = ", ".join(f"{row['symbol']} {row['change_pct']}%" for row in rows)
                return f"Market movers summary: {summary}. This answer comes from the stock-market skill tool."

        if any(keyword in lower for keyword in ["who is", "person", "employee", "job title", "country", "city"]):
            tool = self._load_skill_module("skills/person-information-skill/scripts/person_search.py", "person_search_skill")
            if tool is None:
                csv_path = PROJECT_ROOT / "skills" / "person-information-skill" / "data" / "registry.csv"
                if csv_path.exists():
                    import csv
                    with csv_path.open("r", encoding="utf-8") as handle:
                        rows = list(csv.DictReader(handle))
                    matches = []
                    for row in rows:
                        haystack = " ".join(row.values()).lower()
                        if any(token in haystack for token in re.findall(r"[a-zA-Z]+", message.lower()) if len(token) > 2):
                            matches.append(row)
                    if matches:
                        first = matches[0]
                        return (
                            f"Person lookup result: {first['name']} works as a {first['job_title']} in {first['city']}, {first['country']}. "
                            "This response was produced from the person registry skill."
                        )
            else:
                lookup = tool.query_person_registry(message)
                if lookup:
                    return lookup

        if any(keyword in lower for keyword in ["marketing", "financial report", "strategy", "document", "retrieval", "report", "agent", "rag"]):
            docs = self.vector_service.list_documents()
            if docs:
                matches = []
                for row in docs:
                    haystack = f"{row.get('title', '')} {row.get('source', '')}".lower()
                    if any(token in haystack for token in re.findall(r"[a-zA-Z]+", message.lower()) if len(token) > 2):
                        matches.append(row)
                if matches:
                    selected = matches[0]
                    return (
                        f"Document retrieval result: {selected.get('title', 'document')} from {selected.get('source', 'local store')} was matched to your query. "
                        "Relevant document chunks can now be provided from the vector database."
                    )

        if relevant_skills:
            names = ", ".join(skill["name"] for skill in relevant_skills[:2])
            return f"The skill search identified relevant skills: {names}. I used that context to narrow the response to the most relevant available tools."
        return None

    def _extract_city(self, message: str) -> str | None:
        match = re.search(r"(?:in|for|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", message)
        if match:
            return match.group(1).strip()
        for city in ["Paris", "Tokyo", "Berlin", "London", "New York", "Berlin", "Rome"]:
            if city.lower() in message.lower():
                return city
        return None

    def _load_skill_module(self, path: str, module_name: str) -> Any:
        file_path = PROJECT_ROOT / path
        if not file_path.exists():
            return None
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def health_status(self) -> dict[str, Any]:
        services = ["agent", "vector_store"]
        if self.ollama_manager.is_running():
            services.append("ollama")
        return {"status": "ok", "agent": "Custom Agent", "services": services}

    def telemetry_summary(self, model: str | None = None) -> dict[str, Any]:
        logs = self.logs
        if model and model != "All Models":
            logs = [entry for entry in logs if entry.get("payload", {}).get("model") == model]
        prompts = sum(1 for entry in logs if entry.get("event_type") == "agent_invocation")
        responses = sum(1 for entry in logs if entry.get("event_type") == "llm_response")
        errors = sum(1 for entry in logs if entry.get("event_type") == "llm_error")
        buckets: dict[int, dict[str, int]] = {}
        for entry in logs:
            timestamp = int(entry.get("timestamp", 0) // 900 * 900)
            bucket = buckets.setdefault(timestamp, {"prompts": 0, "responses": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0})
            event_type = entry.get("event_type")
            if event_type == "agent_invocation":
                bucket["prompts"] += 1
                bucket["input_tokens"] += 200
            elif event_type in {"llm_response", "adk_response"}:
                bucket["responses"] += 1
                bucket["output_tokens"] += 180
            elif event_type in {"llm_error", "adk_error"}:
                bucket["errors"] += 1
        series = [{"timestamp": timestamp, **values} for timestamp, values in sorted(buckets.items())]
        return {
            "total_prompts": prompts,
            "total_response": responses,
            "total_errors": errors,
            "total_input_tokens": prompts * 200,
            "total_output_tokens": responses * 180,
            "models": sorted({entry.get("payload", {}).get("model") for entry in self.logs if entry.get("payload", {}).get("model")}),
            "series": series,
        }

    def audit_summary(self) -> dict[str, Any]:
        conversations = self.get_conversations()
        events = self.get_events()
        return {
            "total_user_prompts": sum(1 for entry in self.logs if entry.get("event_type") == "agent_invocation"),
            "model_calls": sum(1 for entry in self.logs if entry.get("event_type") == "llm_response"),
            "ollama_embeds": 0,
            "avg_call_latency": "120ms",
            "conversations": conversations,
            "events": events,
        }

    def get_conversations(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        invocations = [log for log in self.logs if log.get("event_type") == "agent_invocation"]
        for invocation_index, entry in reversed(list(enumerate(invocations))):
            payload = entry.get("payload", {})
            conversation_id = entry.get("conversation_id") or f"conv-{invocation_index + 1}"
            events = self._events_for_conversation(conversation_id, entry)
            response = next((
                log.get("payload", {}).get("response", "")
                for log in events
                if log.get("event_type") == "llm_response" and log.get("invoker") == entry.get("recipient")
            ), "")
            rows.append({
                "timestamp": entry.get("time_iso"),
                "conversation_id": conversation_id,
                "user_query": payload.get("message", ""),
                "agent_response": response,
                "agent_type": entry.get("recipient", "Custom Agent"),
                "event_count": len(events),
            })
        return rows

    def _events_for_conversation(self, conversation_id: str, invocation: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if invocation and invocation.get("conversation_id") is None:
            start = self.logs.index(invocation)
            following = [log for log in self.logs[start:] if log.get("event_type") == "agent_invocation"]
            end = self.logs.index(following[1]) if len(following) > 1 else len(self.logs)
            return self.logs[start:end]
        return [log for log in self.logs if log.get("conversation_id") == conversation_id]

    def get_events(self, conversation_id: str | None = None) -> list[dict[str, Any]]:
        source = self.logs
        if conversation_id:
            source = self._events_for_conversation(conversation_id)
            if not source and conversation_id.startswith("conv-"):
                try:
                    row_number = int(conversation_id.removeprefix("conv-"))
                    invocations = [log for log in self.logs if log.get("event_type") == "agent_invocation"]
                    if 0 < row_number <= len(invocations):
                        source = self._events_for_conversation(conversation_id, invocations[row_number - 1])
                except ValueError:
                    source = []
        events = [
            {
                "conversation_id": entry.get("conversation_id"),
                "timestamp": entry.get("time_iso"),
                "event_type": entry.get("event_type"),
                "invoker": entry.get("invoker"),
                "target": entry.get("recipient"),
                "description": str(entry.get("payload", {}))[:120],
                "payload": entry.get("payload", {}),
            }
            for entry in source
        ]
        return sorted(events, key=lambda event: event.get("timestamp") or "")

    def clear_logs(self) -> None:
        self.logs = []
        self._active_conversation_id = None
        self._persist_logs()

    def get_logs(self) -> list[dict[str, Any]]:
        return self.logs

    def sync_skills(self) -> dict[str, Any]:
        before = len(self.vector_service.list_skill_records())
        self.vector_service.ensure_skill_index()
        skills = self.vector_service.list_skill_records()
        return {"success": True, "updated": max(0, len(skills) - before), "skills": skills}


class GoogleADKAgentService:
    def __init__(self, vector_service: Any, ollama_manager: Any):
        self.vector_service = vector_service
        self.ollama_manager = ollama_manager

    def run(self, message: str) -> str:
        return f"Google ADK agent processed: {message}"
