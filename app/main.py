from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import init_db
from app.lti.launch import router as lti_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ia-wiki-lms", lifespan=lifespan)
app.include_router(lti_router, prefix="/lti")


@app.get("/health")
def health():
    return {"status": "ok"}
