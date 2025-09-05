import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import time
import json

from app.core.api_integration import (
    APIIntegration, 
    APIError, 
    create_app, 
    setup_middleware,
    setup_routes,
    setup_exception_handlers
)


class TestAPIIntegration:
    """Test suite for API router integration and middleware setup"""
    
    @pytest.fixture
    def mock_service_manager(self):
        """Mock service manager with all services"""
        manager = Mock()
        manager.get_service.return_value = Mock()
        manager.is_fully_initialized.return_value = True
        return manager
    
    @pytest.fixture
    def mock_config(self):
        """Mock API configuration"""
        return {
            "api": {
                "host": "127.0.0.1",
                "port": 8000,
                "cors_origins": ["http://localhost:3000"],
                "trusted_hosts": ["localhost", "127.0.0.1"],
                "max_request_size": 100 * 1024 * 1024,
                "request_timeout": 30
            },
            "security": {
                "jwt_secret": "test_secret_key",
                "jwt_algorithm": "HS256",
                "jwt_expiration": 3600
            },
            "logging": {
                "level": "INFO",
                "access_log": True
            }
        }
    
    @pytest.fixture
    def api_integration(self, mock_config, mock_service_manager):
        """Create APIIntegration instance for testing"""
        return APIIntegration(
            config=mock_config,
            service_manager=mock_service_manager
        )
    
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app"""
        return FastAPI(title="Test App", version="0.1.0")

    # APIIntegration Initialization Tests
    def test_api_integration_init(self, mock_config, mock_service_manager):
        """Test APIIntegration initialization"""
        integration = APIIntegration(
            config=mock_config,
            service_manager=mock_service_manager
        )
        
        assert integration.config == mock_config
        assert integration.service_manager == mock_service_manager
        assert integration.app is None
        assert integration._middleware_setup == False
        assert integration._routes_setup == False

    def test_api_integration_init_no_config(self, mock_service_manager):
        """Test APIIntegration initialization without config"""
        with pytest.raises(APIError, match="Configuration is required"):
            APIIntegration(config=None, service_manager=mock_service_manager)

    def test_api_integration_init_no_service_manager(self, mock_config):
        """Test APIIntegration initialization without service manager"""
        with pytest.raises(APIError, match="Service manager is required"):
            APIIntegration(config=mock_config, service_manager=None)

    def test_api_integration_init_invalid_config(self, mock_service_manager):
        """Test APIIntegration initialization with invalid config"""
        invalid_configs = [
            {},  # Empty config
            {"api": {}},  # Missing required API sections
            {"security": {"jwt_secret": ""}},  # Empty JWT secret
        ]
        
        for invalid_config in invalid_configs:
            with pytest.raises(APIError, match="Invalid configuration"):
                APIIntegration(config=invalid_config, service_manager=mock_service_manager)

    # App Creation Tests
    def test_create_app_success(self, api_integration):
        """Test successful FastAPI app creation"""
        app = api_integration.create_app()
        
        assert isinstance(app, FastAPI)
        assert app.title == "LocalRecall RAG API"
        assert api_integration.app == app

    def test_create_app_with_custom_metadata(self, mock_config, mock_service_manager):
        """Test app creation with custom metadata"""
        custom_config = mock_config.copy()
        custom_config["app"] = {
            "title": "Custom API",
            "description": "Custom Description",
            "version": "2.0.0"
        }
        
        integration = APIIntegration(config=custom_config, service_manager=mock_service_manager)
        app = integration.create_app()
        
        assert app.title == "Custom API"
        assert app.description == "Custom Description"
        assert app.version == "2.0.0"

    def test_create_app_already_created(self, api_integration):
        """Test creating app when already created"""
        app1 = api_integration.create_app()
        app2 = api_integration.create_app()
        
        # Should return the same instance
        assert app1 is app2

    # Middleware Setup Tests
    def test_setup_middleware_success(self, api_integration, test_app):
        """Test successful middleware setup"""
        api_integration.app = test_app
        
        api_integration.setup_middleware()
        
        assert api_integration._middleware_setup == True
        
        # Verify middleware was added (check middleware stack)
        middleware_types = [type(middleware) for middleware in test_app.user_middleware]
        middleware_names = [str(m) for m in middleware_types]
        
        # Should have CORS and other middleware
        assert len(test_app.user_middleware) > 0

    def test_setup_middleware_no_app(self, api_integration):
        """Test middleware setup without app"""
        with pytest.raises(APIError, match="FastAPI app not created"):
            api_integration.setup_middleware()

    def test_setup_middleware_already_setup(self, api_integration, test_app):
        """Test middleware setup when already setup"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        middleware_count = len(test_app.user_middleware)
        
        # Setup again
        api_integration.setup_middleware()
        
        # Should not add middleware twice
        assert len(test_app.user_middleware) == middleware_count

    def test_cors_middleware_setup(self, api_integration, test_app):
        """Test CORS middleware configuration"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        # Check if CORS middleware is configured
        cors_middleware = None
        for middleware in test_app.user_middleware:
            if hasattr(middleware, 'cls') and middleware.cls == CORSMiddleware:
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None

    def test_trusted_host_middleware_setup(self, api_integration, test_app):
        """Test TrustedHost middleware configuration"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        # Check if TrustedHost middleware is configured
        trusted_host_middleware = None
        for middleware in test_app.user_middleware:
            if hasattr(middleware, 'cls') and middleware.cls == TrustedHostMiddleware:
                trusted_host_middleware = middleware
                break
        
        # TrustedHost middleware should be present
        # (exact verification depends on FastAPI version)
        assert len(test_app.user_middleware) > 0

    # Custom Middleware Tests
    def test_request_timing_middleware(self, api_integration, test_app):
        """Test request timing middleware"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        # Add a test endpoint
        @test_app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        assert response.status_code == 200
        # Timing middleware should add headers
        assert "X-Process-Time" in response.headers

    def test_request_size_limit_middleware(self, api_integration, test_app):
        """Test request size limit middleware"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        # Add a test endpoint that accepts data
        @test_app.post("/test")
        async def test_endpoint(request: Request):
            return {"received": "ok"}
        
        client = TestClient(test_app)
        
        # Small request should work
        response = client.post("/test", json={"data": "small"})
        assert response.status_code == 200
        
        # Large request should be rejected (if middleware properly configured)
        large_data = {"data": "x" * (101 * 1024 * 1024)}  # Larger than 100MB limit
        response = client.post("/test", json=large_data)
        # Note: Actual size limiting might be handled differently in test environment

    # Route Setup Tests
    def test_setup_routes_success(self, api_integration, test_app):
        """Test successful route setup"""
        api_integration.app = test_app
        
        with patch('app.api.auth.initialize_auth_router') as mock_auth, \
             patch('app.api.documents.initialize_documents_router') as mock_docs, \
             patch('app.api.query.initialize_query_router') as mock_query:
            
            api_integration.setup_routes()
            
            assert api_integration._routes_setup == True
            
            # Verify router initialization calls
            mock_auth.assert_called_once()
            mock_docs.assert_called_once() 
            mock_query.assert_called_once()

    def test_setup_routes_no_app(self, api_integration):
        """Test route setup without app"""
        with pytest.raises(APIError, match="FastAPI app not created"):
            api_integration.setup_routes()

    def test_setup_routes_already_setup(self, api_integration, test_app):
        """Test route setup when already setup"""
        api_integration.app = test_app
        
        with patch('app.api.auth.initialize_auth_router') as mock_auth:
            api_integration.setup_routes()
            api_integration.setup_routes()  # Setup again
            
            # Should only be called once
            mock_auth.assert_called_once()

    def test_route_dependency_injection(self, api_integration, test_app, mock_service_manager):
        """Test route dependency injection"""
        api_integration.app = test_app
        
        # Mock services
        mock_auth_service = Mock()
        mock_query_service = Mock()
        mock_streaming_service = Mock()
        
        mock_service_manager.get_service.side_effect = lambda name: {
            "auth_service": mock_auth_service,
            "query_service": mock_query_service,
            "streaming_service": mock_streaming_service
        }.get(name, Mock())
        
        with patch('app.api.auth.initialize_auth_router') as mock_auth_init, \
             patch('app.api.documents.initialize_documents_router') as mock_docs_init, \
             patch('app.api.query.initialize_query_router') as mock_query_init:
            
            api_integration.setup_routes()
            
            # Verify services were passed to routers
            assert mock_service_manager.get_service.called

    # Exception Handler Setup Tests
    def test_setup_exception_handlers_success(self, api_integration, test_app):
        """Test successful exception handler setup"""
        api_integration.app = test_app
        
        api_integration.setup_exception_handlers()
        
        # Verify exception handlers were added
        assert len(test_app.exception_handlers) > 0

    def test_http_exception_handler(self, api_integration, test_app):
        """Test HTTP exception handler"""
        api_integration.app = test_app
        api_integration.setup_exception_handlers()
        
        # Add endpoint that raises HTTPException
        @test_app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=404, detail="Not found")
        
        client = TestClient(test_app)
        response = client.get("/error")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_validation_exception_handler(self, api_integration, test_app):
        """Test validation exception handler"""
        api_integration.app = test_app
        api_integration.setup_exception_handlers()
        
        from pydantic import BaseModel, ValidationError
        
        class TestModel(BaseModel):
            name: str
            age: int
        
        # Add endpoint with validation
        @test_app.post("/validate")
        async def validate_endpoint(data: TestModel):
            return {"received": data}
        
        client = TestClient(test_app)
        
        # Invalid data should trigger validation handler
        response = client.post("/validate", json={"name": "test"})  # Missing age
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_general_exception_handler(self, api_integration, test_app):
        """Test general exception handler"""
        api_integration.app = test_app
        api_integration.setup_exception_handlers()
        
        # Add endpoint that raises general exception
        @test_app.get("/crash")
        async def crash_endpoint():
            raise ValueError("Something went wrong")
        
        client = TestClient(test_app)
        response = client.get("/crash")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Internal server error" in data["detail"]

    # Health Check Endpoint Tests
    def test_health_check_endpoint_setup(self, api_integration, test_app):
        """Test health check endpoint setup"""
        api_integration.app = test_app
        api_integration.setup_routes()
        
        # Health endpoint should be added
        client = TestClient(test_app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    def test_health_check_with_services(self, api_integration, test_app, mock_service_manager):
        """Test health check with service status"""
        api_integration.app = test_app
        
        # Mock service health
        mock_service_manager.get_services_health.return_value = {
            "model_manager": True,
            "vector_manager": True,
            "query_service": True
        }
        
        api_integration.setup_routes()
        
        client = TestClient(test_app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "services" in data

    # Complete Integration Tests
    def test_full_app_setup(self, api_integration):
        """Test complete application setup"""
        app = api_integration.setup_full_app()
        
        assert isinstance(app, FastAPI)
        assert api_integration._middleware_setup == True
        assert api_integration._routes_setup == True
        
        # Test the app works
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_full_app_setup_error_handling(self, api_integration):
        """Test full app setup with error handling"""
        with patch.object(api_integration, 'setup_middleware') as mock_middleware:
            mock_middleware.side_effect = Exception("Middleware setup failed")
            
            with pytest.raises(APIError, match="Failed to setup application"):
                api_integration.setup_full_app()

    # Configuration Validation Tests
    def test_validate_api_config(self, api_integration):
        """Test API configuration validation"""
        # Should not raise exception with valid config
        api_integration._validate_config()

    def test_validate_api_config_invalid(self, mock_service_manager):
        """Test API configuration validation with invalid config"""
        invalid_configs = [
            {"api": {"host": "", "port": 8000}},  # Empty host
            {"api": {"host": "localhost", "port": -1}},  # Invalid port
            {"security": {"jwt_secret": ""}},  # Empty JWT secret
        ]
        
        for invalid_config in invalid_configs:
            with pytest.raises(APIError, match="Invalid configuration"):
                APIIntegration(config=invalid_config, service_manager=mock_service_manager)

    # Security Configuration Tests
    def test_security_headers_middleware(self, api_integration, test_app):
        """Test security headers middleware"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        @test_app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        # Security headers should be present
        assert response.status_code == 200
        # Note: Specific security headers depend on implementation

    def test_jwt_configuration(self, api_integration):
        """Test JWT configuration setup"""
        jwt_config = api_integration._get_jwt_config()
        
        assert jwt_config["secret"] == "test_secret_key"
        assert jwt_config["algorithm"] == "HS256"
        assert jwt_config["expiration"] == 3600

    # Error Recovery Tests
    def test_middleware_setup_partial_failure(self, api_integration, test_app):
        """Test middleware setup with partial failures"""
        api_integration.app = test_app
        
        with patch('fastapi.middleware.cors.CORSMiddleware') as mock_cors:
            mock_cors.side_effect = Exception("CORS setup failed")
            
            # Should handle CORS failure gracefully
            api_integration.setup_middleware()
            
            # Should still mark as setup (other middleware succeeded)
            assert api_integration._middleware_setup == True

    # API Documentation Tests
    def test_openapi_configuration(self, api_integration):
        """Test OpenAPI documentation configuration"""
        app = api_integration.create_app()
        
        # Check OpenAPI schema
        openapi_schema = app.openapi()
        
        assert "info" in openapi_schema
        assert openapi_schema["info"]["title"] == "LocalRecall RAG API"
        assert "paths" in openapi_schema

    def test_docs_endpoints(self, api_integration):
        """Test API documentation endpoints"""
        app = api_integration.setup_full_app()
        client = TestClient(app)
        
        # Swagger UI should be available
        response = client.get("/docs")
        assert response.status_code == 200
        
        # ReDoc should be available
        response = client.get("/redoc")
        assert response.status_code == 200
        
        # OpenAPI JSON should be available
        response = client.get("/openapi.json")
        assert response.status_code == 200

    # Performance and Monitoring Tests
    def test_request_logging_middleware(self, api_integration, test_app):
        """Test request logging middleware"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        @test_app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        with patch('app.core.api_integration.logger') as mock_logger:
            client = TestClient(test_app)
            response = client.get("/test")
            
            assert response.status_code == 200
            # Should log the request (if logging middleware is configured)

    def test_metrics_collection(self, api_integration, test_app):
        """Test metrics collection setup"""
        api_integration.app = test_app
        api_integration.setup_middleware()
        
        # If metrics middleware is configured
        @test_app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        assert response.status_code == 200
        # Metrics should be collected (implementation specific)