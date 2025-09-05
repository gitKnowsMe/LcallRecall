import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional, Union
import traceback

logger = logging.getLogger(__name__)


class StreamingError(Exception):
    """Base exception for streaming service errors"""
    pass


class StreamingService:
    """Service for streaming query responses using Server-Sent Events"""
    
    def __init__(
        self,
        query_service,
        chunk_size: int = 1024,
        flush_interval: float = 0.1
    ):
        """
        Initialize streaming service
        
        Args:
            query_service: Query service for document processing
            chunk_size: Buffer size for streaming chunks
            flush_interval: Time interval to flush buffer (seconds)
        """
        self.query_service = query_service
        self.chunk_size = chunk_size
        self.flush_interval = flush_interval
    
    def _format_sse_message(
        self,
        data: Union[str, Dict, Any],
        event_type: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> str:
        """
        Format Server-Sent Events message
        
        Args:
            data: Data to send (string or JSON-serializable object)
            event_type: Event type (optional)
            message_id: Message ID (optional)
            
        Returns:
            Formatted SSE message string
        """
        message_parts = []
        
        # Add event type if specified
        if event_type:
            message_parts.append(f"event: {event_type}")
        
        # Add message ID if specified
        if message_id:
            message_parts.append(f"id: {message_id}")
        
        # Format data
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data)
        else:
            data_str = str(data)
        
        # Handle multiline data
        if '\n' in data_str:
            for line in data_str.split('\n'):
                message_parts.append(f"data: {line}")
        else:
            message_parts.append(f"data: {data_str}")
        
        # Add empty line to complete message
        message_parts.append("")
        
        return '\n'.join(message_parts) + '\n'
    
    async def stream_query_response(
        self,
        workspace_id: str,
        query: str,
        user_id: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        include_progress: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Stream query response using Server-Sent Events
        
        Args:
            workspace_id: Workspace to search in
            query: User query
            user_id: User making the query
            top_k: Number of results to retrieve
            min_score: Minimum similarity score
            max_tokens: Maximum tokens for response
            temperature: LLM temperature
            include_progress: Include progress events
            
        Yields:
            SSE-formatted message strings
            
        Raises:
            StreamingError: If streaming fails
        """
        try:
            # Validate inputs
            if not query or not query.strip():
                raise StreamingError("Query cannot be empty")
            
            if include_progress:
                # Send progress event - starting search
                progress_data = {
                    "stage": "searching",
                    "progress": 0.0,
                    "message": "Searching for relevant documents..."
                }
                yield self._format_sse_message(progress_data, event_type="progress")
            
            # Get streaming query response
            stream_response = await self.query_service.query_documents_streaming(
                workspace_id=workspace_id,
                query=query,
                user_id=user_id,
                top_k=top_k,
                min_score=min_score,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # Send metadata event with sources and query info
            metadata = {
                "query": stream_response["query"],
                "sources": stream_response["sources"],
                "context_length": stream_response["context_length"],
                "timestamp": int(time.time())
            }
            yield self._format_sse_message(metadata, event_type="metadata")
            
            if include_progress:
                # Send progress event - starting generation
                progress_data = {
                    "stage": "generating",
                    "progress": 0.5,
                    "message": "Generating response..."
                }
                yield self._format_sse_message(progress_data, event_type="progress")
            
            # Stream the response content
            buffer = ""
            last_flush_time = time.time()
            
            async for chunk in stream_response["response_stream"]:
                buffer += chunk
                current_time = time.time()
                
                # Flush buffer if size exceeded or time interval passed
                should_flush = (
                    len(buffer) >= self.chunk_size or
                    (current_time - last_flush_time) >= self.flush_interval
                )
                
                if should_flush and buffer.strip():
                    yield self._format_sse_message(buffer, event_type="chunk")
                    buffer = ""
                    last_flush_time = current_time
            
            # Flush any remaining buffer
            if buffer.strip():
                yield self._format_sse_message(buffer, event_type="chunk")
            
            if include_progress:
                # Send progress event - completed
                progress_data = {
                    "stage": "completed",
                    "progress": 1.0,
                    "message": "Response generation completed"
                }
                yield self._format_sse_message(progress_data, event_type="progress")
            
            # Send completion event
            completion_data = {
                "status": "complete",
                "total_sources": len(stream_response["sources"]),
                "timestamp": int(time.time())
            }
            yield self._format_sse_message(completion_data, event_type="complete")
            
        except Exception as e:
            logger.error(f"Streaming query failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Send error event
            error_data = {
                "error": "Streaming query failed",
                "message": str(e),
                "timestamp": int(time.time())
            }
            yield self._format_sse_message(error_data, event_type="error")
            
            raise StreamingError(f"Failed to stream query response: {str(e)}")
    
    async def stream_search_results(
        self,
        workspace_id: str,
        query: str,
        user_id: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream search results without LLM generation
        
        Args:
            workspace_id: Workspace to search in
            query: Search query
            user_id: User making the query
            top_k: Number of results to retrieve
            min_score: Minimum similarity score
            
        Yields:
            SSE-formatted search result messages
            
        Raises:
            StreamingError: If streaming fails
        """
        try:
            # Search for documents
            search_results = await self.query_service.search_similar_documents(
                workspace_id=workspace_id,
                query=query,
                top_k=top_k,
                min_score=min_score
            )
            
            # Send metadata
            metadata = {
                "query": query,
                "total_results": len(search_results),
                "timestamp": int(time.time())
            }
            yield self._format_sse_message(metadata, event_type="metadata")
            
            # Stream each result
            for i, result in enumerate(search_results):
                result_data = {
                    "index": i,
                    "document_id": result.get("document_id"),
                    "content": result.get("content"),
                    "score": result.get("score"),
                    "metadata": result.get("metadata", {})
                }
                yield self._format_sse_message(result_data, event_type="result")
                
                # Small delay to make streaming visible
                await asyncio.sleep(0.01)
            
            # Send completion
            completion_data = {
                "status": "complete",
                "total_streamed": len(search_results)
            }
            yield self._format_sse_message(completion_data, event_type="complete")
            
        except Exception as e:
            logger.error(f"Streaming search failed: {e}")
            
            # Send error event
            error_data = {
                "error": "Streaming search failed",
                "message": str(e),
                "timestamp": int(time.time())
            }
            yield self._format_sse_message(error_data, event_type="error")
            
            raise StreamingError(f"Failed to stream search results: {str(e)}")
    
    def _create_heartbeat_generator(self, interval: float = 30.0) -> AsyncGenerator[str, None]:
        """
        Create heartbeat generator to keep connection alive
        
        Args:
            interval: Heartbeat interval in seconds
            
        Yields:
            Heartbeat messages
        """
        async def heartbeat():
            while True:
                await asyncio.sleep(interval)
                heartbeat_data = {
                    "type": "heartbeat",
                    "timestamp": int(time.time())
                }
                yield self._format_sse_message(heartbeat_data, event_type="heartbeat")
        
        return heartbeat()
    
    async def stream_with_heartbeat(
        self,
        stream_generator: AsyncGenerator[str, None],
        heartbeat_interval: float = 30.0
    ) -> AsyncGenerator[str, None]:
        """
        Add heartbeat to streaming generator to keep connection alive
        
        Args:
            stream_generator: Original streaming generator
            heartbeat_interval: Heartbeat interval in seconds
            
        Yields:
            Combined stream with heartbeat messages
        """
        try:
            # Create tasks for both streams
            stream_task = asyncio.create_task(self._collect_stream(stream_generator))
            heartbeat_task = asyncio.create_task(
                self._collect_stream(self._create_heartbeat_generator(heartbeat_interval))
            )
            
            # Stream results as they come
            while not stream_task.done():
                done, pending = await asyncio.wait(
                    [stream_task, heartbeat_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=0.1
                )
                
                for task in done:
                    if task == stream_task:
                        # Main stream completed
                        async for chunk in task.result():
                            yield chunk
                        heartbeat_task.cancel()
                        return
                    elif task == heartbeat_task:
                        # Heartbeat - restart heartbeat task
                        async for chunk in task.result():
                            yield chunk
                        heartbeat_task = asyncio.create_task(
                            self._collect_stream(self._create_heartbeat_generator(heartbeat_interval))
                        )
        
        except asyncio.CancelledError:
            # Clean cancellation
            pass
        except Exception as e:
            logger.error(f"Heartbeat streaming failed: {e}")
            raise StreamingError(f"Heartbeat streaming failed: {str(e)}")
    
    async def _collect_stream(self, generator: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        """Helper to collect stream results"""
        async for item in generator:
            yield item
    
    async def cleanup(self):
        """Cleanup streaming resources"""
        # Clear any buffered data
        if hasattr(self, '_current_buffer'):
            self._current_buffer = ""
        
        # Cleanup query service if needed
        if hasattr(self.query_service, 'cleanup'):
            await self.query_service.cleanup()


# Global streaming service instance (will be initialized with dependencies)
streaming_service = None


def initialize_streaming_service(query_service):
    """Initialize global streaming service instance"""
    global streaming_service
    streaming_service = StreamingService(query_service=query_service)
    return streaming_service