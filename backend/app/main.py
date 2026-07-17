from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database.postgres import get_db_session, engine
from app.database.qdrant import init_qdrant, get_qdrant_client


from app.ingestion.ingestion import router as ingestion_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Qdrant
    try:
        await init_qdrant()
        logger.info("Successfully initialized Qdrant")
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant: {e}")
    
    yield
    
    # Shutdown
    await engine.dispose()
    logger.info("Successfully disposed Postgres engine")

app = FastAPI(title="Atlas RAG API", lifespan=lifespan)


app.include_router(ingestion_router)

@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db_session),
    qdrant = Depends(get_qdrant_client)
):
    status = {"api": "ok", "postgres": "error", "qdrant": "error"}
    
    # Check Postgres
    try:
        await db.execute(text("SELECT 1"))
        status["postgres"] = "ok"
    except Exception as e:
        logger.error(f"Postgres health check failed: {e}")

    # Check Qdrant
    try:
        # Simple call to verify connection
        collections = await qdrant.get_collections()
        status["qdrant"] = "ok"
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")

    overall_status = "ok" if all(v == "ok" for v in status.values()) else "degraded"
    
    response = {"status": overall_status, "services": status}
    if overall_status != "ok":
        # Usually 503 is returned if degraded, but 200 with degraded state is fine for this example
        raise HTTPException(status_code=503, detail=response)
        
    return response
