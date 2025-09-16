import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import json
import tempfile
import os
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.services.llm_service import ModelManager
from app.core.service_manager import ServiceManager
from app.api.llm import initialize_llm_router


class TestLLMIntegration:
    """Integration tests for LLM service and API endpoints"""
    
    @pytest.fixture
    def mock_model_manager(self):
        """Mock Phi-2 model manager with realistic behavior"""
        manager = Mock(spec=ModelManager)
        manager.is_loaded = Mock(return_value=True)
        manager._is_mock_mode = Mock(return_value=True)
        
        # Mock text generation
        async def mock_generate(*args, **kwargs):
            prompt = kwargs.get('prompt', '')
            if 'Hello' in prompt:
                return "Hello! I'm Phi-2, happy to help you today."
            elif 'Python' in prompt:
                return "Python is a high-level programming language known for its simplicity and readability."
            else:
                return "I'm Phi-2, an AI assistant ready to help with your questions."
        
        manager.generate = AsyncMock(side_effect=mock_generate)
        
        # Mock streaming generation
        async def mock_generate_stream(*args, **kwargs):
            prompt = kwargs.get('prompt', '')
            if 'Hello' in prompt:
                tokens = ["Hello", "!", " I'm", " Phi", "-2", ", happy", " to", " help", " you", " today", "."]
            elif 'Python' in prompt:
                tokens = ["Python", " is", " a", " high", "-level", " programming", " language", "."]
            else:
                tokens = ["I'm", " Phi", "-2", ", ready", " to", " help", "."]
            
            for token in tokens:
                yield token
                await asyncio.sleep(0.01)  # Simulate streaming delay
        
        manager.generate_stream = Mock(side_effect=mock_generate_stream)
        
        return manager
    
    @pytest.fixture
    def test_app_with_llm(self, mock_model_manager):
        """Create test app with mocked LLM service"""
        from fastapi import FastAPI
        from app.api.llm import router
        
        # Create test app with LLM router
        test_app = FastAPI()
        test_app.include_router(router, prefix="/llm", tags=["LLM"])
        
        # Initialize the router with mock service
        initialize_llm_router(mock_model_manager)
        
        yield test_app, mock_model_manager
        
        # Cleanup
        import app.api.llm
        app.api.llm.llm_service = None

    @pytest.mark.asyncio
    async def test_end_to_end_chat_workflow(self, test_app_with_llm):
        """Test complete chat workflow from request to response"""
        test_app, mock_service = test_app_with_llm
        
        async with AsyncClient(app=test_app, base_url="http://test") as client:
        
        # Test request payload
        request_data = {
            "message": "Hello AI, how are you?",
            "max_tokens": 512,
            "temperature": 0.7
        }
        
        # Make request
        response = await client.post("/llm/chat", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "response" in data
        assert data["model"] == "phi-2"
        assert "Hello! I'm Phi-2, happy to help you today." in data["response"]
        assert data["tokens_used"] > 0
        assert data["processing_time"] >= 0
        
        # Verify service was called correctly
        mock_service.generate.assert_called_once()
        call_args = mock_service.generate.call_args
        assert call_args[1]["max_tokens"] == 512
        assert call_args[1]["temperature"] == 0.7
        assert "Hello AI, how are you?" in call_args[1]["prompt"]

    @pytest.mark.asyncio
    async def test_end_to_end_streaming_workflow(self, test_client_with_llm):
        """Test complete streaming workflow"""
        client, mock_service = test_client_with_llm
        
        # Make streaming request
        response = await client.get("/llm/stream?q=Hello%20there&max_tokens=256&temperature=0.5")
        
        # Verify response headers
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "no-cache" in response.headers["cache-control"]
        assert "keep-alive" in response.headers["connection"]
        
        # Parse SSE content
        content = response.text
        lines = [line for line in content.split('\n') if line.startswith('data:')]
        
        # Verify SSE format
        assert len(lines) >= 3  # At least start, tokens, end
        
        # Parse events
        events = []
        for line in lines:
            try:
                data = json.loads(line[5:])  # Remove 'data: ' prefix
                events.append(data)
            except json.JSONDecodeError:
                continue
        
        # Verify event sequence
        event_types = [event["type"] for event in events]
        assert "start" in event_types
        assert "token" in event_types
        assert "end" in event_types
        
        # Verify token events contain content
        token_events = [event for event in events if event["type"] == "token"]
        assert len(token_events) > 0
        for event in token_events:
            assert "content" in event
            assert len(event["content"]) > 0
        
        # Verify service was called
        mock_service.generate_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self, test_client_with_llm):
        """Test handling of multiple concurrent requests"""
        client, mock_service = test_client_with_llm
        
        # Create multiple request payloads
        request_payloads = [
            {"message": f"Question {i}", "max_tokens": 256}
            for i in range(5)
        ]
        
        # Make concurrent requests
        tasks = [
            client.post("/llm/chat", json=payload)
            for payload in request_payloads
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert data["model"] == "phi-2"
        
        # Verify service was called for each request
        assert mock_service.generate.call_count == 5

    @pytest.mark.asyncio
    async def test_mixed_chat_and_streaming_requests(self, test_client_with_llm):
        """Test concurrent chat and streaming requests"""
        client, mock_service = test_client_with_llm
        
        # Create mixed request tasks
        tasks = [
            client.post("/llm/chat", json={"message": "Chat request 1"}),
            client.get("/llm/stream?q=Stream%20request%201"),
            client.post("/llm/chat", json={"message": "Chat request 2"}),
            client.post("/llm/stream", json={"message": "Stream request 2"}),
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200
        
        # Verify both generation methods were called
        assert mock_service.generate.call_count == 2  # For chat requests
        assert mock_service.generate_stream.call_count == 2  # For streaming requests

    @pytest.mark.asyncio
    async def test_error_propagation_through_layers(self, test_client_with_llm):
        """Test error handling propagation from service to API"""
        client, mock_service = test_client_with_llm
        
        # Configure service to raise error
        mock_service.generate.side_effect = Exception("Model processing error")
        
        response = await client.post("/llm/chat", json={"message": "Test error"})
        
        assert response.status_code == 500
        data = response.json()
        assert "Chat generation failed" in data["detail"]
        assert "Model processing error" in data["detail"]

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, test_client_with_llm):
        """Test error handling in streaming responses"""
        client, mock_service = test_client_with_llm
        
        # Configure streaming to raise error
        async def failing_stream(*args, **kwargs):
            yield "Starting"
            raise Exception("Stream processing error")
        
        mock_service.generate_stream = AsyncMock(side_effect=failing_stream)
        
        response = await client.get("/llm/stream?q=Test%20error")
        
        assert response.status_code == 200  # SSE returns 200 even for errors
        content = response.text
        
        # Should contain error event
        assert '"type": "error"' in content
        assert "Generation failed" in content

    @pytest.mark.asyncio
    async def test_service_lifecycle_integration(self, mock_model_manager):
        """Test service initialization and cleanup"""
        # Test initialization
        initialize_llm_router(mock_model_manager)
        
        # Verify service is available
        import app.api.llm
        assert app.api.llm.llm_service is not None
        assert app.api.llm.llm_service is mock_model_manager
        
        # Test health check works
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/llm/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
        
        # Test cleanup
        app.api.llm.llm_service = None
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/llm/health")
            data = response.json()
            assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_parameter_validation_integration(self, test_client_with_llm):
        """Test parameter validation through the full stack"""
        client, mock_service = test_client_with_llm
        
        # Test valid edge case parameters
        test_cases = [
            {"message": "x", "max_tokens": 1, "temperature": 0.0},  # Minimums
            {"message": "x" * 4000, "max_tokens": 2048, "temperature": 1.0},  # Maximums
        ]
        
        for params in test_cases:
            response = await client.post("/llm/chat", json=params)
            assert response.status_code == 200
        
        # Test invalid parameters
        invalid_cases = [
            {"message": "", "max_tokens": 512},  # Empty message
            {"message": "test", "max_tokens": 0},  # Invalid max_tokens
            {"message": "test", "temperature": -0.1},  # Invalid temperature
        ]
        
        for params in invalid_cases:
            response = await client.post("/llm/chat", json=params)
            assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_response_time_requirements(self, test_client_with_llm):
        """Test response time meets performance requirements"""
        client, mock_service = test_client_with_llm
        
        # Make request and measure time
        import time
        start_time = time.time()
        
        response = await client.post("/llm/chat", json={"message": "Quick test"})
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify response and timing
        assert response.status_code == 200
        assert total_time < 5.0  # Should complete within 5 seconds
        
        # Verify processing time is reported
        data = response.json()
        assert "processing_time" in data
        assert isinstance(data["processing_time"], float)

    @pytest.mark.asyncio
    async def test_streaming_performance(self, test_client_with_llm):
        """Test streaming response performance"""
        client, mock_service = test_client_with_llm
        
        # Measure streaming response time
        import time
        start_time = time.time()
        
        response = await client.get("/llm/stream?q=Performance%20test")
        
        # Verify headers are sent immediately
        first_response_time = time.time() - start_time
        assert first_response_time < 1.0  # Headers should be fast
        
        # Verify content is streamed
        assert response.status_code == 200
        content = response.text
        
        # Should contain multiple events
        events = [line for line in content.split('\n') if line.startswith('data:')]
        assert len(events) >= 3  # start, tokens, end

    @pytest.mark.asyncio 
    async def test_memory_stability_during_requests(self, test_client_with_llm):
        """Test memory stability during multiple requests"""
        client, mock_service = test_client_with_llm
        
        # Make many requests to test for memory leaks
        for i in range(20):
            response = await client.post("/llm/chat", json={
                "message": f"Memory test {i}",
                "max_tokens": 100
            })
            assert response.status_code == 200
        
        # Verify service is still responsive
        response = await client.get("/llm/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_authentication_integration(self, test_client_with_llm):
        """Test JWT token handling in streaming requests"""
        client, mock_service = test_client_with_llm
        
        # Test with token parameter
        test_token = "test_jwt_token_123"
        response = await client.get(f"/llm/stream?q=Auth%20test&token={test_token}")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Service should still be called (auth is handled at higher level)
        mock_service.generate_stream.assert_called()

    @pytest.mark.asyncio
    async def test_cors_headers_in_streaming(self, test_client_with_llm):
        """Test CORS headers are properly set for streaming"""
        client, mock_service = test_client_with_llm
        
        response = await client.get("/llm/stream?q=CORS%20test")
        
        assert response.status_code == 200
        
        # Verify CORS headers
        assert response.headers.get("access-control-allow-origin") == "*"
        assert response.headers.get("access-control-allow-headers") == "*"
        assert "no-cache" in response.headers.get("cache-control", "")

    @pytest.mark.asyncio
    async def test_different_prompt_types(self, test_client_with_llm):
        """Test different types of prompts and responses"""
        client, mock_service = test_client_with_llm
        
        test_prompts = [
            "What is Python?",  # Question
            "Write a hello world program",  # Code request
            "Tell me a story",  # Creative request
            "Explain quantum physics",  # Complex topic
            "Help me debug this code: print('hello')",  # Debug request
        ]
        
        for prompt in test_prompts:
            response = await client.post("/llm/chat", json={"message": prompt})
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["response"]) > 0
            assert data["tokens_used"] > 0
        
        # Verify service handled all requests
        assert mock_service.generate.call_count == len(test_prompts)