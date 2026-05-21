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
