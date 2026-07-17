# Atlas

**A production-grade knowledge retrieval engine for enterprise AI applications.**

Atlas is an agentic, hybrid-retrieval platform built to eliminate hallucinations and solve the attribution gap in modern Retrieval-Augmented Generation (RAG). By combining dense vector similarity with exact keyword matching and deterministic character-level tracking, Atlas delivers verifiable, auditable answers from complex document libraries.

---

## Core Architecture & Capabilities

### 1. Hybrid Retrieval Engine (Dense + Lexical)
Atlas does not rely solely on dense embeddings, which frequently struggle with exact acronyms, serial numbers, and technical terminology.
- **Dense Vector Retrieval:** Powered by local `BGE-large` embeddings stored and indexed in high-performance **Qdrant** vector spaces using Approximate Nearest Neighbor (ANN) search.
- **Lexical Keyword Search:** Concurrent **BM25** sparse retrieval targeting exact term occurrences and technical jargon.
- **Reciprocal Rank Fusion (RRF):** Dynamically merges and normalizes scores across both retrieval strategies to surface optimal passages.

### 2. Exact Attribution & Character-Level Grounding
Most RAG applications cite entire pages or large chunks, leaving users to manually verify claims. Atlas introduces high-precision provenance:
- **Normalized Ingestion Schema:** Custom multi-format extractors (`PDF`, `Markdown`, `TXT`) parse documents into structured hierarchies of pages, bounding boxes, and classified content blocks (`TEXT`, `IMAGE`, `TABLE`).
- **Exact Offset Tracking:** Every generated chunk records absolute `char_start` and `char_end` coordinates relative to the source document, enabling instant click-to-source highlighting in user interfaces.

### 3. Agentic Query Resolution & Self-Correction
Atlas replaces rigid, linear retrieval chains with stateful, decision-driven workflows built on **LangGraph**:
- **Relevance Grading:** Retrieved passages pass through an automated cross-encoder (`bge-reranker-large`) and relevance grader before reaching the generation stage.
- **Dynamic Query Rewriting:** When ambiguous or multi-turn queries yield low-confidence results, the agent autonomously rewrites the prompt using historical context and re-queries the index.
- **Hallucination Guardrails:** If retrieved passages fail to meet strict confidence thresholds after self-correction, Atlas triggers a deterministic refusal rather than fabricating an answer.

---

## Technical Specifications

| Component | Technology | Role |
| :--- | :--- | :--- |
| **API Framework** | FastAPI (Async Python 3.12) | High-throughput, non-blocking HTTP REST & Streaming (SSE) layer |
| **Vector Storage** | Qdrant | Local & cloud-ready vector database with custom payload filtering |
| **Metadata Storage** | PostgreSQL 16 + SQLAlchemy 2.0 | Relational store for document states, chunk boundaries, and audit logs |
| **Document Parsing** | PyMuPDF (fitz) + MarkdownIt | Deep structural extraction and bounding-box calculation |
| **Agentic Loop** | LangGraph | Graph-based state machine handling conditional reasoning and retries |
| **Embeddings & Reranking** | BGE-large & BGE-reranker | Local high-dimensional semantic representations and cross-encoder scoring |

---

## API Reference Overview

<details>
<summary><b>Document Ingestion API</b></summary>

### `POST /ingestion/upload`
Ingests raw documents, extracts structural hierarchy, computes character offsets, and registers metadata.

**Supported MIME Types:**
- `application/pdf`
- `text/markdown`
- `text/plain`

**Response Payload:**
```json
{
  "id": "f7174a8f-6407-46c9-9e34-72307a797c19",
  "filename": "enterprise_architecture_v2.pdf",
  "file_type": "application/pdf",
  "size_bytes": 936262,
  "status": "processing",
  "uploaded_at": "2026-07-17T16:09:34.950Z"
}
```
</details>

<details>
<summary><b>System Diagnostics API</b></summary>

### `GET /health`
Validates real-time connection status across the REST service, PostgreSQL storage, and Qdrant cluster.
</details>

---

## Quickstart (Locally Hosted)

Atlas is containerized for zero-friction local deployment.

### Prerequisites
- Docker Engine & Docker Compose
- Python 3.12+

### 1. Launch Infrastructure
Start the local PostgreSQL and Qdrant instances:
```bash
docker compose up -d
```

### 2. Initialize Backend Environment
Configure virtual environment and apply database schema migrations:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
```

### 3. Start the Engine
Launch the async API server:
```bash
uvicorn app.main:app --reload --port 8000
```
Access the interactive OpenAPI documentation at `http://localhost:8000/docs`.

---

## License

Copyright (c) 2026. All rights reserved.