from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

qdrant_client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

async def init_qdrant():
    """Ensure the Qdrant collection exists."""
    collection_name = settings.QDRANT_COLLECTION_NAME
    collections = await qdrant_client.get_collections()
    
    if collection_name not in [c.name for c in collections.collections]:
        logger.info(f"Creating Qdrant collection: {collection_name}")
        await qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
    else:
        logger.info(f"Qdrant collection {collection_name} already exists.")

async def get_qdrant_client() -> AsyncQdrantClient:
    return qdrant_client
