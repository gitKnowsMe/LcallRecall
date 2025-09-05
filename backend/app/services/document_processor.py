"""
Document processing service - handles PDF processing and chunking pipeline
"""
import logging
import sqlite3
from typing import List, Dict, Any, Optional
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Orchestrates document processing pipeline"""
    
    def __init__(self, pdf_service, chunking_service, vector_service, database):
        """
        Initialize document processor
        
        Args:
            pdf_service: PDF processing service
            chunking_service: Text chunking service  
            vector_service: Vector storage service
            database: Database connection
        """
        self.pdf_service = pdf_service
        self.chunking_service = chunking_service
        self.vector_service = vector_service
        self.database = database
        
        logger.info("DocumentProcessor initialized")
    
    async def process_document(self, file_path: str, workspace_id: str, user_id: int) -> Dict[str, Any]:
        """
        Process a document through the complete pipeline
        
        Args:
            file_path: Path to document file
            workspace_id: Target workspace ID
            user_id: User ID for ownership
            
        Returns:
            Processing result with document metadata
        """
        try:
            logger.info(f"Starting document processing: {file_path}")
            
            # Extract text from PDF
            text_content = await self.pdf_service.extract_text(file_path)
            if not text_content:
                raise ValueError("No text content extracted from document")
            
            # Generate document ID
            document_id = self._generate_document_id(file_path, text_content)
            
            # Check if document already exists
            if self._document_exists(document_id):
                logger.info(f"Document already processed: {document_id}")
                return await self._get_document_info(document_id)
            
            # Chunk text content
            chunks = self.chunking_service.chunk_text(text_content, document_id)
            if not chunks:
                raise ValueError("No chunks generated from document")
            
            # Store in vector database
            vector_ids = await self.vector_service.add_documents(
                workspace_id=workspace_id,
                texts=[chunk['text'] for chunk in chunks],
                metadatas=[{
                    'document_id': document_id,
                    'chunk_id': chunk['chunk_id'],
                    'start_char': chunk['start_char'],
                    'end_char': chunk['end_char']
                } for chunk in chunks]
            )
            
            # Store document metadata
            document_info = await self._store_document_metadata(
                document_id=document_id,
                file_path=file_path,
                workspace_id=workspace_id,
                user_id=user_id,
                text_content=text_content[:1000],  # Store preview
                chunk_count=len(chunks),
                vector_ids=vector_ids
            )
            
            logger.info(f"Document processed successfully: {document_id} ({len(chunks)} chunks)")
            return document_info
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise
    
    async def delete_document(self, document_id: str, workspace_id: str) -> bool:
        """
        Delete document and all associated data
        
        Args:
            document_id: Document identifier
            workspace_id: Workspace ID
            
        Returns:
            Success status
        """
        try:
            # Get vector IDs for deletion
            vector_ids = self._get_document_vector_ids(document_id)
            
            # Remove from vector store
            if vector_ids:
                await self.vector_service.delete_documents(workspace_id, vector_ids)
            
            # Remove from database
            self._delete_document_metadata(document_id)
            
            logger.info(f"Document deleted: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            return False
    
    async def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a document
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of document chunks
        """
        try:
            cursor = self.database.cursor()
            cursor.execute("""
                SELECT chunk_id, text_preview, start_char, end_char, vector_id
                FROM document_chunks 
                WHERE document_id = ?
                ORDER BY chunk_id
            """, (document_id,))
            
            chunks = []
            for row in cursor.fetchall():
                chunks.append({
                    'chunk_id': row[0],
                    'text_preview': row[1],
                    'start_char': row[2],
                    'end_char': row[3],
                    'vector_id': row[4]
                })
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to get document chunks: {e}")
            return []
    
    def _generate_document_id(self, file_path: str, content: str) -> str:
        """Generate unique document ID from file path and content"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        path_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        return f"doc_{path_hash}_{content_hash}"
    
    def _document_exists(self, document_id: str) -> bool:
        """Check if document already exists in database"""
        try:
            cursor = self.database.cursor()
            cursor.execute("SELECT 1 FROM documents WHERE document_id = ?", (document_id,))
            return cursor.fetchone() is not None
        except Exception:
            return False
    
    async def _get_document_info(self, document_id: str) -> Dict[str, Any]:
        """Get existing document information"""
        try:
            cursor = self.database.cursor()
            cursor.execute("""
                SELECT document_id, file_path, workspace_id, user_id, 
                       chunk_count, created_at, status
                FROM documents 
                WHERE document_id = ?
            """, (document_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'document_id': row[0],
                    'file_path': row[1],
                    'workspace_id': row[2],
                    'user_id': row[3],
                    'chunk_count': row[4],
                    'created_at': row[5],
                    'status': row[6]
                }
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get document info: {e}")
            return {}
    
    async def _store_document_metadata(self, document_id: str, file_path: str, 
                                     workspace_id: str, user_id: int,
                                     text_content: str, chunk_count: int,
                                     vector_ids: List[str]) -> Dict[str, Any]:
        """Store document metadata in database"""
        try:
            cursor = self.database.cursor()
            
            # Store document record
            cursor.execute("""
                INSERT INTO documents 
                (document_id, file_path, workspace_id, user_id, text_preview, 
                 chunk_count, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (document_id, file_path, workspace_id, user_id, text_content,
                  chunk_count, datetime.utcnow().isoformat(), 'processed'))
            
            # Store chunk records
            for i, vector_id in enumerate(vector_ids):
                cursor.execute("""
                    INSERT INTO document_chunks
                    (document_id, chunk_id, vector_id, start_char, end_char, text_preview)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (document_id, i, vector_id, 0, 0, ""))  # Simplified for now
            
            self.database.commit()
            
            return {
                'document_id': document_id,
                'file_path': file_path,
                'workspace_id': workspace_id,
                'user_id': user_id,
                'chunk_count': chunk_count,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'processed'
            }
            
        except Exception as e:
            logger.error(f"Failed to store document metadata: {e}")
            self.database.rollback()
            raise
    
    def _get_document_vector_ids(self, document_id: str) -> List[str]:
        """Get vector IDs for a document"""
        try:
            cursor = self.database.cursor()
            cursor.execute("""
                SELECT vector_id FROM document_chunks WHERE document_id = ?
            """, (document_id,))
            
            return [row[0] for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get vector IDs: {e}")
            return []
    
    def _delete_document_metadata(self, document_id: str):
        """Delete document metadata from database"""
        try:
            cursor = self.database.cursor()
            
            # Delete chunk records
            cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
            
            # Delete document record
            cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            
            self.database.commit()
            
        except Exception as e:
            logger.error(f"Failed to delete document metadata: {e}")
            self.database.rollback()
            raise
    
    def is_healthy(self) -> bool:
        """Check service health"""
        try:
            # Basic health check - verify database connection
            cursor = self.database.cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        # Services are cleaned up by service manager
        logger.info("DocumentProcessor service cleaned up")