# ia-wiki-lms — Piano 1: Backend Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPI server funzionante che accetta launch LTI 1.3 da Moodle, autentica utenti, crea record corso/studente nel DB, e può interrogare l'API Moodle per listare e scaricare file PDF/PPTX delle risorse di un corso.

**Architecture:** FastAPI + SQLAlchemy (SQLite in dev, PostgreSQL in prod). LTI 1.3 gestito da pylti1p3. Il Moodle client è una classe stateless che wrappa la REST API di Moodle tramite token webservice. Il polo di autenticazione LTI crea automaticamente il workspace per il corso al primo launch.

**Tech Stack:** Python 3.10+, FastAPI 0.111+, pylti1p3 2.0+, SQLAlchemy 2.0+, Alembic 1.13+, pytest 8+, pytest-asyncio, httpx (test client), requests (Moodle client)

**Spec di riferimento:** `docs/superpowers/specs/2026-05-21-moodle-wiki-chatbot-design.md`

---

## Struttura file

```
ia-wiki-lms/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, router registration, /health
│   ├── lti/
│   │   ├── __init__.py
│   │   ├── config.py            # LTI tool config letto da env vars
│   │   └── launch.py            # POST /lti/launch — auth + upsert corso/studente
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models: Course, Student, WikiPage, Bookmark, ChatSession
│   │   └── session.py           # engine, SessionLocal, init_db(), get_db()
│   └── core/
│       ├── __init__.py
│       └── moodle_client.py     # MoodleClient: list_course_files(), download_file()
├── tests/
│   ├── conftest.py              # Fixtures: test DB, mock Moodle, test client
│   ├── test_health.py
│   ├── test_db_models.py
│   ├── test_lti_launch.py
│   └── test_moodle_client.py
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── alembic.ini
├── requirements.txt
├── .env.example
└── wiki-works/                  # git-ignored, creato a runtime
```

---

## Task 1: Scaffold e dipendenze

**Files:**
- Crea: `requirements.txt`
- Crea: `app/__init__.py` (vuoto)
- Crea: `app/main.py`
- Crea: `tests/test_health.py`
- Crea: `tests/conftest.py` (base)
- Crea: `.env.example`

- [ ] **Step 1: Crea `requirements.txt`**

```
# Ereditato da ai-wiki-system
lancedb>=0.6.0
sentence-transformers>=3.0.0
pyarrow>=14.0.0
pandas>=2.0.0
pyyaml>=6.0
requests>=2.31.0

# Backend
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
python-multipart>=0.0.9

# LTI
pylti1p3>=2.0.0
cryptography>=42.0.0

# DB
sqlalchemy>=2.0.0
alembic>=1.13.0

# Conversione documenti
pypdf2>=3.0.0
python-pptx>=0.6.23

# LLM clients
anthropic>=0.25.0
openai>=1.30.0

# Test
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

- [ ] **Step 2: Crea `app/__init__.py`** (file vuoto)

- [ ] **Step 3: Crea `.env.example`**

```
DATABASE_URL=sqlite:///./ia_wiki_lms.db
LTI_CLIENT_ID=your_client_id_from_moodle
LTI_AUTH_LOGIN_URL=https://your-moodle.edu/mod/lti/auth.php
LTI_AUTH_TOKEN_URL=https://your-moodle.edu/mod/lti/token.php
LTI_KEY_SET_URL=https://your-moodle.edu/mod/lti/certs.php
LTI_DEPLOYMENT_ID=1
LTI_ISSUER=https://your-moodle.edu
MOODLE_URL=https://your-moodle.edu
MOODLE_TOKEN=your_webservice_token
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 4: Scrivi il test che fallisce**

`tests/test_health.py`:
```python
from httpx import AsyncClient, ASGITransport
import pytest

@pytest.mark.asyncio
async def test_health(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

`tests/conftest.py`:
```python
import pytest
from app.main import app as fastapi_app

@pytest.fixture
def app():
    return fastapi_app
```

- [ ] **Step 5: Esegui il test — deve fallire**

```bash
cd C:/Users/giova/ia-wiki-lms-plan
pip install -r requirements.txt
pytest tests/test_health.py -v
```
Output atteso: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 6: Crea `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="ia-wiki-lms")

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Esegui il test — deve passare**

```bash
pytest tests/test_health.py -v
```
Output atteso: `PASSED tests/test_health.py::test_health`

- [ ] **Step 8: Commit**

```bash
git add requirements.txt app/ tests/ .env.example
git commit -m "feat: project scaffold — FastAPI app + health endpoint"
```

---

## Task 2: Schema DB e modelli SQLAlchemy

**Files:**
- Crea: `app/db/__init__.py` (vuoto)
- Crea: `app/db/models.py`
- Crea: `app/db/session.py`
- Crea: `alembic.ini`
- Crea: `alembic/env.py`
- Crea: `alembic/versions/001_initial_schema.py`
- Crea: `tests/test_db_models.py`

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_db_models.py`:
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Course, Student, WikiPage, Bookmark, ChatSession
import uuid

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_course(db_session):
    course = Course(
        course_id=str(uuid.uuid4()),
        moodle_course_id="moodle-101",
        workspace_path="wiki-works/abc",
        lti_client_id="client-1",
    )
    db_session.add(course)
    db_session.commit()
    assert db_session.query(Course).count() == 1

def test_create_student_linked_to_course(db_session):
    cid = str(uuid.uuid4())
    course = Course(course_id=cid, moodle_course_id="m-1", workspace_path="wiki-works/x", lti_client_id="c1")
    student = Student(student_id=str(uuid.uuid4()), moodle_user_id="u-1", course_id=cid)
    db_session.add_all([course, student])
    db_session.commit()
    assert db_session.query(Student).filter_by(course_id=cid).count() == 1

def test_bookmark_toggle(db_session):
    cid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    db_session.add(Course(course_id=cid, moodle_course_id="m-2", workspace_path="wp", lti_client_id="c"))
    db_session.add(Student(student_id=sid, moodle_user_id="u-2", course_id=cid))
    bid = f"{sid}:concepts/rag.md"
    bm = Bookmark(id=bid, student_id=sid, course_id=cid, page_path="concepts/rag.md")
    db_session.add(bm)
    db_session.commit()
    assert db_session.query(Bookmark).filter_by(student_id=sid).count() == 1

def test_wiki_page_source_field(db_session):
    cid = str(uuid.uuid4())
    db_session.add(Course(course_id=cid, moodle_course_id="m-3", workspace_path="wp", lti_client_id="c"))
    page = WikiPage(
        id=f"{cid}:concepts/scheduling.md",
        path="concepts/scheduling.md",
        title="Scheduling",
        category="concepts",
        course_id=cid,
        source="ingest",
    )
    db_session.add(page)
    db_session.commit()
    fetched = db_session.query(WikiPage).first()
    assert fetched.source == "ingest"
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
pytest tests/test_db_models.py -v
```
Output atteso: `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Crea `app/db/__init__.py`** (file vuoto)

- [ ] **Step 4: Crea `app/db/models.py`**

```python
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class Course(Base):
    __tablename__ = "courses"
    course_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    moodle_course_id = Column(String, unique=True, nullable=False)
    workspace_path = Column(String, nullable=False)
    lti_client_id = Column(String, nullable=False)
    llm_config = Column(JSON, default=dict)
    students = relationship("Student", back_populates="course")
    wiki_pages = relationship("WikiPage", back_populates="course")

class Student(Base):
    __tablename__ = "students"
    student_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    moodle_user_id = Column(String, nullable=False)
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False)
    course = relationship("Course", back_populates="students")
    bookmarks = relationship("Bookmark", back_populates="student")
    chat_sessions = relationship("ChatSession", back_populates="student")

class WikiPage(Base):
    __tablename__ = "wiki_pages"
    id = Column(String, primary_key=True)  # "{course_id}:{path}"
    path = Column(String, nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)  # entities | concepts | synthesis
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False)
    source = Column(String, nullable=False)  # ingest | synthesis
    created_at = Column(DateTime, server_default=func.now())
    course = relationship("Course", back_populates="wiki_pages")

class Bookmark(Base):
    __tablename__ = "bookmarks"
    id = Column(String, primary_key=True)  # "{student_id}:{page_path}"
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False)
    course_id = Column(String, nullable=False)
    page_path = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    student = relationship("Student", back_populates="bookmarks")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    session_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False)
    messages = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())
    student = relationship("Student", back_populates="chat_sessions")
```

- [ ] **Step 5: Crea `app/db/session.py`**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ia_wiki_lms.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Esegui i test — devono passare**

```bash
pytest tests/test_db_models.py -v
```
Output atteso: `4 passed`

- [ ] **Step 7: Inizializza Alembic**

```bash
alembic init alembic
```

Modifica `alembic/env.py` — sostituisci le righe target_metadata:
```python
# in cima al file, dopo gli import esistenti
from app.db.models import Base
from app.db.session import DATABASE_URL

# sostituisci la riga "target_metadata = None" con:
target_metadata = Base.metadata

# sostituisci la funzione run_migrations_offline():
def run_migrations_offline() -> None:
    url = DATABASE_URL
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

# sostituisci run_migrations_online():
def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connectable = create_engine(DATABASE_URL)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

Genera la migrazione iniziale:
```bash
alembic revision --autogenerate -m "initial schema"
```

Verifica che il file generato in `alembic/versions/` contenga le tabelle courses, students, wiki_pages, bookmarks, chat_sessions.

- [ ] **Step 8: Commit**

```bash
git add app/db/ alembic/ alembic.ini
git commit -m "feat: DB schema — SQLAlchemy models + Alembic migration"
```

---

## Task 3: LTI 1.3 launch endpoint

**Files:**
- Crea: `app/lti/__init__.py` (vuoto)
- Crea: `app/lti/config.py`
- Crea: `app/lti/launch.py`
- Modifica: `app/main.py` — registra router LTI + chiama `init_db()`
- Crea: `tests/test_lti_launch.py`

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_lti_launch.py`:
```python
import pytest
import uuid
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

# Dati LTI simulati che pylti1p3 restituirebbe dopo validazione JWT
MOCK_LAUNCH_DATA = {
    "sub": "moodle-user-42",
    "aud": "lti-client-001",
    "https://purl.imsglobal.org/spec/lti/claim/context": {"id": "moodle-course-99"},
    "https://purl.imsglobal.org/spec/lti/claim/roles": [
        "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
    ],
}

MOCK_INSTRUCTOR_DATA = {
    **MOCK_LAUNCH_DATA,
    "sub": "moodle-instructor-1",
    "https://purl.imsglobal.org/spec/lti/claim/roles": [
        "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"
    ],
}

@pytest.fixture
def app_with_db(tmp_path):
    import os
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    from importlib import reload
    import app.db.session as s
    reload(s)
    s.init_db()
    from app.main import app
    return app

@pytest.mark.asyncio
async def test_student_launch_creates_course_and_student(app_with_db):
    mock_launch = MagicMock()
    mock_launch.get_launch_data.return_value = MOCK_LAUNCH_DATA

    with patch("app.lti.launch.FastApiMessageLaunch.from_request", return_value=mock_launch):
        async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
            response = await client.post("/lti/launch", data={"id_token": "fake"})

    assert response.status_code == 200
    assert "data-role='student'" in response.text

@pytest.mark.asyncio
async def test_instructor_launch_sets_role(app_with_db):
    mock_launch = MagicMock()
    mock_launch.get_launch_data.return_value = MOCK_INSTRUCTOR_DATA

    with patch("app.lti.launch.FastApiMessageLaunch.from_request", return_value=mock_launch):
        async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
            response = await client.post("/lti/launch", data={"id_token": "fake"})

    assert response.status_code == 200
    assert "data-role='instructor'" in response.text

@pytest.mark.asyncio
async def test_second_student_launch_does_not_duplicate(app_with_db):
    mock_launch = MagicMock()
    mock_launch.get_launch_data.return_value = MOCK_LAUNCH_DATA

    with patch("app.lti.launch.FastApiMessageLaunch.from_request", return_value=mock_launch):
        async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
            await client.post("/lti/launch", data={"id_token": "fake"})
            await client.post("/lti/launch", data={"id_token": "fake"})

    from app.db.session import SessionLocal
    from app.db.models import Student
    db = SessionLocal()
    count = db.query(Student).filter_by(moodle_user_id="moodle-user-42").count()
    db.close()
    assert count == 1
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
pytest tests/test_lti_launch.py -v
```
Output atteso: `ModuleNotFoundError: No module named 'app.lti'`

- [ ] **Step 3: Crea `app/lti/__init__.py`** (file vuoto)

- [ ] **Step 4: Crea `app/lti/config.py`**

```python
import os

def get_lti_config() -> dict:
    issuer = os.getenv("LTI_ISSUER", "https://moodle.example.edu")
    return {
        issuer: [{
            "default": True,
            "client_id": os.getenv("LTI_CLIENT_ID", ""),
            "auth_login_url": os.getenv("LTI_AUTH_LOGIN_URL", ""),
            "auth_token_url": os.getenv("LTI_AUTH_TOKEN_URL", ""),
            "key_set_url": os.getenv("LTI_KEY_SET_URL", ""),
            "deployment_ids": [os.getenv("LTI_DEPLOYMENT_ID", "1")],
        }]
    }
```

- [ ] **Step 5: Crea `app/lti/launch.py`**

```python
import uuid
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from pylti1p3.contrib.fastapi import FastApiMessageLaunch
from app.lti.config import get_lti_config
from app.db.session import get_db
from app.db.models import Course, Student

router = APIRouter()

_INSTRUCTOR_ROLES = {
    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
    "http://purl.imsglobal.org/vocab/lis/v2/institution/person#Administrator",
}

def _is_instructor(roles: list) -> bool:
    return any(r in _INSTRUCTOR_ROLES for r in roles)

@router.post("/launch", response_class=HTMLResponse)
async def lti_launch(request: Request, db=Depends(get_db)):
    launch = await FastApiMessageLaunch.from_request(request, get_lti_config())
    data = launch.get_launch_data()

    moodle_course_id = data.get(
        "https://purl.imsglobal.org/spec/lti/claim/context", {}
    ).get("id", "unknown")
    moodle_user_id = data.get("sub", "")
    roles = data.get("https://purl.imsglobal.org/spec/lti/claim/roles", [])
    role = "instructor" if _is_instructor(roles) else "student"

    # Upsert course
    course = db.query(Course).filter_by(moodle_course_id=moodle_course_id).first()
    if not course:
        course_id = str(uuid.uuid4())
        course = Course(
            course_id=course_id,
            moodle_course_id=moodle_course_id,
            workspace_path=f"wiki-works/{course_id}",
            lti_client_id=data.get("aud", ""),
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        # Crea il workspace su disco immediatamente
        import os
        os.makedirs(course.workspace_path, exist_ok=True)

    # Upsert student (non per instructor)
    student_id = ""
    if role == "student":
        student = db.query(Student).filter_by(
            moodle_user_id=moodle_user_id, course_id=course.course_id
        ).first()
        if not student:
            student = Student(
                student_id=str(uuid.uuid4()),
                moodle_user_id=moodle_user_id,
                course_id=course.course_id,
            )
            db.add(student)
            db.commit()
            db.refresh(student)
        student_id = student.student_id

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>ia-wiki-lms</title></head>
<body
  data-role='{role}'
  data-course='{course.course_id}'
  data-student='{student_id}'
>
  <script src="/static/app.js"></script>
</body>
</html>"""
    return HTMLResponse(html)
```

- [ ] **Step 6: Aggiorna `app/main.py`**

```python
from fastapi import FastAPI
from app.db.session import init_db
from app.lti.launch import router as lti_router

app = FastAPI(title="ia-wiki-lms")
app.include_router(lti_router, prefix="/lti")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Esegui tutti i test**

```bash
pytest tests/ -v
```
Output atteso: `7 passed` (4 db + 3 lti + 1 health)

- [ ] **Step 8: Commit**

```bash
git add app/lti/ app/main.py tests/test_lti_launch.py
git commit -m "feat: LTI 1.3 launch — auth + upsert course/student"
```

---

## Task 4: Moodle REST API client

**Files:**
- Crea: `app/core/__init__.py` (vuoto)
- Crea: `app/core/moodle_client.py`
- Crea: `tests/test_moodle_client.py`

- [ ] **Step 1: Scrivi i test che falliscono**

`tests/test_moodle_client.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from app.core.moodle_client import MoodleClient, MoodleFile

MOCK_COURSE_CONTENTS = [
    {
        "id": 1,
        "name": "Lezione 1",
        "modules": [
            {
                "id": 10,
                "name": "Slide SO - Scheduling",
                "contents": [
                    {
                        "type": "file",
                        "filename": "scheduling.pdf",
                        "fileurl": "https://moodle.edu/pluginfile.php/1/scheduling.pdf",
                        "filesize": 102400,
                        "mimetype": "application/pdf",
                        "timemodified": 1700000000,
                    }
                ],
            },
            {
                "id": 11,
                "name": "Video introduttivo",
                "contents": [
                    {
                        "type": "file",
                        "filename": "intro.mp4",
                        "fileurl": "https://moodle.edu/pluginfile.php/1/intro.mp4",
                        "filesize": 5000000,
                        "mimetype": "video/mp4",
                        "timemodified": 1700000001,
                    }
                ],
            },
        ],
    }
]

def make_client():
    return MoodleClient(base_url="https://moodle.edu", token="fake-token")

def test_list_course_files_returns_only_pdf_pptx():
    client = make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_COURSE_CONTENTS
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response):
        files = client.list_course_files("101")

    assert len(files) == 1
    assert files[0].filename == "scheduling.pdf"
    assert files[0].mimetype == "application/pdf"

def test_list_course_files_includes_pptx():
    client = make_client()
    pptx_content = [{
        "id": 2, "name": "S2",
        "modules": [{
            "id": 20, "name": "Slide PPTX",
            "contents": [{
                "type": "file",
                "filename": "deadlock.pptx",
                "fileurl": "https://moodle.edu/pluginfile.php/2/deadlock.pptx",
                "filesize": 51200,
                "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "timemodified": 1700000002,
            }],
        }],
    }]
    mock_response = MagicMock()
    mock_response.json.return_value = pptx_content
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response):
        files = client.list_course_files("102")

    assert len(files) == 1
    assert files[0].filename == "deadlock.pptx"

def test_download_file_appends_token():
    client = make_client()
    mock_response = MagicMock()
    mock_response.content = b"%PDF-1.4 fake content"
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response) as mock_get:
        data = client.download_file("https://moodle.edu/pluginfile.php/1/file.pdf")

    assert data == b"%PDF-1.4 fake content"
    called_url = mock_get.call_args[0][0]
    assert "fake-token" in called_url

def test_moodle_api_error_raises():
    client = make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = {"exception": "...", "message": "Invalid token"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response):
        with pytest.raises(ValueError, match="Invalid token"):
            client.list_course_files("999")
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
pytest tests/test_moodle_client.py -v
```
Output atteso: `ModuleNotFoundError: No module named 'app.core'`

- [ ] **Step 3: Crea `app/core/__init__.py`** (file vuoto)

- [ ] **Step 4: Crea `app/core/moodle_client.py`**

```python
import requests
from dataclasses import dataclass
from typing import List

_SUPPORTED_MIMETYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

@dataclass
class MoodleFile:
    filename: str
    fileurl: str
    filesize: int
    mimetype: str
    timemodified: int

class MoodleClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._session = requests.Session()

    def _call(self, function: str, **params) -> object:
        response = self._session.get(
            f"{self.base_url}/webservice/rest/server.php",
            params={
                "wstoken": self.token,
                "moodlewsrestformat": "json",
                "wsfunction": function,
                **params,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "exception" in data:
            raise ValueError(data.get("message", "Moodle API error"))
        return data

    def list_course_files(self, course_id: str) -> List[MoodleFile]:
        contents = self._call("core_course_get_contents", courseid=course_id)
        files = []
        for section in contents:
            for module in section.get("modules", []):
                for content in module.get("contents", []):
                    if content.get("type") == "file" and content.get("mimetype") in _SUPPORTED_MIMETYPES:
                        files.append(MoodleFile(
                            filename=content["filename"],
                            fileurl=content["fileurl"],
                            filesize=content.get("filesize", 0),
                            mimetype=content["mimetype"],
                            timemodified=content.get("timemodified", 0),
                        ))
        return files

    def download_file(self, fileurl: str) -> bytes:
        url = f"{fileurl}?token={self.token}"
        response = self._session.get(url, timeout=60)
        response.raise_for_status()
        return response.content
```

- [ ] **Step 5: Esegui tutti i test**

```bash
pytest tests/ -v
```
Output atteso: `11 passed`

- [ ] **Step 6: Commit finale Piano 1**

```bash
git add app/core/ tests/test_moodle_client.py
git commit -m "feat: Moodle REST client — list PDF/PPTX files + download"
git push origin main
```

---

## Verifica milestone Piano 1

Avvia il server e verifica che risponda:

```bash
uvicorn app.main:app --reload --port 8000
```

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

Il server è pronto per:
- Accettare launch LTI 1.3 su `POST /lti/launch`
- Creare automaticamente workspace corso al primo launch
- Distinguere ruolo instructor / student
- Listare e scaricare PDF/PPTX dalle risorse di un corso Moodle tramite token webservice

**Piano 2 (prossimo):** ingest pipeline (PDF/PPTX → markdown → pagine wiki via LLM + bge-m3 + LanceDB) + endpoint `/api/wiki` + query RAG + auto-synthesis.
