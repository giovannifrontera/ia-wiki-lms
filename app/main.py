from fastapi import FastAPI

app = FastAPI(title="ia-wiki-lms")

@app.get("/health")
def health():
    return {"status": "ok"}
