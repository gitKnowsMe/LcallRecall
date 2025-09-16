from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
import asyncio
import logging
from datetime import datetime

from app.api.auth import get_current_user_from_token

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["llm"])

# Import services (will be injected at startup)
model_manager = None


# Pydantic models for request/response
class LLMRequest(BaseModel):
    """Request model for direct LLM generation"""
    prompt: str = Field(..., min_length=1, max_length=5000, description="Prompt for LLM")
    max_tokens: Optional[int] = Field(1024, ge=1, le=2048, description="Maximum response tokens")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Generation temperature")
    
    @validator('prompt')
    def prompt_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Prompt cannot be empty or whitespace only')
        return v.strip()


class StreamingLLMRequest(LLMRequest):
    """Request model for streaming LLM generation"""
    pass


class LLMResponse(BaseModel):
    """Response model for LLM generation"""
    response: str = Field(..., description="Generated response")
    prompt: str = Field(..., description="Original prompt")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
    tokens_generated: Optional[int] = Field(None, description="Number of tokens generated")


# API Endpoints

@router.post("/chat", response_model=LLMResponse)
async def direct_llm_chat(
    request: LLMRequest,
    current_user: dict = Depends(get_current_user_from_token)
) -> LLMResponse:
    """
    Direct LLM chat without RAG pipeline
    
    This endpoint sends the user's prompt directly to Phi-2 without
    any document search, context injection, or guardrails.
    """
    try:
        start_time = datetime.now()
        
        # Generate response with minimal system prompt for quality
        formatted_prompt = f"You are Phi, a helpful AI assistant. Answer the user's question directly and concisely.\n\nUser: {request.prompt}\nAssistant:"
        response = await model_manager.generate(
            prompt=formatted_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        end_time = datetime.now()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return LLMResponse(
            response=response,
            prompt=request.prompt,
            response_time_ms=response_time_ms,
            tokens_generated=None  # Could implement token counting later
        )
        
    except Exception as e:
        logger.error(f"Direct LLM generation failed for prompt '{request.prompt[:50]}...': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM generation failed: {str(e)}"
        )


@router.get("/stream")
async def stream_llm_get(
    prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    token: Optional[str] = None,
    request: Request = None
) -> StreamingResponse:
    """
    Stream LLM response using Server-Sent Events (GET method for EventSource)
    
    This endpoint provides real-time streaming of LLM responses via GET request,
    sending the prompt directly to Phi-2 without any RAG processing.
    """
    try:
        # Validate prompt
        prompt = str(prompt) if prompt is not None else ""
        if not prompt or not prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="Prompt parameter is required and cannot be empty"
            )
        
        # Handle authentication for EventSource (token in query params)
        if token:
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
        
        # Create streaming generator
        async def generate_stream():
            try:
                # Send start event
                yield f"event: start\ndata: {{}}\n\n"
                
                # Stream LLM response with minimal system prompt for quality  
                formatted_prompt = f"You are Phi, a helpful AI assistant. Answer the user's question directly and concisely.\n\nUser: {prompt.strip()}\nAssistant:"
                async for chunk in model_manager.generate_stream(
                    prompt=formatted_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                ):
                    # Send chunk event
                    yield f"event: chunk\ndata: {chunk}\n\n"
                
                # Send completion event
                yield f"event: complete\ndata: {{}}\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                # Send error event and close stream
                yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"
        
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
        logger.error(f"Failed to initialize LLM streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize streaming response"
        )


@router.post("/stream")
async def stream_llm_post(
    request: StreamingLLMRequest,
    current_user: dict = Depends(get_current_user_from_token)
) -> StreamingResponse:
    """
    Stream LLM response using Server-Sent Events (POST method)
    
    This endpoint provides real-time streaming of LLM responses,
    sending the prompt directly to Phi-2 without any RAG processing.
    """
    try:
        # Create streaming generator
        async def generate_stream():
            try:
                # Send start event
                yield f"event: start\ndata: {{}}\n\n"
                
                # Stream LLM response with minimal system prompt for quality
                formatted_prompt = f"You are Phi, a helpful AI assistant. Answer the user's question directly and concisely.\n\nUser: {request.prompt}\nAssistant:"
                async for chunk in model_manager.generate_stream(
                    prompt=formatted_prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature
                ):
                    # Send chunk event
                    yield f"event: chunk\ndata: {chunk}\n\n"
                
                # Send completion event
                yield f"event: complete\ndata: {{}}\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                # Send error event and close stream
                yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"
        
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
        logger.error(f"Failed to initialize LLM streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize streaming response"
        )


# Utility endpoints

@router.get("/health")
async def health_check():
    """Health check endpoint for LLM service"""
    return {
        "status": "healthy",
        "service": "llm",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "model_manager": model_manager is not None,
            "model_loaded": model_manager.is_loaded() if model_manager else False
        }
    }


@router.get("/info")
async def llm_info(
    current_user: dict = Depends(get_current_user_from_token)
):
    """Get LLM model information"""
    try:
        return {
            "model_type": "Phi-2",
            "model_path": "/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf",
            "model_loaded": model_manager.is_loaded() if model_manager else False,
            "capabilities": [
                "Text generation",
                "Conversational AI", 
                "Code assistance",
                "Creative writing"
            ],
            "note": "Direct LLM access without RAG constraints"
        }
        
    except Exception as e:
        logger.error(f"Failed to get LLM info: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve LLM information"
        )


# Service initialization function
def initialize_llm_router(model_mgr):
    """Initialize the LLM router with service dependencies"""
    global model_manager
    model_manager = model_mgr
    logger.info("LLM router initialized with model manager")