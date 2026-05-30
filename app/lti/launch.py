import uuid
import os
import html as _html
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from pylti1p3.message_launch import MessageLaunch
from pylti1p3.request import Request as LtiRequest
from pylti1p3.cookie import CookieService
from pylti1p3.tool_config.dict import ToolConfDict
from app.lti.config import get_lti_config
from app.db.session import get_db
from app.db.models import Course, Student

_WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", os.getcwd())


# ---------------------------------------------------------------------------
# Minimal FastAPI adapter for pylti1p3
# ---------------------------------------------------------------------------

class _FastApiRequest(LtiRequest):
    """Wraps a FastAPI Request so pylti1p3 can read form params."""

    def __init__(self, fastapi_request: Request, form_data: dict):
        self._request = fastapi_request
        self._form_data = form_data

    @property
    def session(self):
        # We use an in-memory dict; real deployments would use a proper session store
        if not hasattr(self, "_session_data"):
            self._session_data = {}
        return self._session_data

    def is_secure(self) -> bool:
        return self._request.url.scheme == "https"

    def get_param(self, key: str) -> str:
        return self._form_data.get(key, "")


class _InMemorySessionService:
    """In-memory session service for stateless FastAPI — adequate for test/dev.
    For production OIDC flow, replace with a Redis-backed or DB-backed implementation."""

    def __init__(self):
        self._store: dict = {}

    def save_launch_data(self, key: str, jwt_body: dict) -> None:
        self._store[key] = jwt_body

    def get_launch_data(self, key: str) -> dict:
        return self._store.get(key, {})

    def save_nonce(self, nonce: str) -> None:
        self._store[f"nonce:{nonce}"] = True

    def check_nonce(self, nonce: str) -> bool:
        return self._store.get(f"nonce:{nonce}", False)

    def set_state_valid(self, state: str, client_id: str) -> None:
        self._store[f"state:{state}"] = client_id

    def check_state_is_valid(self, state: str, client_id: str) -> bool:
        return self._store.get(f"state:{state}") == client_id


class _NullCookieService(CookieService):
    """No-op cookie service — LTI launch POST doesn't need cookie state here."""

    def get_cookie(self, name: str):
        return None

    def set_cookie(self, name: str, value, exp=None):
        pass


class FastApiMessageLaunch(MessageLaunch):
    """Concrete MessageLaunch subclass for FastAPI."""

    def _get_request_param(self, key: str) -> str:
        return self._request.get_param(key)

    @classmethod
    async def from_request(
        cls, fastapi_request: Request, tool_config: dict
    ) -> "FastApiMessageLaunch":
        form_data = dict(await fastapi_request.form())
        lti_request = _FastApiRequest(fastapi_request, form_data)
        conf = ToolConfDict(settings=tool_config)
        session_svc = _InMemorySessionService()
        cookie_svc = _NullCookieService()
        obj = cls(lti_request, conf, session_service=session_svc, cookie_service=cookie_svc)
        return obj.validate()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

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
        workspace_path = os.path.join(_WORKSPACE_ROOT, "wiki-works", course_id)
        course = Course(
            course_id=course_id,
            moodle_course_id=moodle_course_id,
            workspace_path=workspace_path,
            lti_client_id=data.get("aud", "") if isinstance(data.get("aud"), str) else (data.get("aud", [""])[0]),
        )
        db.add(course)
        db.commit()
        db.refresh(course)
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

    safe_role = _html.escape(role)
    safe_course_id = _html.escape(course.course_id)
    safe_student_id = _html.escape(student_id)

    html_response = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ia-wiki-lms</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body
  data-role="{safe_role}"
  data-course="{safe_course_id}"
  data-student="{safe_student_id}"
>
  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>"""
    return HTMLResponse(html_response)
