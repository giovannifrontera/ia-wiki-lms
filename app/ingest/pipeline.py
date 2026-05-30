"""
Orchestratore dell'ingest pipeline.

Flusso per ogni file del corso:
  1. Scarica il file dal LMS (MoodleClient)
  2. Estrai i chunk di testo (extractor)
  3. Per ogni chunk → chiedi all'LLM di generare una wiki-page
  4. Scrivi il file .md in modo atomico (wiki_writer)
  5. Calcola embedding e fai upsert su LanceDB (embedder)
  6. Salva il record WikiPage nel DB relazionale

Il chiamante (endpoint FastAPI) passa course_id e db session;
la pipeline usa os.getenv per leggere credenziali LMS e LLM.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.core.moodle_client import MoodleClient, MoodleFile
from app.db.models import WikiPage
from app.ingest import embedder, extractor, wiki_writer
from app.ingest.extractor import TextChunk
from app.ingest.wiki_writer import WikiPageData

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM helper — genera la wiki-page da un chunk
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Sei un assistente specializzato in pedagogia. Dato un estratto di materiale didattico,
genera una wiki-page in italiano con:
- title: titolo breve e specifico del concetto/entità
- category: "concepts" (per idee astratte, metodi, teorie) o "entities" (per definizioni, \
termini, persone, strumenti specifici)
- content: spiegazione chiara e completa in Markdown (2–5 paragrafi, mai elenchi vuoti)

Rispondi SOLO con JSON valido, senza testo extra:
{"title": "...", "category": "concepts|entities", "content": "..."}
"""


def _llm_generate_page(chunk: TextChunk) -> WikiPageData | None:
    """Chiama l'LLM per trasformare un TextChunk in una WikiPageData."""
    import json  # noqa: PLC0415

    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    source_ref = f"{'slide' if chunk.source_type == 'pptx' else 'page'} {chunk.page_or_slide}"
    user_content = (
        f"Materiale: {chunk.source_file} ({source_ref})\n\n"
        f"---\n{chunk.text}\n---"
    )

    raw = ""
    try:
        if provider == "anthropic":
            import anthropic  # noqa: PLC0415
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            response = client.messages.create(
                model=os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text
        elif provider == "openai":
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            response = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content
        else:
            raise ValueError(f"LLM_PROVIDER non supportato: {provider!r}")

        data = json.loads(raw)
        return WikiPageData(
            title=data["title"],
            category=data["category"],
            content=data["content"],
            source_file=chunk.source_file,
            source_ref=source_ref,
        )
    except Exception as exc:
        log.warning("LLM generation failed per chunk '%s' (%s): %s", chunk.source_file, source_ref, exc)
        # Fallback: crea una pagina grezza dal testo del chunk
        title = chunk.text.split("\n")[0][:80] or f"{chunk.source_file} {source_ref}"
        return WikiPageData(
            title=title,
            category="concepts",
            content=chunk.text,
            source_file=chunk.source_file,
            source_ref=source_ref,
        )


# ---------------------------------------------------------------------------
# Orchestratore principale
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    course_id: str
    files_processed: int
    pages_created: int
    errors: List[str]


def run_ingest(course_id: str, workspace_path: str, moodle_course_id: str, db: Session) -> IngestResult:
    """
    Scarica tutti i file supportati dal corso LMS, li processa e popola il wiki.

    Richiede le variabili d'ambiente:
      MOODLE_URL, MOODLE_TOKEN  — credenziali LMS
      ANTHROPIC_API_KEY o OPENAI_API_KEY + LLM_PROVIDER
    """
    moodle_url = os.environ["MOODLE_URL"]
    moodle_token = os.environ["MOODLE_TOKEN"]
    client = MoodleClient(base_url=moodle_url, token=moodle_token)

    # Ripulisci eventuali file parziali da crash precedenti
    wiki_writer.cleanup_orphans(workspace_path)

    files: List[MoodleFile] = client.list_course_files(moodle_course_id)
    pages_created = 0
    errors: List[str] = []

    for mfile in files:
        try:
            log.info("Ingest: scaricando %s (%d bytes)", mfile.filename, mfile.filesize)
            content = client.download_file(mfile.fileurl)

            chunks = extractor.extract(content, mfile.filename, mfile.mimetype)
            log.info("  → %d chunk estratti", len(chunks))

            for chunk in chunks:
                page_data = _llm_generate_page(chunk)
                if page_data is None:
                    continue

                # Scrivi .md
                final_path = wiki_writer.write_page(workspace_path, page_data)
                relative_path = str(final_path.relative_to(workspace_path))

                # Embedding + LanceDB
                embedder.upsert_page(
                    course_id=course_id,
                    path=relative_path,
                    title=page_data.title,
                    category=page_data.category,
                    content=page_data.content,
                )

                # DB relazionale
                page_id = f"{course_id}:{relative_path}"
                existing = db.get(WikiPage, page_id)
                if existing:
                    existing.title = page_data.title
                    existing.category = page_data.category
                else:
                    db.add(WikiPage(
                        id=page_id,
                        path=relative_path,
                        title=page_data.title,
                        category=page_data.category,
                        course_id=course_id,
                        source="ingest",
                    ))

                # Calcola e salva link semantici
                from app.db.models import PageLink as _PageLink  # noqa: PLC0415
                semantic_links = embedder.compute_links(course_id, relative_path, top_k=5)
                for lnk in semantic_links:
                    link_id = f"{course_id}:{relative_path}:{lnk['target_path']}"
                    if not db.get(_PageLink, link_id):
                        db.add(_PageLink(
                            id=link_id,
                            course_id=course_id,
                            source_path=relative_path,
                            target_path=lnk["target_path"],
                            weight=str(lnk["weight"]),
                            link_type="semantic",
                        ))

                pages_created += 1

            db.commit()
            log.info("  → %d pagine create per %s", len(chunks), mfile.filename)

        except Exception as exc:
            db.rollback()
            msg = f"{mfile.filename}: {exc}"
            log.error("Ingest error: %s", msg)
            errors.append(msg)

    return IngestResult(
        course_id=course_id,
        files_processed=len(files),
        pages_created=pages_created,
        errors=errors,
    )
