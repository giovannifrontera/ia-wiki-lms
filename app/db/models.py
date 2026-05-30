import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, UniqueConstraint, func
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
    __table_args__ = (
        UniqueConstraint("moodle_user_id", "course_id", name="uq_student_per_course"),
    )
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


class PageLink(Base):
    __tablename__ = "page_links"
    id = Column(String, primary_key=True)  # "{course_id}:{source}:{target}"
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False)
    source_path = Column(String, nullable=False)
    target_path = Column(String, nullable=False)
    weight = Column(String, nullable=False)  # float serializzato come string (SQLite compat)
    link_type = Column(String, nullable=False, default="semantic")
    __table_args__ = (
        UniqueConstraint("course_id", "source_path", "target_path", name="uq_page_link"),
    )


class Bookmark(Base):
    __tablename__ = "bookmarks"
    id = Column(String, primary_key=True)  # "{student_id}:{page_path}"
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False)
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False)
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
