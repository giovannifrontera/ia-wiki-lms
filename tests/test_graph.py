"""Test del grafo della conoscenza: compute_links e endpoint /graph."""
import pytest
from unittest.mock import patch, MagicMock


def test_compute_links_returns_empty_when_no_table():
    """Se LanceDB non ha ancora la tabella del corso, restituisce lista vuota."""
    from app.ingest.embedder import compute_links
    result = compute_links(course_id="corso-vuoto-xyz", source_path="concepts/rag.md")
    assert result == []


def test_compute_links_excludes_self(tmp_path, monkeypatch):
    """La pagina sorgente non deve comparire tra i propri link."""
    monkeypatch.setenv("LANCEDB_ROOT", str(tmp_path))

    from app.ingest import embedder

    # Popola 3 pagine
    for i in range(3):
        embedder.upsert_page(
            course_id="c1",
            path=f"concepts/page{i}.md",
            title=f"Pagina {i}",
            category="concepts",
            content="Testo di esempio per la pagina " + str(i),
        )

    links = embedder.compute_links(course_id="c1", source_path="concepts/page0.md", top_k=5)
    paths = [l["target_path"] for l in links]
    assert "concepts/page0.md" not in paths
    assert all("weight" in l for l in links)
    assert all(0.0 <= float(l["weight"]) <= 1.0 for l in links)


def test_graph_endpoint_returns_nodes_and_edges(tmp_path, monkeypatch):
    """GET /wiki/{course_id}/graph restituisce nodi e archi del corso."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")

    from importlib import reload
    import app.db.session as sess
    reload(sess)
    sess.init_db()

    from app.db.session import SessionLocal
    from app.db.models import Course, WikiPage, PageLink
    db = SessionLocal()

    course_id = "graph-test-course"
    course = Course(
        course_id=course_id,
        moodle_course_id="m-graph",
        workspace_path=str(tmp_path),
        lti_client_id="dev",
    )
    db.add(course)
    db.add(WikiPage(id=f"{course_id}:concepts/rag.md", path="concepts/rag.md",
                    title="RAG", category="concepts", course_id=course_id, source="ingest"))
    db.add(WikiPage(id=f"{course_id}:entities/llm.md", path="entities/llm.md",
                    title="LLM", category="entities", course_id=course_id, source="ingest"))
    db.add(PageLink(
        id=f"{course_id}:concepts/rag.md:entities/llm.md",
        course_id=course_id,
        source_path="concepts/rag.md",
        target_path="entities/llm.md",
        weight="0.85",
        link_type="semantic",
    ))
    db.commit()
    db.close()

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get(f"/wiki/{course_id}/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data and "edges" in data
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["edges"][0]["weight"] == 0.85
    assert data["edges"][0]["type"] == "semantic"
