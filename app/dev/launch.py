"""
Dev launch endpoint — bypassa LTI per sviluppo locale.
Attivo SOLO se DEV_MODE=true nel .env.

Uso:
  GET /dev/launch?course_id=XXX&student_id=YYY&role=student
  GET /dev/launch?course_id=XXX&role=instructor

Se student_id non viene passato (ruolo student), ne viene creato uno
automaticamente con moodle_user_id="dev-user" per il corso indicato.
"""

import os
import uuid
import html as _html

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.db.session import get_db
from app.db.models import Course, Student

router = APIRouter()


def _check_dev_mode():
    if os.getenv("DEV_MODE", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/dev/launch", response_class=HTMLResponse)
def dev_launch(
    course_id: str = Query(...),
    role: str = Query(default="student"),
    student_id: str = Query(default=""),
    db=Depends(get_db),
):
    _check_dev_mode()

    course: Course | None = db.get(Course, course_id)
    if not course:
        # Crea un corso fittizio per dev
        course = Course(
            course_id=course_id,
            moodle_course_id=f"dev-{course_id}",
            workspace_path=os.path.join(
                os.getenv("WORKSPACE_ROOT", "."), "wiki-works", course_id
            ),
            lti_client_id="dev-client",
        )
        db.add(course)
        db.commit()
        os.makedirs(course.workspace_path, exist_ok=True)

    resolved_student_id = ""
    if role == "student":
        if student_id:
            student = db.get(Student, student_id)
        else:
            student = db.query(Student).filter_by(
                moodle_user_id="dev-user", course_id=course_id
            ).first()
            if not student:
                student = Student(
                    student_id=str(uuid.uuid4()),
                    moodle_user_id="dev-user",
                    course_id=course_id,
                )
                db.add(student)
                db.commit()
        resolved_student_id = student.student_id if student else ""

    safe_role = _html.escape(role)
    safe_course = _html.escape(course_id)
    safe_student = _html.escape(resolved_student_id)

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ia-wiki-lms [dev]</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body
  data-role="{safe_role}"
  data-course="{safe_course}"
  data-student="{safe_student}"
  data-dev="true"
>
  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>""")
