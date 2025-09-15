import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from fastapi import FastAPI

from app.api.llm import router, initialize_llm_router, DirectChatRequest, DirectChatResponse


class TestLLMEndpoints:
    """Test suite for LLM API endpoints"""
    
    @pytest.fixture
    def test_app(self):
        """Create FastAPI app with LLM router for testing"""
        app = FastAPI()
        app.include_router(router, prefix="/llm", tags=["LLM"])
        return app
    
    @pytest.fixture
    def client(self, test_app):
        """Create test client"""
        return TestClient(test_app)
    
    @pytest.fixture  
    async def async_client(self, test_app):
        """Create async test client"""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service (ModelManager)"""
        service = Mock()
        service.is_loaded = Mock(return_value=True)
        service.generate = AsyncMock()
        
        # Create proper async generator mock
        async def mock_stream_generator():
            yield "Hello"
            yield " "
            yield "World"
        
        # Mock that returns the async generator directly (not awaitable)
        service.generate_stream = Mock(return_value=mock_stream_generator())
        service._is_mock_mode = Mock(return_value=True)
        return service
    
    @pytest.fixture
    def initialize_router_with_mock(self, mock_llm_service):
        """Initialize router with mock service"""
        initialize_llm_router(mock_llm_service)
        yield mock_llm_service
        # Cleanup: reset to None
        import app.api.llm
        app.api.llm.llm_service = None

    def test_direct_chat_request_validation(self):
        """Test DirectChatRequest model validation"""
        # Valid request
        valid_request = DirectChatRequest(
            message="Hello AI",
            max_tokens=1024,
            temperature=0.7
        )
        assert valid_request.message == "Hello AI"
        assert valid_request.max_tokens == 1024
        assert valid_request.temperature == 0.7
        
        # Test defaults
        minimal_request = DirectChatRequest(message="Test")
        assert minimal_request.max_tokens == 1024
        assert minimal_request.temperature == 0.7
        
        # Test validation errors
        with pytest.raises(ValueError):
            DirectChatRequest(message="")  # Empty message
        
        with pytest.raises(ValueError):
            DirectChatRequest(message="x" * 4001)  # Too long
            
        with pytest.raises(ValueError):
            DirectChatRequest(message="Test", max_tokens=0)  # Below minimum
            
        with pytest.raises(ValueError):
            DirectChatRequest(message="Test", max_tokens=3000)  # Above maximum
            
        with pytest.raises(ValueError):
            DirectChatRequest(message="Test", temperature=-0.1)  # Below minimum
            
        with pytest.raises(ValueError):
            DirectChatRequest(message="Test", temperature=1.1)  # Above maximum

    def test_system_prompt_creation(self):
        """Test system prompt formatting"""
        from app.api.llm import create_system_prompt
        
        user_message = "What is Python?"
        prompt = create_system_prompt(user_message)
        
        expected = "You are Phi-2, a helpful AI assistant. Answer the user's question directly and concisely.\n\nUser: What is Python?\nAssistant:"
        assert prompt == expected
        
        # Test with special characters
        special_message = "Hello\nWorld!"
        prompt = create_system_prompt(special_message)
        assert "Hello\nWorld!" in prompt

    @pytest.mark.asyncio
    async def test_direct_chat_success(self, client, initialize_router_with_mock):
        """Test successful direct chat endpoint"""
        mock_service = initialize_router_with_mock
        mock_service.generate.return_value = "Hello! I'm Phi-2, happy to help you today."
        
        request_data = {
            "message": "Hello AI",
            "max_tokens": 512,
            "temperature": 0.5
        }
        
        response = client.post("/llm/chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "response" in data
        assert data["model"] == "phi-2"
        assert "tokens_used" in data
        assert "processing_time" in data
        assert data["response"] == "Hello! I'm Phi-2, happy to help you today."
        
        # Verify service was called correctly
        mock_service.generate.assert_called_once()
        call_args = mock_service.generate.call_args
        assert call_args[1]["max_tokens"] == 512
        assert call_args[1]["temperature"] == 0.5
        assert "Hello AI" in call_args[1]["prompt"]

    @pytest.mark.asyncio 
    async def test_direct_chat_default_parameters(self, client, initialize_router_with_mock):
        """Test direct chat with default parameters"""
        mock_service = initialize_router_with_mock
        mock_service.generate.return_value = "Response with defaults"
        
        request_data = {"message": "Test message"}
        response = client.post("/llm/chat", json=request_data)
        
        assert response.status_code == 200
        
        # Verify default parameters were used
        call_args = mock_service.generate.call_args
        assert call_args[1]["max_tokens"] == 1024
        assert call_args[1]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_direct_chat_service_not_initialized(self, client):
        """Test error when LLM service not initialized"""
        # Ensure service is None
        import app.api.llm
        app.api.llm.llm_service = None
        
        request_data = {"message": "Hello"}
        response = client.post("/llm/chat", json=request_data)
        
        assert response.status_code == 503
        assert "LLM service not initialized" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_direct_chat_service_not_loaded(self, client, initialize_router_with_mock):
        """Test error when LLM service not available"""
        mock_service = initialize_router_with_mock
        mock_service.is_loaded.return_value = False
        
        request_data = {"message": "Hello"}
        response = client.post("/llm/chat", json=request_data)
        
        assert response.status_code == 503
        assert "LLM service not available" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_direct_chat_generation_error(self, client, initialize_router_with_mock):
        """Test error handling during generation"""
        mock_service = initialize_router_with_mock
        mock_service.generate.side_effect = Exception("Model generation failed")
        
        request_data = {"message": "Hello"}
        response = client.post("/llm/chat", json=request_data)
        
        assert response.status_code == 500
        assert "Chat generation failed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_streaming_get_endpoint(self, client, initialize_router_with_mock):
        """Test GET streaming endpoint"""
        mock_service = initialize_router_with_mock
        
        # Mock async generator for streaming
        async def mock_stream():
            yield "Hello"
            yield " there"
            yield "!"
        
        # Reset the mock to return our specific generator
        mock_service.generate_stream = Mock(return_value=mock_stream())
        
        response = client.get("/llm/stream?q=Hello&max_tokens=512&temperature=0.5")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Parse SSE content
        content = response.text
        assert "data:" in content
        assert '"type": "start"' in content
        assert '"type": "token"' in content
        assert '"type": "end"' in content

    @pytest.mark.asyncio
    async def test_streaming_post_endpoint(self, client, initialize_router_with_mock):
        """Test POST streaming endpoint"""
        mock_service = initialize_router_with_mock
        
        async def mock_stream():
            yield "Response"
            yield " token"
        
        mock_service.generate_stream.return_value = mock_stream()
        
        request_data = {
            "message": "Test streaming",
            "max_tokens": 256,
            "temperature": 0.8
        }
        
        response = client.post("/llm/stream", json=request_data)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Verify service called with correct parameters
        call_args = mock_service.generate_stream.call_args
        assert call_args[1]["max_tokens"] == 256
        assert call_args[1]["temperature"] == 0.8

    @pytest.mark.asyncio
    async def test_streaming_service_error(self, client, initialize_router_with_mock):
        """Test streaming error handling"""
        mock_service = initialize_router_with_mock
        mock_service.generate_stream.side_effect = Exception("Streaming failed")
        
        response = client.get("/llm/stream?q=Hello")
        
        assert response.status_code == 200  # SSE returns 200 even for errors
        content = response.text
        assert '"type": "error"' in content
        assert "Generation failed" in content

    @pytest.mark.asyncio
    async def test_streaming_empty_tokens(self, client, initialize_router_with_mock):
        """Test streaming with empty tokens (should be filtered)"""
        mock_service = initialize_router_with_mock
        
        async def mock_stream_with_empty():
            yield "Hello"
            yield ""  # Empty token should be filtered
            yield None  # None token should be filtered  
            yield "World"
        
        mock_service.generate_stream = Mock(return_value=mock_stream_with_empty())
        
        response = client.get("/llm/stream?q=Test")
        
        assert response.status_code == 200
        content = response.text
        
        # Should contain non-empty tokens but not empty ones
        assert '"content": "Hello"' in content
        assert '"content": "World"' in content
        assert '"content": ""' not in content

    def test_health_endpoint_healthy(self, client, initialize_router_with_mock):
        """Test health endpoint when service is healthy"""
        mock_service = initialize_router_with_mock
        
        response = client.get("/llm/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["model"] == "phi-2"
        assert data["loaded"] is True
        assert data["mock_mode"] is True

    def test_health_endpoint_unavailable(self, client, initialize_router_with_mock):
        """Test health endpoint when service unavailable"""
        mock_service = initialize_router_with_mock
        mock_service.is_loaded.return_value = False
        
        response = client.get("/llm/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "unavailable"
        assert data["loaded"] is False

    def test_health_endpoint_not_initialized(self, client):
        """Test health endpoint when service not initialized"""
        import app.api.llm
        app.api.llm.llm_service = None
        
        response = client.get("/llm/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "error"
        assert "not initialized" in data["message"]

    def test_health_endpoint_error(self, client, initialize_router_with_mock):
        """Test health endpoint error handling"""
        mock_service = initialize_router_with_mock
        mock_service.is_loaded.side_effect = Exception("Health check failed")
        
        response = client.get("/llm/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "error"
        assert "Health check failed" in data["message"]

    def test_info_endpoint(self, client):
        """Test info endpoint"""
        response = client.get("/llm/info")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["model"] == "phi-2"
        assert "description" in data
        assert "capabilities" in data
        assert isinstance(data["capabilities"], list)
        assert data["max_tokens"] == 2048
        assert data["context_window"] == 2048
        assert "features" in data
        assert "streaming" in data["features"]
        assert "non-streaming" in data["features"]

    @pytest.mark.asyncio
    async def test_parameter_boundaries(self, client, initialize_router_with_mock):
        """Test parameter boundary validation"""
        mock_service = initialize_router_with_mock
        mock_service.generate.return_value = "Response"
        
        # Test minimum values
        request_data = {
            "message": "x",  # Minimum length
            "max_tokens": 1,  # Minimum tokens
            "temperature": 0.0  # Minimum temperature
        }
        response = client.post("/llm/chat", json=request_data)
        assert response.status_code == 200
        
        # Test maximum values
        request_data = {
            "message": "x" * 4000,  # Maximum length
            "max_tokens": 2048,  # Maximum tokens
            "temperature": 1.0  # Maximum temperature
        }
        response = client.post("/llm/chat", json=request_data)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, test_app, initialize_router_with_mock):
        """Test handling of concurrent requests"""
        mock_service = initialize_router_with_mock
        mock_service.generate.return_value = "Concurrent response"
        
        # Create multiple concurrent requests
        import asyncio
        import httpx
        
        async def make_request():
            async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.post("/llm/chat", json={"message": "Concurrent test"})
                return response.status_code
        
        # Run 5 concurrent requests
        tasks = [make_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(status == 200 for status in results)
        assert mock_service.generate.call_count == 5

    @pytest.mark.asyncio
    async def test_token_counting_approximation(self, client, initialize_router_with_mock):
        """Test token usage calculation"""
        mock_service = initialize_router_with_mock
        test_response = "This is a test response with multiple words"
        mock_service.generate.return_value = test_response
        
        response = client.post("/llm/chat", json={"message": "Test"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Token count should approximate word count
        expected_tokens = len(test_response.split())
        assert data["tokens_used"] == expected_tokens

    @pytest.mark.asyncio
    async def test_processing_time_measurement(self, client, initialize_router_with_mock):
        """Test processing time is measured"""
        mock_service = initialize_router_with_mock
        
        # Add delay to simulate processing
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return "Slow response"
        
        mock_service.generate = slow_generate
        
        response = client.post("/llm/chat", json={"message": "Test"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Processing time should be measured (at least 100ms)
        assert data["processing_time"] >= 0.1
        assert isinstance(data["processing_time"], float)