from fastapi import FastAPI

app = FastAPI(title="standalone2 baseline", version="0.1.0")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "standalone2"}
