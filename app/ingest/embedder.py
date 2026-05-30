"""
Gestione vettori con bge-m3 + LanceDB.

Una tabella LanceDB per corso: ogni riga = una wiki-page.
Schema:
  id         : str  — "{course_id}:{relative_path}"
  course_id  : str
  path       : str  — path relativo (es. "concepts/rag.md")
  title      : str
  category   : str
  content    : str  — corpo del documento (per snippet in risposta)
  vector     : list[float]  — embedding bge-m3 (1024-dim)

Le operazioni sono idempotenti (upsert): reingestire lo stesso file
aggiorna il record senza duplicati.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

import numpy as np


# ---------------------------------------------------------------------------
# Modello di embedding (singleton per processo)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_model():
    """Carica bge-m3 una volta sola. Richiede ~2 GB RAM la prima volta."""
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    return SentenceTransformer(model_name)


def embed(texts: list[str]) -> np.ndarray:
    """Restituisce matrice (N, 1024) di embedding normalizzati."""
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


# ---------------------------------------------------------------------------
# LanceDB helpers
# ---------------------------------------------------------------------------

_LANCEDB_ROOT = os.getenv("LANCEDB_ROOT", "lancedb")
_TABLE_PREFIX = "wiki_"


def _db(course_id: str):
    """Apre (o crea) il database LanceDB per il corso."""
    import lancedb  # noqa: PLC0415
    lancedb_root = os.getenv("LANCEDB_ROOT", _LANCEDB_ROOT)
    db_path = Path(lancedb_root) / course_id
    db_path.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(db_path))


def _schema():
    """Schema PyArrow per la tabella LanceDB."""
    import pyarrow as pa  # noqa: PLC0415
    return pa.schema([
        pa.field("id", pa.string()),
        pa.field("course_id", pa.string()),
        pa.field("path", pa.string()),
        pa.field("title", pa.string()),
        pa.field("category", pa.string()),
        pa.field("content", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 1024)),
    ])


def _table_name(course_id: str) -> str:
    return f"{_TABLE_PREFIX}{course_id.replace('-', '_')}"


def upsert_page(
    course_id: str,
    path: str,
    title: str,
    category: str,
    content: str,
) -> None:
    """
    Inserisce o aggiorna un vettore per la wiki-page indicata.
    L'embedding viene calcolato su title + content.
    """
    import pyarrow as pa  # noqa: PLC0415

    record_id = f"{course_id}:{path}"
    text_to_embed = f"{title}\n\n{content}"
    vector = embed([text_to_embed])[0].tolist()

    row = {
        "id": record_id,
        "course_id": course_id,
        "path": path,
        "title": title,
        "category": category,
        "content": content[:2000],  # tronca per evitare righe enormi
        "vector": vector,
    }

    db = _db(course_id)
    tname = _table_name(course_id)

    if tname in db.table_names():
        tbl = db.open_table(tname)
        # Elimina il vecchio record se esiste, poi inserisci
        try:
            tbl.delete(f"id = '{record_id}'")
        except Exception:
            pass
        tbl.add([row])
    else:
        tbl = db.create_table(tname, schema=_schema())
        tbl.add([row])


def compute_links(
    course_id: str,
    source_path: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Calcola i top-K link semantici dalla pagina sorgente alle altre pagine del corso.
    Restituisce lista di {"target_path": str, "weight": float}.
    Esclude la pagina sorgente stessa.
    """
    db = _db(course_id)
    tname = _table_name(course_id)
    if tname not in db.table_names():
        return []

    tbl = db.open_table(tname)
    record_id = f"{course_id}:{source_path}"

    # Recupera il vettore della pagina sorgente
    rows = tbl.search().where(f"id = '{record_id}'").limit(1).to_list()
    if not rows:
        return []

    source_vec = rows[0]["vector"]

    # Cerca le pagine più simili (top_k+1 per escludere se stessa)
    results = tbl.search(source_vec).limit(top_k + 1).to_list()

    links = []
    for r in results:
        if r["path"] == source_path:
            continue
        dist = float(r.get("_distance", 1.0))
        weight = round(max(0.0, 1.0 - dist), 4)
        links.append({"target_path": r["path"], "weight": weight})
        if len(links) >= top_k:
            break

    return links


def delete_page(course_id: str, path: str) -> None:
    """Rimuove il vettore associato alla wiki-page."""
    db = _db(course_id)
    tname = _table_name(course_id)
    if tname not in db.table_names():
        return
    record_id = f"{course_id}:{path}"
    db.open_table(tname).delete(f"id = '{record_id}'")


def search(
    course_id: str,
    query: str,
    top_k: int = 5,
    bookmark_paths: list[str] | None = None,
    boost: float = 1.5,
) -> List[dict]:
    """
    Ricerca semantica nel vettore store del corso.

    bookmark_paths: pagine preferite dallo studente → ricevono un boost sul punteggio.
    boost: moltiplicatore applicato al _distance score_ (abbassa la distanza, quindi sale in classifica).

    Restituisce lista di dict con campi: id, path, title, category, content, score.
    """
    db = _db(course_id)
    tname = _table_name(course_id)
    if tname not in db.table_names():
        return []

    tbl = db.open_table(tname)
    query_vec = embed([query])[0].tolist()

    # Recuperiamo più risultati di top_k per poi ri-rankare
    fetch_k = max(top_k * 3, 20)
    results = (
        tbl.search(query_vec)
        .limit(fetch_k)
        .to_list()
    )

    if not results:
        return []

    bookmarked = set(bookmark_paths or [])

    # Normalizza distanza in score (0–1, più alto = più rilevante)
    # LanceDB restituisce _distance (cosine distance, 0 = identico)
    def _score(row: dict) -> float:
        dist = row.get("_distance", 1.0)
        base = 1.0 - float(dist)
        if row["path"] in bookmarked:
            base = min(base * boost, 1.0)
        return base

    ranked = sorted(results, key=_score, reverse=True)[:top_k]

    return [
        {
            "id": r["id"],
            "path": r["path"],
            "title": r["title"],
            "category": r["category"],
            "content": r["content"],
            "score": round(_score(r), 4),
        }
        for r in ranked
    ]
