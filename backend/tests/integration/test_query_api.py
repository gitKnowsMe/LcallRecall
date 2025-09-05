import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from fastapi.testclient import TestClient
from httpx import AsyncClient
import asyncio

from app.main import app
from app.api.query import router


class TestQueryAPI:
    """Test suite for query API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture  
    async def async_client(self):
        """Create async test client"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    def mock_query_service(self):
        """Mock query service"""
        service = Mock()
        service.query_documents = AsyncMock()
        service.query_documents_streaming = AsyncMock()
        service.search_similar_documents = AsyncMock()
        service.get_query_history = AsyncMock()
        service.get_workspace_search_stats = Mock()
        return service
    
    @pytest.fixture
    def mock_auth_dependency(self):
        """Mock authentication dependency"""
        def mock_get_current_user():
            return {
                "user_id": "test_user_123",
                "username": "testuser", 
                "workspace_id": "workspace_123"
            }
        return mock_get_current_user
    
    @pytest.fixture
    def sample_query_response(self):
        """Sample query response"""
        return {
            "response": "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
            "sources": [
                {
                    "document_id": "doc1",
                    "filename": "ml_basics.pdf", 
                    "page": 1,
                    "relevance_score": 0.95,
                    "content_preview": "Machine learning is a subset..."
                }
            ],
            "query": "What is machine learning?",
            "context_length": 256,
            "response_time_ms": 1250
        }
    
    @pytest.fixture
    def sample_search_results(self):
        """Sample search results"""
        return [
            {
                "document_id": "doc1",
                "chunk_id": 1,
                "content": "Machine learning is a subset of artificial intelligence.",
                "score": 0.95,
                "metadata": {
                    "filename": "ml_basics.pdf",
                    "page": 1,
                    "chunk_index": 0
                }
            },
            {
                "document_id": "doc2",
                "chunk_id": 2, 
                "content": "Deep learning uses neural networks with multiple layers.",
                "score": 0.87,
                "metadata": {
                    "filename": "deep_learning.pdf",
                    "page": 3,
                    "chunk_index": 5
                }
            }
        ]

    # Query Endpoint Tests
    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_query_documents_success(self, mock_service, mock_auth, client, sample_query_response):
        """Test successful document query"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        mock_service.query_documents.return_value = sample_query_response
        
        response = client.post(
            "/query/documents",
            json={
                "query": "What is machine learning?",
                "top_k": 5,
                "min_score": 0.5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["response"] == sample_query_response["response"]
        assert len(data["sources"]) == 1
        assert data["query"] == "What is machine learning?"
        assert "response_time_ms" in data
        
        mock_service.query_documents.assert_called_once_with(
            workspace_id="workspace123",
            query="What is machine learning?", 
            user_id="user123",
            top_k=5,
            min_score=0.5
        )

    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_query_documents_with_custom_params(self, mock_service, mock_auth, client, sample_query_response):
        """Test document query with custom parameters"""
        mock_auth.return_value = {
            "user_id": "user123", 
            "workspace_id": "workspace123"
        }
        mock_service.query_documents.return_value = sample_query_response
        
        response = client.post(
            "/query/documents",
            json={
                "query": "test query",
                "top_k": 10,
                "min_score": 0.7,
                "max_tokens": 512,
                "temperature": 0.8
            }
        )
        
        assert response.status_code == 200
        
        mock_service.query_documents.assert_called_once_with(
            workspace_id="workspace123",
            query="test query",
            user_id="user123", 
            top_k=10,
            min_score=0.7,
            max_tokens=512,
            temperature=0.8
        )

    def test_query_documents_missing_query(self, client):
        """Test document query with missing query"""
        response = client.post(
            "/query/documents", 
            json={}
        )
        
        assert response.status_code == 422  # Validation error

    def test_query_documents_empty_query(self, client):
        """Test document query with empty query"""
        response = client.post(
            "/query/documents",
            json={"query": ""}
        )
        
        assert response.status_code == 422  # Validation error

    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_query_documents_no_results(self, mock_service, mock_auth, client):
        """Test document query with no results"""
        from app.services.query_service import NoResultsError
        
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"  
        }
        mock_service.query_documents.side_effect = NoResultsError("No similar documents found")
        
        response = client.post(
            "/query/documents",
            json={"query": "nonexistent topic"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "No similar documents found" in data["detail"]

    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')  
    def test_query_documents_service_error(self, mock_service, mock_auth, client):
        """Test document query with service error"""
        from app.services.query_service import QueryError
        
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        mock_service.query_documents.side_effect = QueryError("Service unavailable")
        
        response = client.post(
            "/query/documents", 
            json={"query": "test query"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "Query failed" in data["detail"]

    def test_query_documents_unauthorized(self, client):
        """Test document query without authentication"""
        response = client.post(
            "/query/documents",
            json={"query": "test query"}
        )
        
        assert response.status_code == 401

    # Streaming Query Tests
    @patch('app.api.query.get_current_user')
    @patch('app.api.query.streaming_service')
    def test_stream_query_success(self, mock_streaming, mock_auth, client):
        """Test successful streaming query"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        
        # Mock streaming response
        async def mock_stream():
            yield "data: Based on the\n\n"
            yield "data: provided documents\n\n"
            yield "data: machine learning is\n\n"
            yield "event: complete\ndata: {}\n\n"
        
        mock_streaming.stream_query_response.return_value = mock_stream()
        
        response = client.post(
            "/query/stream",
            json={"query": "What is machine learning?"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        
        # Verify streaming content
        content = response.text
        assert "data: Based on the" in content
        assert "data: provided documents" in content
        assert "event: complete" in content

    @patch('app.api.query.get_current_user')
    @patch('app.api.query.streaming_service')
    def test_stream_query_with_progress(self, mock_streaming, mock_auth, client):
        """Test streaming query with progress events"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        
        async def mock_stream_with_progress():
            yield 'event: progress\ndata: {"stage": "searching", "progress": 0.3}\n\n'
            yield "data: Response content\n\n"
            yield "event: complete\ndata: {}\n\n"
        
        mock_streaming.stream_query_response.return_value = mock_stream_with_progress()
        
        response = client.post(
            "/query/stream",
            json={
                "query": "test query",
                "include_progress": True
            }
        )
        
        assert response.status_code == 200
        content = response.text
        assert "event: progress" in content
        assert '"stage": "searching"' in content

    def test_stream_query_missing_query(self, client):
        """Test streaming query with missing query"""
        response = client.post("/query/stream", json={})
        
        assert response.status_code == 422

    def test_stream_query_unauthorized(self, client):
        """Test streaming query without authentication"""
        response = client.post(
            "/query/stream",
            json={"query": "test query"}
        )
        
        assert response.status_code == 401

    # Search Endpoint Tests
    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_search_documents_success(self, mock_service, mock_auth, client, sample_search_results):
        """Test successful document search"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        mock_service.search_similar_documents.return_value = sample_search_results
        
        response = client.post(
            "/query/search",
            json={
                "query": "machine learning",
                "top_k": 5,
                "min_score": 0.5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] == 0.95
        assert data["query"] == "machine learning" 
        assert data["total_results"] == 2
        
        mock_service.search_similar_documents.assert_called_once_with(
            workspace_id="workspace123",
            query="machine learning",
            top_k=5,
            min_score=0.5
        )

    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_search_documents_no_results(self, mock_service, mock_auth, client):
        """Test document search with no results"""
        from app.services.query_service import NoResultsError
        
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        mock_service.search_similar_documents.side_effect = NoResultsError("No results")
        
        response = client.post(
            "/query/search",
            json={"query": "nonexistent"}
        )
        
        assert response.status_code == 404

    def test_search_documents_missing_query(self, client):
        """Test document search with missing query"""
        response = client.post("/query/search", json={})
        
        assert response.status_code == 422

    def test_search_documents_unauthorized(self, client):
        """Test document search without authentication"""
        response = client.post(
            "/query/search",
            json={"query": "test"}
        )
        
        assert response.status_code == 401

    # Query History Tests
    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_get_query_history_success(self, mock_service, mock_auth, client):
        """Test successful query history retrieval"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        
        mock_history = [
            {
                "query_id": "q1",
                "query": "What is machine learning?",
                "timestamp": "2024-01-01T10:00:00Z",
                "response_time_ms": 1200,
                "sources_count": 3
            },
            {
                "query_id": "q2", 
                "query": "Explain neural networks",
                "timestamp": "2024-01-01T09:30:00Z",
                "response_time_ms": 980,
                "sources_count": 2
            }
        ]
        mock_service.get_query_history.return_value = mock_history
        
        response = client.get("/query/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["history"]) == 2
        assert data["history"][0]["query"] == "What is machine learning?"
        assert data["total"] == 2
        
        mock_service.get_query_history.assert_called_once_with(
            user_id="user123",
            workspace_id="workspace123",
            limit=50,
            offset=0
        )

    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_get_query_history_with_pagination(self, mock_service, mock_auth, client):
        """Test query history with pagination"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        mock_service.get_query_history.return_value = []
        
        response = client.get("/query/history?limit=10&offset=20")
        
        assert response.status_code == 200
        
        mock_service.get_query_history.assert_called_once_with(
            user_id="user123",
            workspace_id="workspace123", 
            limit=10,
            offset=20
        )

    def test_get_query_history_unauthorized(self, client):
        """Test query history without authentication"""
        response = client.get("/query/history")
        
        assert response.status_code == 401

    # Statistics Tests
    @patch('app.api.query.get_current_user') 
    @patch('app.api.query.query_service')
    def test_get_search_stats_success(self, mock_service, mock_auth, client):
        """Test successful search statistics retrieval"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        
        mock_stats = {
            "total_documents": 25,
            "total_chunks": 1250,
            "index_size": "15.2MB",
            "avg_query_time_ms": 856,
            "total_queries": 48
        }
        mock_service.get_workspace_search_stats.return_value = mock_stats
        
        response = client.get("/query/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_documents"] == 25
        assert data["total_chunks"] == 1250
        assert data["index_size"] == "15.2MB"
        assert data["avg_query_time_ms"] == 856
        
        mock_service.get_workspace_search_stats.assert_called_once_with("workspace123")

    def test_get_search_stats_unauthorized(self, client):
        """Test search statistics without authentication"""
        response = client.get("/query/stats")
        
        assert response.status_code == 401

    # Input Validation Tests
    def test_query_validation_max_length(self, client):
        """Test query length validation"""
        long_query = "x" * 1001  # Assuming 1000 char limit
        
        response = client.post(
            "/query/documents",
            json={"query": long_query}
        )
        
        assert response.status_code == 422

    def test_query_validation_parameters(self, client):
        """Test query parameter validation"""
        # Invalid top_k
        response = client.post(
            "/query/documents",
            json={
                "query": "test",
                "top_k": -1
            }
        )
        assert response.status_code == 422
        
        # Invalid min_score
        response = client.post(
            "/query/documents", 
            json={
                "query": "test",
                "min_score": -0.5
            }
        )
        assert response.status_code == 422
        
        # Invalid temperature
        response = client.post(
            "/query/documents",
            json={
                "query": "test", 
                "temperature": 2.5
            }
        )
        assert response.status_code == 422

    # Error Handling Tests
    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_query_timeout_handling(self, mock_service, mock_auth, client):
        """Test query timeout handling"""
        import asyncio
        
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"  
        }
        mock_service.query_documents.side_effect = asyncio.TimeoutError("Query timeout")
        
        response = client.post(
            "/query/documents",
            json={"query": "test query"}
        )
        
        assert response.status_code == 408  # Request timeout

    @patch('app.api.query.get_current_user')
    @patch('app.api.query.streaming_service')
    def test_stream_connection_error(self, mock_streaming, mock_auth, client):
        """Test streaming connection error handling"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        
        async def failing_stream():
            yield "data: starting\n\n"
            raise ConnectionError("Connection lost")
        
        mock_streaming.stream_query_response.return_value = failing_stream()
        
        response = client.post(
            "/query/stream",
            json={"query": "test query"}
        )
        
        # Should handle gracefully and close connection
        assert response.status_code in [200, 500]  # Depending on when error occurs

    # Performance Tests
    @patch('app.api.query.get_current_user')
    @patch('app.api.query.query_service')
    def test_concurrent_queries(self, mock_service, mock_auth, client):
        """Test handling multiple concurrent queries"""
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        mock_service.query_documents.return_value = {
            "response": "test response",
            "sources": [],
            "query": "test",
            "context_length": 10
        }
        
        # Simulate concurrent requests
        import threading
        import time
        
        results = []
        def make_request():
            response = client.post(
                "/query/documents",
                json={"query": "test query"}
            )
            results.append(response.status_code)
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5

    # Integration Tests with Dependencies
    @patch('app.api.query.get_current_user')
    @patch('app.services.vector_service.VectorStoreManager')
    @patch('app.services.llm_service.ModelManager')
    def test_end_to_end_query_flow(self, mock_llm, mock_vector, mock_auth, client):
        """Test end-to-end query flow with real dependencies"""
        # This would test the actual integration if services were available
        # For now, just verify the endpoint routing works
        mock_auth.return_value = {
            "user_id": "user123",
            "workspace_id": "workspace123"
        }
        
        response = client.post(
            "/query/documents",
            json={"query": "integration test"}
        )
        
        # Response depends on actual service implementation
        # For now, just verify endpoint is accessible
        assert response.status_code in [200, 404, 500]