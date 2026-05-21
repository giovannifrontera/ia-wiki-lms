# ia-wiki-lms

**AI-Wiki-LMS** is an open-source backend that transforms any Moodle course into a living, navigable knowledge ecosystem — going far beyond what a standard RAG chatbot can offer.

> **Status:** Alpha · License: AGPL-3.0 · Built on [ai-wiki-system](https://github.com/giovannifrontera/ai-wiki-system)

---

## The Problem with Standard RAG in Education

Most AI integrations in Learning Management Systems work like this: a student asks a question, the system retrieves relevant document chunks, an LLM generates an answer, and the exchange ends. The next session starts from zero. Knowledge does not accumulate — it evaporates.

This "oracle" pattern has well-known pedagogical costs:
- **Fragmented understanding:** students receive isolated answers, not a connected picture of the subject.
- **Passive consumption:** the AI does the thinking; the student is a spectator.
- **Session amnesia:** nothing persists between conversations; every interaction reinvents the wheel.
- **No explainability path:** answers appear without a navigable structure the student can explore and verify independently.

These are not implementation problems — they are architectural ones. Adding a better embedding model or a bigger context window does not solve them.

---

## A Different Approach: the Wiki-Agent Paradigm

**AI-Wiki-LMS** is built on a fundamentally different premise: instead of answering questions and forgetting them, the AI *curates* a persistent, structured knowledge base — a Wiki — that grows with every interaction and every piece of course material.

The conceptual seed for this approach comes from a [gist by Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), who sketched the idea of an LLM maintaining a persistent markdown wiki as its external memory. This project takes that idea and evolves it substantially:

| Dimension | Karpathy's sketch | AI-Wiki-LMS |
|---|---|---|
| **Persistence** | Single flat file | Structured directory of markdown pages per course |
| **Multi-tenancy** | Single user | Fully isolated workspace per Moodle course |
| **Semantic retrieval** | Plain text | Hybrid vector search (bge-m3 + LanceDB) |
| **Knowledge growth** | Manual | Auto-synthesis: new wiki pages generated from complex queries |
| **Personalization** | None | Bookmark-based RAG boosting per student |
| **LMS integration** | None | Native LTI 1.3 — plugs into Moodle with no code changes |
| **Ingest pipeline** | None | Automatic: PDF/PPTX slides → structured wiki pages |
| **Explainability** | None | Every chatbot response cites internal wiki pages as clickable links |
| **Self-healing** | None | Lint passes remove orphan links and stale content |

---

## How It Works

### For the instructor

Upload slides and PDFs to Moodle as usual. AI-Wiki-LMS automatically intercepts the course materials via the Moodle API, processes them through an ingest pipeline (PDF/PPTX → markdown), and populates a structured wiki for the course. No extra steps. No configuration per lesson.

### For the student

Inside the course, an LTI activity presents a dual interface:

- **Left panel — Wiki navigator:** a browsable network of concepts, entities, and AI-generated synthesis pages. Each page is a Markdown document the student can read, bookmark, and navigate like a subject-specific Wikipedia.
- **Right panel — Contextual chatbot:** a conversational assistant that answers questions by querying the wiki semantically. Every response cites the wiki pages it drew from as clickable links, making the reasoning fully transparent.

### The key innovation: Bookmark-Boosted RAG

When a student bookmarks a wiki page, that page receives a ×1.5 relevance boost in all subsequent semantic searches. This means the chatbot silently adapts to each student's actual study focus — without any explicit personalization step. The student shapes their own AI tutor simply by marking what matters to them.

### Auto-Synthesis

When the chatbot synthesizes an answer that draws from two or more wiki sources and produces a substantive response, it automatically saves the synthesis as a new wiki page. The knowledge base compounds over time: the more it is used, the richer it becomes.

---

## Architecture

```
Moodle (LTI 1.3)
      │
      ▼
┌─────────────────────────────────────┐
│  FastAPI backend (ia-wiki-lms)      │
│                                     │
│  POST /lti/launch  ─► upsert        │
│                       course/student│
│                       in SQLite DB  │
│                                     │
│  Ingest pipeline                    │
│  PDF/PPTX ──► markdown ──► wiki     │
│               pages + embeddings    │
│               (bge-m3 + LanceDB)    │
│                                     │
│  Query RAG                          │
│  question ──► vector search ──► LLM │
│  (bookmark boost)   (hybrid)        │
│                                     │
│  Auto-synthesis                     │
│  complex answer ──► new wiki page   │
└─────────────────────────────────────┘
      │
      ▼
  wiki-works/<course_id>/
  ├── concepts/
  ├── entities/
  └── synthesis/
```

The core wiki engine is provided by **[ai-wiki-system](https://github.com/giovannifrontera/ai-wiki-system)**, a standalone Python library for LLM-maintained persistent wikis with atomic writes, self-healing lint, and hybrid vector search. AI-Wiki-LMS is its native integration layer for Moodle environments.

---

## Pedagogical Rationale

This architecture is grounded in socio-constructivist learning theory (Vygotsky, Bruner). The wiki functions as *structural scaffolding*: a visible, navigable representation of the course's conceptual space that students can explore actively rather than consume passively.

Key properties aligned with evidence-based pedagogy:

- **Explainability over oracle-ness:** every chatbot response links back to wiki pages, giving students a path to verify, deepen, and connect — not just accept.
- **Active knowledge construction:** students navigate a concept network, bookmark what is relevant, and watch the system reflect their focus back in future responses. The AI becomes a mirror of their learning, not a shortcut around it.
- **Persistent scaffolding:** unlike session-based chatbots, the wiki accumulates knowledge over the entire course arc. A student joining in week 8 has access to a knowledge base enriched by all prior interactions.
- **Metacognitive support:** the bookmark mechanism and the navigation structure make the student's own knowledge gaps visible and actionable.

A systematic review of 308 studies on AI agents in LMS environments (PRISMA 2000–2026) confirms that wiki-agent architectures improve conceptual recall substantially (up to 34%, Chen & Wang, 2025) compared to flat RAG or search-based assistants. The review also identifies a critical gap in the literature: no existing open-source framework offers a deep, native LTI 1.3 integration that implements this paradigm. This project is a first step toward filling that gap.

---

## Current Status (Alpha — Plan 1 complete)

- [x] FastAPI server with LTI 1.3 launch endpoint
- [x] SQLAlchemy schema: Course, Student, WikiPage, Bookmark, ChatSession
- [x] Automatic course workspace creation on first LTI launch
- [x] Moodle REST API client (list and download PDF/PPTX files)
- [x] Instructor / student role distinction
- [ ] Ingest pipeline: PDF/PPTX → wiki pages (Plan 2)
- [ ] Query RAG + auto-synthesis (Plan 2)
- [ ] Student chat + wiki sidebar UI (Plan 3)
- [ ] Bookmark-boosted RAG (Plan 3)
- [ ] OIDC login handler for full LTI 1.3 compliance (Plan 2)

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.111+, uvicorn |
| LTI 1.3 | pylti1p3 2.0+ (custom FastAPI adapter) |
| Database | SQLAlchemy 2.0 + Alembic (SQLite dev / PostgreSQL prod) |
| Vector store | LanceDB |
| Embeddings | bge-m3 (local, multilingual) |
| LLM clients | Anthropic, OpenAI (configurable per course) |
| Document parsing | PyPDF2, python-pptx |
| Tests | pytest, pytest-asyncio, httpx |

---

## Quick Start

```bash
git clone https://github.com/giovannifrontera/ia-wiki-lms
cd ia-wiki-lms
pip install -r requirements.txt
cp .env.example .env   # fill in your Moodle credentials
uvicorn app.main:app --reload
# → http://localhost:8000/health
```

---

## Related

- **[ai-wiki-system](https://github.com/giovannifrontera/ai-wiki-system)** — the standalone wiki engine this project builds on
- **[Karpathy's LLM wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)** — the conceptual inspiration for persistent LLM-maintained wikis

---

## License

AGPL-3.0 · Copyright 2026 Giovanni Frontera

Contributions welcome. If you use this in a research context, a citation to the accompanying preprint is appreciated.
