"""
Direct LLM Chat API endpoints - no RAG, direct model access  
Provides streaming and non-streaming chat with Phi-2
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import asyncio
import logging
from pydantic import BaseModel, Field

router = APIRouter(tags=["llm"])
logger = logging.getLogger(__name__)

# Import services (will be injected at startup)
llm_service = None


def initialize_llm_router(model_manager_svc):
    """Initialize the LLM router with service dependencies"""
    global llm_service
    llm_service = model_manager_svc
    logger.info("LLM router initialized with model service")

class DirectChatRequest(BaseModel):
    """Request model for direct LLM chat"""
    message: str = Field(..., min_length=1, max_length=4000, description="User message to send to LLM")
    max_tokens: Optional[int] = Field(default=1024, ge=1, le=2048, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=1.0, description="Response randomness")

class DirectChatResponse(BaseModel):
    """Response model for direct LLM chat"""
    response: str
    model: str = "phi-2"
    tokens_used: Optional[int] = None
    processing_time: Optional[float] = None

def create_system_prompt(user_message: str) -> str:
    """Create system prompt for quality direct LLM responses"""
    return f"You are Phi-2, a helpful AI assistant. Answer the user's question directly and concisely.\n\nUser: {user_message}\nAssistant:"

@router.post("/chat", response_model=DirectChatResponse)
async def direct_chat(request: DirectChatRequest):
    """
    Direct chat with LLM (non-streaming)
    No document context - pure LLM conversation
    """
    try:
        if llm_service is None:
            raise HTTPException(status_code=503, detail="LLM service not initialized")
        
        if not llm_service.is_loaded():
            raise HTTPException(status_code=503, detail="LLM service not available")
        
        # Create system prompt for better responses
        system_prompt = create_system_prompt(request.message)
        
        # Generate response
        import time
        start_time = time.time()
        
        response_text = await llm_service.generate(
            prompt=system_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        processing_time = time.time() - start_time
        
        return DirectChatResponse(
            response=response_text,
            tokens_used=len(response_text.split()),  # Approximate
            processing_time=processing_time
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions (like 503 errors) without modification
        raise
    except Exception as e:
        logger.error(f"Direct chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(e)}")

@router.get("/stream")
async def direct_chat_stream_get(
    q: str = Query(..., description="User message"),
    max_tokens: Optional[int] = Query(default=1024, ge=1, le=2048),
    temperature: Optional[float] = Query(default=0.7, ge=0.0, le=1.0),
    token: Optional[str] = Query(None, description="JWT token for auth")
):
    """
    Direct LLM streaming (GET with query params)
    For EventSource/Server-Sent Events compatibility
    """
    return await _stream_response(q, max_tokens, temperature)

@router.post("/stream")
async def direct_chat_stream_post(request: DirectChatRequest):
    """
    Direct LLM streaming (POST with JSON body)
    For programmatic API access
    """
    return await _stream_response(request.message, request.max_tokens, request.temperature)

async def _stream_response(message: str, max_tokens: int, temperature: float):
    """Internal streaming response handler"""
    try:
        if llm_service is None:
            raise HTTPException(status_code=503, detail="LLM service not initialized")
        
        if not llm_service.is_loaded():
            raise HTTPException(status_code=503, detail="LLM service not available")
        
        # Create system prompt
        system_prompt = create_system_prompt(message)
        
        async def generate_stream():
            """Generate streaming response with proper SSE format"""
            try:
                # Start streaming
                yield "data: " + json.dumps({"type": "start", "message": "Generating response..."}) + "\n\n"
                
                # Stream tokens
                async for token in llm_service.generate_stream(
                    prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                ):
                    if token:  # Only send non-empty tokens
                        event_data = {"type": "token", "content": token}
                        yield "data: " + json.dumps(event_data) + "\n\n"
                        
                        # Small delay to prevent overwhelming the client
                        await asyncio.sleep(0.01)
                
                # End stream
                yield "data: " + json.dumps({"type": "end", "message": "Response complete"}) + "\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                error_event = {"type": "error", "message": f"Generation failed: {str(e)}"}
                yield "data: " + json.dumps(error_event) + "\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except Exception as e:
        logger.error(f"Stream setup error: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")

@router.get("/health")
async def llm_health():
    """Health check for LLM service"""
    try:
        if llm_service is None:
            return {"status": "error", "message": "LLM service not initialized"}
        
        return {
            "status": "healthy" if llm_service.is_loaded() else "unavailable",
            "model": "phi-2",
            "loaded": llm_service.is_loaded(),
            "mock_mode": llm_service._is_mock_mode() if hasattr(llm_service, '_is_mock_mode') else False
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/info")
async def llm_info():
    """Get LLM model information and capabilities"""
    return {
        "model": "phi-2",
        "description": "Microsoft Phi-2 2.7B parameter language model",
        "capabilities": [
            "Direct conversation",
            "Code assistance", 
            "Creative writing",
            "Question answering",
            "Text completion"
        ],
        "max_tokens": 2048,
        "context_window": 2048,
        "features": ["streaming", "non-streaming", "temperature_control"]
    }