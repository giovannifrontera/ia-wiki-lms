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
