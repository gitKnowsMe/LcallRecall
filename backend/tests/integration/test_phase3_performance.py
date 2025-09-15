"""
Phase 3: Performance and Load Testing
Tests system behavior under realistic load scenarios
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import Mock, AsyncMock
from httpx import AsyncClient
from fastapi import FastAPI

from app.api.llm import router as llm_router, initialize_llm_router
from app.services.llm_service import ModelManager


class TestPerformanceAndLoad:
    """Performance and load testing for LLM chat feature"""
    
    @pytest.fixture
    def performance_mock_model(self):
        """Mock model optimized for performance testing"""
        manager = Mock(spec=ModelManager)
        manager.is_loaded = Mock(return_value=True)
        manager._is_mock_mode = Mock(return_value=True)
        
        # Track performance metrics
        manager.call_times = []
        manager.total_calls = 0
        
        async def mock_generate(prompt: str, max_tokens: int = 1024, **kwargs):
            start_time = time.time()
            manager.total_calls += 1
            
            # Simulate realistic processing delay
            await asyncio.sleep(0.1)
            
            processing_time = time.time() - start_time
            manager.call_times.append(processing_time)
            
            return f"Performance test response {manager.total_calls} for prompt: {prompt[:30]}..."
        
        manager.generate = AsyncMock(side_effect=mock_generate)
        
        # Mock streaming with performance tracking
        async def mock_generate_stream(prompt: str, max_tokens: int = 1024, **kwargs):
            start_time = time.time()
            manager.total_calls += 1
            
            # Simulate token streaming
            tokens = [f"Token_{i}" for i in range(10)]  # Fixed number for consistency
            
            for i, token in enumerate(tokens):
                yield token
                await asyncio.sleep(0.01)  # Consistent streaming delay
            
            processing_time = time.time() - start_time
            manager.call_times.append(processing_time)
        
        manager.generate_stream = Mock(side_effect=mock_generate_stream)
        
        return manager
    
    @pytest.fixture
    def performance_app(self, performance_mock_model):
        """FastAPI app optimized for performance testing"""
        app = FastAPI(title="Performance Test App")
        app.include_router(llm_router, prefix="/llm", tags=["LLM"])
        
        initialize_llm_router(performance_mock_model)
        
        yield app, performance_mock_model
        
        # Cleanup
        import app.api.llm
        app.api.llm.llm_service = None

    @pytest.mark.asyncio
    async def test_response_time_requirements(self, performance_app):
        """Test response time meets performance requirements"""
        app, mock_service = performance_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response_times = []
            
            # Test 10 individual requests
            for i in range(10):
                start_time = time.time()
                
                response = await client.post("/llm/chat", json={
                    "message": f"Performance test message {i}",
                    "max_tokens": 256,
                    "temperature": 0.7
                })
                
                end_time = time.time()
                total_time = end_time - start_time
                response_times.append(total_time)
                
                assert response.status_code == 200
                data = response.json()
                assert "response" in data
                assert "processing_time" in data
            
            # Performance analysis
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
            
            # Performance requirements
            assert avg_response_time < 2.0, f"Average response time {avg_response_time:.2f}s exceeds 2s limit"
            assert max_response_time < 5.0, f"Max response time {max_response_time:.2f}s exceeds 5s limit"
            assert min_response_time > 0.05, f"Min response time {min_response_time:.2f}s too fast (unrealistic)"
            
            # Consistency check - standard deviation should be reasonable
            std_dev = statistics.stdev(response_times)
            assert std_dev < 1.0, f"Response time standard deviation {std_dev:.2f}s too high"

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, performance_app):
        """Test concurrent request handling performance"""
        app, mock_service = performance_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test various concurrency levels
            concurrency_levels = [2, 5, 10]
            
            for concurrency in concurrency_levels:
                mock_service.call_times.clear()  # Reset metrics
                mock_service.total_calls = 0
                
                # Create concurrent requests
                tasks = []
                for i in range(concurrency):
                    task = client.post("/llm/chat", json={
                        "message": f"Concurrent test {i} at level {concurrency}",
                        "max_tokens": 128,
                        "temperature": 0.7
                    })
                    tasks.append(task)
                
                # Execute all requests concurrently
                start_time = time.time()
                responses = await asyncio.gather(*tasks)
                total_time = time.time() - start_time
                
                # Verify all requests succeeded
                success_count = sum(1 for r in responses if r.status_code == 200)
                success_rate = success_count / len(responses)
                
                assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95% at concurrency {concurrency}"
                
                # Performance metrics
                requests_per_second = len(responses) / total_time
                avg_processing_time = statistics.mean(mock_service.call_times) if mock_service.call_times else 0
                
                # Performance requirements scale with concurrency
                min_rps = max(0.5, concurrency * 0.3)  # Expect at least 30% efficiency
                assert requests_per_second >= min_rps, f"RPS {requests_per_second:.2f} below minimum {min_rps} at concurrency {concurrency}"
                
                # Individual processing times should remain consistent
                assert avg_processing_time < 1.0, f"Average processing time {avg_processing_time:.2f}s too high at concurrency {concurrency}"

    @pytest.mark.asyncio
    async def test_streaming_performance(self, performance_app):
        """Test streaming response performance characteristics"""
        app, mock_service = performance_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            streaming_metrics = []
            
            # Test multiple streaming requests
            for i in range(5):
                start_time = time.time()
                
                response = await client.get("/llm/stream", params={
                    "q": f"Streaming performance test {i}",
                    "max_tokens": 100,
                    "temperature": 0.6
                })
                
                first_byte_time = time.time() - start_time
                
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                
                # Measure full response time
                content = response.text
                total_time = time.time() - start_time
                
                streaming_metrics.append({
                    "first_byte_time": first_byte_time,
                    "total_time": total_time,
                    "content_length": len(content)
                })
            
            # Analyze streaming performance
            avg_first_byte = statistics.mean(m["first_byte_time"] for m in streaming_metrics)
            avg_total_time = statistics.mean(m["total_time"] for m in streaming_metrics)
            avg_content_length = statistics.mean(m["content_length"] for m in streaming_metrics)
            
            # Streaming performance requirements
            assert avg_first_byte < 0.5, f"First byte time {avg_first_byte:.2f}s too slow"
            assert avg_total_time < 2.0, f"Total streaming time {avg_total_time:.2f}s too slow"
            assert avg_content_length > 50, f"Average content length {avg_content_length} too small"

    @pytest.mark.asyncio
    async def test_memory_stability_under_load(self, performance_app):
        """Test memory stability during extended usage"""
        app, mock_service = performance_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Simulate extended usage pattern
            total_requests = 50
            batch_size = 10
            
            for batch in range(0, total_requests, batch_size):
                # Create batch of requests
                batch_tasks = []
                for i in range(batch, min(batch + batch_size, total_requests)):
                    task = client.post("/llm/chat", json={
                        "message": f"Memory stability test {i}",
                        "max_tokens": 256
                    })
                    batch_tasks.append(task)
                
                # Execute batch
                responses = await asyncio.gather(*batch_tasks)
                
                # Verify batch success
                batch_success = sum(1 for r in responses if r.status_code == 200)
                batch_success_rate = batch_success / len(responses)
                
                assert batch_success_rate >= 0.9, f"Batch {batch//batch_size} success rate {batch_success_rate:.2%} below 90%"
                
                # Check system health after each batch
                health_response = await client.get("/llm/health")
                assert health_response.status_code == 200
                
                health_data = health_response.json()
                assert health_data["status"] == "healthy", f"System unhealthy after batch {batch//batch_size}"
                
                # Brief pause between batches to allow cleanup
                await asyncio.sleep(0.1)
            
            # Final verification
            assert mock_service.total_calls == total_requests, f"Expected {total_requests} calls, got {mock_service.total_calls}"
            
            # Performance should remain consistent throughout
            if len(mock_service.call_times) >= 10:
                first_10_avg = statistics.mean(mock_service.call_times[:10])
                last_10_avg = statistics.mean(mock_service.call_times[-10:])
                
                # Performance degradation should be minimal
                degradation_ratio = last_10_avg / first_10_avg
                assert degradation_ratio < 2.0, f"Performance degraded by {degradation_ratio:.1f}x"

    @pytest.mark.asyncio
    async def test_mixed_load_patterns(self, performance_app):
        """Test system behavior under mixed request patterns"""
        app, mock_service = performance_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create mixed request pattern: burst + steady + concurrent streams
            mixed_tasks = []
            
            # 1. Burst of direct chat requests
            for i in range(8):
                mixed_tasks.append(
                    client.post("/llm/chat", json={
                        "message": f"Burst request {i}",
                        "max_tokens": 128
                    })
                )
            
            # 2. Concurrent streaming requests
            for i in range(4):
                mixed_tasks.append(
                    client.get(f"/llm/stream?q=Stream%20{i}&max_tokens=64")
                )
            
            # 3. Steady chat requests with different parameters
            for i in range(6):
                mixed_tasks.append(
                    client.post("/llm/chat", json={
                        "message": f"Steady request {i}",
                        "max_tokens": 256,
                        "temperature": 0.3 + (i * 0.1)  # Varying temperature
                    })
                )
            
            # Execute mixed load
            start_time = time.time()
            responses = await asyncio.gather(*mixed_tasks)
            total_time = time.time() - start_time
            
            # Analyze mixed load results
            success_count = sum(1 for r in responses if r.status_code == 200)
            success_rate = success_count / len(responses)
            
            assert success_rate >= 0.85, f"Mixed load success rate {success_rate:.2%} below 85%"
            assert total_time < 30.0, f"Mixed load took {total_time:.1f}s, exceeding 30s limit"
            
            # Categorize responses
            chat_responses = []
            stream_responses = []
            
            for i, response in enumerate(responses):
                if response.status_code == 200:
                    if i < 8 or i >= 12:  # Chat requests
                        chat_responses.append(response)
                    else:  # Stream requests
                        stream_responses.append(response)
            
            # Verify response types
            assert len(chat_responses) >= 12, "Not enough successful chat responses"
            assert len(stream_responses) >= 3, "Not enough successful stream responses"
            
            # Verify response characteristics
            for chat_resp in chat_responses[:5]:  # Check first few
                data = chat_resp.json()
                assert "response" in data
                assert "processing_time" in data
                assert data["model"] == "phi-2"
            
            for stream_resp in stream_responses[:2]:  # Check first few
                assert stream_resp.headers["content-type"] == "text/event-stream; charset=utf-8"
                assert len(stream_resp.text) > 0

    @pytest.mark.asyncio
    async def test_error_resilience_under_load(self, performance_app):
        """Test system resilience when errors occur under load"""
        app, mock_service = performance_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Configure some requests to fail
            original_generate = mock_service.generate.side_effect
            
            async def intermittent_failure_generate(*args, **kwargs):
                # Fail ~20% of requests
                mock_service.total_calls += 1
                if mock_service.total_calls % 5 == 0:
                    raise Exception("Intermittent service error")
                return await original_generate(*args, **kwargs)
            
            mock_service.generate.side_effect = intermittent_failure_generate
            mock_service.total_calls = 0
            
            # Create high-load scenario with expected failures
            resilience_tasks = []
            for i in range(25):  # 25 requests, ~5 should fail
                resilience_tasks.append(
                    client.post("/llm/chat", json={
                        "message": f"Resilience test {i}",
                        "max_tokens": 128
                    })
                )
            
            responses = await asyncio.gather(*resilience_tasks, return_exceptions=True)
            
            # Analyze resilience results
            successful_responses = []
            failed_responses = []
            
            for response in responses:
                if isinstance(response, Exception):
                    continue  # Skip exceptions from gather
                elif response.status_code == 200:
                    successful_responses.append(response)
                else:
                    failed_responses.append(response)
            
            # Resilience requirements
            success_rate = len(successful_responses) / len(resilience_tasks)
            assert success_rate >= 0.65, f"Success rate {success_rate:.2%} below 65% during failures"
            assert success_rate <= 0.85, f"Success rate {success_rate:.2%} too high - failures not occurring as expected"
            
            # Failed requests should have proper error responses
            for failed_resp in failed_responses[:3]:  # Check first few failures
                assert failed_resp.status_code == 500
                error_data = failed_resp.json()
                assert "Chat generation failed" in error_data["detail"]
            
            # System should remain healthy despite failures
            health_response = await client.get("/llm/health")
            assert health_response.status_code == 200
            health_data = health_response.json()
            assert health_data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_parameter_variation_performance(self, performance_app):
        """Test performance across different parameter combinations"""
        app, mock_service = performance_app
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test different parameter combinations
            parameter_combinations = [
                {"max_tokens": 50, "temperature": 0.1},    # Fast, deterministic
                {"max_tokens": 256, "temperature": 0.5},   # Medium
                {"max_tokens": 512, "temperature": 0.9},   # Slow, creative
                {"max_tokens": 1024, "temperature": 1.0},  # Max parameters
            ]
            
            performance_results = []
            
            for params in parameter_combinations:
                param_times = []
                
                # Test each parameter set multiple times
                for i in range(5):
                    start_time = time.time()
                    
                    response = await client.post("/llm/chat", json={
                        "message": f"Parameter test with {params['max_tokens']} tokens",
                        **params
                    })
                    
                    end_time = time.time()
                    param_times.append(end_time - start_time)
                    
                    assert response.status_code == 200
                
                # Analyze parameter performance
                avg_time = statistics.mean(param_times)
                performance_results.append({
                    "params": params,
                    "avg_time": avg_time,
                    "times": param_times
                })
            
            # Verify performance characteristics
            for result in performance_results:
                params = result["params"]
                avg_time = result["avg_time"]
                
                # All configurations should meet basic performance requirements
                assert avg_time < 3.0, f"Average time {avg_time:.2f}s too slow for params {params}"
                
                # Consistency check
                std_dev = statistics.stdev(result["times"])
                assert std_dev < 1.0, f"Too much variation {std_dev:.2f}s for params {params}"
            
            # Performance should generally correlate with max_tokens
            # (though this is a mock, so correlation might not be perfect)
            times_by_tokens = [(r["params"]["max_tokens"], r["avg_time"]) for r in performance_results]
            times_by_tokens.sort()
            
            # At minimum, max tokens shouldn't make performance dramatically worse
            min_time = min(t[1] for t in times_by_tokens)
            max_time = max(t[1] for t in times_by_tokens)
            
            assert max_time / min_time < 5.0, f"Performance varies too much: {min_time:.2f}s to {max_time:.2f}s"