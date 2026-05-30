"""
Endpoint per leggere il wiki del corso.

GET /wiki/{course_id}/pages
  → lista di tutte le wiki-page del corso (id, path, title, category, bookmarked)

GET /wiki/{course_id}/pages/{path:path}
  → contenuto markdown della pagina (raw) + metadati
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db.models import Bookmark, Course, WikiPage, PageLink
from app.db.session import get_db
from app.ingest.wiki_writer import read_page

router = APIRouter()


class PageSummary(BaseModel):
    path: str
    title: str
    category: str
    bookmarked: bool


class PageDetail(BaseModel):
    path: str
    title: str
    category: str
    content: str          # markdown grezzo
    bookmarked: bool


@router.get("/wiki/{course_id}/pages", response_model=list[PageSummary])
def list_pages(
    course_id: str,
    student_id: str = Query(default=""),
    db=Depends(get_db),
):
    course: Course | None = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, f"Corso non trovato: {course_id}")

    pages = db.query(WikiPage).filter_by(course_id=course_id).all()

    bookmarked_paths: set[str] = set()
    if student_id:
        bms = db.query(Bookmark).filter_by(
            student_id=student_id, course_id=course_id
        ).all()
        bookmarked_paths = {b.page_path for b in bms}

    return [
        PageSummary(
            path=p.path,
            title=p.title,
            category=p.category,
            bookmarked=p.path in bookmarked_paths,
        )
        for p in pages
    ]


@router.get("/wiki/{course_id}/pages/{path:path}", response_model=PageDetail)
def get_page(
    course_id: str,
    path: str,
    student_id: str = Query(default=""),
    db=Depends(get_db),
):
    course: Course | None = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, f"Corso non trovato: {course_id}")

    page_id = f"{course_id}:{path}"
    page: WikiPage | None = db.get(WikiPage, page_id)
    if not page:
        raise HTTPException(404, f"Pagina non trovata: {path}")

    try:
        content = read_page(course.workspace_path, path)
    except FileNotFoundError:
        content = "*Contenuto non disponibile sul disco.*"

    bookmarked = False
    if student_id:
        bm_id = f"{student_id}:{path}"
        bookmarked = db.get(Bookmark, bm_id) is not None

    return PageDetail(
        path=page.path,
        title=page.title,
        category=page.category,
        content=content,
        bookmarked=bookmarked,
    )


class GraphNode(BaseModel):
    id: str          # path relativo
    title: str
    category: str


class GraphEdge(BaseModel):
    source: str      # path sorgente
    target: str      # path destinazione
    weight: float
    type: str        # "semantic"


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@router.get("/wiki/{course_id}/graph", response_model=GraphResponse)
def get_graph(course_id: str, db=Depends(get_db)):
    course: Course | None = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, f"Corso non trovato: {course_id}")

    pages = db.query(WikiPage).filter_by(course_id=course_id).all()
    links = db.query(PageLink).filter_by(course_id=course_id).all()

    nodes = [GraphNode(id=p.path, title=p.title, category=p.category) for p in pages]
    edges = [
        GraphEdge(
            source=lnk.source_path,
            target=lnk.target_path,
            weight=float(lnk.weight),
            type=lnk.link_type,
        )
        for lnk in links
    ]
    return GraphResponse(nodes=nodes, edges=edges)
