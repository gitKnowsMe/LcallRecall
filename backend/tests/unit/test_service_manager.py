import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import tempfile
import os
from typing import Optional, Dict, Any

from app.core.service_manager import ServiceManager, ServiceError, ServiceInitializationError


class TestServiceManager:
    """Test suite for service initialization and dependency management"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for configuration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_config(self, temp_config_dir):
        """Mock configuration"""
        return {
            "database": {
                "auth_db_path": os.path.join(temp_config_dir, "auth.db"),
                "metadata_db_path": os.path.join(temp_config_dir, "metadata.db")
            },
            "model": {
                "path": "/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf",
                "max_context_length": 4096,
                "batch_size": 512
            },
            "vector_store": {
                "workspace_dir": os.path.join(temp_config_dir, "workspaces"),
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            "services": {
                "max_file_size": 100 * 1024 * 1024,
                "chunk_size": 512,
                "chunk_overlap": 50
            }
        }
    
    @pytest.fixture
    def service_manager(self, mock_config):
        """Create ServiceManager instance for testing"""
        return ServiceManager(config=mock_config)

    # Service Manager Initialization Tests
    def test_service_manager_init(self, mock_config):
        """Test ServiceManager initialization"""
        manager = ServiceManager(config=mock_config)
        
        assert manager.config == mock_config
        assert manager._services == {}
        assert manager._initialized == False
        assert manager._startup_order == []

    def test_service_manager_init_no_config(self):
        """Test ServiceManager initialization without config"""
        with pytest.raises(ServiceError, match="Configuration is required"):
            ServiceManager(config=None)

    def test_service_manager_init_invalid_config(self):
        """Test ServiceManager initialization with invalid config"""
        invalid_configs = [
            {},  # Empty config
            {"database": {}},  # Missing required sections
            {"model": {"path": ""}},  # Empty model path
        ]
        
        for invalid_config in invalid_configs:
            with pytest.raises(ServiceError, match="Invalid configuration"):
                ServiceManager(config=invalid_config)

    # Service Registration Tests
    def test_register_service_success(self, service_manager):
        """Test successful service registration"""
        mock_service = Mock()
        mock_service.name = "test_service"
        
        service_manager.register_service("test_service", mock_service)
        
        assert "test_service" in service_manager._services
        assert service_manager._services["test_service"] == mock_service

    def test_register_service_duplicate(self, service_manager):
        """Test registering duplicate service"""
        mock_service1 = Mock()
        mock_service2 = Mock()
        
        service_manager.register_service("test_service", mock_service1)
        
        with pytest.raises(ServiceError, match="Service 'test_service' already registered"):
            service_manager.register_service("test_service", mock_service2)

    def test_register_service_invalid_name(self, service_manager):
        """Test registering service with invalid name"""
        mock_service = Mock()
        
        invalid_names = ["", None, " ", "service with spaces"]
        
        for invalid_name in invalid_names:
            with pytest.raises(ServiceError, match="Invalid service name"):
                service_manager.register_service(invalid_name, mock_service)

    def test_register_service_none_service(self, service_manager):
        """Test registering None as service"""
        with pytest.raises(ServiceError, match="Service cannot be None"):
            service_manager.register_service("test_service", None)

    # Service Retrieval Tests
    def test_get_service_success(self, service_manager):
        """Test successful service retrieval"""
        mock_service = Mock()
        service_manager.register_service("test_service", mock_service)
        
        retrieved = service_manager.get_service("test_service")
        assert retrieved == mock_service

    def test_get_service_not_found(self, service_manager):
        """Test retrieving non-existent service"""
        with pytest.raises(ServiceError, match="Service 'nonexistent' not found"):
            service_manager.get_service("nonexistent")

    def test_get_service_optional_success(self, service_manager):
        """Test optional service retrieval - service exists"""
        mock_service = Mock()
        service_manager.register_service("test_service", mock_service)
        
        retrieved = service_manager.get_service_optional("test_service")
        assert retrieved == mock_service

    def test_get_service_optional_not_found(self, service_manager):
        """Test optional service retrieval - service doesn't exist"""
        retrieved = service_manager.get_service_optional("nonexistent")
        assert retrieved is None

    # Core Service Initialization Tests
    @patch('app.core.service_manager.sqlite3')
    def test_initialize_database_services_success(self, mock_sqlite, service_manager, temp_config_dir):
        """Test successful database service initialization"""
        # Mock database connections
        mock_auth_conn = Mock()
        mock_metadata_conn = Mock()
        mock_sqlite.connect.side_effect = [mock_auth_conn, mock_metadata_conn]
        
        service_manager._initialize_database_services()
        
        # Verify services were registered
        assert "auth_db" in service_manager._services
        assert "metadata_db" in service_manager._services
        
        # Verify database connections were created
        assert mock_sqlite.connect.call_count == 2

    @patch('app.services.llm_service.ModelManager')
    def test_initialize_model_service_success(self, mock_model_manager, service_manager):
        """Test successful model service initialization"""
        mock_instance = Mock()
        mock_model_manager.return_value = mock_instance
        
        service_manager._initialize_model_service()
        
        assert "model_manager" in service_manager._services
        assert service_manager._services["model_manager"] == mock_instance
        
        mock_model_manager.assert_called_once_with(
            model_path="/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf",
            max_context_length=4096,
            batch_size=512
        )

    @patch('app.services.llm_service.ModelManager')
    def test_initialize_model_service_file_not_found(self, mock_model_manager, service_manager):
        """Test model service initialization with missing model file"""
        mock_model_manager.side_effect = FileNotFoundError("Model file not found")
        
        with pytest.raises(ServiceInitializationError, match="Failed to initialize model service"):
            service_manager._initialize_model_service()

    @patch('app.services.vector_service.VectorStoreManager')
    def test_initialize_vector_service_success(self, mock_vector_manager, service_manager, temp_config_dir):
        """Test successful vector service initialization"""
        mock_instance = Mock()
        mock_vector_manager.return_value = mock_instance
        
        service_manager._initialize_vector_service()
        
        assert "vector_manager" in service_manager._services
        assert service_manager._services["vector_manager"] == mock_instance
        
        mock_vector_manager.assert_called_once_with(
            workspace_dir=os.path.join(temp_config_dir, "workspaces"),
            embedding_model="sentence-transformers/all-MiniLM-L6-v2"
        )

    # Application Service Initialization Tests
    def test_initialize_pdf_service(self, service_manager):
        """Test PDF service initialization"""
        with patch('app.services.pdf_service.PDFService') as mock_pdf_service:
            mock_instance = Mock()
            mock_pdf_service.return_value = mock_instance
            
            service_manager._initialize_pdf_service()
            
            assert "pdf_service" in service_manager._services
            mock_pdf_service.assert_called_once_with(
                max_file_size=100 * 1024 * 1024
            )

    def test_initialize_semantic_chunking_service(self, service_manager):
        """Test semantic chunking service initialization"""
        with patch('app.services.semantic_chunking.SemanticChunking') as mock_chunking:
            mock_instance = Mock()
            mock_chunking.return_value = mock_instance
            
            service_manager._initialize_semantic_chunking_service()
            
            assert "semantic_chunking" in service_manager._services
            mock_chunking.assert_called_once_with(
                chunk_size=512,
                chunk_overlap=50
            )

    def test_initialize_document_processor(self, service_manager):
        """Test document processor initialization"""
        # Setup mock dependencies
        mock_pdf_service = Mock()
        mock_chunking_service = Mock()
        mock_vector_manager = Mock()
        mock_db = Mock()
        
        service_manager._services.update({
            "pdf_service": mock_pdf_service,
            "semantic_chunking": mock_chunking_service,
            "vector_manager": mock_vector_manager,
            "metadata_db": mock_db
        })
        
        with patch('app.services.document_processor.DocumentProcessor') as mock_processor:
            mock_instance = Mock()
            mock_processor.return_value = mock_instance
            
            service_manager._initialize_document_processor()
            
            assert "document_processor" in service_manager._services
            mock_processor.assert_called_once_with(
                pdf_service=mock_pdf_service,
                chunking_service=mock_chunking_service,
                vector_service=mock_vector_manager,
                database=mock_db
            )

    def test_initialize_query_service(self, service_manager):
        """Test query service initialization"""
        # Setup mock dependencies
        mock_vector_manager = Mock()
        mock_model_manager = Mock()
        
        service_manager._services.update({
            "vector_manager": mock_vector_manager,
            "model_manager": mock_model_manager
        })
        
        with patch('app.services.query_service.QueryService') as mock_query:
            mock_instance = Mock()
            mock_query.return_value = mock_instance
            
            service_manager._initialize_query_service()
            
            assert "query_service" in service_manager._services
            mock_query.assert_called_once_with(
                vector_service=mock_vector_manager,
                llm_service=mock_model_manager
            )

    def test_initialize_streaming_service(self, service_manager):
        """Test streaming service initialization"""
        # Setup mock dependencies
        mock_query_service = Mock()
        
        service_manager._services.update({
            "query_service": mock_query_service
        })
        
        with patch('app.services.streaming_service.StreamingService') as mock_streaming:
            mock_instance = Mock()
            mock_streaming.return_value = mock_instance
            
            service_manager._initialize_streaming_service()
            
            assert "streaming_service" in service_manager._services
            mock_streaming.assert_called_once_with(
                query_service=mock_query_service
            )

    # Full Initialization Tests
    @pytest.mark.asyncio
    async def test_initialize_all_services_success(self, service_manager, temp_config_dir):
        """Test complete service initialization sequence"""
        with patch.multiple(
            service_manager,
            _initialize_database_services=Mock(),
            _initialize_model_service=Mock(),
            _initialize_vector_service=Mock(),
            _initialize_pdf_service=Mock(),
            _initialize_semantic_chunking_service=Mock(),
            _initialize_document_processor=Mock(),
            _initialize_query_service=Mock(),
            _initialize_streaming_service=Mock()
        ):
            await service_manager.initialize_all_services()
            
            assert service_manager._initialized == True
            
            # Verify initialization order
            service_manager._initialize_database_services.assert_called_once()
            service_manager._initialize_model_service.assert_called_once()
            service_manager._initialize_vector_service.assert_called_once()
            service_manager._initialize_pdf_service.assert_called_once()
            service_manager._initialize_semantic_chunking_service.assert_called_once()
            service_manager._initialize_document_processor.assert_called_once()
            service_manager._initialize_query_service.assert_called_once()
            service_manager._initialize_streaming_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_all_services_already_initialized(self, service_manager):
        """Test initialization when already initialized"""
        service_manager._initialized = True
        
        await service_manager.initialize_all_services()
        
        # Should return without doing anything

    @pytest.mark.asyncio
    async def test_initialize_all_services_failure(self, service_manager):
        """Test initialization failure handling"""
        with patch.object(service_manager, '_initialize_model_service') as mock_init:
            mock_init.side_effect = Exception("Model initialization failed")
            
            with pytest.raises(ServiceInitializationError, match="Service initialization failed"):
                await service_manager.initialize_all_services()
            
            assert service_manager._initialized == False

    # Service Dependencies Tests
    def test_check_dependencies_success(self, service_manager):
        """Test dependency checking with all dependencies available"""
        # Setup required services
        service_manager._services.update({
            "auth_db": Mock(),
            "metadata_db": Mock(),
            "model_manager": Mock(),
            "vector_manager": Mock(),
            "pdf_service": Mock(),
            "semantic_chunking": Mock(),
            "document_processor": Mock(),
            "query_service": Mock(),
            "streaming_service": Mock()
        })
        
        # Should not raise exception
        service_manager._check_service_dependencies()

    def test_check_dependencies_missing_service(self, service_manager):
        """Test dependency checking with missing service"""
        # Setup incomplete services
        service_manager._services.update({
            "auth_db": Mock(),
            "metadata_db": Mock(),
            # Missing model_manager
        })
        
        with pytest.raises(ServiceError, match="Required service 'model_manager' not available"):
            service_manager._check_service_dependencies()

    def test_get_service_dependencies(self, service_manager):
        """Test getting service dependency mapping"""
        dependencies = service_manager._get_service_dependencies()
        
        expected_deps = {
            "document_processor": ["pdf_service", "semantic_chunking", "vector_manager", "metadata_db"],
            "query_service": ["vector_manager", "model_manager"],
            "streaming_service": ["query_service"]
        }
        
        assert dependencies == expected_deps

    # Service Cleanup Tests
    @pytest.mark.asyncio
    async def test_cleanup_services_success(self, service_manager):
        """Test successful service cleanup"""
        # Setup services with cleanup methods
        mock_services = {}
        for name in ["model_manager", "vector_manager", "query_service"]:
            service = Mock()
            service.cleanup = AsyncMock()
            mock_services[name] = service
        
        service_manager._services.update(mock_services)
        service_manager._initialized = True
        
        await service_manager.cleanup_all_services()
        
        # Verify all cleanup methods were called
        for service in mock_services.values():
            service.cleanup.assert_called_once()
        
        assert service_manager._initialized == False

    @pytest.mark.asyncio
    async def test_cleanup_services_with_errors(self, service_manager):
        """Test service cleanup with errors"""
        # Setup services - some with failing cleanup
        mock_service1 = Mock()
        mock_service1.cleanup = AsyncMock()
        
        mock_service2 = Mock()
        mock_service2.cleanup = AsyncMock(side_effect=Exception("Cleanup failed"))
        
        service_manager._services.update({
            "service1": mock_service1,
            "service2": mock_service2
        })
        service_manager._initialized = True
        
        # Should not raise exception, but log errors
        await service_manager.cleanup_all_services()
        
        # Both cleanup methods should have been called
        mock_service1.cleanup.assert_called_once()
        mock_service2.cleanup.assert_called_once()
        
        assert service_manager._initialized == False

    # Service Health Checks
    def test_get_service_health(self, service_manager):
        """Test service health reporting"""
        # Setup services with health check methods
        mock_services = {}
        for name in ["model_manager", "vector_manager"]:
            service = Mock()
            service.is_healthy = Mock(return_value=True)
            mock_services[name] = service
        
        service_manager._services.update(mock_services)
        
        health = service_manager.get_services_health()
        
        assert health["model_manager"] == True
        assert health["vector_manager"] == True

    def test_get_service_health_no_health_method(self, service_manager):
        """Test service health for services without health check"""
        service_manager._services["simple_service"] = Mock()
        
        health = service_manager.get_services_health()
        
        # Should report as healthy if service exists
        assert health["simple_service"] == True

    def test_is_fully_initialized(self, service_manager):
        """Test checking if all services are initialized"""
        # Not initialized yet
        assert service_manager.is_fully_initialized() == False
        
        # Mark as initialized
        service_manager._initialized = True
        assert service_manager.is_fully_initialized() == True

    # Error Recovery Tests
    @pytest.mark.asyncio
    async def test_restart_service_success(self, service_manager):
        """Test restarting individual service"""
        # Setup service
        mock_service = Mock()
        mock_service.cleanup = AsyncMock()
        service_manager._services["test_service"] = mock_service
        
        # Mock re-initialization
        with patch.object(service_manager, '_initialize_model_service') as mock_init:
            await service_manager.restart_service("model_manager")
            
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_nonexistent_service(self, service_manager):
        """Test restarting non-existent service"""
        with pytest.raises(ServiceError, match="Service 'nonexistent' not found"):
            await service_manager.restart_service("nonexistent")

    def test_get_initialization_status(self, service_manager):
        """Test getting detailed initialization status"""
        service_manager._services.update({
            "service1": Mock(),
            "service2": Mock()
        })
        service_manager._initialized = True
        
        status = service_manager.get_initialization_status()
        
        assert status["initialized"] == True
        assert status["service_count"] == 2
        assert "service1" in status["services"]
        assert "service2" in status["services"]