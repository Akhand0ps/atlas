import json
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, nullable=False, default="processing")
    summary = Column(Text, nullable=True)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)

    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)

    doc_char_start = Column(Integer, nullable=False)
    doc_char_end = Column(Integer, nullable=False)

    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)

    chunking_method = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)

    # JSON fields stored as serialized strings
    bbox_union = Column(Text, nullable=True)       # JSON string: [x0, y0, x1, y1]
    section_path = Column(Text, nullable=True)     # JSON string: ["Heading 1", ...]
    block_types = Column(Text, nullable=True)      # JSON string: ["text", "heading"]

    prev_chunk_id = Column(String, nullable=True)
    next_chunk_id = Column(String, nullable=True)

    # Populated during embedding stage, not at chunking time
    embedding_model = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
