import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os
from io import BytesIO

from app.main import app
from app.models.document import Document, DocumentChunk


class TestDocumentsAPI:
    """Integration tests for document management API endpoints"""
    
    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_document_processor(self):
        """Mock DocumentProcessor for testing"""
        processor = Mock()
        processor.process_document = AsyncMock()
        processor.delete_document = AsyncMock()
        processor.get_document_status = AsyncMock()
        return processor
    
    @pytest.fixture
    def mock_user_manager(self):
        """Mock UserManager for authentication"""
        manager = Mock()
        manager.get_current_user.return_value = {
            "user_id": 1,
            "username": "testuser",
            "workspace_id": 1,
            "email": "test@example.com"
        }
        manager.is_authenticated.return_value = True
        manager.get_current_workspace_id.return_value = 1
        manager.validate_workspace_access = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_auth_service(self):
        """Mock AuthService for token validation"""
        service = Mock()
        service.verify_token.return_value = {
            "user_id": 1,
            "username": "testuser",
            "workspace_id": 1
        }
        return service
    
    @pytest.fixture
    def sample_pdf_file(self):
        """Create sample PDF file for upload testing"""
        content = b"Mock PDF content for testing document upload"
        return BytesIO(content)

    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for API requests"""
        return {"Authorization": "Bearer fake_jwt_token"}

    # Document Upload Tests
    def test_upload_document_success(self, client, mock_document_processor, mock_user_manager, 
                                   mock_auth_service, auth_headers):
        """Test successful document upload"""
        mock_document_processor.process_document.return_value = {
            "document_id": 1,
            "filename": "test.pdf",
            "total_chunks": 3,
            "processing_status": "completed",
            "metadata": {
                "page_count": 2,
                "file_size": 1024
            }
        }
        
        with patch('app.api.documents.document_processor', mock_document_processor), \
             patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            # Create file data for upload
            files = {"file": ("test.pdf", b"mock pdf content", "application/pdf")}
            
            response = client.post("/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["document_id"] == 1
        assert data["filename"] == "test.pdf"
        assert data["total_chunks"] == 3
        assert data["processing_status"] == "completed"
        
        mock_document_processor.process_document.assert_called_once()

    def test_upload_document_unauthenticated(self, client):
        """Test document upload without authentication"""
        files = {"file": ("test.pdf", b"mock pdf content", "application/pdf")}
        
        response = client.post("/documents/upload", files=files)
        
        assert response.status_code == 403  # Forbidden

    def test_upload_document_invalid_file_type(self, client, mock_user_manager, 
                                             mock_auth_service, auth_headers):
        """Test document upload with invalid file type"""
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            files = {"file": ("test.txt", b"text content", "text/plain")}
            
            response = client.post("/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Only PDF files are supported" in response.json()["detail"]

    def test_upload_document_no_file(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document upload without file"""
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            response = client.post("/documents/upload", headers=auth_headers)
        
        assert response.status_code == 422  # Unprocessable Entity

    def test_upload_document_processing_failure(self, client, mock_document_processor, 
                                              mock_user_manager, mock_auth_service, auth_headers):
        """Test document upload with processing failure"""
        from app.services.document_processor import DocumentProcessingError
        
        mock_document_processor.process_document.side_effect = DocumentProcessingError("Processing failed")
        
        with patch('app.api.documents.document_processor', mock_document_processor), \
             patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            files = {"file": ("test.pdf", b"mock pdf content", "application/pdf")}
            
            response = client.post("/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 500
        assert "Processing failed" in response.json()["detail"]

    def test_upload_document_workspace_access_denied(self, client, mock_user_manager, 
                                                   mock_auth_service, auth_headers):
        """Test document upload with workspace access denied"""
        from app.auth.user_manager import WorkspaceError
        
        mock_user_manager.validate_workspace_access.side_effect = WorkspaceError("Access denied")
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            files = {"file": ("test.pdf", b"mock pdf content", "application/pdf")}
            
            response = client.post("/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    # Document List Tests
    def test_list_documents_success(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test successful document listing"""
        mock_documents = [
            {
                "id": 1,
                "filename": "doc1.pdf",
                "original_filename": "document1.pdf",
                "file_size": 1024,
                "total_pages": 2,
                "total_chunks": 3,
                "processing_status": "completed",
                "created_at": "2025-01-03T12:00:00",
                "processed_at": "2025-01-03T12:01:00"
            },
            {
                "id": 2,
                "filename": "doc2.pdf",
                "original_filename": "document2.pdf",
                "file_size": 2048,
                "total_pages": 4,
                "total_chunks": 6,
                "processing_status": "completed",
                "created_at": "2025-01-03T12:05:00",
                "processed_at": "2025-01-03T12:06:00"
            }
        ]
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_user_documents', return_value=mock_documents):
            
            response = client.get("/documents", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2
        assert data["total"] == 2
        assert data["documents"][0]["filename"] == "doc1.pdf"
        assert data["documents"][1]["filename"] == "doc2.pdf"

    def test_list_documents_unauthenticated(self, client):
        """Test document listing without authentication"""
        response = client.get("/documents")
        
        assert response.status_code == 403

    def test_list_documents_empty(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document listing with no documents"""
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_user_documents', return_value=[]):
            
            response = client.get("/documents", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 0
        assert data["total"] == 0

    def test_list_documents_with_pagination(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document listing with pagination parameters"""
        mock_documents = [{"id": i, "filename": f"doc{i}.pdf"} for i in range(1, 6)]
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_user_documents', return_value=mock_documents[2:4]):  # offset=2, limit=2
            
            response = client.get("/documents?offset=2&limit=2", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2
        assert data["documents"][0]["id"] == 3
        assert data["documents"][1]["id"] == 4

    # Document Details Tests
    def test_get_document_details_success(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test successful document details retrieval"""
        mock_document = {
            "id": 1,
            "filename": "test.pdf",
            "original_filename": "original_test.pdf",
            "file_size": 1024,
            "content_hash": "abc123",
            "total_pages": 2,
            "total_chunks": 3,
            "processing_status": "completed",
            "created_at": "2025-01-03T12:00:00",
            "processed_at": "2025-01-03T12:01:00",
            "chunks": [
                {
                    "id": 1,
                    "chunk_index": 0,
                    "char_count": 100,
                    "page_number": 1
                },
                {
                    "id": 2,
                    "chunk_index": 1,
                    "char_count": 150,
                    "page_number": 1
                }
            ]
        }
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_document_details', return_value=mock_document):
            
            response = client.get("/documents/1", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["filename"] == "test.pdf"
        assert data["total_chunks"] == 3
        assert len(data["chunks"]) == 2

    def test_get_document_details_not_found(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document details retrieval for non-existent document"""
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_document_details', return_value=None):
            
            response = client.get("/documents/999", headers=auth_headers)
        
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

    def test_get_document_details_unauthenticated(self, client):
        """Test document details retrieval without authentication"""
        response = client.get("/documents/1")
        
        assert response.status_code == 403

    # Document Deletion Tests
    def test_delete_document_success(self, client, mock_document_processor, mock_user_manager, 
                                   mock_auth_service, auth_headers):
        """Test successful document deletion"""
        mock_document_processor.delete_document.return_value = True
        
        with patch('app.api.documents.document_processor', mock_document_processor), \
             patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            response = client.delete("/documents/1", headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Document deleted successfully"
        
        mock_document_processor.delete_document.assert_called_once_with(
            document_id=1,
            workspace_id=1
        )

    def test_delete_document_not_found(self, client, mock_document_processor, mock_user_manager, 
                                     mock_auth_service, auth_headers):
        """Test document deletion for non-existent document"""
        mock_document_processor.delete_document.return_value = False
        
        with patch('app.api.documents.document_processor', mock_document_processor), \
             patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            response = client.delete("/documents/999", headers=auth_headers)
        
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

    def test_delete_document_unauthenticated(self, client):
        """Test document deletion without authentication"""
        response = client.delete("/documents/1")
        
        assert response.status_code == 403

    def test_delete_document_processing_error(self, client, mock_document_processor, 
                                            mock_user_manager, mock_auth_service, auth_headers):
        """Test document deletion with processing error"""
        from app.services.document_processor import DocumentProcessingError
        
        mock_document_processor.delete_document.side_effect = DocumentProcessingError("Deletion failed")
        
        with patch('app.api.documents.document_processor', mock_document_processor), \
             patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            response = client.delete("/documents/1", headers=auth_headers)
        
        assert response.status_code == 500
        assert "Deletion failed" in response.json()["detail"]

    # Document Processing Status Tests
    def test_get_processing_status_success(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test successful processing status retrieval"""
        mock_status = {
            "document_id": 1,
            "processing_status": "processing",
            "progress_percentage": 75,
            "current_stage": "chunking",
            "error_message": None
        }
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_processing_status', return_value=mock_status):
            
            response = client.get("/documents/1/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == 1
        assert data["processing_status"] == "processing"
        assert data["progress_percentage"] == 75
        assert data["current_stage"] == "chunking"

    def test_get_processing_status_completed(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test processing status for completed document"""
        mock_status = {
            "document_id": 1,
            "processing_status": "completed",
            "progress_percentage": 100,
            "current_stage": "completed",
            "total_chunks": 5,
            "processing_time_seconds": 12.5
        }
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_processing_status', return_value=mock_status):
            
            response = client.get("/documents/1/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_status"] == "completed"
        assert data["progress_percentage"] == 100
        assert data["total_chunks"] == 5

    def test_get_processing_status_failed(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test processing status for failed document"""
        mock_status = {
            "document_id": 1,
            "processing_status": "failed",
            "progress_percentage": 30,
            "current_stage": "pdf_extraction",
            "error_message": "PDF extraction failed"
        }
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.get_processing_status', return_value=mock_status):
            
            response = client.get("/documents/1/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_status"] == "failed"
        assert data["error_message"] == "PDF extraction failed"

    # Document Search Tests
    def test_search_documents_success(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test successful document search"""
        mock_results = {
            "query": "machine learning",
            "total_results": 2,
            "documents": [
                {
                    "document_id": 1,
                    "filename": "ml_guide.pdf",
                    "relevance_score": 0.95,
                    "matched_chunks": [
                        {
                            "chunk_id": 1,
                            "text": "Machine learning is a powerful tool...",
                            "page_number": 1,
                            "similarity": 0.95
                        }
                    ]
                },
                {
                    "document_id": 2,
                    "filename": "ai_fundamentals.pdf",
                    "relevance_score": 0.87,
                    "matched_chunks": [
                        {
                            "chunk_id": 3,
                            "text": "Learning algorithms in machine learning...",
                            "page_number": 2,
                            "similarity": 0.87
                        }
                    ]
                }
            ]
        }
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.search_documents', return_value=mock_results):
            
            response = client.get("/documents/search?q=machine%20learning", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "machine learning"
        assert data["total_results"] == 2
        assert len(data["documents"]) == 2
        assert data["documents"][0]["relevance_score"] == 0.95

    def test_search_documents_empty_query(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document search with empty query"""
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            response = client.get("/documents/search", headers=auth_headers)
        
        assert response.status_code == 400
        assert "Search query is required" in response.json()["detail"]

    def test_search_documents_no_results(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document search with no results"""
        mock_results = {
            "query": "nonexistent topic",
            "total_results": 0,
            "documents": []
        }
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service), \
             patch('app.api.documents.search_documents', return_value=mock_results):
            
            response = client.get("/documents/search?q=nonexistent%20topic", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 0
        assert len(data["documents"]) == 0

    # File Upload Validation Tests
    def test_upload_document_large_file(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document upload with file exceeding size limit"""
        # Simulate large file
        large_content = b"x" * (100 * 1024 * 1024 + 1)  # Slightly over 100MB
        
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            files = {"file": ("large.pdf", large_content, "application/pdf")}
            
            response = client.post("/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 413  # Payload Too Large
        assert "File too large" in response.json()["detail"]

    def test_upload_document_empty_file(self, client, mock_user_manager, mock_auth_service, auth_headers):
        """Test document upload with empty file"""
        with patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            files = {"file": ("empty.pdf", b"", "application/pdf")}
            
            response = client.post("/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 400
        assert "File is empty" in response.json()["detail"]

    def test_upload_document_duplicate(self, client, mock_document_processor, mock_user_manager, 
                                     mock_auth_service, auth_headers):
        """Test document upload with duplicate content"""
        from app.services.document_processor import DocumentProcessingError
        
        mock_document_processor.process_document.side_effect = DocumentProcessingError("Document already exists")
        
        with patch('app.api.documents.document_processor', mock_document_processor), \
             patch('app.api.documents.user_manager', mock_user_manager), \
             patch('app.api.documents.auth_service', mock_auth_service):
            
            files = {"file": ("duplicate.pdf", b"duplicate content", "application/pdf")}
            
            response = client.post("/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 409  # Conflict
        assert "Document already exists" in response.json()["detail"]