import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
import json
import re

logger = logging.getLogger(__name__)


class QueryError(Exception):
    """Base exception for query service errors"""
    pass


class NoResultsError(QueryError):
    """Exception raised when no search results found"""
    pass


class QueryService:
    """Service for querying documents using RAG pipeline"""
    
    def __init__(
        self,
        vector_service,
        llm_service,
        default_top_k: int = 5,
        min_similarity_score: float = 0.5
    ):
        """
        Initialize query service
        
        Args:
            vector_service: Vector store service for document search
            llm_service: LLM service for text generation
            default_top_k: Default number of results to retrieve
            min_similarity_score: Minimum similarity score threshold
        """
        self.vector_service = vector_service
        self.llm_service = llm_service
        self.default_top_k = default_top_k
        self.min_similarity_score = min_similarity_score
    
    async def search_similar_documents(
        self,
        workspace_id: str,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents in workspace
        
        Args:
            workspace_id: Workspace to search in
            query: Search query
            top_k: Number of results to return
            min_score: Minimum similarity score
            
        Returns:
            List of similar document chunks
            
        Raises:
            QueryError: If search fails
            NoResultsError: If no results found
        """
        try:
            if not query or not query.strip():
                raise QueryError("Query cannot be empty")
                
            if not workspace_id or not str(workspace_id).strip():
                raise QueryError("Workspace ID is required")
            
            # Use defaults if not specified
            if top_k is None:
                top_k = self.default_top_k
            if min_score is None:
                min_score = self.min_similarity_score
            
            # Perform vector search
            results = await self.vector_service.search(
                workspace_id=workspace_id,
                query=query,
                k=top_k,
                score_threshold=min_score
            )
            
            # Results are already filtered by score_threshold in vector_service.search
            filtered_results = results
            
            if not filtered_results:
                raise NoResultsError("No similar documents found for the query")
            
            return filtered_results
            
        except (NoResultsError, QueryError):
            raise
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            raise QueryError(f"Failed to search documents: {str(e)}")
    
    def prepare_rag_context(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Prepare context string from search results for RAG
        
        Args:
            search_results: List of search results with content and metadata
            
        Returns:
            Formatted context string
        """
        if not search_results:
            return ""
        
        context_parts = []
        for i, result in enumerate(search_results, 1):
            # Vector service returns results with 'text' key
            content = result.get("text", "")
            
            # Format with source attribution  
            filename = result.get("filename", "Unknown")
            chunk_index = result.get("chunk_index", i)
            
            source_info = f"[Source: {filename}, Chunk {chunk_index}]"
            context_part = f"{source_info}\n{content}\n"
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _format_sources(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format source information from search results
        
        Args:
            search_results: Raw search results
            
        Returns:
            Formatted source information
        """
        sources = []
        for result in search_results:
            source = {
                "document_id": result.get("document_id", result.get("doc_id", "")),
                "filename": result.get("filename", "Unknown"),
                "page": result.get("page", 1),
                "chunk_index": result.get("chunk_index", result.get("chunk_id", 0)),
                "relevance_score": result.get("similarity", 0.0),
                "content_preview": result.get("text", "")[:150] + "..." if len(result.get("text", "")) > 150 else result.get("text", "")
            }
            sources.append(source)
        return sources
    
    def _estimate_context_length(self, context: str) -> int:
        """
        Estimate context length for token management
        
        Args:
            context: Context string
            
        Returns:
            Estimated length in characters
        """
        return len(context)
    
    async def query_documents(
        self,
        workspace_id: str,
        query: str,
        user_id: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Query documents using RAG pipeline
        
        Args:
            workspace_id: Workspace to search in
            query: User query
            user_id: User making the query
            top_k: Number of results to retrieve
            min_score: Minimum similarity score
            max_tokens: Maximum tokens for response
            temperature: LLM temperature
            
        Returns:
            Query response with sources and metadata
            
        Raises:
            QueryError: If query processing fails
            NoResultsError: If no results found
        """
        start_time = time.time()
        
        try:
            # Validate inputs
            if not query or not query.strip():
                raise QueryError("Query cannot be empty")
                
            if not workspace_id or not str(workspace_id).strip():
                raise QueryError("Workspace ID is required")
                
            if not user_id or not str(user_id).strip():
                raise QueryError("User ID is required")
            
            # Search for similar documents
            search_results = await self.search_similar_documents(
                workspace_id=workspace_id,
                query=query,
                top_k=top_k,
                min_score=min_score
            )
            
            # Prepare RAG context
            context = self.prepare_rag_context(search_results)
            context_length = self._estimate_context_length(context)
            
            # Create RAG prompt
            rag_prompt = self.llm_service.create_rag_prompt(
                context=context,
                query=query
            )
            
            # Generate response
            generation_params = {}
            if max_tokens is not None:
                generation_params["max_tokens"] = max_tokens
            if temperature is not None:
                generation_params["temperature"] = temperature
            
            response = await self.llm_service.generate(
                prompt=rag_prompt,
                **generation_params
            )
            
            # Format sources
            sources = self._format_sources(search_results)
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return {
                "response": response,
                "sources": sources,
                "query": query,
                "context_length": context_length,
                "response_time_ms": response_time_ms,
                "total_sources": len(sources)
            }
            
        except (NoResultsError, QueryError):
            raise
        except Exception as e:
            logger.error(f"Failed to generate response for query '{query}': {e}")
            raise QueryError(f"Failed to generate response: {str(e)}")
    
    async def query_documents_streaming(
        self,
        workspace_id: str,
        query: str,
        user_id: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Query documents using streaming RAG pipeline
        
        Args:
            workspace_id: Workspace to search in
            query: User query
            user_id: User making the query
            top_k: Number of results to retrieve
            min_score: Minimum similarity score
            max_tokens: Maximum tokens for response
            temperature: LLM temperature
            
        Returns:
            Query response with streaming generator and metadata
            
        Raises:
            QueryError: If query processing fails
            NoResultsError: If no results found
        """
        try:
            # Validate inputs and ensure proper types
            query = str(query) if query is not None else ""
            if not query or not query.strip():
                raise QueryError("Query cannot be empty")
                
            workspace_id = str(workspace_id) if workspace_id is not None else ""
            if not workspace_id or not workspace_id.strip():
                raise QueryError("Workspace ID is required")
                
            user_id = str(user_id) if user_id is not None else ""
            if not user_id or not user_id.strip():
                raise QueryError("User ID is required")
            
            # Search for similar documents
            search_results = await self.search_similar_documents(
                workspace_id=workspace_id,
                query=query,
                top_k=top_k,
                min_score=min_score
            )
            
            # Prepare RAG context
            context = self.prepare_rag_context(search_results)
            context_length = self._estimate_context_length(context)
            
            # Create RAG prompt
            rag_prompt = self.llm_service.create_rag_prompt(
                context=context,
                query=query
            )
            
            # Setup generation parameters
            generation_params = {}
            if max_tokens is not None:
                generation_params["max_tokens"] = max_tokens
            if temperature is not None:
                generation_params["temperature"] = temperature
            
            # Generate streaming response
            response_stream = self.llm_service.generate_stream(
                prompt=rag_prompt,
                **generation_params
            )
            
            # Format sources
            sources = self._format_sources(search_results)
            
            return {
                "response_stream": response_stream,
                "sources": sources,
                "query": query,
                "context_length": context_length
            }
            
        except (NoResultsError, QueryError):
            raise
        except Exception as e:
            logger.error(f"Failed to generate streaming response for query '{query}': {e}")
            raise QueryError(f"Failed to generate streaming response: {str(e)}")
    
    async def get_query_history(
        self,
        user_id: str,
        workspace_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get query history for user and workspace
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            limit: Maximum number of results
            offset: Results offset
            
        Returns:
            List of historical queries
        """
        # Placeholder implementation - would integrate with database
        # For now, return empty list
        return []
    
    def get_workspace_search_stats(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get search statistics for workspace
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Workspace search statistics
        """
        try:
            # Get base stats from vector service
            base_stats = self.vector_service.get_workspace_stats(workspace_id)
            
            # Add query-specific stats
            stats = base_stats.copy()
            stats.update({
                "avg_query_time_ms": 850,  # Placeholder - would be from metrics
                "total_queries": 0  # Placeholder - would be from database
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get workspace stats: {e}")
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "index_size": "0MB",
                "avg_query_time_ms": 0,
                "total_queries": 0
            }
    
    async def cleanup(self):
        """Cleanup resources"""
        # Placeholder for cleanup logic
        pass