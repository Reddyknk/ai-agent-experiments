"""
Agent Orchestrator Service.
Coordinates intent routing, skill selection, RAG document search,
context evidence grouping by step, LLM synthesis, logging, and telemetry.
"""
import uuid
import time
from typing import Dict, Any, List, Optional

from config import MIN_SKILL_SCORE, MIN_RAG_DOC_SCORE, DEFAULT_LLM_MODEL
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
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main multi-step cognitive pipeline:
        1. Log user prompt & record prompt telemetry
        2. Skill vector search -> match skills with score > MIN_SKILL_SCORE (Step: Skill Search)
        3. If skill matches, call LLM with skill to get execution instruction / plan (Step: Tool Planning)
        4. If skill matches and model directs document search, query document vector DB (Step: Document Search)
           Execute matching procedural tools (Step: Tool Execution)
        5. Assemble categorized context evidence & synthesize answer with LLM (Step: LLM Synthesis)
        6. Record telemetry & return response with steps and logs
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
            payload={"query": query, "model": model, "temperature": temperature, "max_tokens": max_tokens, "max_rag_chunks": max_rag_chunks},
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

        # Step 2: Skill Search Invocation & Response
        vectorizer_name = ollama_service.current_model
        step_skill_start = time.time()
        audit_logger.log_call(
            event_type="skill search",
            call_type="invocation",
            invoker="agent",
            recipient="skill search",
            payload={"query": query, "min_score": MIN_SKILL_SCORE, "vectorizer": vectorizer_name},
            description=f"Message sent to skill search for: '{query}' using vectorizer {vectorizer_name}",
            conversation_id=cid
        )

        matched_skills = skill_manager.match_skills(query, min_score=MIN_SKILL_SCORE, conversation_id=cid)

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

        # Step 3: If skill matches with score > MIN_SKILL_SCORE, call LLM with highest-scoring skill to get execution plan
        tool_plan_text = ""
        model_directed_doc_search = False
        step_plan_elapsed = 0.0
        highest_skill = matched_skills[0] if matched_skills else None

        if highest_skill:
            step_plan_start = time.time()
            skill_text = (
                f"- Skill: {highest_skill['name']}\n"
                f"  Folder: {highest_skill.get('folder_name')}\n"
                f"  Similarity Score: {highest_skill['score']}\n"
                f"  Description: {highest_skill['description']}\n"
                f"  SOP:\n{highest_skill.get('full_text', '')[:400]}"
            )

            plan_prompt = (
                f"User Question: {query}\n\n"
                f"Highest Matching Skill (Score: {highest_skill['score']} > {MIN_SKILL_SCORE}):\n{skill_text}\n\n"
                f"Analyze the user question and provide a tool execution plan for the Agent. "
                f"If the user question is a general knowledge question or cannot be answered by this skill, state 'DIRECTIVE: NO_TOOL_NEEDED'. "
                f"If document retrieval from the document vector store is required and this skill is document-retriever-skill, explicitly state 'DIRECTIVE: EXECUTE_DOCUMENT_SEARCH' with the search query. "
                f"If this procedural tool should be executed, state 'DIRECTIVE: EXECUTE_TOOL: {highest_skill['name']}'."
            )

            plan_res = llm_service.generate_response(
                prompt=plan_prompt,
                system_instruction="You are an AI Agent Orchestrator. Formulate a precise tool execution plan based on the highest matching skill. Determine whether document search or procedural tools must be executed.",
                model=model,
                temperature=temperature,
                max_tokens=1024,
                custom_endpoint=custom_endpoint,
                conversation_id=cid
            )
            tool_plan_text = plan_res.get("content", "")
            step_plan_elapsed = round((time.time() - step_plan_start) * 1000, 2)

            # Check if model directed document search
            plan_lower = tool_plan_text.lower()
            if any(term in plan_lower for term in ["execute_document_search", "document search", "search document", "retrieve document", "vector search"]):
                model_directed_doc_search = True

        # Step 4: Execute Matched Skills & Document Search
        # Only perform vector search for documents when the skill search result and the model direct the Agent to perform the search!
        has_doc_skill = ("retriever" in highest_skill.get("folder_name", "").lower() or "document" in highest_skill.get("folder_name", "").lower()) if highest_skill else False
        doc_chunks = []
        step_rag_elapsed = 0.0

        if has_doc_skill and model_directed_doc_search:
            step_rag_start = time.time()
            audit_logger.log_call(
                event_type="document search",
                call_type="invocation",
                invoker="agent",
                recipient="document search",
                payload={"query": query, "top_k": max_rag_chunks, "min_score": MIN_RAG_DOC_SCORE},
                description=f"Message sent to document search for: '{query}' (directed by model plan)",
                conversation_id=cid
            )
            doc_chunks = doc_vector_store.query_similar(query, top_k=max_rag_chunks, min_score=MIN_RAG_DOC_SCORE, conversation_id=cid, invoker="document search")
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
            step_rag_elapsed = round((time.time() - step_rag_start) * 1000, 2)

        # Execute procedural tool for highest_skill only if directed by model plan
        plan_lower = tool_plan_text.lower()
        no_tool_needed = (
            "no_tool_needed" in plan_lower or
            "no tool needed" in plan_lower or
            "no tool is relevant" in plan_lower or
            "neither skill" in plan_lower or
            "no tool required" in plan_lower
        ) if highest_skill else True

        step_tool_elapsed = 0.0
        if highest_skill and not has_doc_skill and not no_tool_needed:
            folder_name = highest_skill.get("folder_name", "")
            skill_kw = folder_name.replace("-skill", "").split("-")
            is_relevant = any(kw in plan_lower for kw in skill_kw) or "execute_tool" in plan_lower or not tool_plan_text
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
                step_tool_elapsed = round((time.time() - step_tool_start) * 1000, 2)

        # Step 5: Construct Grounded Prompt for Synthesis
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

        # Step 6: LLM Synthesis
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
        step_syn_elapsed = round((time.time() - step_syn_start) * 1000, 2)

        agent_answer = llm_result.get("content", "")
        latency = (time.time() - start_time) * 1000

        # Step 7: Telemetry & Final Response Logging (Response)
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
