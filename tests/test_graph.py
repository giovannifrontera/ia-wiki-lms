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
