import os
import hashlib
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
import logging

from ..auth.auth_service import auth_service
from ..auth.user_manager import user_manager, WorkspaceError
from ..core.database_manager import database_manager
from ..models.document import Document, DocumentChunk
from ..services.document_processor_api import DocumentProcessor, DocumentProcessingError

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for API responses
class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    content_hash: str
    mime_type: str
    total_pages: Optional[int]
    total_chunks: Optional[int]
    processing_status: str
    error_message: Optional[str]
    created_at: str
    processed_at: Optional[str]
    workspace_id: int

class DocumentChunkResponse(BaseModel):
    id: int
    chunk_index: int
    page_number: Optional[int]
    char_count: int
    token_count: Optional[int]
    vector_id: Optional[int]

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    offset: int = 0
    limit: int = 50

class DocumentDetailsResponse(DocumentResponse):
    chunks: List[DocumentChunkResponse]

class UploadResponse(BaseModel):
    document_id: int
    filename: str
    processing_status: str
    total_chunks: Optional[int] = None
    message: str

class ProcessingStatusResponse(BaseModel):
    document_id: int
    processing_status: str
    progress_percentage: int
    current_stage: str
    error_message: Optional[str] = None
    total_chunks: Optional[int] = None
    processing_time_seconds: Optional[float] = None

class SearchResult(BaseModel):
    document_id: int
    filename: str
    relevance_score: float
    matched_chunks: List[Dict[str, Any]]

class SearchResponse(BaseModel):
    query: str
    total_results: int
    documents: List[SearchResult]

# Import the existing auth dependency
from ..api.auth import get_current_user_from_token

# Helper functions
async def get_user_documents(workspace_id: int, offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    """Get all documents for a workspace"""
    async with database_manager.get_session() as db:
        query = select(Document).where(
            Document.workspace_id == workspace_id
        ).offset(offset).limit(limit).order_by(Document.created_at.desc())
        
        result = await db.execute(query)
        documents = result.scalars().all()
        
        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "original_filename": doc.original_filename,
                "file_path": doc.file_path,
                "file_size": doc.file_size,
                "content_hash": doc.content_hash,
                "mime_type": doc.mime_type,
                "total_pages": doc.total_pages,
                "total_chunks": doc.total_chunks,
                "processing_status": doc.processing_status,
                "error_message": doc.error_message,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                "workspace_id": doc.workspace_id
            }
            for doc in documents
        ]

async def get_document_details(document_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed document information including chunks"""
    async with database_manager.get_session() as db:
        query = select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id
        ).options(selectinload(Document.chunks))
        
        result = await db.execute(query)
        document = result.scalar_one_or_none()
        
        if not document:
            return None
        
        # Get document chunks
        chunks_query = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id
        ).order_by(DocumentChunk.chunk_index)
        
        chunks_result = await db.execute(chunks_query)
        chunks = chunks_result.scalars().all()
        
        return {
            "id": document.id,
            "filename": document.filename,
            "original_filename": document.original_filename,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "content_hash": document.content_hash,
            "mime_type": document.mime_type,
            "total_pages": document.total_pages,
            "total_chunks": document.total_chunks,
            "processing_status": document.processing_status,
            "error_message": document.error_message,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None,
            "workspace_id": document.workspace_id,
            "chunks": [
                {
                    "id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "char_count": chunk.char_count,
                    "token_count": chunk.token_count,
                    "vector_id": chunk.vector_id
                }
                for chunk in chunks
            ]
        }

# API Endpoints

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Upload and process a document"""
    try:
        # Validate user workspace
        workspace_id = current_user["workspace_id"]
        await user_manager.validate_workspace_access(workspace_id)
        
        # Validate file
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Check file size (100MB limit)
        MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large. Maximum size is 100MB"
            )
        
        # Check for empty file
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith("application/pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported"
            )
        
        # Reset file pointer for processing
        await file.seek(0)
        
        # Initialize document processor
        document_processor = DocumentProcessor(workspace_id)
        
        # Process document
        result = await document_processor.process_document(file, current_user["user_id"])
        
        logger.info(f"Document uploaded successfully: {file.filename} by user {current_user['username']}")
        
        return UploadResponse(
            document_id=result["document_id"],
            filename=result["filename"],
            processing_status=result["processing_status"],
            total_chunks=result.get("total_chunks"),
            message="Document uploaded successfully"
        )
        
    except WorkspaceError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except DocumentProcessingError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of documents to return"),
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """List all documents for the current user's workspace"""
    try:
        workspace_id = current_user["workspace_id"]
        
        # Get documents
        documents = await get_user_documents(workspace_id, offset, limit)
        
        # Get total count
        async with database_manager.get_session() as db:
            count_query = select(func.count(Document.id)).where(
                Document.workspace_id == workspace_id
            )
            result = await db.execute(count_query)
            total = result.scalar() or 0
        
        return DocumentListResponse(
            documents=[DocumentResponse(**doc) for doc in documents],
            total=total,
            offset=offset,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )

@router.get("/{document_id}", response_model=DocumentDetailsResponse)
async def get_document(
    document_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Get detailed information about a specific document"""
    try:
        workspace_id = current_user["workspace_id"]
        
        document_details = await get_document_details(document_id, workspace_id)
        
        if not document_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentDetailsResponse(**document_details)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )

@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Delete a document and all associated data"""
    try:
        workspace_id = current_user["workspace_id"]
        
        # Initialize document processor
        document_processor = DocumentProcessor(workspace_id)
        
        # Delete document
        success = await document_processor.delete_document(document_id, workspace_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        logger.info(f"Document {document_id} deleted by user {current_user['username']}")
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except DocumentProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )

@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Get chunks for a specific document"""
    try:
        workspace_id = current_user["workspace_id"]
        
        # Verify document exists and belongs to user's workspace
        async with database_manager.get_session() as db:
            doc_query = select(Document).where(
                Document.id == document_id,
                Document.workspace_id == workspace_id
            )
            doc_result = await db.execute(doc_query)
            document = doc_result.scalar_one_or_none()
            
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
            
            # Get chunks
            chunks_query = select(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            ).offset(offset).limit(limit).order_by(DocumentChunk.chunk_index)
            
            chunks_result = await db.execute(chunks_query)
            chunks = chunks_result.scalars().all()
            
            # Get total count
            count_query = select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0
        
        return {
            "chunks": [
                DocumentChunkResponse(
                    id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    char_count=chunk.char_count,
                    token_count=chunk.token_count,
                    vector_id=chunk.vector_id
                ) for chunk in chunks
            ],
            "total": total,
            "offset": offset,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chunks for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document chunks"
        )

@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(
    document_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Get processing status for a document"""
    try:
        workspace_id = current_user["workspace_id"]
        
        async with database_manager.get_session() as db:
            query = select(Document).where(
                Document.id == document_id,
                Document.workspace_id == workspace_id
            )
            result = await db.execute(query)
            document = result.scalar_one_or_none()
            
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
        
        # Calculate progress percentage based on status
        progress_map = {
            "pending": 0,
            "processing": 50,
            "completed": 100,
            "failed": 30  # Failed partway through
        }
        
        progress_percentage = progress_map.get(document.processing_status, 0)
        
        # Determine current stage
        stage_map = {
            "pending": "queued",
            "processing": "pdf_extraction",
            "completed": "completed",
            "failed": "pdf_extraction"
        }
        
        current_stage = stage_map.get(document.processing_status, "unknown")
        
        response_data = {
            "document_id": document.id,
            "processing_status": document.processing_status,
            "progress_percentage": progress_percentage,
            "current_stage": current_stage,
            "error_message": document.error_message
        }
        
        # Add additional data for completed documents
        if document.processing_status == "completed":
            response_data["total_chunks"] = document.total_chunks
            if document.processed_at and document.created_at:
                processing_time = (document.processed_at - document.created_at).total_seconds()
                response_data["processing_time_seconds"] = processing_time
        
        return ProcessingStatusResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get processing status"
        )

@router.get("/search")
async def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results to return"),
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Search documents using vector similarity"""
    try:
        workspace_id = current_user["workspace_id"]
        
        if not q or not q.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query is required"
            )
        
        # Import vector service here to avoid circular imports
        from ..services.vector_service import VectorStoreManager
        
        # Initialize vector store manager
        vector_manager = VectorStoreManager(workspace_id)
        
        # Perform search
        search_results = await vector_manager.search(q.strip(), top_k=limit)
        
        # Group results by document
        documents_map = {}
        
        for result in search_results:
            doc_id = result.get("document_id")
            if doc_id not in documents_map:
                documents_map[doc_id] = {
                    "document_id": doc_id,
                    "filename": result.get("filename", f"Document {doc_id}"),
                    "relevance_score": result.get("similarity", 0.0),
                    "matched_chunks": []
                }
            
            # Add matched chunk
            documents_map[doc_id]["matched_chunks"].append({
                "chunk_id": result.get("chunk_id"),
                "text": result.get("text", "")[:200] + "..." if len(result.get("text", "")) > 200 else result.get("text", ""),
                "page_number": result.get("page_number"),
                "similarity": result.get("similarity", 0.0)
            })
            
            # Update document relevance score (use highest scoring chunk)
            documents_map[doc_id]["relevance_score"] = max(
                documents_map[doc_id]["relevance_score"],
                result.get("similarity", 0.0)
            )
        
        # Sort documents by relevance
        documents = sorted(
            documents_map.values(),
            key=lambda x: x["relevance_score"],
            reverse=True
        )
        
        return SearchResponse(
            query=q,
            total_results=len(documents),
            documents=[SearchResult(**doc) for doc in documents]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed for query '{q}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )