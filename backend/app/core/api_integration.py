import asyncio
import logging
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import json

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API integration error"""
    pass


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request timing"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"{request.method} {request.url.path} - {request.client.host if request.client else 'unknown'}")
        
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response


class APIIntegration:
    """Manages FastAPI application integration and setup"""
    
    def __init__(self, config: Dict[str, Any], service_manager):
        """
        Initialize API integration
        
        Args:
            config: Application configuration
            service_manager: Service manager instance
        """
        if not config:
            raise APIError("Configuration is required")
        
        if not service_manager:
            raise APIError("Service manager is required")
        
        self._validate_config(config)
        
        self.config = config
        self.service_manager = service_manager
        self.app: Optional[FastAPI] = None
        self._middleware_setup = False
        self._routes_setup = False
        
        logger.info("APIIntegration initialized")
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration"""
        # Check for required sections
        if "api" not in config:
            raise APIError("Invalid configuration: missing 'api' section")
        
        if "security" not in config:
            raise APIError("Invalid configuration: missing 'security' section")
        
        api_config = config["api"]
        security_config = config["security"]
        
        # Validate API config
        if not api_config.get("host"):
            raise APIError("Invalid configuration: API host is required")
        
        if not isinstance(api_config.get("port"), int) or api_config["port"] <= 0:
            raise APIError("Invalid configuration: valid API port is required")
        
        # Validate security config
        if not security_config.get("jwt_secret"):
            raise APIError("Invalid configuration: JWT secret is required")
    
    def create_app(self) -> FastAPI:
        """Create FastAPI application"""
        if self.app is not None:
            return self.app
        
        # Get app metadata
        app_config = self.config.get("app", {})
        app_name = app_config.get("name", "LocalRecall RAG API")
        app_description = app_config.get("description", "Local RAG application with document processing and query capabilities")
        app_version = app_config.get("version", "1.0.0")
        
        # Create FastAPI app
        self.app = FastAPI(
            title=app_name,
            description=app_description,
            version=app_version,
            openapi_url="/openapi.json",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        logger.info(f"Created FastAPI app: {app_name} v{app_version}")
        return self.app
    
    def setup_middleware(self) -> None:
        """Setup middleware stack"""
        if not self.app:
            raise APIError("FastAPI app not created. Call create_app() first.")
        
        if self._middleware_setup:
            logger.debug("Middleware already setup")
            return
        
        api_config = self.config["api"]
        
        # Security headers middleware
        self.app.add_middleware(SecurityHeadersMiddleware)
        
        # Request timing middleware
        self.app.add_middleware(RequestTimingMiddleware)
        
        # Request logging middleware (if enabled)
        log_config = self.config.get("logging", {})
        if log_config.get("access_log", True):
            self.app.add_middleware(RequestLoggingMiddleware)
        
        # CORS middleware
        cors_origins = api_config.get("cors_origins", ["http://localhost:3000"])
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins for development
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
            allow_headers=["*"],
            expose_headers=["*"]
        )
        
        # Trusted host middleware
        trusted_hosts = api_config.get("trusted_hosts", ["localhost", "127.0.0.1"])
        if trusted_hosts:
            self.app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=trusted_hosts
            )
        
        self._middleware_setup = True
        logger.info("Middleware setup completed")
    
    def setup_exception_handlers(self) -> None:
        """Setup exception handlers"""
        if not self.app:
            raise APIError("FastAPI app not created. Call create_app() first.")
        
        @self.app.exception_handler(StarletteHTTPException)
        async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
            logger.warning(f"HTTP {exc.status_code} error: {exc.detail} - {request.url}")
            return await http_exception_handler(request, exc)
        
        @self.app.exception_handler(RequestValidationError)
        async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
            logger.warning(f"Validation error: {exc} - {request.url}")
            return await request_validation_exception_handler(request, exc)
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            logger.error(f"Unhandled exception: {exc} - {request.url}", exc_info=True)
            return HTTPException(
                status_code=500,
                detail="Internal server error"
            )
        
        logger.info("Exception handlers setup completed")
    
    def setup_routes(self) -> None:
        """Setup API routes"""
        if not self.app:
            raise APIError("FastAPI app not created. Call create_app() first.")
        
        if self._routes_setup:
            logger.debug("Routes already setup")
            return
        
        # Health check endpoint
        @self.app.get("/health")
        async def health_check():
            """Application health check"""
            try:
                services_health = self.service_manager.get_services_health()
                initialization_status = self.service_manager.get_initialization_status()
                
                return {
                    "status": "healthy" if all(services_health.values()) else "unhealthy",
                    "timestamp": int(time.time()),
                    "services": services_health,
                    "initialization": initialization_status
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {
                    "status": "unhealthy",
                    "timestamp": int(time.time()),
                    "error": str(e)
                }
        
        # Initialize API routers with services
        self._initialize_api_routers()
        
        # Include routers
        from app.api import auth, documents, query
        
        self.app.include_router(auth.router, prefix="/auth", tags=["authentication"])
        self.app.include_router(documents.router, prefix="/documents", tags=["documents"])
        self.app.include_router(query.router, prefix="/query", tags=["query"])
        
        self._routes_setup = True
        logger.info("Routes setup completed")
    
    def _initialize_api_routers(self) -> None:
        """Initialize API routers with service dependencies"""
        try:
            # Get services
            auth_service = self.service_manager.get_service_optional("auth_service")
            document_processor = self.service_manager.get_service_optional("document_processor")
            query_service = self.service_manager.get_service_optional("query_service")
            streaming_service = self.service_manager.get_service_optional("streaming_service")
            
            # Initialize routers (if they have initialization functions)
            from app.api import auth, documents, query
            
            # Pass services to routers if they have initialization functions
            if hasattr(auth, 'initialize_auth_router'):
                auth.initialize_auth_router(auth_service)
            
            if hasattr(documents, 'initialize_documents_router'):
                documents.initialize_documents_router(document_processor)
            
            if hasattr(query, 'initialize_query_router'):
                query.initialize_query_router(query_service, streaming_service)
            
            logger.info("API routers initialized with service dependencies")
            
        except Exception as e:
            logger.error(f"Failed to initialize API routers: {e}")
            # Don't raise exception - routers might work without specific service injection
    
    def _get_jwt_config(self) -> Dict[str, Any]:
        """Get JWT configuration"""
        security_config = self.config["security"]
        
        return {
            "secret": security_config["jwt_secret"],
            "algorithm": security_config.get("jwt_algorithm", "HS256"),
            "expiration": security_config.get("jwt_expiration", 3600)
        }
    
    def setup_full_app(self) -> FastAPI:
        """Setup complete FastAPI application"""
        try:
            logger.info("Setting up complete FastAPI application...")
            
            # Create app
            app = self.create_app()
            
            # Setup middleware
            self.setup_middleware()
            
            # Setup exception handlers
            self.setup_exception_handlers()
            
            # Setup routes
            self.setup_routes()
            
            logger.info("FastAPI application setup completed successfully")
            return app
            
        except Exception as e:
            logger.error(f"Failed to setup application: {e}")
            raise APIError(f"Failed to setup application: {str(e)}")


def create_app(config: Dict[str, Any], service_manager) -> FastAPI:
    """
    Create and configure FastAPI application
    
    Args:
        config: Application configuration
        service_manager: Service manager instance
        
    Returns:
        Configured FastAPI application
    """
    api_integration = APIIntegration(config=config, service_manager=service_manager)
    return api_integration.setup_full_app()


# Global API integration instance
api_integration: Optional[APIIntegration] = None


def initialize_api_integration(config: Dict[str, Any], service_manager) -> APIIntegration:
    """Initialize global API integration instance"""
    global api_integration
    api_integration = APIIntegration(config=config, service_manager=service_manager)
    return api_integration


def get_api_integration() -> Optional[APIIntegration]:
    """Get global API integration instance"""
    return api_integration