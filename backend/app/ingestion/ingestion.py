from fastapi import  FastAPI , APIRouter , Depends , HTTPException ,UploadFile , File
from app.database.postgres import get_db_session
from app.database.qdrant import get_qdrant_client , init_qdrant
from app.models import Document , Chunk
from pydantic import BaseModel
from typing import Annotated
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.utils.text_extracter import extract_pdf,extract_txt,extract_md
from sqlalchemy import select
from datetime import datetime

from app.ingestion.utils.chunking import chunk_document , chunkingMethod
import json

router = APIRouter(
    prefix="/ingestion",
    tags=["ingestion"]
)


class DocumentType(str,Enum):
    PDF = "application/pdf"
    MD = "text/markdown"
    TXT = "text/plain"

class status(str,Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"



class DocumentResponse(BaseModel):
    id:str
    filename: str
    file_type: DocumentType
    size_bytes: int
    status: status
    summary: str | None = None    
    uploaded_at: datetime
    model_config = {"from_attributes":True}

class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]

class ChunkResponse(BaseModel):
    chunk_id: str
    page: int
    char_start: int
    char_end: int
    embedding_model: str
    created_at: str
    text_preview: str



allowed_format = {
    DocumentType.PDF,
    DocumentType.MD,
    DocumentType.TXT
}


@router.get("/health")
async def health():

    return {
        "message":"document ingesstion , all is well, for now😊"
    }

@router.post("/upload")
async def upload(
    file:Annotated[UploadFile, File()],
    db: AsyncSession = Depends(get_db_session)
    
):
    filename = file.filename
    file_type = file.content_type
    if file_type not in allowed_format:
        raise HTTPException(status_code=400, detail="Invalid file type")
    

    file_content = await file.read()
    file_size = len(file_content)


    # print(ext(file_content))
    extracted_document = None
    if file_type == DocumentType.PDF:
        extracted_document = extract_pdf(file_content)

    if file_type == DocumentType.TXT:
        extracted_document = extract_txt(file_content)

    if file_type == DocumentType.MD:
        extracted_document = extract_md(file_content)

    #create a Document Object
    document = Document(
        filename=filename,
        file_type=file_type,
        size_bytes=file_size,
        status=status.PROCESSING,
        summary=None
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    """
        document:DocumentSchema,
    document_id:str,
    method:chunkingMethod = chunkingMethod.RCTS,
    chunk_size: int = 512,
    chunk_overlap:int = 64,
    """

    chunks = chunk_document(
        extracted_document,
        document.id,
        chunkingMethod.RCTS
    )

    # Save chunks to DB
    db_chunks = []
    for i, chunk in enumerate(chunks):
        db_chunks.append(
            Chunk(
                id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_index=i,
                text=chunk.text,
                token_count=chunk.token_count,
                doc_char_start=chunk.doc_char_start,
                doc_char_end=chunk.doc_char_end,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                chunking_method=chunk.chunking_method.value,
                content_hash=chunk.content_hash,
                bbox_union=json.dumps(chunk.bbox_union) if chunk.bbox_union else None,
                section_path=json.dumps(chunk.section_path),
                block_types=json.dumps(chunk.block_types),
                prev_chunk_id=chunk.prev_chunk_id,
                next_chunk_id=chunk.next_chunk_id,
            )
        )

    db.add_all(db_chunks)
    await db.commit()

    return {"document_id": document.id, "chunks_saved": len(db_chunks)}

@router.get("/documents",response_model=DocumentListResponse)
async def get_all_documents(db:AsyncSession = Depends(get_db_session)):
    documents = await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
    return {"documents":documents.scalars().all()}