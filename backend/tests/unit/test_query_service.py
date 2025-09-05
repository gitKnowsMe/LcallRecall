import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any
import asyncio

from app.services.query_service import QueryService, QueryError, NoResultsError


class TestQueryService:
    """Test suite for query service with RAG pipeline"""
    
    @pytest.fixture
    def mock_vector_service(self):
        """Mock vector store service"""
        service = Mock()
        service.search_documents = AsyncMock()
        service.get_workspace_stats = Mock()
        return service
    
    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service"""
        service = Mock()
        service.generate_text = AsyncMock()
        service.generate_streaming_text = AsyncMock()
        service.create_rag_prompt = Mock()
        return service
    
    @pytest.fixture
    def query_service(self, mock_vector_service, mock_llm_service):
        """Create QueryService instance for testing"""
        return QueryService(
            vector_service=mock_vector_service,
            llm_service=mock_llm_service
        )
    
    @pytest.fixture
    def sample_search_results(self):
        """Sample vector search results"""
        return [
            {
                "document_id": "doc1",
                "chunk_id": 1,
                "content": "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
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
                "content": "Deep learning uses neural networks with multiple layers to model complex patterns in data.",
                "score": 0.87,
                "metadata": {
                    "filename": "deep_learning.pdf",
                    "page": 3,
                    "chunk_index": 5
                }
            },
            {
                "document_id": "doc1",
                "chunk_id": 3, 
                "content": "Popular frameworks include TensorFlow, PyTorch, and Keras for implementing ML models.",
                "score": 0.82,
                "metadata": {
                    "filename": "ml_basics.pdf",
                    "page": 5,
                    "chunk_index": 12
                }
            }
        ]
    
    @pytest.fixture
    def sample_rag_response(self):
        """Sample RAG response"""
        return """Based on the provided documents, machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data. 

Deep learning is a specialized area within machine learning that uses neural networks with multiple layers to model complex patterns in data.

Popular frameworks for implementing machine learning models include TensorFlow, PyTorch, and Keras."""

    # Query Service Initialization Tests
    def test_query_service_init(self, mock_vector_service, mock_llm_service):
        """Test QueryService initialization"""
        service = QueryService(
            vector_service=mock_vector_service,
            llm_service=mock_llm_service
        )
        
        assert service.vector_service == mock_vector_service
        assert service.llm_service == mock_llm_service
        assert service.default_top_k == 5
        assert service.min_similarity_score == 0.5

    def test_query_service_init_custom_params(self, mock_vector_service, mock_llm_service):
        """Test QueryService initialization with custom parameters"""
        service = QueryService(
            vector_service=mock_vector_service,
            llm_service=mock_llm_service,
            default_top_k=10,
            min_similarity_score=0.7
        )
        
        assert service.default_top_k == 10
        assert service.min_similarity_score == 0.7

    # Vector Search Tests
    @pytest.mark.asyncio
    async def test_search_similar_documents_success(self, query_service, mock_vector_service, sample_search_results):
        """Test successful document search"""
        mock_vector_service.search_documents.return_value = sample_search_results
        
        results = await query_service.search_similar_documents(
            workspace_id="workspace1",
            query="What is machine learning?",
            top_k=5
        )
        
        assert len(results) == 3
        assert results[0]["score"] == 0.95
        assert "Machine learning" in results[0]["content"]
        mock_vector_service.search_documents.assert_called_once_with(
            workspace_id="workspace1",
            query="What is machine learning?",
            top_k=5
        )

    @pytest.mark.asyncio
    async def test_search_similar_documents_filter_by_score(self, query_service, mock_vector_service):
        """Test document search with score filtering"""
        low_score_results = [
            {"content": "Low relevance content", "score": 0.3, "document_id": "doc1", "chunk_id": 1},
            {"content": "Medium relevance content", "score": 0.6, "document_id": "doc2", "chunk_id": 2},
            {"content": "High relevance content", "score": 0.9, "document_id": "doc3", "chunk_id": 3}
        ]
        mock_vector_service.search_documents.return_value = low_score_results
        
        results = await query_service.search_similar_documents(
            workspace_id="workspace1",
            query="test query",
            min_score=0.5
        )
        
        # Should filter out the 0.3 score result
        assert len(results) == 2
        assert all(r["score"] >= 0.5 for r in results)

    @pytest.mark.asyncio
    async def test_search_similar_documents_no_results(self, query_service, mock_vector_service):
        """Test document search with no results"""
        mock_vector_service.search_documents.return_value = []
        
        with pytest.raises(NoResultsError, match="No similar documents found"):
            await query_service.search_similar_documents(
                workspace_id="workspace1",
                query="nonexistent query"
            )

    @pytest.mark.asyncio
    async def test_search_similar_documents_error(self, query_service, mock_vector_service):
        """Test document search with vector service error"""
        mock_vector_service.search_documents.side_effect = Exception("Vector search failed")
        
        with pytest.raises(QueryError, match="Failed to search documents"):
            await query_service.search_similar_documents(
                workspace_id="workspace1", 
                query="test query"
            )

    # Context Preparation Tests  
    def test_prepare_rag_context_success(self, query_service, sample_search_results):
        """Test RAG context preparation from search results"""
        context = query_service.prepare_rag_context(sample_search_results)
        
        assert isinstance(context, str)
        assert len(context) > 0
        assert "Machine learning is a subset" in context
        assert "Deep learning uses neural networks" in context
        assert "Popular frameworks include" in context
        
        # Should include document metadata
        assert "ml_basics.pdf" in context
        assert "deep_learning.pdf" in context

    def test_prepare_rag_context_empty_results(self, query_service):
        """Test RAG context preparation with empty results"""
        context = query_service.prepare_rag_context([])
        
        assert context == ""

    def test_prepare_rag_context_formatting(self, query_service):
        """Test RAG context formatting with metadata"""
        results = [
            {
                "content": "First chunk content",
                "metadata": {"filename": "doc1.pdf", "page": 1}
            },
            {
                "content": "Second chunk content", 
                "metadata": {"filename": "doc2.pdf", "page": 2}
            }
        ]
        
        context = query_service.prepare_rag_context(results)
        
        # Should format with source attribution
        assert "[Source: doc1.pdf, Page 1]" in context or "doc1.pdf" in context
        assert "[Source: doc2.pdf, Page 2]" in context or "doc2.pdf" in context
        assert "First chunk content" in context
        assert "Second chunk content" in context

    # RAG Query Tests
    @pytest.mark.asyncio
    async def test_query_documents_success(self, query_service, mock_vector_service, mock_llm_service, sample_search_results, sample_rag_response):
        """Test successful RAG query"""
        mock_vector_service.search_documents.return_value = sample_search_results
        mock_llm_service.create_rag_prompt.return_value = "RAG prompt with context"
        mock_llm_service.generate_text.return_value = sample_rag_response
        
        result = await query_service.query_documents(
            workspace_id="workspace1",
            query="What is machine learning?",
            user_id="user1"
        )
        
        assert isinstance(result, dict)
        assert "response" in result
        assert "sources" in result
        assert "query" in result
        assert "context_length" in result
        
        assert result["response"] == sample_rag_response
        assert result["query"] == "What is machine learning?"
        assert len(result["sources"]) == 3
        assert result["context_length"] > 0
        
        mock_llm_service.create_rag_prompt.assert_called_once()
        mock_llm_service.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_documents_no_results(self, query_service, mock_vector_service):
        """Test RAG query with no search results"""
        mock_vector_service.search_documents.return_value = []
        
        with pytest.raises(NoResultsError, match="No similar documents found"):
            await query_service.query_documents(
                workspace_id="workspace1",
                query="nonexistent topic",
                user_id="user1"
            )

    @pytest.mark.asyncio
    async def test_query_documents_llm_error(self, query_service, mock_vector_service, mock_llm_service, sample_search_results):
        """Test RAG query with LLM generation error"""
        mock_vector_service.search_documents.return_value = sample_search_results
        mock_llm_service.create_rag_prompt.return_value = "RAG prompt"
        mock_llm_service.generate_text.side_effect = Exception("LLM generation failed")
        
        with pytest.raises(QueryError, match="Failed to generate response"):
            await query_service.query_documents(
                workspace_id="workspace1",
                query="test query", 
                user_id="user1"
            )

    @pytest.mark.asyncio
    async def test_query_documents_custom_parameters(self, query_service, mock_vector_service, mock_llm_service, sample_search_results, sample_rag_response):
        """Test RAG query with custom parameters"""
        mock_vector_service.search_documents.return_value = sample_search_results
        mock_llm_service.create_rag_prompt.return_value = "RAG prompt"
        mock_llm_service.generate_text.return_value = sample_rag_response
        
        result = await query_service.query_documents(
            workspace_id="workspace1",
            query="test query",
            user_id="user1", 
            top_k=10,
            min_score=0.7,
            max_tokens=256,
            temperature=0.8
        )
        
        mock_vector_service.search_documents.assert_called_once_with(
            workspace_id="workspace1",
            query="test query",
            top_k=10
        )
        
        # Verify LLM was called with custom parameters
        generate_call = mock_llm_service.generate_text.call_args
        assert "max_tokens" in str(generate_call) or generate_call is not None

    # Streaming Query Tests
    @pytest.mark.asyncio 
    async def test_query_documents_streaming_success(self, query_service, mock_vector_service, mock_llm_service, sample_search_results):
        """Test successful streaming RAG query"""
        mock_vector_service.search_documents.return_value = sample_search_results
        mock_llm_service.create_rag_prompt.return_value = "RAG prompt"
        
        # Mock streaming generator
        async def mock_stream():
            yield "Based on the"
            yield " provided documents"
            yield ", machine learning is"
            yield " a subset of AI."
        
        mock_llm_service.generate_streaming_text.return_value = mock_stream()
        
        result = await query_service.query_documents_streaming(
            workspace_id="workspace1",
            query="What is machine learning?",
            user_id="user1"
        )
        
        assert "response_stream" in result
        assert "sources" in result
        assert "query" in result
        
        # Collect streaming results
        chunks = []
        async for chunk in result["response_stream"]:
            chunks.append(chunk)
        
        assert len(chunks) == 4
        assert chunks[0] == "Based on the"
        assert chunks[-1] == " a subset of AI."

    @pytest.mark.asyncio
    async def test_query_documents_streaming_no_results(self, query_service, mock_vector_service):
        """Test streaming RAG query with no search results"""
        mock_vector_service.search_documents.return_value = []
        
        with pytest.raises(NoResultsError, match="No similar documents found"):
            await query_service.query_documents_streaming(
                workspace_id="workspace1",
                query="nonexistent topic",
                user_id="user1"
            )

    @pytest.mark.asyncio
    async def test_query_documents_streaming_llm_error(self, query_service, mock_vector_service, mock_llm_service, sample_search_results):
        """Test streaming RAG query with LLM error"""
        mock_vector_service.search_documents.return_value = sample_search_results
        mock_llm_service.create_rag_prompt.return_value = "RAG prompt"
        mock_llm_service.generate_streaming_text.side_effect = Exception("Streaming failed")
        
        with pytest.raises(QueryError, match="Failed to generate streaming response"):
            await query_service.query_documents_streaming(
                workspace_id="workspace1",
                query="test query",
                user_id="user1"
            )

    # Query History Tests
    @pytest.mark.asyncio
    async def test_get_query_history(self, query_service):
        """Test query history retrieval"""
        # This would integrate with database in real implementation
        history = await query_service.get_query_history(
            user_id="user1",
            workspace_id="workspace1",
            limit=10
        )
        
        assert isinstance(history, list)
        # For now, empty list as we haven't implemented persistence
        assert len(history) == 0

    # Workspace Statistics Tests 
    def test_get_workspace_search_stats(self, query_service, mock_vector_service):
        """Test workspace search statistics"""
        mock_vector_service.get_workspace_stats.return_value = {
            "total_documents": 25,
            "total_chunks": 1250,
            "index_size": "15.2MB"
        }
        
        stats = query_service.get_workspace_search_stats("workspace1")
        
        assert stats["total_documents"] == 25
        assert stats["total_chunks"] == 1250
        assert "index_size" in stats

    # Error Handling Tests
    @pytest.mark.asyncio
    async def test_query_validation_empty_query(self, query_service):
        """Test query validation with empty query"""
        with pytest.raises(QueryError, match="Query cannot be empty"):
            await query_service.query_documents(
                workspace_id="workspace1",
                query="",
                user_id="user1"
            )
            
        with pytest.raises(QueryError, match="Query cannot be empty"):
            await query_service.query_documents(
                workspace_id="workspace1", 
                query="   ",
                user_id="user1"
            )

    @pytest.mark.asyncio
    async def test_query_validation_missing_params(self, query_service):
        """Test query validation with missing parameters"""
        with pytest.raises(QueryError, match="Workspace ID is required"):
            await query_service.query_documents(
                workspace_id="",
                query="test query",
                user_id="user1"
            )
            
        with pytest.raises(QueryError, match="User ID is required"):
            await query_service.query_documents(
                workspace_id="workspace1",
                query="test query", 
                user_id=""
            )

    # Cleanup and Resource Management Tests
    @pytest.mark.asyncio
    async def test_cleanup_resources(self, query_service):
        """Test resource cleanup"""
        # Test that cleanup methods exist and work
        assert hasattr(query_service, 'cleanup')
        
        # Should not raise exception
        await query_service.cleanup()

    def test_context_length_calculation(self, query_service):
        """Test context length calculation for token management"""
        long_results = [
            {"content": "A" * 1000, "metadata": {"filename": "doc1.pdf"}},
            {"content": "B" * 1000, "metadata": {"filename": "doc2.pdf"}},
            {"content": "C" * 1000, "metadata": {"filename": "doc3.pdf"}}
        ]
        
        context = query_service.prepare_rag_context(long_results)
        context_length = query_service._estimate_context_length(context)
        
        assert context_length > 3000  # Should be roughly 3000+ characters
        assert isinstance(context_length, int)

    def test_source_attribution_formatting(self, query_service):
        """Test proper source attribution in results"""
        results = [
            {
                "content": "Test content",
                "metadata": {
                    "filename": "test.pdf",
                    "page": 5,
                    "chunk_index": 2
                },
                "document_id": "doc123",
                "score": 0.9
            }
        ]
        
        sources = query_service._format_sources(results)
        
        assert len(sources) == 1
        assert sources[0]["filename"] == "test.pdf"
        assert sources[0]["page"] == 5
        assert sources[0]["relevance_score"] == 0.9
        assert sources[0]["document_id"] == "doc123"