---
name: Document Vector Database Retriever Skill
description: Retrieve relevant context text chunks from the local document vector database with similarity score exceeding MIN_RAG_DOC_SCORE (0.3) for factual grounding.
Trigger Queries:
  - What does our company marketing strategy say about enterprise acquisition?
  - Retrieve details from the annual financial report about revenue and operating expenses
  - Explain the architecture of Agent and RAG technology from our documents
  - Search internal documents for financial projections and ARR growth
  - What are our customer retention metrics according to the marketing documentation?
---

# Document Vector Database Retriever Skill

## Overview
This skill performs semantic vector similarity search against the document vector database (`database/doc_vectors.json`). It returns text chunks whose cosine similarity score exceeds `MIN_RAG_DOC_SCORE` (default: 0.3), supplying verifiable context evidence to ground LLM reasoning.

## Standard Operating Procedure (SOP)
1. **Analyze User Inquiry**: Formulate dense semantic search representation from the user's question.
2. **Execute Vector Search**:
   - Query the document vector store with the query embedding.
   - Filter chunks where similarity score >= `MIN_RAG_DOC_SCORE`.
   - Limit to top-K chunks specified by the user interface (RAG max chunks parameter).
3. **Assemble Evidence**:
   - Package matched chunks with source document title, chunk index, character length, and similarity score.
   - Ground the final answer directly in this retrieved evidence.
