from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Document(Base):
    """Document metadata model"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    content_hash = Column(String(64), nullable=False, index=True)  # SHA256
    mime_type = Column(String(100), default="application/pdf")
    
    # Processing metadata
    total_pages = Column(Integer, nullable=True)
    total_chunks = Column(Integer, nullable=True)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Document(filename='{self.filename}', workspace_id={self.workspace_id})>"

class DocumentChunk(Base):
    """Document chunk model for tracking vector embeddings"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    
    # Chunk content
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Order in document
    page_number = Column(Integer, nullable=True)
    
    # Vector information
    vector_id = Column(Integer, nullable=True)  # ID in FAISS index
    embedding_model = Column(String(100), default="all-MiniLM-L6-v2")
    
    # Metadata
    char_count = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<DocumentChunk(document_id={self.document_id}, chunk_index={self.chunk_index})>"