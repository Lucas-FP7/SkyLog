from fastapi import FastAPI
from api import router as api_router

app = FastAPI(title="Solar Shield Ingestor Service")

app.include_router(api_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
