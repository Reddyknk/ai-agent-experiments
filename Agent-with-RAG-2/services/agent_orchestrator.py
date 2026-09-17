"""
Agent Orchestrator Service.
Coordinates intent routing, skill selection, RAG document search,
context evidence grouping by step, LLM synthesis, logging, and telemetry.
"""
import uuid
import time
from typing import Dict, Any, List, Optional

from config import MIN_SKILL_SCORE, MIN_RAG_DOC_SCORE
from services.skill_manager import skill_manager
from services.vector_store import doc_vector_store
from services.llm_service import llm_service
from services.log_service import audit_logger
from services.telemetry_service import telemetry_service

class AgentOrchestrator:
    def process_chat(
        self,
        query: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_rag_chunks: int = 5,
        custom_endpoint: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main multi-step cognitive pipeline:
        1. Log user prompt & record prompt telemetry
        2. Skill vector search -> execute matching tools (Step: Skill Search)
        3. Document vector search -> retrieve chunks (Step: Document Search)
        4. Assemble categorized context evidence
        5. Synthesize answer with LLM
        6. Record telemetry & log final response
        """
        cid = conversation_id or f"conv-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        # Step 1: Log User Prompt
        audit_logger.log_event(
            event_type="User Prompt",
            invoker="user",
            target="agent",
            payload={"query": query, "model": model, "temperature": temperature, "max_tokens": max_tokens, "max_rag_chunks": max_rag_chunks},
            response={"status": "processing"},
            description=f"User prompt: {query}",
            conversation_id=cid
        )

        telemetry_service.record_event(
            event_type="prompt",
            model=model,
            input_tokens=len(query.split())
        )

        retrieved_evidence: List[Dict[str, Any]] = []

        # Step 2: Skill Matching & Evaluation
        audit_logger.log_event(
            event_type="Skill Query",
            invoker="agent",
            target="skill",
            payload={"query": query, "min_score": MIN_SKILL_SCORE},
            response={"status": "evaluating_skills"},
            description=f"Agent querying skill database for: '{query}'",
            conversation_id=cid
        )
        matched_skills = skill_manager.match_skills(query, min_score=MIN_SKILL_SCORE)
        skill_context_snippets = []

        for skill in matched_skills:
            exec_result = skill_manager.execute_skill(skill, query, conversation_id=cid)
            evidence_item = {
                "step": "Skill Search",
                "title": f"Skill: {skill['name']} (Score: {skill['score']})",
                "score": skill["score"],
                "content": exec_result.get("evidence_text", ""),
                "details": exec_result.get("result_data", {})
            }
            retrieved_evidence.append(evidence_item)
            skill_context_snippets.append(f"[{skill['name']} Execution Output]: {exec_result.get('evidence_text', '')}")

        # Step 3: Document Vector Database Search
        audit_logger.log_event(
            event_type="Vector DB Search",
            invoker="agent",
            target="vector database",
            payload={"query": query, "top_k": max_rag_chunks, "min_score": MIN_RAG_DOC_SCORE},
            response={"status": "searching_chunks"},
            description="Agent searching vector database for relevant text chunks",
            conversation_id=cid
        )
        doc_chunks = doc_vector_store.query_similar(query, top_k=max_rag_chunks, min_score=MIN_RAG_DOC_SCORE, conversation_id=cid)
        doc_context_snippets = []

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

        # Step 4: Construct Grounded Prompt for Synthesis
        context_block = ""
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
            full_prompt = f"User Question: {query}\n\nAnswer the user directly and inform them if additional documentation needs to be ingested for specific domain queries."

        # Step 5: LLM Synthesis
        llm_result = llm_service.generate_response(
            prompt=full_prompt,
            system_instruction=system_instruction,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            custom_endpoint=custom_endpoint,
            conversation_id=cid
        )

        agent_answer = llm_result.get("content", "")
        latency = (time.time() - start_time) * 1000

        # Step 6: Telemetry & Final Response Logging
        telemetry_service.record_event(
            event_type="response",
            model=model,
            input_tokens=llm_result.get("input_tokens", 0),
            output_tokens=llm_result.get("output_tokens", 0),
            latency_ms=latency
        )

        audit_logger.log_event(
            event_type="Agent Response",
            invoker="agent",
            target="user",
            payload={"conversation_id": cid},
            response={"content": agent_answer, "evidence_count": len(retrieved_evidence)},
            description="Agent returned final synthesized response to user",
            conversation_id=cid,
            latency_ms=latency
        )

        return {
            "conversation_id": cid,
            "answer": agent_answer,
            "model_used": model,
            "retrieved_evidence": retrieved_evidence,
            "latency_ms": round(latency, 2),
            "tokens": {
                "input": llm_result.get("input_tokens", 0),
                "output": llm_result.get("output_tokens", 0)
            }
        }

# Global singleton
orchestrator = AgentOrchestrator()
