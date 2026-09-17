"""
Skill Manager Service.
Scans skills/ directory, parses SKILL.md files, vectors skill metadata,
and dispatches execution to skill scripts and SOP workflows.
"""
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

from config import SKILLS_DIR, MIN_SKILL_SCORE
from services.vector_store import skill_vector_store, doc_vector_store
from services.ollama_service import ollama_service
from services.log_service import audit_logger

def parse_skill_markdown(skill_path: Path) -> Dict[str, Any]:
    """
    Parse SKILL.md file with YAML frontmatter and markdown body.
    """
    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        return {}

    raw_text = skill_file.read_text(encoding="utf-8")
    frontmatter = {}
    body = raw_text

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, re.DOTALL)
    if match:
        fm_text, body = match.groups()
        try:
            frontmatter = yaml.safe_load(fm_text) or {}
        except Exception as e:
            print(f"Error parsing YAML frontmatter in {skill_file}: {e}")

    # Fallback extraction if frontmatter missing
    name = frontmatter.get("name") or skill_path.name
    description = frontmatter.get("description", "")
    trigger_queries = frontmatter.get("Trigger Queries") or frontmatter.get("trigger_queries", [])

    return {
        "folder_name": skill_path.name,
        "path": str(skill_path),
        "name": name,
        "description": description,
        "trigger_queries": trigger_queries,
        "full_text": raw_text,
        "body": body
    }

class SkillManager:
    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = Path(skills_dir)

    def scan_and_load_skills(self) -> Dict[str, Any]:
        """
        Scan the skills/ folder and load new skills that are not in the skill database.
        Skills already in the database should not be re-loaded.
        """
        if not self.skills_dir.exists():
            return {"loaded_skills": [], "skipped_skills": [], "total_skills": 0}

        existing_data = skill_vector_store._load()
        existing_skill_folders = {
            c.get("metadata", {}).get("folder_name")
            for c in existing_data.get("chunks", [])
        }

        newly_loaded = []
        skipped = []

        for item in sorted(self.skills_dir.iterdir()):
            if not item.is_dir():
                continue
            skill_folder_name = item.name

            if skill_folder_name in existing_skill_folders:
                skipped.append(skill_folder_name)
                continue

            parsed = parse_skill_markdown(item)
            if not parsed:
                continue

            # Embed name, description, and trigger queries
            queries_str = " ".join(parsed["trigger_queries"]) if isinstance(parsed["trigger_queries"], list) else str(parsed["trigger_queries"])
            embed_text = f"{parsed['name']}. {parsed['description']} Trigger queries: {queries_str}"

            vector = ollama_service.generate_embedding(embed_text)

            # Store the vectors and complete text of the SKILL.md file as one record
            chunk_record = {
                "id": f"skill-{skill_folder_name}",
                "content_hash": skill_folder_name,
                "text": parsed["full_text"],
                "vector": vector,
                "metadata": {
                    "folder_name": skill_folder_name,
                    "name": parsed["name"],
                    "description": parsed["description"],
                    "trigger_queries": parsed["trigger_queries"],
                    "path": parsed["path"],
                    "embed_text": embed_text
                }
            }

            existing_data["chunks"].append(chunk_record)
            existing_data["documents"][skill_folder_name] = {
                "chunks_count": 1,
                "total_characters": len(parsed["full_text"]),
                "source": "skill_definition"
            }
            newly_loaded.append(skill_folder_name)

        skill_vector_store._save(existing_data)

        audit_logger.log_event(
            event_type="Skill DB Update",
            invoker="System",
            target="SkillManager",
            payload={"scanned_folder": str(self.skills_dir)},
            response={"newly_loaded": newly_loaded, "skipped": skipped},
            description=f"Loaded {len(newly_loaded)} new skills into skill database"
        )

        return {
            "loaded_skills": newly_loaded,
            "skipped_skills": skipped,
            "total_skills": len(existing_data.get("chunks", []))
        }

    def match_skills(self, user_query: str, min_score: float = MIN_SKILL_SCORE) -> List[Dict[str, Any]]:
        """
        Query the skill vector database.
        Returns skills with similarity score > min_score (default 0.5).
        """
        results = skill_vector_store.query_similar(user_query, top_k=5, min_score=min_score)
        matched = []
        for r in results:
            meta = r.get("metadata", {})
            matched.append({
                "folder_name": meta.get("folder_name"),
                "name": meta.get("name"),
                "description": meta.get("description"),
                "score": r.get("score"),
                "full_text": r.get("text"),
                "path": meta.get("path")
            })
        return matched

    def execute_skill(self, skill_info: Dict[str, Any], user_query: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatch execution from skill to procedural tool.
        Logs interactions between 'skill', 'tool', and 'external API call'.
        """
        folder_name = skill_info.get("folder_name", "")
        skill_name = skill_info.get("name", "")
        score = skill_info.get("score", 0.0)

        result_data = None
        evidence_text = ""

        if "weather" in folder_name.lower() or "time" in folder_name.lower():
            try:
                script_path = self.skills_dir / folder_name / "scripts" / "env_tools.py"
                if script_path.exists():
                    spec = importlib.util.spec_from_file_location("env_tools", str(script_path))
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    # Extract city from query
                    stop_words = {"what", "is", "the", "weather", "in", "time", "at", "for", "check", "tell", "me", "how", "right", "now", "currently", "today", "forecast", "like", "please", "conditions"}
                    words = [w.strip("?,.!\"'") for w in user_query.split() if w.lower().strip("?,.!\"'") not in stop_words]
                    city = " ".join(words).strip() or "Tokyo"

                    # Log invocation from skill to tool
                    audit_logger.log_event(
                        event_type="Tool Invocation",
                        invoker="skill",
                        target="tool",
                        payload={"tool": "env_tools.py", "function": "get_weather_and_time", "city": city},
                        response={"status": "invoking"},
                        description=f"Skill '{skill_name}' invoking tool for city: {city}",
                        conversation_id=conversation_id
                    )

                    result_data = mod.get_weather_and_time(city)

                    # Log external API call result from tool
                    audit_logger.log_event(
                        event_type="External API Request",
                        invoker="tool",
                        target="external API call",
                        payload={"api": "Open-Meteo", "city": city},
                        response={"status": result_data.get("status"), "data": result_data},
                        description=f"Tool queried Open-Meteo API for {city}",
                        conversation_id=conversation_id
                    )

                    evidence_text = f"Weather in {result_data.get('city', city)}: {result_data.get('condition')}, Temp: {result_data.get('temperature_celsius')}°C / {result_data.get('temperature_fahrenheit')}°F, Time: {result_data.get('local_time')}"
            except Exception as e:
                result_data = {"error": str(e)}
                evidence_text = f"Skill execution error: {e}"

        elif "person" in folder_name.lower() or "registry" in folder_name.lower():
            try:
                script_path = self.skills_dir / folder_name / "scripts" / "person_search.py"
                if script_path.exists():
                    spec = importlib.util.spec_from_file_location("person_search", str(script_path))
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    search_words = [w for w in user_query.split() if w.lower() not in ["who", "where", "is", "the", "find", "all", "what", "job", "title", "of", "person", "in", "lives"]]
                    kw = " ".join(search_words).strip()

                    audit_logger.log_event(
                        event_type="Tool Invocation",
                        invoker="skill",
                        target="tool",
                        payload={"tool": "person_search.py", "keyword": kw},
                        response={"status": "invoking"},
                        description=f"Skill '{skill_name}' searching registry for keyword: {kw}",
                        conversation_id=conversation_id
                    )

                    matches = mod.query_person_registry(kw)
                    result_data = {"matches": matches, "query_keyword": kw}
                    if matches:
                        evidence_text = f"Found {len(matches)} personnel records: " + "; ".join([f"{p['name']} ({p.get('job_title', '')}, {p.get('city', '')}, {p.get('country', '')})" for p in matches[:5]])
                    else:
                        evidence_text = f"No matching registry records found for query keyword '{kw}'."
            except Exception as e:
                result_data = {"error": str(e)}
                evidence_text = f"Skill execution error: {e}"

        elif "stock" in folder_name.lower():
            try:
                script_path = self.skills_dir / folder_name / "scripts" / "stock_search.py"
                if script_path.exists():
                    spec = importlib.util.spec_from_file_location("stock_search", str(script_path))
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    audit_logger.log_event(
                        event_type="Tool Invocation",
                        invoker="skill",
                        target="tool",
                        payload={"tool": "stock_search.py", "query": user_query},
                        response={"status": "invoking"},
                        description=f"Skill '{skill_name}' analyzing market equities for: '{user_query}'",
                        conversation_id=conversation_id
                    )

                    result_data = mod.analyze_stock_query(user_query)
                    stocks = result_data.get("stocks", [])
                    evidence_text = f"{result_data.get('category')}: " + ", ".join([f"{s['ticker']} ({s['change_pct']:+.2f}%, ${s['price']})" for s in stocks])
            except Exception as e:
                result_data = {"error": str(e)}
                evidence_text = f"Skill execution error: {e}"

        elif "retriever" in folder_name.lower() or "document" in folder_name.lower():
            doc_matches = doc_vector_store.query_similar(user_query, top_k=3, conversation_id=conversation_id)
            result_data = {"doc_matches": doc_matches}
            evidence_text = f"Retrieved {len(doc_matches)} text chunks from document vector store."

        else:
            result_data = {"info": "Skill matched based on SOP triggers."}
            evidence_text = skill_info.get("description", "")

        # Log completion from tool back to skill
        audit_logger.log_event(
            event_type="Tool Response",
            invoker="tool",
            target="skill",
            payload={"skill": folder_name, "score": score},
            response=result_data,
            description=f"Tool returned execution results for {skill_name}",
            conversation_id=conversation_id
        )

        return {
            "skill_name": skill_name,
            "folder_name": folder_name,
            "score": score,
            "result_data": result_data,
            "evidence_text": evidence_text
        }

# Global singleton
skill_manager = SkillManager()
