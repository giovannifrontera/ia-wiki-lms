import pytest
import uuid
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

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
def app_with_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
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
