"""
Phase 3: Cross-Feature Compatibility Tests
Tests RAG vs Direct LLM coexistence, model sharing, and resource management
"""

import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from typing import AsyncGenerator
from httpx import AsyncClient
from fastapi import FastAPI

from app.api.llm import router as llm_router, initialize_llm_router
from app.api.query import router as query_router  # RAG endpoints
from app.services.llm_service import ModelManager
from app.services.query_service import QueryService
from app.services.vector_service import VectorService


class TestCrossFeatureCompatibility:
    """Test coexistence of RAG chat and Direct LLM chat features"""
    
    @pytest.fixture
    def shared_model_manager(self):
        """Mock the shared ModelManager singleton used by both RAG and Direct LLM"""
        manager = Mock(spec=ModelManager)
        manager.is_loaded = Mock(return_value=True)
        manager._is_mock_mode = Mock(return_value=True)
        
        # Track usage statistics
        manager.rag_calls = 0
        manager.direct_calls = 0
        
        # Mock generation with usage tracking
        async def mock_generate(prompt: str, context: str = None, **kwargs):
            await asyncio.sleep(0.1)  # Simulate processing
            
            if context:  # RAG call (has context)
                manager.rag_calls += 1
                return f"Based on the provided context: {context[:50]}..., I can answer that {prompt[:30]}..."
            else:  # Direct LLM call (no context)
                manager.direct_calls += 1
                if "hello" in prompt.lower():
                    return "Hello! I'm Phi-2, ready to help you directly without any document context."
                else:
                    return f"Direct response to: {prompt[:50]}..."
        
        manager.generate = AsyncMock(side_effect=mock_generate)
        
        # Mock streaming with usage tracking
        async def mock_generate_stream(prompt: str, context: str = None, **kwargs):
            await asyncio.sleep(0.05)
            
            if context:  # RAG streaming
                manager.rag_calls += 1
                tokens = ["Based", " on", " the", " context", ",", " here's", " the", " answer", "."]
            else:  # Direct LLM streaming
                manager.direct_calls += 1
                tokens = ["Direct", " streaming", " response", " without", " context", "."]
            
            for token in tokens:
                yield token
                await asyncio.sleep(0.02)
        
        manager.generate_stream = Mock(side_effect=mock_generate_stream)
        
        return manager
    
    @pytest.fixture
    def mock_vector_service(self):
        """Mock vector service for RAG functionality"""
        vector_service = Mock(spec=VectorService)
        
        # Mock document search results
        async def mock_search(query: str, workspace_id: str, top_k: int = 5):
            # Return mock search results
            return [
                {
                    "content": f"Document content related to {query}",
                    "metadata": {"source": "test_doc.pdf", "page": 1},
                    "score": 0.9
                },
                {
                    "content": f"Additional context for {query}",
                    "metadata": {"source": "test_doc2.pdf", "page": 2},
                    "score": 0.8
                }
            ]
        
        vector_service.search = AsyncMock(side_effect=mock_search)
        vector_service.is_workspace_initialized = Mock(return_value=True)
        
        return vector_service
    
    @pytest.fixture
    def mock_query_service(self, shared_model_manager, mock_vector_service):
        """Mock RAG query service"""
        query_service = Mock(spec=QueryService)
        
        async def mock_process_query(query: str, workspace_id: str, **kwargs):
            # Simulate RAG pipeline: vector search + LLM generation
            search_results = await mock_vector_service.search(query, workspace_id)
            context = "\\n".join([result["content"] for result in search_results])
            
            # Use shared model manager for RAG
            response = await shared_model_manager.generate(
                prompt=query,
                context=context,
                **kwargs
            )
            
            return {
                "response": response,
                "sources": search_results,
                "tokens_used": 150,
                "processing_time": 0.8
            }
        
        query_service.process_query = AsyncMock(side_effect=mock_process_query)
        
        return query_service
    
    @pytest.fixture
    def dual_feature_app(self, shared_model_manager, mock_query_service):
        """Create app with both RAG and Direct LLM endpoints"""
        app = FastAPI(title="Dual Feature Test App")
        
        # Add both routers
        app.include_router(llm_router, prefix="/llm", tags=["Direct LLM"])
        app.include_router(query_router, prefix="/query", tags=["RAG Query"])
        
        # Initialize LLM service for direct chat
        initialize_llm_router(shared_model_manager)
        
        # Initialize query service for RAG
        # In a real app, this would be done through ServiceManager
        with patch('app.api.query.query_service', mock_query_service):
            yield app, shared_model_manager, mock_query_service
        
        # Cleanup
        import app.api.llm
        app.api.llm.llm_service = None

    @pytest.mark.asyncio
    async def test_concurrent_rag_and_direct_llm_usage(self, dual_feature_app):
        """Test using RAG chat and Direct LLM chat simultaneously"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create concurrent requests mixing RAG and Direct LLM
            tasks = [
                # RAG requests (with document context)
                client.post("/query/ask", json={
                    "question": "What is machine learning?",
                    "workspace_id": "test_workspace"
                }),
                
                # Direct LLM requests (no context)
                client.post("/llm/chat", json={
                    "message": "Hello, how are you today?",
                    "max_tokens": 256
                }),
                
                # More RAG requests
                client.post("/query/ask", json={
                    "question": "Explain neural networks",
                    "workspace_id": "test_workspace"
                }),
                
                # More Direct LLM requests
                client.post("/llm/chat", json={
                    "message": "Tell me a joke",
                    "max_tokens": 128
                }),
                
                # Direct LLM streaming
                client.get("/llm/stream?q=What%20is%20Python%3F&max_tokens=200"),
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # Verify all requests succeeded
            for i, response in enumerate(responses):
                assert response.status_code == 200
                
                if i in [0, 2]:  # RAG responses
                    data = response.json()
                    assert "response" in data
                    assert "sources" in data
                    assert "Based on the provided context" in data["response"]
                elif i in [1, 3]:  # Direct LLM responses
                    data = response.json()
                    assert "response" in data
                    assert "model" in data
                    assert data["model"] == "phi-2"
                    assert "Direct response" in data["response"] or "Hello!" in data["response"]
                else:  # Streaming response
                    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                    assert "Direct streaming response" in response.text
            
            # Verify shared model was used by both features
            assert shared_model.rag_calls == 2  # Two RAG requests
            assert shared_model.direct_calls == 3  # Two direct + one streaming

    @pytest.mark.asyncio
    async def test_model_sharing_efficiency(self, dual_feature_app):
        """Test that both features efficiently share the same model instance"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Reset call counters
            shared_model.rag_calls = 0
            shared_model.direct_calls = 0
            
            # Rapid switching between RAG and Direct LLM
            requests = []
            for i in range(10):
                if i % 2 == 0:
                    # RAG request
                    requests.append(
                        client.post("/query/ask", json={
                            "question": f"RAG question {i}",
                            "workspace_id": "test_workspace"
                        })
                    )
                else:
                    # Direct LLM request
                    requests.append(
                        client.post("/llm/chat", json={
                            "message": f"Direct question {i}",
                            "max_tokens": 128
                        })
                    )
            
            responses = await asyncio.gather(*requests)
            
            # All should succeed
            for response in responses:
                assert response.status_code == 200
            
            # Verify model usage distribution
            assert shared_model.rag_calls == 5  # Even indices (0,2,4,6,8)
            assert shared_model.direct_calls == 5  # Odd indices (1,3,5,7,9)
            
            # Total calls should equal number of requests
            total_calls = shared_model.rag_calls + shared_model.direct_calls
            assert total_calls == 10
            
            # Both services should be healthy
            health_response = await client.get("/llm/health")
            assert health_response.status_code == 200
            assert health_response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_independent_chat_histories(self, dual_feature_app):
        """Test that RAG and Direct LLM maintain independent chat histories"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # RAG conversation thread
            rag_conversation = [
                "What is artificial intelligence according to the documents?",
                "How does AI relate to machine learning in the context?",
                "What are the applications mentioned in the sources?"
            ]
            
            # Direct LLM conversation thread
            direct_conversation = [
                "Hello, introduce yourself",
                "What can you help me with?",
                "Tell me about your capabilities"
            ]
            
            # Interleave conversations to test independence
            mixed_requests = []
            for i in range(3):
                # RAG request
                mixed_requests.append(
                    client.post("/query/ask", json={
                        "question": rag_conversation[i],
                        "workspace_id": "test_workspace"
                    })
                )
                
                # Direct LLM request
                mixed_requests.append(
                    client.post("/llm/chat", json={
                        "message": direct_conversation[i],
                        "max_tokens": 256
                    })
                )
            
            responses = await asyncio.gather(*mixed_requests)
            
            # Analyze responses for context independence
            rag_responses = []
            direct_responses = []
            
            for i, response in enumerate(responses):
                assert response.status_code == 200
                data = response.json()
                
                if i % 2 == 0:  # RAG responses
                    rag_responses.append(data)
                    # Should contain context-based information
                    assert "Based on the provided context" in data["response"]
                    assert "sources" in data
                else:  # Direct LLM responses
                    direct_responses.append(data)
                    # Should be context-free responses
                    assert "Direct response" in data["response"] or "Hello!" in data["response"]
                    assert "model" in data
            
            # Verify response characteristics
            assert len(rag_responses) == 3
            assert len(direct_responses) == 3
            
            # RAG responses should reference documents/context
            for rag_resp in rag_responses:
                assert len(rag_resp.get("sources", [])) > 0
            
            # Direct responses should not have sources
            for direct_resp in direct_responses:
                assert "sources" not in direct_resp

    @pytest.mark.asyncio
    async def test_resource_contention_handling(self, dual_feature_app):
        """Test handling of resource contention between RAG and Direct LLM"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create high-load scenario with both features
            high_load_tasks = []
            
            # Heavy RAG usage
            for i in range(8):
                high_load_tasks.append(
                    client.post("/query/ask", json={
                        "question": f"Complex RAG question {i} requiring detailed analysis",
                        "workspace_id": "test_workspace"
                    })
                )
            
            # Heavy Direct LLM usage
            for i in range(8):
                high_load_tasks.append(
                    client.post("/llm/chat", json={
                        "message": f"Complex direct question {i} requiring detailed response",
                        "max_tokens": 512
                    })
                )
            
            # Mixed streaming requests
            for i in range(4):
                high_load_tasks.append(
                    client.get(f"/llm/stream?q=Streaming%20question%20{i}&max_tokens=256")
                )
            
            # Execute all requests concurrently
            import time
            start_time = time.time()
            responses = await asyncio.gather(*high_load_tasks)
            end_time = time.time()
            
            # Verify all succeeded despite load
            success_count = 0
            for response in responses:
                if response.status_code == 200:
                    success_count += 1
            
            # Should handle most requests successfully
            success_rate = success_count / len(responses)
            assert success_rate >= 0.9  # At least 90% success rate
            
            # Performance should be reasonable under load
            total_time = end_time - start_time
            assert total_time < 60.0  # Should complete within 60 seconds
            
            # System should remain stable
            health_check = await client.get("/llm/health")
            assert health_check.status_code == 200

    @pytest.mark.asyncio
    async def test_streaming_coexistence(self, dual_feature_app):
        """Test streaming from both RAG and Direct LLM simultaneously"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Note: RAG streaming would need to be implemented in the actual app
            # For now, we test Direct LLM streaming alongside RAG regular requests
            
            tasks = [
                # Direct LLM streaming requests
                client.get("/llm/stream?q=Stream%20question%201&max_tokens=200"),
                client.post("/llm/stream", json={"message": "Stream question 2", "max_tokens": 150}),
                
                # Regular RAG requests (which could be extended to streaming)
                client.post("/query/ask", json={
                    "question": "Document question during streaming",
                    "workspace_id": "test_workspace"
                }),
                
                # More streaming
                client.get("/llm/stream?q=Stream%20question%203&max_tokens=100"),
                
                # More RAG
                client.post("/query/ask", json={
                    "question": "Another document question",
                    "workspace_id": "test_workspace"
                }),
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # Verify mixed response types
            streaming_responses = 0
            regular_responses = 0
            
            for i, response in enumerate(responses):
                assert response.status_code == 200
                
                if i in [0, 1, 3]:  # Streaming responses
                    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                    assert len(response.text) > 0
                    streaming_responses += 1
                else:  # Regular RAG responses
                    data = response.json()
                    assert "response" in data
                    assert "sources" in data
                    regular_responses += 1
            
            assert streaming_responses == 3
            assert regular_responses == 2
            
            # Verify model usage
            assert shared_model.direct_calls == 3  # Streaming calls
            assert shared_model.rag_calls == 2     # RAG calls

    @pytest.mark.asyncio
    async def test_error_isolation_between_features(self, dual_feature_app):
        """Test that errors in one feature don't affect the other"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Configure RAG service to fail
            query_service.process_query.side_effect = Exception("RAG service error")
            
            # Test that RAG fails but Direct LLM still works
            rag_response = await client.post("/query/ask", json={
                "question": "This will fail",
                "workspace_id": "test_workspace"
            })
            
            direct_response = await client.post("/llm/chat", json={
                "message": "This should still work",
                "max_tokens": 128
            })
            
            # RAG should fail
            assert rag_response.status_code == 500
            
            # Direct LLM should succeed
            assert direct_response.status_code == 200
            data = direct_response.json()
            assert "response" in data
            
            # Reset RAG service and break LLM service
            query_service.process_query.side_effect = None  # Fix RAG
            shared_model.generate.side_effect = Exception("LLM service error")  # Break Direct LLM
            
            # Now RAG should work but Direct LLM should fail
            rag_response2 = await client.post("/query/ask", json={
                "question": "RAG should work now",
                "workspace_id": "test_workspace"
            })
            
            direct_response2 = await client.post("/llm/chat", json={
                "message": "This should fail now",
                "max_tokens": 128
            })
            
            # RAG should succeed
            assert rag_response2.status_code == 200
            data2 = rag_response2.json()
            assert "response" in data2
            
            # Direct LLM should fail
            assert direct_response2.status_code == 500

    @pytest.mark.asyncio
    async def test_workspace_isolation_with_direct_llm(self, dual_feature_app):
        """Test that Direct LLM works independently of workspace context"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # RAG requests with different workspaces
            workspace_tasks = [
                client.post("/query/ask", json={
                    "question": "Workspace A question",
                    "workspace_id": "workspace_a"
                }),
                client.post("/query/ask", json={
                    "question": "Workspace B question", 
                    "workspace_id": "workspace_b"
                }),
            ]
            
            # Direct LLM requests (workspace-agnostic)
            direct_tasks = [
                client.post("/llm/chat", json={
                    "message": "Direct question 1 - no workspace",
                    "max_tokens": 128
                }),
                client.post("/llm/chat", json={
                    "message": "Direct question 2 - no workspace",
                    "max_tokens": 128
                }),
            ]
            
            # Execute all together
            all_responses = await asyncio.gather(*workspace_tasks, *direct_tasks)
            
            # All should succeed
            for response in all_responses:
                assert response.status_code == 200
            
            # RAG responses should have workspace context
            rag_responses = all_responses[:2]
            for rag_resp in rag_responses:
                data = rag_resp.json()
                assert "sources" in data
                assert "Based on the provided context" in data["response"]
            
            # Direct LLM responses should be workspace-agnostic
            direct_responses = all_responses[2:]
            for direct_resp in direct_responses:
                data = direct_resp.json()
                assert "sources" not in data
                assert "Direct response" in data["response"]
                assert data["model"] == "phi-2"

    @pytest.mark.asyncio
    async def test_feature_health_independence(self, dual_feature_app):
        """Test health monitoring for both features"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Check Direct LLM health
            llm_health = await client.get("/llm/health")
            assert llm_health.status_code == 200
            
            health_data = llm_health.json()
            assert health_data["status"] == "healthy"
            assert health_data["model"]["loaded"] == True
            assert health_data["model"]["name"] == "phi-2"
            
            # Check Direct LLM info
            llm_info = await client.get("/llm/info")
            assert llm_info.status_code == 200
            
            info_data = llm_info.json()
            assert info_data["model"]["name"] == "phi-2"
            assert info_data["capabilities"]["chat"] == True
            assert info_data["capabilities"]["streaming"] == True
            
            # Make mixed requests to exercise both features
            mixed_usage = [
                client.post("/llm/chat", json={"message": "Health test"}),
                client.post("/query/ask", json={
                    "question": "RAG health test",
                    "workspace_id": "test_workspace"
                }),
                client.get("/llm/stream?q=Stream%20health%20test&max_tokens=50"),
            ]
            
            usage_responses = await asyncio.gather(*mixed_usage)
            for response in usage_responses:
                assert response.status_code == 200
            
            # Health should remain good after usage
            final_health = await client.get("/llm/health")
            assert final_health.status_code == 200
            assert final_health.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_memory_efficiency_with_shared_model(self, dual_feature_app):
        """Test memory efficiency when sharing model between features"""
        app, shared_model, query_service = dual_feature_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Simulate extended usage of both features
            extended_usage = []
            
            # Alternating pattern to test model sharing efficiency
            for i in range(20):
                if i % 3 == 0:
                    # RAG request
                    extended_usage.append(
                        client.post("/query/ask", json={
                            "question": f"Extended RAG test {i}",
                            "workspace_id": "test_workspace"
                        })
                    )
                elif i % 3 == 1:
                    # Direct LLM chat
                    extended_usage.append(
                        client.post("/llm/chat", json={
                            "message": f"Extended direct test {i}",
                            "max_tokens": 256
                        })
                    )
                else:
                    # Direct LLM streaming
                    extended_usage.append(
                        client.get(f"/llm/stream?q=Extended%20stream%20{i}&max_tokens=128")
                    )
            
            responses = await asyncio.gather(*extended_usage)
            
            # All should succeed
            for response in responses:
                assert response.status_code == 200
            
            # Verify balanced usage of shared model
            expected_rag_calls = len([i for i in range(20) if i % 3 == 0])
            expected_direct_calls = len([i for i in range(20) if i % 3 != 0])
            
            assert shared_model.rag_calls == expected_rag_calls
            assert shared_model.direct_calls == expected_direct_calls
            
            # System should remain healthy after extended use
            final_health = await client.get("/llm/health")
            assert final_health.status_code == 200
            health_data = final_health.json()
            assert health_data["status"] == "healthy"
            
            # Memory usage should be stable (model loaded once, shared efficiently)
            # This would be validated through actual memory monitoring in production
            assert health_data["model"]["loaded"] == True  # Model still loaded efficiently