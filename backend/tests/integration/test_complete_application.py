import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import tempfile
import os
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.service_manager import ServiceManager
from app.core.app_lifespan import AppLifespan
from app.core.api_integration import APIIntegration
from app.core.database_manager import DatabaseManager
from app.core.config_manager import ConfigManager
from app.main import create_application


class TestCompleteApplicationWorkflow:
    """Integration tests for complete application workflow"""
    
    @pytest.fixture
    def temp_app_dir(self):
        """Create temporary directory for application data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def test_config(self, temp_app_dir):
        """Complete test configuration"""
        return {
            "app": {
                "name": "LocalRecall RAG API",
                "version": "1.0.0",
                "environment": "test"
            },
            "database": {
                "auth_db_path": os.path.join(temp_app_dir, "auth.db"),
                "metadata_db_path": os.path.join(temp_app_dir, "metadata.db"),
                "connection_timeout": 30,
                "max_connections": 5
            },
            "model": {
                "path": "/mock/model/path/phi-2-instruct-Q4_K_M.gguf",
                "max_context_length": 2048,  # Smaller for testing
                "batch_size": 256,
                "preload": False  # Don't preload in tests
            },
            "vector_store": {
                "workspace_dir": os.path.join(temp_app_dir, "workspaces"),
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            "api": {
                "host": "127.0.0.1",
                "port": 8000,
                "cors_origins": ["http://localhost:3000"],
                "trusted_hosts": ["localhost", "127.0.0.1"],
                "max_request_size": 10 * 1024 * 1024  # 10MB for testing
            },
            "security": {
                "jwt_secret": "test-secret-key-for-testing-only",
                "jwt_algorithm": "HS256",
                "jwt_expiration": 3600
            },
            "services": {
                "max_file_size": 10 * 1024 * 1024,  # 10MB for testing
                "chunk_size": 256,
                "chunk_overlap": 25
            },
            "logging": {
                "level": "INFO",
                "file": os.path.join(temp_app_dir, "app.log")
            }
        }

    # Complete Application Initialization Tests
    @pytest.mark.asyncio
    async def test_complete_application_startup(self, test_config):
        """Test complete application startup sequence"""
        with patch('app.services.llm_service.ModelManager') as mock_model, \
             patch('app.services.vector_service.VectorStoreManager') as mock_vector, \
             patch('sqlite3.connect') as mock_sqlite:
            
            # Mock successful service initialization
            mock_model.return_value = Mock()
            mock_vector.return_value = Mock()
            mock_sqlite.return_value = Mock()
            
            # Create application components
            config_manager = ConfigManager()
            config_manager.load_from_dict(test_config)
            
            database_manager = DatabaseManager(config=test_config)
            service_manager = ServiceManager(config=test_config)
            app_lifespan = AppLifespan(config=test_config, service_manager=service_manager)
            api_integration = APIIntegration(config=test_config, service_manager=service_manager)
            
            # Test startup sequence
            await database_manager.initialize_all_databases()
            await service_manager.initialize_all_services()
            
            app = api_integration.setup_full_app()
            
            # Verify application is ready
            assert app is not None
            assert service_manager.is_fully_initialized() == True
            assert api_integration._middleware_setup == True
            assert api_integration._routes_setup == True

    @pytest.mark.asyncio
    async def test_application_lifespan_context(self, test_config):
        """Test application lifespan as context manager"""
        with patch('app.services.llm_service.ModelManager') as mock_model, \
             patch('app.services.vector_service.VectorStoreManager') as mock_vector, \
             patch('sqlite3.connect') as mock_sqlite:
            
            # Mock services
            mock_model.return_value = Mock()
            mock_vector.return_value = Mock()
            mock_sqlite.return_value = Mock()
            
            service_manager = ServiceManager(config=test_config)
            app_lifespan = AppLifespan(config=test_config, service_manager=service_manager)
            
            startup_completed = False
            shutdown_completed = False
            
            async def test_startup():
                nonlocal startup_completed
                await service_manager.initialize_all_services()
                startup_completed = True
            
            async def test_shutdown():
                nonlocal shutdown_completed
                await service_manager.cleanup_all_services()
                shutdown_completed = True
            
            app_lifespan.register_startup_task("test_startup", test_startup)
            app_lifespan.register_shutdown_task("test_shutdown", test_shutdown)
            
            # Test lifespan context
            async with app_lifespan:
                assert startup_completed == True
                assert app_lifespan.is_healthy() == True
            
            assert shutdown_completed == True

    # End-to-End API Testing
    @pytest.mark.asyncio 
    async def test_end_to_end_api_workflow(self, test_config):
        """Test complete API workflow from startup to shutdown"""
        with patch('app.services.llm_service.ModelManager') as mock_model, \
             patch('app.services.vector_service.VectorStoreManager') as mock_vector, \
             patch('sqlite3.connect') as mock_sqlite:
            
            # Setup mocks
            mock_model_instance = Mock()
            mock_vector_instance = Mock()
            mock_sqlite_conn = Mock()
            
            mock_model.return_value = mock_model_instance
            mock_vector.return_value = mock_vector_instance
            mock_sqlite.return_value = mock_sqlite_conn
            
            # Create complete application
            app = await create_application(test_config)
            
            # Test API endpoints
            client = TestClient(app)
            
            # Test health check
            response = client.get("/health")
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["status"] == "healthy"

    def test_api_middleware_integration(self, test_config):
        """Test API middleware integration"""
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect'):
            
            service_manager = ServiceManager(config=test_config)
            api_integration = APIIntegration(config=test_config, service_manager=service_manager)
            
            app = api_integration.setup_full_app()
            client = TestClient(app)
            
            # Test CORS headers
            response = client.options("/health", headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            })
            
            assert response.status_code in [200, 204]
            
            # Test request timing
            response = client.get("/health")
            assert "X-Process-Time" in response.headers

    # Database Integration Tests
    @pytest.mark.asyncio
    async def test_database_integration_workflow(self, test_config, temp_app_dir):
        """Test database integration workflow"""
        database_manager = DatabaseManager(config=test_config)
        
        with patch('sqlite3.connect') as mock_connect:
            mock_auth_conn = Mock()
            mock_metadata_conn = Mock()
            mock_connect.side_effect = [mock_auth_conn, mock_metadata_conn]
            
            # Initialize databases
            await database_manager.initialize_all_databases()
            
            # Verify connections were created
            assert "auth_db" in database_manager._connections
            assert "metadata_db" in database_manager._connections
            
            # Test health check
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            mock_auth_conn.execute.return_value = mock_cursor
            mock_metadata_conn.execute.return_value = mock_cursor
            
            health = database_manager.check_database_health()
            assert health["overall"] == True

    # Service Dependency Resolution Tests
    @pytest.mark.asyncio
    async def test_service_dependency_resolution(self, test_config):
        """Test service dependency resolution and initialization order"""
        with patch('app.services.llm_service.ModelManager') as mock_model, \
             patch('app.services.vector_service.VectorStoreManager') as mock_vector, \
             patch('sqlite3.connect') as mock_sqlite, \
             patch('app.services.pdf_service.PDFService') as mock_pdf, \
             patch('app.services.semantic_chunking.SemanticChunking') as mock_chunking:
            
            # Setup mocks
            mock_instances = {}
            for name, mock_class in [
                ("model", mock_model), ("vector", mock_vector), 
                ("pdf", mock_pdf), ("chunking", mock_chunking)
            ]:
                instance = Mock()
                mock_class.return_value = instance
                mock_instances[name] = instance
            
            mock_sqlite.return_value = Mock()
            
            service_manager = ServiceManager(config=test_config)
            
            # Initialize all services
            await service_manager.initialize_all_services()
            
            # Verify dependency chain
            assert "model_manager" in service_manager._services
            assert "vector_manager" in service_manager._services
            assert "pdf_service" in service_manager._services
            assert "semantic_chunking" in service_manager._services
            assert "document_processor" in service_manager._services
            assert "query_service" in service_manager._services
            assert "streaming_service" in service_manager._services

    # Error Handling and Recovery Tests
    @pytest.mark.asyncio
    async def test_application_startup_error_recovery(self, test_config):
        """Test application startup error handling and recovery"""
        service_manager = ServiceManager(config=test_config)
        
        with patch('app.services.llm_service.ModelManager') as mock_model:
            # First attempt fails
            mock_model.side_effect = [Exception("Model loading failed"), Mock()]
            
            # First initialization should fail
            with pytest.raises(Exception):
                await service_manager.initialize_all_services()
            
            # Second attempt should succeed
            await service_manager.initialize_all_services()
            
            assert service_manager.is_fully_initialized() == True

    @pytest.mark.asyncio
    async def test_application_graceful_shutdown(self, test_config):
        """Test application graceful shutdown"""
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect'):
            
            service_manager = ServiceManager(config=test_config)
            database_manager = DatabaseManager(config=test_config)
            app_lifespan = AppLifespan(config=test_config, service_manager=service_manager)
            
            # Initialize
            await database_manager.initialize_all_databases()
            await service_manager.initialize_all_services()
            
            # Shutdown
            await app_lifespan.shutdown()
            await service_manager.cleanup_all_services()
            await database_manager.cleanup_all_databases()
            
            assert service_manager.is_fully_initialized() == False
            assert database_manager._initialized == False

    # Configuration Integration Tests
    def test_configuration_integration(self, test_config, temp_app_dir):
        """Test configuration integration across components"""
        config_manager = ConfigManager()
        config_manager.load_from_dict(test_config)
        
        # Test configuration access
        assert config_manager.get("database.auth_db_path").endswith("auth.db")
        assert config_manager.get("model.max_context_length") == 2048
        assert config_manager.get("api.port") == 8000
        
        # Test environment-specific overrides
        with patch.dict(os.environ, {"API_PORT": "9000"}):
            test_config_with_env = test_config.copy()
            test_config_with_env["api"]["port"] = "${API_PORT:8000}"
            
            config_manager.load_from_dict(test_config_with_env)
            config_manager.resolve_environment_variables()
            
            assert config_manager.get("api.port") == "9000"

    # Performance and Load Testing
    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self, test_config):
        """Test concurrent service operations"""
        with patch('app.services.llm_service.ModelManager') as mock_model, \
             patch('app.services.vector_service.VectorStoreManager') as mock_vector, \
             patch('sqlite3.connect'):
            
            # Setup async-capable mocks
            mock_model_instance = Mock()
            mock_vector_instance = Mock()
            mock_model.return_value = mock_model_instance
            mock_vector.return_value = mock_vector_instance
            
            service_manager = ServiceManager(config=test_config)
            await service_manager.initialize_all_services()
            
            # Simulate concurrent operations
            tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    service_manager.get_services_health()  # Non-blocking operation
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All operations should succeed
            for result in results:
                assert not isinstance(result, Exception)

    def test_memory_usage_monitoring(self, test_config):
        """Test memory usage monitoring during application lifecycle"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect'):
            
            service_manager = ServiceManager(config=test_config)
            
            # Memory should not increase dramatically during initialization
            # (since we're mocking the heavy components)
            peak_memory = process.memory_info().rss
            memory_increase = peak_memory - initial_memory
            
            # Should be reasonable increase (less than 100MB for mocked components)
            assert memory_increase < 100 * 1024 * 1024

    # Security Integration Tests
    def test_security_configuration_integration(self, test_config):
        """Test security configuration integration"""
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect'):
            
            service_manager = ServiceManager(config=test_config)
            api_integration = APIIntegration(config=test_config, service_manager=service_manager)
            
            app = api_integration.setup_full_app()
            client = TestClient(app)
            
            # Test JWT configuration
            jwt_config = api_integration._get_jwt_config()
            assert jwt_config["secret"] == "test-secret-key-for-testing-only"
            assert jwt_config["algorithm"] == "HS256"
            
            # Test CORS configuration
            response = client.get("/health", headers={
                "Origin": "http://localhost:3000"
            })
            assert response.status_code == 200

    # Monitoring and Observability Tests
    def test_application_monitoring_setup(self, test_config):
        """Test application monitoring and observability setup"""
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect'):
            
            service_manager = ServiceManager(config=test_config)
            api_integration = APIIntegration(config=test_config, service_manager=service_manager)
            
            app = api_integration.setup_full_app()
            client = TestClient(app)
            
            # Test health endpoint with detailed status
            response = client.get("/health")
            assert response.status_code == 200
            
            health_data = response.json()
            assert "timestamp" in health_data
            assert "components" in health_data

    # Integration with External Dependencies Tests
    @pytest.mark.asyncio
    async def test_external_dependency_integration(self, test_config):
        """Test integration with external dependencies"""
        # Test with actual file system operations (limited scope)
        temp_workspace_dir = test_config["vector_store"]["workspace_dir"]
        
        # Ensure workspace directory exists
        os.makedirs(temp_workspace_dir, exist_ok=True)
        
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager') as mock_vector:
            
            # Mock vector service that uses file system
            mock_vector_instance = Mock()
            mock_vector_instance.workspace_exists = Mock(return_value=True)
            mock_vector.return_value = mock_vector_instance
            
            service_manager = ServiceManager(config=test_config)
            await service_manager.initialize_all_services()
            
            # Test workspace directory creation
            assert os.path.exists(temp_workspace_dir)

    # Complete Workflow Integration Tests
    @pytest.mark.asyncio
    async def test_complete_document_processing_workflow(self, test_config):
        """Test complete document processing workflow integration"""
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('app.services.pdf_service.PDFService'), \
             patch('app.services.semantic_chunking.SemanticChunking'), \
             patch('sqlite3.connect'):
            
            service_manager = ServiceManager(config=test_config)
            await service_manager.initialize_all_services()
            
            # Get document processor
            document_processor = service_manager.get_service("document_processor")
            assert document_processor is not None

    @pytest.mark.asyncio
    async def test_complete_query_processing_workflow(self, test_config):
        """Test complete query processing workflow integration"""
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect'):
            
            service_manager = ServiceManager(config=test_config)
            await service_manager.initialize_all_services()
            
            # Get query services
            query_service = service_manager.get_service("query_service")
            streaming_service = service_manager.get_service("streaming_service")
            
            assert query_service is not None
            assert streaming_service is not None

    # Application State Management Tests
    def test_application_state_consistency(self, test_config):
        """Test application state consistency across restarts"""
        state_file = os.path.join(test_config["database"]["auth_db_path"], "../app_state.json")
        
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect'):
            
            # First application instance
            service_manager1 = ServiceManager(config=test_config)
            
            # Second application instance (restart simulation)
            service_manager2 = ServiceManager(config=test_config)
            
            # Both should have same configuration
            assert service_manager1.config == service_manager2.config

    # Cleanup and Resource Management Tests
    @pytest.mark.asyncio
    async def test_complete_resource_cleanup(self, test_config):
        """Test complete resource cleanup"""
        with patch('app.services.llm_service.ModelManager'), \
             patch('app.services.vector_service.VectorStoreManager'), \
             patch('sqlite3.connect') as mock_sqlite:
            
            mock_connections = []
            def mock_connect(*args, **kwargs):
                conn = Mock()
                mock_connections.append(conn)
                return conn
            
            mock_sqlite.side_effect = mock_connect
            
            database_manager = DatabaseManager(config=test_config)
            service_manager = ServiceManager(config=test_config)
            
            # Initialize
            await database_manager.initialize_all_databases()
            await service_manager.initialize_all_services()
            
            # Cleanup
            await service_manager.cleanup_all_services()
            await database_manager.cleanup_all_databases()
            
            # Verify all connections were closed
            for conn in mock_connections:
                conn.close.assert_called_once()