# PRD — Production-Grade Retrieval Engine (RAG Platform)

## 1. Problem Statement
Most RAG tutorials retrieve top-k chunks and pipe them straight to an LLM. This produces irrelevant
context, hallucinated answers, no citations, no confidence estimate, and no way to debug retrieval
quality. This project builds a retrieval system with evaluation, observability, and a self-correcting
retrieval loop — closer to what an enterprise AI assistant actually needs than a chatbot demo.

## 2. Goals
- Answer questions strictly from uploaded documents, with citations.
- Detect and refuse low-confidence answers instead of hallucinating.
- Make retrieval quality measurable (metrics, not vibes).
- Demonstrate an actual agentic retrieval loop (not a static chain) using LangGraph.

## 3. Non-Goals (v1)
- Multi-tenant auth / RBAC — not needed for a portfolio deployment.
- Horizontal scaling / distributed workers — demonstrate the *pattern*, not production scale.
- Supporting every document format — PDF + Markdown/TXT is enough to prove the pipeline; HTML/URL
  ingestion is a stretch add.

## 4. Scope Split — MVP (v1) vs Stretch (v2)

This is the change from the original doc: build a **working, demoable core in ~3–4 weeks**, then
layer maturity features only if time remains before you need this ready.

### MVP — must work end-to-end
| # | Feature |
|---|---|
| 1 | Document ingestion: PDF + MD/TXT only |
| 2 | Chunking: Recursive + Markdown-aware (skip semantic/sliding-window/parent-child for v1) |
| 3 | Embedding pipeline (BGE-large) + Qdrant storage |
| 4 | Hybrid retrieval: dense + BM25, merged |
| 5 | Cross-encoder reranking (BGE-reranker-large) |
| 6 | **Agentic loop in LangGraph**: retrieve → grade relevance → if weak, rewrite query and retry once → generate |
| 7 | Confidence scoring (retrieval score + reranker score + grounding check) |
| 8 | Hallucination guard (explicit refuse-to-answer path) |
| 9 | Source attribution (doc name, page, chunk id, similarity) |
| 10 | Core REST API (upload, query, list/delete docs, health) |

### Stretch — add only after MVP is fully working and documented
| # | Feature |
|---|---|
| 11 | Semantic / sliding-window / parent-child chunking + strategy comparison |
| 12 | RAGAS/DeepEval benchmark suite (100–300 Qs) with auto-generated reports |
| 13 | Observability dashboard (latency breakdown, token cost, prompt/response inspector) |
| 14 | Embedding + query + semantic caching |
| 15 | Async ingestion queue (arq, not Celery — see notes) |
| 16 | HTML / URL ingestion |

**Rule:** don't start a stretch item until every MVP item has a passing test and a README section.

## 5. Architecture (revised)

```
Upload → Clean → Extract Metadata → Chunk → Embed → Store (Qdrant + Postgres metadata)

Query → Embed Query
      → [LangGraph loop]
           Dense Retrieval ─┐
           BM25 Retrieval ──┼→ Merge → Rerank (cross-encoder)
                             └→ Relevance Grade
                                 ├─ if weak → Rewrite Query → retry (max 1 retry)
                                 └─ if strong → Build Context
      → Confidence Score (retrieval + reranker + grounding)
      → if below threshold → refuse ("couldn't find enough relevant information...")
      → else → LLM generate with citations
```

The retry/grade/rewrite loop is the part that actually uses LangGraph as a graph rather than a
chain — this is the differentiator worth spending real time on.

## 6. Tech Stack (revised from original)

| Layer | Original | Recommended | Why |
|---|---|---|---|
| Orchestration | LangChain + LangGraph | LangGraph only (LangChain utils where needed) | avoid redundant frameworks |
| Async jobs | Celery | FastAPI BackgroundTasks → arq if you need a real queue | Celery's ops overhead isn't worth it solo |
| Embeddings | BAAI bge-large | keep | still solid, self-hosted, free |
| Vector DB | Qdrant | keep | good docs, easy local Docker |
| Reranker | bge-reranker-large | keep | |
| DB | PostgreSQL | keep | metadata, eval results |
| Cache | Redis | keep, stretch-phase only | |
| Eval | Ragas / DeepEval | keep, stretch-phase only | |

## 7. API Contract (MVP)
```
POST   /documents/upload
POST   /query
GET    /documents
DELETE /documents/{id}
GET    /health
```
Add `/metrics` and `/evaluation` only in stretch phase once there's something real to expose.

## 8. Success Criteria
- A query against an uploaded doc returns an answer with correct citations >90% of the time on a
  small hand-built test set (20–30 Qs is enough for MVP — don't build the 300-Q benchmark yet).
- A query with no supporting content in the corpus triggers the refusal path, not a hallucination.
- The rewrite/retry loop demonstrably changes behavior on at least a few test queries (log before/after).

---

# Workflow — How to Actually Build This

## Weekly structure (MVP target: 3–4 weeks)

| Week | Focus | Exit condition |
|---|---|---|
| 1 | Phase 1–2: Docker/FastAPI/Qdrant/Postgres setup, ingestion + chunking | Can upload a PDF and see chunks stored with metadata |
| 2 | Phase 3–4: embeddings, dense search, hybrid (BM25) retrieval, basic answer with citations | Can ask a question and get a cited answer from real hybrid retrieval |
| 3 | Phase 5–6: reranking + LangGraph agentic loop (grade/rewrite/retry) + confidence scoring + hallucination guard | Refusal path and retry path both demonstrably work on test queries |
| 4 | Polish: README, architecture diagram, 20–30 Q test set, basic unit tests, deploy (Docker Compose) | A stranger could clone the repo, run `docker compose up`, and query it |

Only after week 4 is fully closed out, decide whether to spend more time on stretch items — don't
let them bleed into the MVP weeks.

## Daily working pattern
1. Pick **one** item from the current week's table. Don't touch two phases in the same day.
2. Write the smallest thing that proves the mechanism works (e.g. one query end-to-end) before
   generalizing.
3. Commit at a working checkpoint, not at end-of-day regardless of state.
4. If a bug eats more than ~2 hours, write down what you tried and move to a different sub-task —
   come back with fresh eyes rather than tunneling.

## Git / branching
- `main` — always runnable via `docker compose up`.
- `phase/<n>-<name>` branches per phase (e.g. `phase/3-hybrid-retrieval`), merged to main only when
  the exit condition for that week is met.
- Tag `v1-mvp` once all MVP items are done and documented — this is the resume-ready checkpoint,
  independent of whether you ever get to stretch items.

## Definition of "done" per feature
A feature isn't done when the code runs once — it's done when:
- There's a test (even a manual curl script) that reproduces it.
- It's in the README with a one-line description.
- It survives a fresh `docker compose up` from a clean clone.

## Documentation checklist (do this continuously, not at the end)
- Architecture diagram (the LangGraph loop is worth an actual diagram, not just prose).
- One paragraph per phase on *why* a design choice was made (e.g. "chose hybrid retrieval because
  BM25 alone missed exact-term queries dense search fuzzed over").
- A short "what I'd do differently at scale" section — shows engineering judgment, not just
  execution.

## Risks to watch
- **Scope creep back into the stretch list before MVP is solid** — the original doc's biggest trap.
- **LangGraph used as a rename for a linear chain** — if there's no branching logic, you haven't
  actually used the graph structure; don't claim it on the resume until the retry loop exists.
- **Eval work turning into a black hole** — building a 300-question benchmark before the core loop
  is stable wastes time re-labeling ground truth every time retrieval logic changes. Do a small
  test set first, expand only once the pipeline is stable.
