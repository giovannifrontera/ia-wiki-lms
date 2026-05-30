<div align="center">

# ia-wiki-lms

### Architecting Living Knowledge Ecosystems for Higher Education

**ia-wiki-lms** is a specialized LTI 1.3 backend that transforms static course materials into a structured, AI-curated wiki paired with a contextual, evidence-based tutor.

[Vision](#the-vision) · [Pedagogy](#pedagogical-scaffolding) · [Architecture](#the-wiki-agent-paradigm) · [Quick Start](#quick-start)

</div>

---

## The Vision

Most AI integrations in LMS platforms follow a fragmented "Oracle" model: students ask questions, receive isolated chunks of information, and the session ends without building a coherent mental model.

**ia-wiki-lms** shifts the paradigm from *stateless retrieval* to *persistent knowledge construction*. By maintaining a dynamic markdown wiki as the agent's external memory, the system ensures that:

1.  **Knowledge is Navigable:** Concepts are not just retrieved; they are connected in a browsable network.
2.  **Memory is Persistent:** The AI "remembers" and evolves its understanding of the course materials over time.
3.  **Citations are Native:** Every response is grounded in specific wiki pages, fostering student trust and verifiability.

---

## Pedagogical Scaffolding

Grounding AI in **Socio-Constructivist theory** (Vygotsky, Bruner), this system acts as a digital *Scaffold*:

*   **Active Construction:** The wiki acts as a visible representation of the course's conceptual space.
*   **Metacognitive Support:** Through "Bookmark-Boosted RAG", the system silently adapts to each student's specific focus areas.
*   **Compounding Knowledge:** The "Auto-Synthesis" engine generates new wiki pages when the AI identifies non-obvious connections between sources.

---

## The Wiki-Agent Paradigm

Building on [Karpathy's LLM-Wiki concept](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), we implemented a dual-representation architecture:

*   **Markdown Layer:** For human navigation and LLM generation.
*   **Vector Layer (LanceDB):** For high-recall semantic search using the `bge-m3` model.

The two layers are kept in atomic synchronization, ensuring that what the human reads is exactly what the AI understands.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI / LTI 1.3 |
| **Vector DB** | LanceDB |
| **Embeddings** | bge-m3 (Multilingual, 1024-dim) |
| **Database** | SQLAlchemy (PostgreSQL/SQLite) |

---

## Quick Start

```bash
git clone https://github.com/giovannifrontera/ia-wiki-lms
cd ia-wiki-lms
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

---

*Part of the **[AI-Wiki Ecosystem](https://github.com/giovannifrontera/giovannifrontera)** · Developed by Giovanni Frontera, Ph.D.*
