from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import asyncio
import logging
from datetime import datetime

from app.api.auth import get_current_user_from_token
from app.services.query_service import QueryError, NoResultsError
from app.services.streaming_service import StreamingError

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["query"])

# Import services (will be injected at startup)
query_service = None
streaming_service = None


# Pydantic models for request/response
class QueryRequest(BaseModel):
    """Request model for document queries"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    top_k: Optional[int] = Field(5, ge=1, le=50, description="Number of results to return")
    min_score: Optional[float] = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity score")
    max_tokens: Optional[int] = Field(None, ge=1, le=2048, description="Maximum response tokens")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Generation temperature")
    
    @validator('query')
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class StreamingQueryRequest(QueryRequest):
    """Request model for streaming queries"""
    include_progress: bool = Field(False, description="Include progress events")


class SearchRequest(BaseModel):
    """Request model for document search (without LLM)"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    top_k: Optional[int] = Field(5, ge=1, le=50, description="Number of results to return")
    min_score: Optional[float] = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity score")
    
    @validator('query')
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class QueryResponse(BaseModel):
    """Response model for document queries"""
    response: str = Field(..., description="Generated response")
    sources: List[Dict[str, Any]] = Field(..., description="Source documents")
    query: str = Field(..., description="Original query")
    context_length: int = Field(..., description="Context length in characters")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
    total_sources: int = Field(..., description="Total number of sources")


class SearchResponse(BaseModel):
    """Response model for document search"""
    results: List[Dict[str, Any]] = Field(..., description="Search results")
    query: str = Field(..., description="Original query")
    total_results: int = Field(..., description="Total number of results")


class QueryHistoryResponse(BaseModel):
    """Response model for query history"""
    history: List[Dict[str, Any]] = Field(..., description="Query history")
    total: int = Field(..., description="Total number of queries")


class StatsResponse(BaseModel):
    """Response model for workspace statistics"""
    total_documents: int = Field(..., description="Total documents in workspace")
    total_chunks: int = Field(..., description="Total chunks in workspace")
    index_size: str = Field(..., description="Index size")
    avg_query_time_ms: int = Field(..., description="Average query time")
    total_queries: int = Field(..., description="Total queries processed")


# API Endpoints

@router.post("/documents", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user_from_token)
) -> QueryResponse:
    """
    Query documents using RAG pipeline
    
    This endpoint searches for relevant documents in the user's workspace
    and generates a response using the retrieved context.
    """
    try:
        # Extract user info
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)
        workspace_id = current_user.get("workspace_id") if isinstance(current_user, dict) else getattr(current_user, "workspace_id", None)
        
        # Execute query
        result = await query_service.query_documents(
            workspace_id=workspace_id,
            query=request.query,
            user_id=user_id,
            top_k=request.top_k,
            min_score=request.min_score,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        return QueryResponse(**result)
        
    except NoResultsError as e:
        logger.warning(f"No results found for query '{request.query}': {e}")
        raise HTTPException(
            status_code=404,
            detail=f"No similar documents found for the query: {str(e)}"
        )
    except QueryError as e:
        logger.error(f"Query failed for '{request.query}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )
    except asyncio.TimeoutError:
        logger.error(f"Query timeout for '{request.query}'")
        raise HTTPException(
            status_code=408,
            detail="Query timed out. Please try again with a simpler query."
        )
    except Exception as e:
        logger.error(f"Unexpected error during query '{request.query}': {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during query processing"
        )


@router.get("/stream")
async def stream_query_get(
    query: str,
    top_k: int = 5,
    min_score: float = 0.5,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    include_progress: bool = False,
    token: Optional[str] = None,
    request: Request = None
) -> StreamingResponse:
    """
    Stream query response using Server-Sent Events (GET method for EventSource)
    
    This endpoint provides real-time streaming of query responses via GET request,
    allowing EventSource clients to receive partial results as they're generated.
    """
    try:
        # Validate query and ensure it's a string
        query = str(query) if query is not None else ""
        if not query or not query.strip():
            raise HTTPException(
                status_code=400,
                detail="Query parameter is required and cannot be empty"
            )
        
        # Handle authentication for EventSource (token in query params)
        if token:
            # Verify JWT token directly
            try:
                from app.auth.auth_service import auth_service
                from app.auth.user_manager import user_manager
                
                payload = auth_service.verify_token(token)
                current_user = user_manager.get_current_user()
                
                if not current_user or current_user.get("user_id") != payload.get("user_id"):
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid authentication credentials"
                    )
            except Exception as e:
                logger.error(f"Token verification failed: {e}")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired token"
                )
        else:
            raise HTTPException(
                status_code=401,
                detail="Authentication required - provide token parameter for streaming"
            )
        
        # Extract user info
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)
        workspace_id = current_user.get("workspace_id") if isinstance(current_user, dict) else getattr(current_user, "workspace_id", None)
        
        # Create streaming generator
        async def generate_stream():
            try:
                async for chunk in streaming_service.stream_query_response(
                    workspace_id=workspace_id,
                    query=query.strip(),
                    user_id=user_id,
                    top_k=top_k,
                    min_score=min_score,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    include_progress=include_progress
                ):
                    yield chunk
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                # Send error event and close stream
                error_message = streaming_service._format_sse_message(
                    {"error": str(e)},
                    event_type="error"
                )
                yield error_message
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize streaming response"
        )


@router.post("/stream")
async def stream_query_post(
    request: StreamingQueryRequest,
    current_user: dict = Depends(get_current_user_from_token)
) -> StreamingResponse:
    """
    Stream query response using Server-Sent Events
    
    This endpoint provides real-time streaming of query responses,
    allowing clients to receive partial results as they're generated.
    """
    try:
        # Extract user info
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)
        workspace_id = current_user.get("workspace_id") if isinstance(current_user, dict) else getattr(current_user, "workspace_id", None)
        
        # Create streaming generator
        async def generate_stream():
            try:
                async for chunk in streaming_service.stream_query_response(
                    workspace_id=workspace_id,
                    query=request.query,
                    user_id=user_id,
                    top_k=request.top_k,
                    min_score=request.min_score,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    include_progress=request.include_progress
                ):
                    yield chunk
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                # Send error event and close stream
                error_message = streaming_service._format_sse_message(
                    {"error": str(e)},
                    event_type="error"
                )
                yield error_message
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize streaming response"
        )


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    current_user: dict = Depends(get_current_user_from_token)
) -> SearchResponse:
    """
    Search documents without LLM generation
    
    This endpoint performs vector similarity search and returns
    relevant document chunks without generating a response.
    """
    try:
        # Extract user info
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)
        workspace_id = current_user.get("workspace_id") if isinstance(current_user, dict) else getattr(current_user, "workspace_id", None)
        
        # Execute search
        results = await query_service.search_similar_documents(
            workspace_id=workspace_id,
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score
        )
        
        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results)
        )
        
    except NoResultsError as e:
        logger.warning(f"No search results for query '{request.query}': {e}")
        raise HTTPException(
            status_code=404,
            detail=f"No similar documents found: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Search failed for '{request.query}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Document search failed: {str(e)}"
        )


@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user_from_token)
) -> QueryHistoryResponse:
    """
    Get query history for current user and workspace
    
    Returns a paginated list of previous queries with metadata.
    """
    try:
        # Extract user info
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)
        workspace_id = current_user.get("workspace_id") if isinstance(current_user, dict) else getattr(current_user, "workspace_id", None)
        
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            limit = 50
        if offset < 0:
            offset = 0
        
        # Get query history
        history = await query_service.get_query_history(
            user_id=user_id,
            workspace_id=workspace_id,
            limit=limit,
            offset=offset
        )
        
        return QueryHistoryResponse(
            history=history,
            total=len(history)  # TODO: Get actual total from database
        )
        
    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve query history"
        )


@router.get("/stats", response_model=StatsResponse)
async def get_search_stats(
    current_user: dict = Depends(get_current_user_from_token)
) -> StatsResponse:
    """
    Get search statistics for current workspace
    
    Returns statistics about the workspace's document index
    and query performance metrics.
    """
    try:
        # Extract workspace ID
        workspace_id = current_user["workspace_id"]
        
        # Get workspace stats
        stats = query_service.get_workspace_search_stats(workspace_id)
        
        return StatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve search statistics"
        )


@router.post("/search/stream")
async def stream_search(
    request: SearchRequest,
    current_user: dict = Depends(get_current_user_from_token)
) -> StreamingResponse:
    """
    Stream search results without LLM generation
    
    This endpoint streams search results as they're found,
    useful for large result sets or real-time search interfaces.
    """
    try:
        # Extract user info
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)
        workspace_id = current_user.get("workspace_id") if isinstance(current_user, dict) else getattr(current_user, "workspace_id", None)
        
        # Create streaming generator
        async def generate_search_stream():
            try:
                async for chunk in streaming_service.stream_search_results(
                    workspace_id=workspace_id,
                    query=request.query,
                    user_id=user_id,
                    top_k=request.top_k,
                    min_score=request.min_score
                ):
                    yield chunk
            except Exception as e:
                logger.error(f"Search streaming error: {e}")
                # Send error event
                error_message = streaming_service._format_sse_message(
                    {"error": str(e)},
                    event_type="error"
                )
                yield error_message
        
        return StreamingResponse(
            generate_search_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize search streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize search streaming"
        )


# Utility endpoints

@router.get("/health")
async def health_check():
    """Health check endpoint for query service"""
    return {
        "status": "healthy",
        "service": "query",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "query_service": query_service is not None,
            "streaming_service": streaming_service is not None
        }
    }


# Service initialization function
def initialize_query_router(query_svc, streaming_svc):
    """Initialize the query router with service dependencies"""
    global query_service, streaming_service
    query_service = query_svc
    streaming_service = streaming_svc
    logger.info("Query router initialized with services")