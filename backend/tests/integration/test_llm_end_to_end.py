"""
Phase 3: End-to-End Integration Tests
Tests complete user journeys, cross-feature compatibility, and real-world scenarios
"""

import pytest
import asyncio
import json
import time
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from typing import AsyncGenerator
from httpx import AsyncClient
from fastapi import FastAPI

from app.api.llm import router as llm_router, initialize_llm_router
from app.services.llm_service import ModelManager


class TestLLMEndToEnd:
    """End-to-end integration tests for the LLM chat feature"""
    
    @pytest.fixture
    def mock_phi2_model(self):
        """Mock Phi-2 model with realistic response generation"""
        manager = Mock(spec=ModelManager)
        manager.is_loaded = Mock(return_value=True)
        manager._is_mock_mode = Mock(return_value=True)
        
        # Realistic response patterns based on prompt content
        async def mock_generate(prompt: str, max_tokens: int = 1024, temperature: float = 0.7, **kwargs):
            await asyncio.sleep(0.1)  # Simulate processing time
            
            if "hello" in prompt.lower():
                return "Hello! I'm Phi-2, an AI assistant. How can I help you today?"
            elif "python" in prompt.lower() and ("example" in prompt.lower() or "simple" in prompt.lower()):
                return "Here's a simple example:\\n\\ndef hello_world():\\n    print('Hello, World!')\\n\\nhello_world()"
            elif "python" in prompt.lower():
                return "Python is a versatile programming language known for its simplicity and readability. It's great for beginners and experts alike."
            elif "code" in prompt.lower() or "example" in prompt.lower():
                return "Here's a simple example:\\n\\ndef hello_world():\\n    print('Hello, World!')\\n\\nhello_world()"
            elif "error" in prompt.lower():
                raise Exception("Simulated model error")
            else:
                return f"I understand you're asking about something. Let me help you with that topic."
        
        manager.generate = AsyncMock(side_effect=mock_generate)
        
        # Mock streaming generation
        async def mock_generate_stream(prompt: str, max_tokens: int = 1024, temperature: float = 0.7, **kwargs):
            await asyncio.sleep(0.05)  # Initial delay
            
            if "hello" in prompt.lower():
                tokens = ["Hello", "!", " I'm", " Phi", "-2", ",", " an", " AI", " assistant", ".", " How", " can", " I", " help", " you", " today", "?"]
            elif "python" in prompt.lower():
                tokens = ["Python", " is", " a", " versatile", " programming", " language", " known", " for", " its", " simplicity", " and", " readability", "."]
            elif "code" in prompt.lower():
                tokens = ["Here", "'s", " a", " simple", " example", ":", "\\n\\n", "def", " hello", "_world", "()", ":", "\\n", "    print", "('Hello", ", World", "!')", "\\n"]
            else:
                tokens = ["I", " understand", " you're", " asking", " about", " something", ".", " Let", " me", " help", " you", "."]
            
            for i, token in enumerate(tokens):
                yield token
                await asyncio.sleep(0.02)  # Simulate token streaming delay
        
        manager.generate_stream = Mock(side_effect=mock_generate_stream)
        
        return manager
    
    @pytest.fixture
    def integration_app(self, mock_phi2_model):
        """Create FastAPI app with LLM router for integration testing"""
        app = FastAPI(title="LLM Integration Test App")
        app.include_router(llm_router, prefix="/llm", tags=["LLM"])
        
        # Initialize LLM service
        initialize_llm_router(mock_phi2_model)
        
        yield app, mock_phi2_model
        
        # Cleanup
        import app.api.llm
        app.api.llm.llm_service = None

    @pytest.mark.asyncio
    async def test_complete_user_journey_direct_chat(self, integration_app):
        """Test complete user journey: login → navigate → chat → response"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Simulate user starting a chat conversation
            conversation = [
                "Hello, I'm new to programming",
                "Can you help me learn Python?",
                "Show me a simple Python example",
                "Thank you for the help!"
            ]
            
            responses = []
            for message in conversation:
                response = await client.post("/llm/chat", json={
                    "message": message,
                    "max_tokens": 512,
                    "temperature": 0.7
                })
                
                assert response.status_code == 200
                data = response.json()
                responses.append(data)
                
                # Verify response structure
                assert "response" in data
                assert "model" in data
                assert "tokens_used" in data
                assert "processing_time" in data
                assert data["model"] == "phi-2"
                assert len(data["response"]) > 0
                assert data["tokens_used"] > 0
                assert data["processing_time"] >= 0
            
            # Verify conversation progression
            assert len(responses) == 4
            
            # Verify contextual responses
            hello_response = responses[0]["response"].lower()
            assert "hello" in hello_response or "hi" in hello_response
            
            python_response = responses[1]["response"].lower()
            assert "python" in python_response
            
            code_response = responses[2]["response"].lower()
            assert "def" in code_response or "print" in code_response
            
            # Verify service was called for each message
            assert mock_service.generate.call_count == 4

    @pytest.mark.asyncio
    async def test_streaming_user_journey(self, integration_app):
        """Test complete streaming user journey with real-time responses"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test GET streaming endpoint
            response = await client.get("/llm/stream", params={
                "q": "Tell me about Python programming",
                "max_tokens": 256,
                "temperature": 0.6
            })
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert "no-cache" in response.headers["cache-control"]
            
            # Parse streaming response
            content = response.text
            lines = [line for line in content.split('\n') if line.startswith('data:')]
            
            # Verify SSE format and event sequence
            events = []
            for line in lines:
                try:
                    event_data = json.loads(line[5:])  # Remove 'data: '
                    events.append(event_data)
                except json.JSONDecodeError:
                    continue
            
            # For now, verify we get streaming content (actual SSE format may vary)
            # In a real implementation, we would have proper event parsing
            assert len(lines) > 0  # Should have some streaming data
            # Verify service was called for streaming
            assert mock_service.generate_stream.call_count >= 1
            
            # Verify token progression
            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) > 5  # Should have multiple tokens
            
            # Reconstruct response from tokens
            full_response = "".join([e.get("content", "") for e in token_events])
            assert len(full_response) > 0
            assert "python" in full_response.lower()
            
            # Test POST streaming endpoint
            post_response = await client.post("/llm/stream", json={
                "message": "Write a hello world function",
                "max_tokens": 256,
                "temperature": 0.7
            })
            
            assert post_response.status_code == 200
            assert post_response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            # Verify both streaming methods were called
            assert mock_service.generate_stream.call_count == 2

    @pytest.mark.asyncio
    async def test_error_recovery_workflows(self, integration_app):
        """Test error handling and recovery in real user scenarios"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create a separate mock function that can be reset
            original_generate = mock_service.generate.side_effect
            
            # Test 1: Service error during generation
            async def error_generate(*args, **kwargs):
                raise Exception("Simulated model error")
            
            mock_service.generate.side_effect = error_generate
            
            response1 = await client.post("/llm/chat", json={
                "message": "This will cause an error",
            })
            
            assert response1.status_code == 500
            error_data = response1.json()
            assert "Chat generation failed" in error_data["detail"]
            assert "Simulated model error" in error_data["detail"]
            
            # Test 2: Recovery after error - restore original function
            mock_service.generate.side_effect = original_generate
            
            response2 = await client.post("/llm/chat", json={
                "message": "Hello, are you working now?",
            })
            
            assert response2.status_code == 200
            recovery_data = response2.json()
            assert "response" in recovery_data
            assert len(recovery_data["response"]) > 0
            
            # Test 3: Validation error handling
            response3 = await client.post("/llm/chat", json={
                "message": "",  # Empty message should fail validation
                "max_tokens": 512
            })
            
            assert response3.status_code == 422
            validation_error = response3.json()
            assert "detail" in validation_error
            
            # Test 4: Service continues working after validation errors
            response4 = await client.post("/llm/chat", json={
                "message": "Normal request after validation error",
            })
            
            assert response4.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_user_sessions(self, integration_app):
        """Test multiple users using LLM chat simultaneously"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Simulate 5 concurrent users
            user_sessions = []
            for user_id in range(5):
                session_tasks = [
                    client.post("/llm/chat", json={
                        "message": f"User {user_id} question {q}",
                        "max_tokens": 256,
                        "temperature": 0.7
                    })
                    for q in range(3)  # Each user asks 3 questions
                ]
                user_sessions.extend(session_tasks)
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*user_sessions)
            
            # Verify all requests succeeded
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert "response" in data
                assert data["model"] == "phi-2"
                assert len(data["response"]) > 0
            
            # Verify service handled all 15 requests (5 users × 3 questions)
            assert mock_service.generate.call_count == 15
            
            # Verify response times are reasonable
            processing_times = [r.json()["processing_time"] for r in responses]
            avg_processing_time = sum(processing_times) / len(processing_times)
            assert avg_processing_time < 5.0  # Average should be under 5 seconds

    @pytest.mark.asyncio
    async def test_mixed_interaction_patterns(self, integration_app):
        """Test mixing direct chat and streaming requests"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create mixed request pattern
            tasks = [
                # Direct chat requests
                client.post("/llm/chat", json={"message": "Direct chat 1"}),
                client.post("/llm/chat", json={"message": "Direct chat 2"}),
                
                # Streaming requests
                client.get("/llm/stream?q=Stream%20request%201&max_tokens=200"),
                client.post("/llm/stream", json={"message": "Stream request 2", "max_tokens": 200}),
                
                # More direct chat
                client.post("/llm/chat", json={"message": "Direct chat 3"}),
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # Verify all requests succeeded
            for i, response in enumerate(responses):
                assert response.status_code == 200
                
                if i in [0, 1, 4]:  # Direct chat responses
                    data = response.json()
                    assert "response" in data
                    assert "tokens_used" in data
                else:  # Streaming responses
                    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                    assert len(response.text) > 0
            
            # Verify service methods were called appropriately
            assert mock_service.generate.call_count == 3  # Direct chat calls
            assert mock_service.generate_stream.call_count == 2  # Streaming calls

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, integration_app):
        """Test health monitoring during active usage"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Initial health check
            health_response = await client.get("/llm/health")
            assert health_response.status_code == 200
            
            health_data = health_response.json()
            assert health_data["status"] == "healthy"
            assert health_data["loaded"] == True
            assert health_data["model"] == "phi-2"
            
            # Make several requests while monitoring health
            for i in range(5):
                # Make chat request
                chat_response = await client.post("/llm/chat", json={
                    "message": f"Health test message {i}",
                    "max_tokens": 128
                })
                assert chat_response.status_code == 200
                
                # Check health after each request
                health_check = await client.get("/llm/health")
                assert health_check.status_code == 200
                health_status = health_check.json()
                assert health_status["status"] == "healthy"
            
            # Final info check
            info_response = await client.get("/llm/info")
            assert info_response.status_code == 200
            
            info_data = info_response.json()
            assert info_data["model"] == "phi-2"
            assert "streaming" in info_data["features"]
            assert "non-streaming" in info_data["features"]
            assert info_data["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_parameter_boundary_workflows(self, integration_app):
        """Test edge cases and boundary conditions in real workflows"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test minimum parameters
            min_response = await client.post("/llm/chat", json={
                "message": "x",  # Minimum length
                "max_tokens": 1,  # Minimum tokens
                "temperature": 0.0  # Minimum temperature
            })
            assert min_response.status_code == 200
            
            # Test maximum parameters
            max_message = "x" * 4000  # Maximum message length
            max_response = await client.post("/llm/chat", json={
                "message": max_message,
                "max_tokens": 2048,  # Maximum tokens
                "temperature": 1.0  # Maximum temperature
            })
            assert max_response.status_code == 200
            
            # Test streaming with edge parameters
            stream_response = await client.get("/llm/stream", params={
                "q": "Short",
                "max_tokens": "10",
                "temperature": "0.1"
            })
            assert stream_response.status_code == 200
            
            # Verify service received correct parameters
            generate_calls = mock_service.generate.call_args_list
            stream_calls = mock_service.generate_stream.call_args_list
            
            # Check parameter passing
            assert len(generate_calls) >= 2
            assert len(stream_calls) >= 1
            
            # Verify boundary parameters were passed correctly
            min_call = generate_calls[0][1]
            assert min_call["max_tokens"] == 1
            assert min_call["temperature"] == 0.0
            
            max_call = generate_calls[1][1]
            assert max_call["max_tokens"] == 2048
            assert max_call["temperature"] == 1.0

    @pytest.mark.asyncio
    async def test_long_conversation_stability(self, integration_app):
        """Test system stability during extended conversations"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Simulate a long conversation (20 exchanges)
            conversation_topics = [
                "programming", "python", "javascript", "databases", "apis",
                "frontend", "backend", "testing", "debugging", "algorithms",
                "data structures", "machine learning", "web development", 
                "mobile apps", "cloud computing", "devops", "security",
                "performance", "scalability", "architecture"
            ]
            
            responses = []
            start_time = time.time()
            
            for i, topic in enumerate(conversation_topics):
                response = await client.post("/llm/chat", json={
                    "message": f"Tell me about {topic} in programming",
                    "max_tokens": 256,
                    "temperature": 0.7
                })
                
                assert response.status_code == 200
                data = response.json()
                responses.append(data)
                
                # Verify response quality doesn't degrade
                assert len(data["response"]) > 10
                assert data["tokens_used"] > 0
                assert data["processing_time"] >= 0
                
                # Check health periodically
                if i % 5 == 0:
                    health = await client.get("/llm/health")
                    assert health.status_code == 200
                    assert health.json()["status"] == "healthy"
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Verify performance requirements
            avg_response_time = sum(r["processing_time"] for r in responses) / len(responses)
            assert avg_response_time < 2.0  # Average processing should be under 2s
            assert total_time < 60.0  # Total conversation should complete in under 60s
            
            # Verify service handled all requests
            assert mock_service.generate.call_count == 20

    @pytest.mark.asyncio
    async def test_authentication_workflow_integration(self, integration_app):
        """Test authentication token handling in complete workflows"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test token authentication in streaming
            test_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.token"
            
            # GET streaming with token
            get_response = await client.get("/llm/stream", params={
                "q": "Authenticated request",
                "token": test_token,
                "max_tokens": 128
            })
            assert get_response.status_code == 200
            
            # POST streaming (JWT in headers would be handled by middleware)
            post_response = await client.post("/llm/stream", json={
                "message": "Authenticated POST streaming",
                "max_tokens": 128
            })
            assert post_response.status_code == 200
            
            # Verify both requests worked
            assert mock_service.generate_stream.call_count == 2
            
            # Test multiple authenticated requests
            auth_tasks = [
                client.get(f"/llm/stream?q=Auth%20test%20{i}&token={test_token}")
                for i in range(3)
            ]
            
            auth_responses = await asyncio.gather(*auth_tasks)
            for response in auth_responses:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @pytest.mark.asyncio
    async def test_cross_endpoint_consistency(self, integration_app):
        """Test consistency between different endpoints and methods"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            test_message = "Tell me about Python programming"
            
            # Make same request via different endpoints
            direct_response = await client.post("/llm/chat", json={
                "message": test_message,
                "max_tokens": 256,
                "temperature": 0.7
            })
            
            get_stream_response = await client.get("/llm/stream", params={
                "q": test_message,
                "max_tokens": 256,
                "temperature": 0.7
            })
            
            post_stream_response = await client.post("/llm/stream", json={
                "message": test_message,
                "max_tokens": 256,
                "temperature": 0.7
            })
            
            # Verify all succeeded
            assert direct_response.status_code == 200
            assert get_stream_response.status_code == 200
            assert post_stream_response.status_code == 200
            
            # Verify service was called with consistent parameters
            generate_call = mock_service.generate.call_args[1]
            stream_calls = mock_service.generate_stream.call_args_list
            
            assert generate_call["max_tokens"] == 256
            assert generate_call["temperature"] == 0.7
            
            for call_args in stream_calls:
                call_kwargs = call_args[1]
                assert call_kwargs["max_tokens"] == 256
                assert call_kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_performance_under_load(self, integration_app):
        """Test performance characteristics under realistic load"""
        app, mock_service = integration_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create load test scenarios
            load_test_requests = []
            
            # Burst of direct chat requests
            for i in range(10):
                load_test_requests.append(
                    client.post("/llm/chat", json={
                        "message": f"Load test message {i}",
                        "max_tokens": 256,
                        "temperature": 0.7
                    })
                )
            
            # Burst of streaming requests
            for i in range(5):
                load_test_requests.append(
                    client.get(f"/llm/stream?q=Load%20stream%20{i}&max_tokens=128")
                )
            
            # Execute load test
            start_time = time.time()
            responses = await asyncio.gather(*load_test_requests)
            end_time = time.time()
            
            # Verify all requests succeeded
            for response in responses:
                assert response.status_code == 200
            
            # Performance analysis
            total_time = end_time - start_time
            requests_per_second = len(responses) / total_time
            
            # Performance assertions
            assert total_time < 30.0  # Should complete within 30 seconds
            assert requests_per_second > 0.5  # Should handle at least 0.5 req/sec
            
            # Verify service handled all requests
            assert mock_service.generate.call_count == 10
            assert mock_service.generate_stream.call_count == 5
            
            # System should still be healthy after load test
            health_response = await client.get("/llm/health")
            assert health_response.status_code == 200
            assert health_response.json()["status"] == "healthy"