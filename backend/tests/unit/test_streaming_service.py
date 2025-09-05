import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import json
from typing import AsyncGenerator

from app.services.streaming_service import StreamingService, StreamingError


class TestStreamingService:
    """Test suite for streaming response service"""
    
    @pytest.fixture
    def mock_query_service(self):
        """Mock query service"""
        service = Mock()
        service.query_documents_streaming = AsyncMock()
        service.search_similar_documents = AsyncMock()
        return service
    
    @pytest.fixture
    def streaming_service(self, mock_query_service):
        """Create StreamingService instance for testing"""
        return StreamingService(query_service=mock_query_service)
    
    @pytest.fixture
    def mock_streaming_response(self):
        """Mock streaming query response"""
        async def mock_stream():
            yield "Based on"
            yield " the provided"
            yield " documents,"
            yield " machine learning"
            yield " is a subset"
            yield " of artificial"
            yield " intelligence."
        
        return {
            "response_stream": mock_stream(),
            "sources": [
                {
                    "document_id": "doc1", 
                    "filename": "ml_basics.pdf",
                    "page": 1,
                    "relevance_score": 0.95
                }
            ],
            "query": "What is machine learning?",
            "context_length": 256
        }

    # Streaming Service Initialization Tests
    def test_streaming_service_init(self, mock_query_service):
        """Test StreamingService initialization"""
        service = StreamingService(query_service=mock_query_service)
        
        assert service.query_service == mock_query_service
        assert service.chunk_size == 1024
        assert service.flush_interval == 0.1

    def test_streaming_service_init_custom_params(self, mock_query_service):
        """Test StreamingService initialization with custom parameters"""
        service = StreamingService(
            query_service=mock_query_service,
            chunk_size=512,
            flush_interval=0.05
        )
        
        assert service.chunk_size == 512
        assert service.flush_interval == 0.05

    # SSE Formatting Tests
    def test_format_sse_message_data_only(self, streaming_service):
        """Test SSE message formatting with data only"""
        message = streaming_service._format_sse_message("test data")
        
        assert message == "data: test data\n\n"

    def test_format_sse_message_with_event_type(self, streaming_service):
        """Test SSE message formatting with event type"""
        message = streaming_service._format_sse_message(
            data="test data",
            event_type="chunk"
        )
        
        assert "event: chunk\n" in message
        assert "data: test data\n\n" in message

    def test_format_sse_message_with_id(self, streaming_service):
        """Test SSE message formatting with message ID"""
        message = streaming_service._format_sse_message(
            data="test data",
            message_id="123"
        )
        
        assert "id: 123\n" in message
        assert "data: test data\n\n" in message

    def test_format_sse_message_json_data(self, streaming_service):
        """Test SSE message formatting with JSON data"""
        data = {"type": "chunk", "content": "test", "index": 1}
        message = streaming_service._format_sse_message(data)
        
        expected_json = json.dumps(data)
        assert f"data: {expected_json}\n\n" == message

    def test_format_sse_message_multiline_data(self, streaming_service):
        """Test SSE message formatting with multiline data"""
        multiline_data = "Line 1\nLine 2\nLine 3"
        message = streaming_service._format_sse_message(multiline_data)
        
        # Each line should be prefixed with "data: "
        assert "data: Line 1\n" in message
        assert "data: Line 2\n" in message  
        assert "data: Line 3\n" in message
        assert message.endswith("\n")

    # Streaming Response Generation Tests
    @pytest.mark.asyncio
    async def test_stream_query_response_success(self, streaming_service, mock_query_service, mock_streaming_response):
        """Test successful streaming query response"""
        mock_query_service.query_documents_streaming.return_value = mock_streaming_response
        
        chunks = []
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1",
            query="What is machine learning?",
            user_id="user1"
        ):
            chunks.append(chunk)
        
        # Should have metadata event + content chunks + completion event
        assert len(chunks) >= 3
        
        # First chunk should be metadata
        assert "event: metadata\n" in chunks[0]
        
        # Should have content chunks
        content_chunks = [c for c in chunks if "event: chunk\n" in c]
        assert len(content_chunks) > 0
        
        # Last chunk should be completion
        assert "event: complete\n" in chunks[-1]

    @pytest.mark.asyncio
    async def test_stream_query_response_with_sources(self, streaming_service, mock_query_service, mock_streaming_response):
        """Test streaming response includes source information"""
        mock_query_service.query_documents_streaming.return_value = mock_streaming_response
        
        chunks = []
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1",
            query="test query",
            user_id="user1"
        ):
            chunks.append(chunk)
        
        # Find metadata chunk
        metadata_chunk = next(c for c in chunks if "event: metadata\n" in c)
        
        # Extract JSON data from metadata
        data_line = next(line for line in metadata_chunk.split('\n') if line.startswith('data: '))
        metadata = json.loads(data_line[6:])  # Remove "data: " prefix
        
        assert "sources" in metadata
        assert len(metadata["sources"]) == 1
        assert metadata["sources"][0]["filename"] == "ml_basics.pdf"

    @pytest.mark.asyncio
    async def test_stream_query_response_error_handling(self, streaming_service, mock_query_service):
        """Test streaming response error handling"""
        mock_query_service.query_documents_streaming.side_effect = Exception("Query failed")
        
        with pytest.raises(StreamingError, match="Failed to stream query response"):
            async for chunk in streaming_service.stream_query_response(
                workspace_id="workspace1",
                query="test query",
                user_id="user1"
            ):
                pass

    @pytest.mark.asyncio
    async def test_stream_query_response_empty_query(self, streaming_service):
        """Test streaming response with empty query"""
        with pytest.raises(StreamingError, match="Query cannot be empty"):
            async for chunk in streaming_service.stream_query_response(
                workspace_id="workspace1",
                query="",
                user_id="user1"  
            ):
                pass

    # Chunk Buffering Tests
    @pytest.mark.asyncio
    async def test_stream_with_buffering(self, streaming_service, mock_query_service):
        """Test streaming with chunk buffering"""
        async def mock_large_stream():
            # Generate many small chunks
            for i in range(50):
                yield f"chunk{i} "
        
        mock_response = {
            "response_stream": mock_large_stream(),
            "sources": [],
            "query": "test",
            "context_length": 100
        }
        mock_query_service.query_documents_streaming.return_value = mock_response
        
        # Set small buffer size for testing
        streaming_service.chunk_size = 50
        
        chunks = []
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1",
            query="test query", 
            user_id="user1"
        ):
            if "event: chunk\n" in chunk:
                chunks.append(chunk)
        
        # Should have fewer output chunks than input due to buffering
        assert len(chunks) < 50

    @pytest.mark.asyncio
    async def test_stream_flush_on_interval(self, streaming_service, mock_query_service):
        """Test streaming flushes on time interval"""
        async def slow_stream():
            yield "start"
            await asyncio.sleep(0.2)  # Longer than flush interval
            yield "end"
        
        mock_response = {
            "response_stream": slow_stream(),
            "sources": [],
            "query": "test",
            "context_length": 10
        }
        mock_query_service.query_documents_streaming.return_value = mock_response
        
        streaming_service.flush_interval = 0.1
        
        start_time = asyncio.get_event_loop().time()
        chunks = []
        
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1",
            query="test query",
            user_id="user1"
        ):
            if "event: chunk\n" in chunk:
                chunks.append(chunk)
                current_time = asyncio.get_event_loop().time()
                # First content chunk should come quickly due to flush
                if len(chunks) == 1:
                    assert current_time - start_time < 0.15

    # Progress Tracking Tests  
    @pytest.mark.asyncio
    async def test_stream_with_progress_events(self, streaming_service, mock_query_service, mock_streaming_response):
        """Test streaming includes progress events"""
        mock_query_service.query_documents_streaming.return_value = mock_streaming_response
        
        chunks = []
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1", 
            query="test query",
            user_id="user1",
            include_progress=True
        ):
            chunks.append(chunk)
        
        # Should have progress events
        progress_chunks = [c for c in chunks if "event: progress\n" in c]
        assert len(progress_chunks) > 0
        
        # Check progress data format
        progress_chunk = progress_chunks[0]
        data_line = next(line for line in progress_chunk.split('\n') if line.startswith('data: '))
        progress_data = json.loads(data_line[6:])
        
        assert "stage" in progress_data
        assert "progress" in progress_data

    # Connection Management Tests
    @pytest.mark.asyncio
    async def test_handle_client_disconnect(self, streaming_service, mock_query_service):
        """Test handling client disconnect during streaming"""
        async def infinite_stream():
            i = 0
            while True:
                yield f"chunk{i}"
                i += 1
                await asyncio.sleep(0.01)
        
        mock_response = {
            "response_stream": infinite_stream(),
            "sources": [],
            "query": "test",
            "context_length": 10
        }
        mock_query_service.query_documents_streaming.return_value = mock_response
        
        # Simulate client disconnect by cancelling
        stream_task = asyncio.create_task(
            streaming_service.stream_query_response(
                workspace_id="workspace1",
                query="test query",
                user_id="user1"
            ).__anext__()
        )
        
        await asyncio.sleep(0.05)  # Let it start streaming
        stream_task.cancel()
        
        # Should handle cancellation gracefully
        with pytest.raises(asyncio.CancelledError):
            await stream_task

    # Error Recovery Tests
    @pytest.mark.asyncio
    async def test_stream_partial_failure_recovery(self, streaming_service, mock_query_service):
        """Test streaming recovery from partial failures"""
        call_count = 0
        
        async def failing_stream():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield "chunk1"
                raise Exception("Stream error")
            else:
                yield "recovered chunk"
        
        mock_response = {
            "response_stream": failing_stream(),
            "sources": [],
            "query": "test",
            "context_length": 10
        }
        mock_query_service.query_documents_streaming.return_value = mock_response
        
        # Should propagate the error rather than recovering
        with pytest.raises(StreamingError):
            async for chunk in streaming_service.stream_query_response(
                workspace_id="workspace1",
                query="test query",
                user_id="user1"
            ):
                pass

    # Memory Management Tests
    @pytest.mark.asyncio
    async def test_stream_memory_cleanup(self, streaming_service, mock_query_service, mock_streaming_response):
        """Test streaming properly cleans up memory"""
        mock_query_service.query_documents_streaming.return_value = mock_streaming_response
        
        # Process stream completely
        chunks = []
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1",
            query="test query", 
            user_id="user1"
        ):
            chunks.append(chunk)
        
        # Verify stream was exhausted
        assert len(chunks) > 0
        
        # Buffer should be cleared
        assert not hasattr(streaming_service, '_current_buffer') or not streaming_service._current_buffer

    # Custom Event Types Tests
    @pytest.mark.asyncio
    async def test_stream_custom_event_types(self, streaming_service, mock_query_service, mock_streaming_response):
        """Test streaming with custom event types"""
        mock_query_service.query_documents_streaming.return_value = mock_streaming_response
        
        chunks = []
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1",
            query="test query",
            user_id="user1"
        ):
            chunks.append(chunk)
        
        # Check for different event types
        event_types = []
        for chunk in chunks:
            for line in chunk.split('\n'):
                if line.startswith('event: '):
                    event_types.append(line[7:])
        
        assert "metadata" in event_types
        assert "chunk" in event_types  
        assert "complete" in event_types

    # Performance Tests
    @pytest.mark.asyncio
    async def test_streaming_performance_large_response(self, streaming_service, mock_query_service):
        """Test streaming performance with large response"""
        async def large_stream():
            # Generate large response
            for i in range(1000):
                yield f"This is chunk number {i} with some content. "
        
        mock_response = {
            "response_stream": large_stream(),
            "sources": [],
            "query": "test",
            "context_length": 10000
        }
        mock_query_service.query_documents_streaming.return_value = mock_response
        
        start_time = asyncio.get_event_loop().time()
        chunk_count = 0
        
        async for chunk in streaming_service.stream_query_response(
            workspace_id="workspace1",
            query="test query",
            user_id="user1"
        ):
            if "event: chunk\n" in chunk:
                chunk_count += 1
        
        end_time = asyncio.get_event_loop().time()
        
        # Should process efficiently (less than 1 second for 1000 chunks)
        assert end_time - start_time < 1.0
        assert chunk_count > 0

    # Cleanup Tests
    @pytest.mark.asyncio
    async def test_cleanup_resources(self, streaming_service):
        """Test resource cleanup"""
        assert hasattr(streaming_service, 'cleanup')
        
        # Should not raise exception
        await streaming_service.cleanup()