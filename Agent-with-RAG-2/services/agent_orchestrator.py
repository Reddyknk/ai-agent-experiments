"""
Agent Orchestrator Service.
Coordinates intent routing, skill selection, RAG document search,
context evidence grouping by step, LLM synthesis, logging, and telemetry.
"""
import uuid
import time
from typing import Dict, Any, List, Optional

from config import (
    MIN_SKILL_SCORE,
    MIN_RAG_DOC_SCORE,
    DEFAULT_LLM_MODEL,
    DEFAULT_SKILL_THRESHOLD,
    DEFAULT_DOC_THRESHOLD,
    DEFAULT_MAX_TURNS,
    MAX_TURNS_LIMIT
)
from services.skill_manager import skill_manager
from services.vector_store import doc_vector_store
from services.llm_service import llm_service
from services.log_service import audit_logger
from services.telemetry_service import telemetry_service
from services.ollama_service import ollama_service

class AgentOrchestrator:
    def process_chat(
        self,
        query: str,
        model: str = DEFAULT_LLM_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_rag_chunks: int = 5,
        custom_endpoint: Optional[str] = None,
        conversation_id: Optional[str] = None,
        skills_mode: str = "vector_store",
        skill_threshold: float = DEFAULT_SKILL_THRESHOLD,
        doc_threshold: float = DEFAULT_DOC_THRESHOLD,
        max_turns: int = DEFAULT_MAX_TURNS
    ) -> Dict[str, Any]:
        """
        Main multi-step cognitive pipeline:
        1. Log user prompt & record prompt telemetry
        2. Skill resolution based on skills_mode:
           - 'vector_store': Query skill vector store with skill_threshold
           - 'llm_selected': Ask LLM to select relevant skill from skills/ directory
           - specific skill folder: Use that skill directly
        3. If no skill found: send user query to LLM using simple system prompt as assistant
        4. If skill found: send user message and skill to LLM to get tool execution plan
        5. If procedural tool or document search is directed, execute tool/search, feed results back to LLM
           Repeat until final answer is received, limited to max_turns loops (<= MAX_TURNS_LIMIT)
        6. Return grounded response with steps and logs
        """
        cid = conversation_id or f"conv-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        steps: List[Dict[str, Any]] = []

        # Step 1: Log User Message to Agent (Invocation)
        audit_logger.log_call(
            event_type="agent",
            call_type="invocation",
            invoker="user",
            recipient="agent",
            payload={
                "query": query,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "max_rag_chunks": max_rag_chunks,
                "skills_mode": skills_mode,
                "skill_threshold": skill_threshold,
                "doc_threshold": doc_threshold,
                "max_turns": max_turns
            },
            description=f"Message sent to agent: '{query}'",
            conversation_id=cid
        )

        telemetry_service.record_event(
            event_type="prompt",
            model=model,
            input_tokens=len(query.split())
        )

        retrieved_evidence: List[Dict[str, Any]] = []
        skill_context_snippets = []
        doc_context_snippets = []
        step_skill_elapsed = 0.0
        matched_skills: List[Dict[str, Any]] = []
        vectorizer_name = ollama_service.current_model

        # Step 2: Skill Resolution Mode
        if skills_mode == "vector_store":
            step_skill_start = time.time()
            audit_logger.log_call(
                event_type="skill search",
                call_type="invocation",
                invoker="agent",
                recipient="skill search",
                payload={"query": query, "min_score": skill_threshold, "vectorizer": vectorizer_name},
                description=f"Message sent to skill search for: '{query}' using vectorizer {vectorizer_name} (threshold: {skill_threshold})",
                conversation_id=cid
            )

            matched_skills = skill_manager.match_skills(query, min_score=skill_threshold, conversation_id=cid)

            audit_logger.log_call(
                event_type="skill search",
                call_type="response",
                invoker="skill search",
                recipient="agent",
                payload={
                    "vectorizer": vectorizer_name,
                    "vectorizer_response": {"status": "success", "model": vectorizer_name},
                    "matched_skills": [{"name": s.get("name"), "folder_name": s.get("folder_name"), "score": s.get("score")} for s in matched_skills],
                    "count": len(matched_skills)
                },
                description=f"Response received from skill search: {len(matched_skills)} skill(s) matched using {vectorizer_name}",
                conversation_id=cid
            )
            step_skill_elapsed = round((time.time() - step_skill_start) * 1000, 2)

        elif skills_mode == "llm_selected":
            step_skill_start = time.time()
            all_skills = skill_manager.get_all_skills()
            skills_listing = "\n".join([f"- Folder: {s['folder_name']} | Name: {s['name']} | Description: {s['description']}" for s in all_skills])

            sel_prompt = (
                f"User Question: {query}\n\n"
                f"Available Skills:\n{skills_listing}\n\n"
                f"Determine which skill (if any) should be used to answer the question. "
                f"If the question is general knowledge or none of the skills are relevant, respond with 'NONE'. "
                f"Otherwise, respond with ONLY the exact folder name of the selected skill."
            )

            sel_res = llm_service.generate_response(
                prompt=sel_prompt,
                system_instruction="You are a skill router. Select the best matching skill folder name or respond with NONE.",
                model=model,
                temperature=0.1,
                max_tokens=64,
                custom_endpoint=custom_endpoint,
                conversation_id=cid
            )
            sel_text = sel_res.get("content", "").strip()

            chosen_skill = None
            for s in all_skills:
                if s["folder_name"].lower() in sel_text.lower() or s["name"].lower() in sel_text.lower():
                    chosen_skill = skill_manager.get_skill_by_folder(s["folder_name"])
                    break

            if chosen_skill:
                matched_skills = [chosen_skill]
            step_skill_elapsed = round((time.time() - step_skill_start) * 1000, 2)

        else:
            # Specific skill folder selected by user
            chosen_skill = skill_manager.get_skill_by_folder(skills_mode)
            if chosen_skill:
                matched_skills = [chosen_skill]

        # Step 3: Handle Case Where No Skill is Found / Selected
        step_plan_elapsed = 0.0
        step_tool_elapsed = 0.0
        step_rag_elapsed = 0.0
        step_syn_elapsed = 0.0
        tool_plan_text = ""
        llm_result: Dict[str, Any] = {}
        highest_skill = matched_skills[0] if matched_skills else None

        if not highest_skill:
            # Per SPECIFICATION.md: "If no skill is found, send the user query to the LLM using the simple system prompt as an assistant to answer the question."
            step_syn_start = time.time()
            llm_result = llm_service.generate_response(
                prompt=f"User Question: {query}\n\nAnswer the user directly and concisely.",
                system_instruction="You are a helpful AI assistant. Answer the question directly and concisely.",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                custom_endpoint=custom_endpoint,
                conversation_id=cid
            )
            step_syn_elapsed = round((time.time() - step_syn_start) * 1000, 2)
            agent_answer = llm_result.get("content", "")

        else:
            # Step 4: Skill Found - Call LLM to get instruction or plan for tool execution
            # Per SPECIFICATION.md: "If there are skills found, send the user message and the skills to the LLM to get the instruction or plan for the tool execution."
            step_plan_start = time.time()
            skill_text = (
                f"- Skill: {highest_skill['name']}\n"
                f"  Folder: {highest_skill.get('folder_name')}\n"
                f"  Description: {highest_skill['description']}\n"
                f"  SOP / Instructions:\n{highest_skill.get('full_text', '')[:450]}"
            )

            plan_prompt = (
                f"User Question: {query}\n\n"
                f"Highest Matching Skill:\n{skill_text}\n\n"
                f"Analyze the user question and provide a tool execution plan for the Agent. "
                f"If the user question is general knowledge or cannot be answered by this skill, state 'DIRECTIVE: NO_TOOL_NEEDED'. "
                f"If document retrieval from the document vector store is required and this skill is document-retriever-skill, explicitly state 'DIRECTIVE: EXECUTE_DOCUMENT_SEARCH' with the search query. "
                f"If this procedural tool should be executed, state 'DIRECTIVE: EXECUTE_TOOL: {highest_skill['name']}'."
            )

            plan_res = llm_service.generate_response(
                prompt=plan_prompt,
                system_instruction="You are an AI Agent Orchestrator. Formulate a precise tool execution plan based on the matching skill.",
                model=model,
                temperature=temperature,
                max_tokens=1024,
                custom_endpoint=custom_endpoint,
                conversation_id=cid
            )
            tool_plan_text = plan_res.get("content", "")
            step_plan_elapsed = round((time.time() - step_plan_start) * 1000, 2)

            # Execution loop limited to max_turns (no more than MAX_TURNS_LIMIT)
            # Per SPECIFICATION.md: "If the LLM determines that a procedural tool should be executed, execute the tool to obtain the needed information. Send a prompt to the LLM with the results from the tool. Repeat until the final answer is received. Limit the number of loops no more than MAX_LLM_TURNS."
            turns_limit = min(max(1, int(max_turns)), MAX_TURNS_LIMIT)
            current_turn = 1
            has_doc_skill = ("retriever" in highest_skill.get("folder_name", "").lower() or "document" in highest_skill.get("folder_name", "").lower())
            latest_plan = tool_plan_text

            agent_answer = ""

            while current_turn <= turns_limit:
                plan_lower = latest_plan.lower()
                no_tool_needed = (
                    "no_tool_needed" in plan_lower or
                    "no tool needed" in plan_lower or
                    "no tool is relevant" in plan_lower or
                    "no tool required" in plan_lower
                )

                # 1. Document Search if directed
                if has_doc_skill and any(term in plan_lower for term in ["execute_document_search", "document search", "search document", "retrieve document"]):
                    step_rag_start = time.time()
                    audit_logger.log_call(
                        event_type="document search",
                        call_type="invocation",
                        invoker="agent",
                        recipient="document search",
                        payload={"query": query, "top_k": max_rag_chunks, "min_score": doc_threshold},
                        description=f"Message sent to document search for: '{query}' (directed by model plan, threshold: {doc_threshold})",
                        conversation_id=cid
                    )
                    doc_chunks = doc_vector_store.query_similar(query, top_k=max_rag_chunks, min_score=doc_threshold, conversation_id=cid, invoker="document search")
                    audit_logger.log_call(
                        event_type="document search",
                        call_type="response",
                        invoker="document search",
                        recipient="agent",
                        payload={
                            "retrieved_chunks": [
                                {
                                    "doc_name": c.get("metadata", {}).get("document_name"),
                                    "chunk_index": c.get("metadata", {}).get("chunk_index"),
                                    "score": c.get("score"),
                                    "text": c.get("text")
                                }
                                for c in doc_chunks
                            ],
                            "count": len(doc_chunks)
                        },
                        description=f"Response received from document search: {len(doc_chunks)} chunks retrieved",
                        conversation_id=cid
                    )
                    for chunk in doc_chunks:
                        meta = chunk.get("metadata", {})
                        doc_name = meta.get("document_name", "Document")
                        evidence_item = {
                            "step": "Document Search",
                            "title": f"Doc: {doc_name} (Chunk #{meta.get('chunk_index', 0)}, Score: {chunk['score']})",
                            "score": chunk["score"],
                            "content": chunk["text"],
                            "details": meta
                        }
                        retrieved_evidence.append(evidence_item)
                        doc_context_snippets.append(f"[From {doc_name}]:\n{chunk['text']}")
                    step_rag_elapsed += round((time.time() - step_rag_start) * 1000, 2)

                # 2. Procedural Tool if directed
                elif not has_doc_skill and not no_tool_needed:
                    folder_name = highest_skill.get("folder_name", "")
                    skill_kw = folder_name.replace("-skill", "").split("-")
                    is_relevant = any(kw in plan_lower for kw in skill_kw) or "execute_tool" in plan_lower or not latest_plan
                    if is_relevant:
                        step_tool_start = time.time()
                        exec_result = skill_manager.execute_skill(highest_skill, query, conversation_id=cid)
                        evidence_item = {
                            "step": "Skill Search",
                            "title": f"Skill: {highest_skill['name']} (Score: {highest_skill['score']})",
                            "score": highest_skill["score"],
                            "content": exec_result.get("evidence_text", ""),
                            "details": exec_result.get("result_data", {})
                        }
                        retrieved_evidence.append(evidence_item)
                        skill_context_snippets.append(f"[{highest_skill['name']} Execution Output]: {exec_result.get('evidence_text', '')}")
                        step_tool_elapsed += round((time.time() - step_tool_start) * 1000, 2)

                # Send prompt to LLM with cumulative results from tools
                context_block = ""
                if tool_plan_text:
                    context_block += f"--- Orchestrator Tool Plan ---\n{tool_plan_text.strip()}\n\n"
                if skill_context_snippets:
                    context_block += "--- Skill Tool Execution Outputs ---\n" + "\n\n".join(skill_context_snippets) + "\n\n"
                if doc_context_snippets:
                    context_block += "--- Document Vector DB Chunks ---\n" + "\n\n".join(doc_context_snippets) + "\n"

                system_instruction = (
                    "You are an advanced AI Agent equipped with Retrieval-Augmented Generation (RAG) and dynamic tool execution. "
                    "Always synthesize answers grounded factually in the provided evidence. "
                    "If specific metrics, figures, names, or real-time status are present in the context, present them clearly."
                )

                if context_block.strip():
                    full_prompt = (
                        f"User Question: {query}\n\n"
                        f"=== RETRIEVED CONTEXT EVIDENCE ===\n"
                        f"{context_block.strip()}\n"
                        f"=== END CONTEXT ===\n\n"
                        f"Provide a helpful, precise, and factually grounded response to the user's question."
                    )
                else:
                    full_prompt = f"User Question: {query}\n\nAnswer the user directly and concisely."

                step_syn_start = time.time()
                llm_result = llm_service.generate_response(
                    prompt=full_prompt,
                    system_instruction=system_instruction,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    custom_endpoint=custom_endpoint,
                    conversation_id=cid
                )
                step_syn_elapsed += round((time.time() - step_syn_start) * 1000, 2)
                agent_answer = llm_result.get("content", "")

                # If final grounded response received without requiring further tool loop, exit loop
                if agent_answer:
                    break

                current_turn += 1

        latency = (time.time() - start_time) * 1000

        # Record telemetry & log final agent response
        telemetry_service.record_event(
            event_type="response",
            model=model,
            input_tokens=llm_result.get("input_tokens", 0),
            output_tokens=llm_result.get("output_tokens", 0),
            latency_ms=latency
        )

        audit_logger.log_call(
            event_type="agent",
            call_type="response",
            invoker="agent",
            recipient="user",
            payload={"response": agent_answer, "content": agent_answer, "evidence_count": len(retrieved_evidence)},
            description="Full response received from the agent",
            conversation_id=cid,
            latency_ms=latency
        )

        # Retrieve all events for this conversation and assemble bubbles showing components that generated logs
        all_conv_events = audit_logger.get_conversation_logs(cid)

        # 1. Skills Component
        skill_logs = [e for e in all_conv_events if e.get("event_type") in ["skill search", "ollama vector"] and (not tool_plan_text or e.get("timestamp") <= all_conv_events[min(len(all_conv_events)-1, 3)].get("timestamp"))]
        steps.append({
            "component": "Skills",
            "icon": "⚡",
            "step_name": "Skills",
            "elapsed_ms": step_skill_elapsed,
            "summary": f"Scanned skill database ({vectorizer_name}). Highest match: {highest_skill['name']} ({highest_skill['score']})" if highest_skill else "No skills matched above threshold.",
            "logs": [e for e in all_conv_events if e.get("event_type") == "skill search"]
        })

        # 2. Agent Component (tool planning by orchestrator using highest scoring skill)
        if highest_skill:
            steps.append({
                "component": "Agent",
                "icon": "🤖",
                "step_name": "Agent",
                "elapsed_ms": step_plan_elapsed,
                "summary": f"Agent evaluated highest-scoring skill '{highest_skill['name']}' and planned tool directives with {model}.",
                "logs": [e for e in all_conv_events if e.get("event_type") == "LLM" and "Highest Matching Skill" in str(e.get("payload", ""))]
            })

        # 3. RAG Component (if document search was performed)
        if step_rag_elapsed > 0:
            rag_logs = [e for e in all_conv_events if e.get("event_type") == "document search"]
            steps.append({
                "component": "RAG",
                "icon": "📚",
                "step_name": "RAG",
                "elapsed_ms": step_rag_elapsed,
                "summary": f"Retrieved {len(doc_chunks)} chunk(s) from document vector store exceeding {MIN_RAG_DOC_SCORE}.",
                "logs": rag_logs
            })

        # 4. Tools Component (if procedural tool was executed)
        if step_tool_elapsed > 0:
            tool_logs = [e for e in all_conv_events if e.get("event_type") in ["tool", "external API call"]]
            steps.append({
                "component": "Tools",
                "icon": "🛠️",
                "step_name": "Tools",
                "elapsed_ms": step_tool_elapsed,
                "summary": f"Executed procedural tool for '{highest_skill['name']}'.",
                "logs": tool_logs
            })

        # 5. LLM Synthesis Component
        synthesis_logs = [e for e in all_conv_events if e.get("event_type") == "LLM" and ("RETRIEVED CONTEXT EVIDENCE" in str(e.get("payload", "")) or "Answer the user directly" in str(e.get("payload", "")))]
        if not synthesis_logs:
            synthesis_logs = [e for e in all_conv_events if e.get("event_type") == "LLM"][-1:]
        steps.append({
            "component": "LLM",
            "icon": "🧠",
            "step_name": "LLM",
            "elapsed_ms": step_syn_elapsed,
            "summary": f"Synthesized final grounded response with {model}.",
            "logs": synthesis_logs
        })

        return {
            "conversation_id": cid,
            "answer": agent_answer,
            "model_used": model,
            "retrieved_evidence": retrieved_evidence,
            "steps": steps,
            "latency_ms": round(latency, 2),
            "tokens": {
                "input": llm_result.get("input_tokens", 0),
                "output": llm_result.get("output_tokens", 0)
            }
        }

# Global singleton
orchestrator = AgentOrchestrator()
