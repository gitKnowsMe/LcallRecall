import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import tempfile
import os
from typing import AsyncGenerator, List, Dict

from app.services.query_service import QueryService
from app.services.streaming_service import StreamingService
from app.services.vector_service import VectorStoreManager
from app.services.llm_service import ModelManager


class TestEndToEndQueryWorkflow:
    """Integration tests for complete query workflow"""
    
    @pytest.fixture
    def mock_model_manager(self):
        """Mock Phi-2 model manager"""
        manager = Mock(spec=ModelManager)
        manager.generate_text = AsyncMock()
        manager.generate_streaming_text = AsyncMock()
        manager.create_rag_prompt = Mock()
        manager.is_loaded = True
        return manager
    
    @pytest.fixture
    def mock_vector_manager(self):
        """Mock FAISS vector store manager"""
        manager = Mock(spec=VectorStoreManager)
        manager.search_documents = AsyncMock()
        manager.add_documents = AsyncMock()
        manager.get_workspace_stats = Mock()
        manager.workspace_exists = Mock(return_value=True)
        return manager
    
    @pytest.fixture
    def query_service(self, mock_vector_manager, mock_model_manager):
        """Create QueryService with mocked dependencies"""
        return QueryService(
            vector_service=mock_vector_manager,
            llm_service=mock_model_manager
        )
    
    @pytest.fixture
    def streaming_service(self, query_service):
        """Create StreamingService with query service"""
        return StreamingService(query_service=query_service)
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing"""
        return [
            {
                "document_id": "ml_guide_1",
                "filename": "machine_learning_guide.pdf",
                "content": """Machine Learning Fundamentals
                
                Machine learning is a subset of artificial intelligence (AI) that focuses on the development of algorithms and statistical models that enable computer systems to learn and improve from experience without being explicitly programmed.

                Key Concepts:
                1. Supervised Learning: Uses labeled training data to learn a mapping function
                2. Unsupervised Learning: Finds hidden patterns in data without labels  
                3. Reinforcement Learning: Learns through interaction with environment

                Popular Algorithms:
                - Linear Regression
                - Decision Trees
                - Neural Networks
                - Support Vector Machines""",
                "metadata": {
                    "page_count": 5,
                    "file_size": 2048000
                }
            },
            {
                "document_id": "dl_basics_2", 
                "filename": "deep_learning_basics.pdf",
                "content": """Deep Learning Introduction

                Deep learning is a specialized subset of machine learning that uses artificial neural networks with multiple layers (deep networks) to model and understand complex patterns in data.

                Architecture Types:
                1. Feedforward Neural Networks
                2. Convolutional Neural Networks (CNNs)
                3. Recurrent Neural Networks (RNNs) 
                4. Transformer Networks

                Popular Frameworks:
                - TensorFlow: Google's open-source framework
                - PyTorch: Facebook's dynamic computation framework
                - Keras: High-level neural network API""",
                "metadata": {
                    "page_count": 3,
                    "file_size": 1536000
                }
            }
        ]
    
    @pytest.fixture  
    def sample_chunks(self, sample_documents):
        """Sample document chunks for vector search"""
        return [
            {
                "document_id": "ml_guide_1",
                "chunk_id": 1,
                "content": "Machine learning is a subset of artificial intelligence (AI) that focuses on the development of algorithms and statistical models that enable computer systems to learn and improve from experience without being explicitly programmed.",
                "score": 0.95,
                "metadata": {
                    "filename": "machine_learning_guide.pdf",
                    "page": 1,
                    "chunk_index": 0
                }
            },
            {
                "document_id": "ml_guide_1",
                "chunk_id": 2, 
                "content": "Supervised Learning: Uses labeled training data to learn a mapping function. Unsupervised Learning: Finds hidden patterns in data without labels. Reinforcement Learning: Learns through interaction with environment.",
                "score": 0.87,
                "metadata": {
                    "filename": "machine_learning_guide.pdf", 
                    "page": 2,
                    "chunk_index": 3
                }
            },
            {
                "document_id": "dl_basics_2",
                "chunk_id": 3,
                "content": "Deep learning is a specialized subset of machine learning that uses artificial neural networks with multiple layers (deep networks) to model and understand complex patterns in data.",
                "score": 0.82,
                "metadata": {
                    "filename": "deep_learning_basics.pdf",
                    "page": 1,
                    "chunk_index": 0
                }
            }
        ]

    # End-to-End Query Workflow Tests
    @pytest.mark.asyncio
    async def test_complete_query_workflow_success(self, query_service, mock_vector_manager, mock_model_manager, sample_chunks):
        """Test complete query workflow from search to response generation"""
        # Setup mocks
        mock_vector_manager.search_documents.return_value = sample_chunks
        mock_model_manager.create_rag_prompt.return_value = "You are an AI assistant. Answer based on context: [CONTEXT] User question: What is machine learning?"
        mock_model_manager.generate_text.return_value = """Based on the provided context, machine learning is a subset of artificial intelligence (AI) that focuses on the development of algorithms and statistical models that enable computer systems to learn and improve from experience without being explicitly programmed.

The context shows that machine learning includes several key approaches:
- Supervised Learning: Uses labeled training data to learn mapping functions
- Unsupervised Learning: Finds hidden patterns in data without labels  
- Reinforcement Learning: Learns through interaction with the environment

This technology forms the foundation for more advanced techniques like deep learning, which uses neural networks with multiple layers to model complex patterns."""
        
        # Execute query
        result = await query_service.query_documents(
            workspace_id="test_workspace",
            query="What is machine learning and what are its main types?",
            user_id="test_user"
        )
        
        # Verify workflow execution
        assert isinstance(result, dict)
        assert "response" in result
        assert "sources" in result
        assert "query" in result
        assert "context_length" in result
        
        # Verify response content
        assert "machine learning" in result["response"].lower()
        assert "supervised learning" in result["response"].lower()
        assert "unsupervised learning" in result["response"].lower()
        
        # Verify sources
        assert len(result["sources"]) == 3
        assert result["sources"][0]["filename"] == "machine_learning_guide.pdf"
        
        # Verify service calls
        mock_vector_manager.search_documents.assert_called_once()
        mock_model_manager.create_rag_prompt.assert_called_once()
        mock_model_manager.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_query_workflow_success(self, streaming_service, query_service, mock_vector_manager, mock_model_manager, sample_chunks):
        """Test complete streaming query workflow"""
        # Setup mocks
        mock_vector_manager.search_documents.return_value = sample_chunks
        mock_model_manager.create_rag_prompt.return_value = "RAG prompt with context"
        
        # Mock streaming response
        async def mock_stream():
            response_parts = [
                "Based on the",
                " provided context,",
                " machine learning is",
                " a subset of",
                " artificial intelligence",
                " that focuses on",
                " algorithm development."
            ]
            for part in response_parts:
                yield part
                await asyncio.sleep(0.01)  # Simulate processing delay
        
        mock_model_manager.generate_streaming_text.return_value = mock_stream()
        
        # Execute streaming query
        result = await streaming_service.stream_query_response(
            workspace_id="test_workspace", 
            query="What is machine learning?",
            user_id="test_user"
        )
        
        # Collect streamed chunks
        chunks = []
        async for chunk in result:
            chunks.append(chunk)
            if "event: complete" in chunk:
                break
        
        # Verify streaming workflow
        assert len(chunks) >= 3  # metadata + content chunks + complete
        
        # Verify metadata chunk
        metadata_chunk = next(c for c in chunks if "event: metadata" in c)
        assert "sources" in metadata_chunk
        
        # Verify content chunks
        content_chunks = [c for c in chunks if "event: chunk" in c]
        assert len(content_chunks) > 0
        
        # Verify completion
        complete_chunk = next(c for c in chunks if "event: complete" in c)
        assert complete_chunk is not None

    @pytest.mark.asyncio
    async def test_query_with_no_relevant_documents(self, query_service, mock_vector_manager):
        """Test query workflow when no relevant documents found"""
        from app.services.query_service import NoResultsError
        
        # Setup: no search results
        mock_vector_manager.search_documents.return_value = []
        
        # Execute query
        with pytest.raises(NoResultsError, match="No similar documents found"):
            await query_service.query_documents(
                workspace_id="test_workspace",
                query="quantum computing advanced topics",
                user_id="test_user"
            )

    @pytest.mark.asyncio 
    async def test_query_with_low_relevance_scores(self, query_service, mock_vector_manager, mock_model_manager):
        """Test query workflow with low relevance scores"""
        # Setup: low-score results that get filtered out
        low_score_chunks = [
            {
                "document_id": "doc1",
                "chunk_id": 1,
                "content": "Unrelated content about cooking recipes",
                "score": 0.3,
                "metadata": {"filename": "cooking.pdf", "page": 1}
            }
        ]
        
        mock_vector_manager.search_documents.return_value = low_score_chunks
        
        # Execute with default min_score (0.5)
        from app.services.query_service import NoResultsError
        with pytest.raises(NoResultsError):
            await query_service.query_documents(
                workspace_id="test_workspace",
                query="machine learning algorithms",
                user_id="test_user"
            )

    @pytest.mark.asyncio
    async def test_rag_context_preparation_and_formatting(self, query_service, sample_chunks):
        """Test RAG context preparation with proper formatting"""
        context = query_service.prepare_rag_context(sample_chunks)
        
        # Verify context structure
        assert isinstance(context, str)
        assert len(context) > 0
        
        # Verify all chunk content is included
        for chunk in sample_chunks:
            assert chunk["content"] in context
        
        # Verify source attribution
        assert "machine_learning_guide.pdf" in context
        assert "deep_learning_basics.pdf" in context
        
        # Verify proper formatting (sources should be distinguishable)
        assert "Source:" in context or "[" in context  # Some form of source marking

    @pytest.mark.asyncio
    async def test_llm_prompt_creation_with_context(self, query_service, mock_model_manager, sample_chunks):
        """Test LLM prompt creation with proper context injection"""
        mock_vector_manager = Mock()
        mock_vector_manager.search_documents.return_value = sample_chunks
        query_service.vector_service = mock_vector_manager
        
        # Setup prompt creation mock
        mock_model_manager.create_rag_prompt.return_value = "System prompt with context"
        mock_model_manager.generate_text.return_value = "Response"
        
        # Execute query
        await query_service.query_documents(
            workspace_id="test_workspace",
            query="What is machine learning?",
            user_id="test_user"
        )
        
        # Verify prompt creation was called with context
        mock_model_manager.create_rag_prompt.assert_called_once()
        call_args = mock_model_manager.create_rag_prompt.call_args[1]
        
        assert "context" in call_args
        assert "query" in call_args
        assert call_args["query"] == "What is machine learning?"
        assert len(call_args["context"]) > 0

    # Performance and Stress Tests
    @pytest.mark.asyncio
    async def test_concurrent_query_processing(self, query_service, mock_vector_manager, mock_model_manager, sample_chunks):
        """Test handling multiple concurrent queries"""
        # Setup mocks for concurrent access
        mock_vector_manager.search_documents.return_value = sample_chunks
        mock_model_manager.create_rag_prompt.return_value = "RAG prompt"
        mock_model_manager.generate_text.return_value = "Concurrent response"
        
        # Execute multiple concurrent queries
        queries = [
            "What is machine learning?",
            "Explain deep learning",
            "Compare supervised vs unsupervised learning",
            "What are neural networks?",
            "Describe reinforcement learning"
        ]
        
        tasks = []
        for i, query in enumerate(queries):
            task = query_service.query_documents(
                workspace_id=f"workspace_{i}",
                query=query,
                user_id=f"user_{i}"
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all queries succeeded
        assert len(results) == 5
        for result in results:
            assert not isinstance(result, Exception)
            assert "response" in result

    @pytest.mark.asyncio
    async def test_large_context_handling(self, query_service, mock_vector_manager, mock_model_manager):
        """Test handling queries with large context"""
        # Create large chunks
        large_chunks = []
        for i in range(10):  # Many chunks
            large_chunks.append({
                "document_id": f"large_doc_{i}",
                "chunk_id": i,
                "content": "Large content section. " * 200,  # ~4000 characters each
                "score": 0.8,
                "metadata": {
                    "filename": f"large_document_{i}.pdf",
                    "page": 1,
                    "chunk_index": i
                }
            })
        
        mock_vector_manager.search_documents.return_value = large_chunks
        mock_model_manager.create_rag_prompt.return_value = "Large context prompt"
        mock_model_manager.generate_text.return_value = "Response with large context"
        
        # Execute query
        result = await query_service.query_documents(
            workspace_id="test_workspace",
            query="Complex query requiring large context",
            user_id="test_user"
        )
        
        # Verify handling of large context
        assert "response" in result
        assert result["context_length"] > 30000  # Should be quite large
        assert len(result["sources"]) == 10

    @pytest.mark.asyncio
    async def test_error_recovery_in_workflow(self, query_service, mock_vector_manager, mock_model_manager, sample_chunks):
        """Test error recovery at different workflow stages"""
        from app.services.query_service import QueryError
        
        # Test 1: Vector search fails
        mock_vector_manager.search_documents.side_effect = Exception("Vector search failed")
        
        with pytest.raises(QueryError, match="Failed to search documents"):
            await query_service.query_documents(
                workspace_id="test_workspace",
                query="test query",
                user_id="test_user"
            )
        
        # Test 2: LLM generation fails
        mock_vector_manager.search_documents.side_effect = None
        mock_vector_manager.search_documents.return_value = sample_chunks
        mock_model_manager.create_rag_prompt.return_value = "Prompt"
        mock_model_manager.generate_text.side_effect = Exception("LLM failed")
        
        with pytest.raises(QueryError, match="Failed to generate response"):
            await query_service.query_documents(
                workspace_id="test_workspace", 
                query="test query",
                user_id="test_user"
            )

    @pytest.mark.asyncio
    async def test_streaming_error_recovery(self, streaming_service, query_service, mock_vector_manager, mock_model_manager, sample_chunks):
        """Test streaming error recovery"""
        from app.services.streaming_service import StreamingError
        
        # Setup mocks
        mock_vector_manager.search_documents.return_value = sample_chunks
        mock_model_manager.create_rag_prompt.return_value = "Prompt"
        
        # Mock failing stream
        async def failing_stream():
            yield "Start of response"
            await asyncio.sleep(0.01)
            raise Exception("Streaming failed")
        
        mock_model_manager.generate_streaming_text.return_value = failing_stream()
        
        # Test error propagation
        with pytest.raises(StreamingError):
            async for chunk in streaming_service.stream_query_response(
                workspace_id="test_workspace",
                query="test query", 
                user_id="test_user"
            ):
                pass

    # Memory and Resource Management Tests
    @pytest.mark.asyncio
    async def test_memory_cleanup_after_query(self, query_service, mock_vector_manager, mock_model_manager, sample_chunks):
        """Test proper memory cleanup after query processing"""
        mock_vector_manager.search_documents.return_value = sample_chunks
        mock_model_manager.create_rag_prompt.return_value = "Prompt"
        mock_model_manager.generate_text.return_value = "Response"
        
        # Execute query
        result = await query_service.query_documents(
            workspace_id="test_workspace",
            query="test query",
            user_id="test_user"
        )
        
        # Verify result is properly formed
        assert result is not None
        
        # Verify cleanup (this would be implementation specific)
        # For now, just ensure no exceptions during cleanup
        await query_service.cleanup()

    # Integration with Real Components (when available)
    @pytest.mark.skipif(True, reason="Requires actual model and vector store setup")
    @pytest.mark.asyncio
    async def test_real_components_integration(self):
        """Test integration with actual Phi-2 model and FAISS"""
        # This test would run with actual components
        # Skipped for now as it requires model setup
        pass

    # Workspace Isolation Tests
    @pytest.mark.asyncio
    async def test_workspace_isolation(self, query_service, mock_vector_manager, mock_model_manager, sample_chunks):
        """Test that queries are isolated by workspace"""
        mock_vector_manager.search_documents.return_value = sample_chunks
        mock_model_manager.create_rag_prompt.return_value = "Prompt"
        mock_model_manager.generate_text.return_value = "Response"
        
        # Execute queries for different workspaces
        result1 = await query_service.query_documents(
            workspace_id="workspace_1",
            query="test query",
            user_id="user_1"
        )
        
        result2 = await query_service.query_documents(
            workspace_id="workspace_2", 
            query="test query",
            user_id="user_2"
        )
        
        # Verify both succeed and are independent
        assert result1 is not None
        assert result2 is not None
        
        # Verify search was called with correct workspace IDs
        calls = mock_vector_manager.search_documents.call_args_list
        assert len(calls) == 2
        assert calls[0][1]["workspace_id"] == "workspace_1"
        assert calls[1][1]["workspace_id"] == "workspace_2"