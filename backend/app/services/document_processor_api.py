"""
Document processor service for API endpoints - integrates with real services
"""
import os
import tempfile
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy import select

from ..core.database_manager import database_manager
from ..models.document import Document, DocumentChunk
from ..services.pdf_service import pdf_service
from ..services.semantic_chunking import SemanticChunking
from ..services.vector_service import vector_store

logger = logging.getLogger(__name__)

class DocumentProcessingError(Exception):
    """Exception raised during document processing"""
    pass

class DocumentProcessor:
    """Real document processor for API endpoints"""
    
    def __init__(self, workspace_id: int):
        self.workspace_id = workspace_id
        self.chunking_service = SemanticChunking(chunk_size=512, chunk_overlap=50)
    
    async def process_document(self, file: UploadFile, user_id: int) -> Dict[str, Any]:
        """
        Process uploaded document through the complete pipeline
        
        Args:
            file: Uploaded file from FastAPI
            user_id: User ID for ownership
            
        Returns:
            Processing result dictionary
        """
        temp_file_path = None
        try:
            # Read file content
            content = await file.read()
            
            # Generate content hash
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Check for duplicates
            async with database_manager.get_session() as db:
                existing_query = select(Document).where(
                    Document.content_hash == content_hash,
                    Document.workspace_id == self.workspace_id
                )
                result = await db.execute(existing_query)
                existing_doc = result.scalar_one_or_none()
                
                if existing_doc:
                    raise DocumentProcessingError("Document already exists")
                
                # Save to temporary file for PDF processing
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(content)
                    temp_file_path = temp_file.name
                
                # Process PDF - extract text with page information
                logger.info(f"Extracting text from PDF: {file.filename}")
                pdf_result = pdf_service.extract_text_from_pdf(temp_file_path)
                text_content = pdf_result["text"]
                pdf_metadata = pdf_result["metadata"]
                pages = pdf_result.get("pages", [])
                
                if not text_content or not text_content.strip():
                    raise DocumentProcessingError("No text content found in PDF")
                
                # Chunk the text with page information
                logger.info("Chunking text content with page tracking")
                if pages:
                    chunks = self.chunking_service.chunk_pages(pages, document_id=f"doc_{content_hash[:8]}")
                else:
                    # Fallback to old method if pages not available
                    chunks = self.chunking_service.chunk_text(text_content, document_id=f"doc_{content_hash[:8]}")
                
                if not chunks:
                    raise DocumentProcessingError("No chunks generated from document")
                
                # Initialize vector store for workspace
                await vector_store.initialize()
                await vector_store.load_workspace(str(self.workspace_id))
                
                # Generate embeddings and add to vector store
                logger.info(f"Adding {len(chunks)} chunks to vector store")
                chunk_texts = [chunk['text'] for chunk in chunks]
                chunk_metadata = [{
                    'document_id': content_hash[:8],
                    'chunk_index': chunk['chunk_id'],
                    'filename': file.filename,
                    'page': chunk.get('page_number', 1)
                } for chunk in chunks]
                
                vector_ids = await vector_store.add_documents(
                    workspace_id=str(self.workspace_id),
                    texts=chunk_texts,
                    metadata=chunk_metadata
                )
                
                # Create document record
                new_document = Document(
                    workspace_id=self.workspace_id,
                    filename=file.filename,
                    original_filename=file.filename,
                    file_path=temp_file_path,
                    file_size=len(content),
                    content_hash=content_hash,
                    mime_type=file.content_type,
                    processing_status="completed",
                    total_pages=pdf_metadata["page_count"],
                    total_chunks=len(chunks),
                    created_at=datetime.utcnow(),
                    processed_at=datetime.utcnow()
                )
                
                db.add(new_document)
                await db.commit()
                await db.refresh(new_document)
                
                # Create chunk records
                for i, (chunk, vector_id) in enumerate(zip(chunks, vector_ids)):
                    chunk_record = DocumentChunk(
                        document_id=new_document.id,
                        workspace_id=self.workspace_id,
                        chunk_text=chunk['text'][:1000],  # Store preview
                        chunk_index=chunk['chunk_id'],
                        page_number=chunk.get('page_number', 1),
                        char_count=chunk['length'],
                        vector_id=vector_id,
                        created_at=datetime.utcnow()
                    )
                    db.add(chunk_record)
                
                await db.commit()
                
                logger.info(f"Document processed successfully: {file.filename} ({len(chunks)} chunks)")
                
                return {
                    "document_id": new_document.id,
                    "filename": new_document.filename,
                    "processing_status": new_document.processing_status,
                    "total_chunks": new_document.total_chunks
                }
                
        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise DocumentProcessingError(f"Processing failed: {str(e)}")
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file_path}: {e}")
    
    async def delete_document(self, document_id: int, workspace_id: int) -> bool:
        """
        Delete document and associated chunks from database and vector store
        
        Args:
            document_id: Document ID to delete
            workspace_id: Workspace ID for security check
            
        Returns:
            True if deleted, False if not found
        """
        try:
            async with database_manager.get_session() as db:
                # Find document
                query = select(Document).where(
                    Document.id == document_id,
                    Document.workspace_id == workspace_id
                )
                result = await db.execute(query)
                document = result.scalar_one_or_none()
                
                if not document:
                    return False
                
                # Get chunks for vector store cleanup
                chunks_query = select(DocumentChunk).where(
                    DocumentChunk.document_id == document_id
                )
                chunks_result = await db.execute(chunks_query)
                chunks = chunks_result.scalars().all()
                
                # Clean up from vector store
                await vector_store.load_workspace(str(workspace_id))
                for chunk in chunks:
                    if chunk.vector_id is not None:
                        await vector_store.delete_document(str(workspace_id), chunk.vector_id)
                
                # Delete chunks from database
                for chunk in chunks:
                    await db.delete(chunk)
                
                # Delete document file if it exists
                if document.file_path and os.path.exists(document.file_path):
                    try:
                        os.unlink(document.file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete document file {document.file_path}: {e}")
                
                # Delete document record
                await db.delete(document)
                await db.commit()
                
                logger.info(f"Document deleted successfully: {document_id}")
                return True
                
        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            raise DocumentProcessingError(f"Deletion failed: {str(e)}")