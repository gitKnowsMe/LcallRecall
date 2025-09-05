import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Core components
from app.core.config_manager import ConfigManager, initialize_config_manager
from app.core.database_manager import DatabaseManager, initialize_database_manager
from app.core.service_manager import ServiceManager, initialize_service_manager
from app.core.app_lifespan import AppLifespan, initialize_app_lifespan
from app.core.api_integration import APIIntegration, initialize_api_integration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global application components
config_manager: ConfigManager = None
database_manager: DatabaseManager = None
service_manager: ServiceManager = None
app_lifespan: AppLifespan = None
api_integration: APIIntegration = None


def load_default_config() -> Dict[str, Any]:
    """Load default configuration for LocalRecall"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    
    return {
        "app": {
            "name": "LocalRecall RAG API",
            "version": "1.0.0",
            "description": "Private local RAG application with Phi-2 and FAISS",
            "environment": os.getenv("ENVIRONMENT", "development")
        },
        "database": {
            "auth_db_path": os.path.join(data_dir, "auth.db"),
            "metadata_db_path": os.path.join(data_dir, "metadata.db"),
            "connection_timeout": 30,
            "max_connections": 10,
            "enable_wal": True,
            "create_tables": True
        },
        "model": {
            "path": "/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf",
            "max_context_length": 4096,
            "batch_size": 512,
            "preload": False  # Set to True for production
        },
        "vector_store": {
            "workspace_dir": os.path.join(data_dir, "workspaces"),
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        },
        "api": {
            "host": "127.0.0.1",
            "port": 8000,
            "cors_origins": ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "*"],
            "trusted_hosts": ["localhost", "127.0.0.1", "0.0.0.0"],
            "max_request_size": 100 * 1024 * 1024  # 100MB
        },
        "security": {
            "jwt_secret": os.getenv("JWT_SECRET", "your-secret-key-change-in-production"),
            "jwt_algorithm": "HS256",
            "jwt_expiration": 3600  # 1 hour
        },
        "services": {
            "max_file_size": 100 * 1024 * 1024,  # 100MB
            "chunk_size": 512,
            "chunk_overlap": 50
        },
        "logging": {
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "file": os.path.join(data_dir, "app.log"),
            "max_size": "10MB",
            "backup_count": 5,
            "access_log": True
        },
        "migrations": {
            "auto_migrate": True,
            "migration_dir": "migrations",
            "create_tables": True
        }
    }


async def initialize_application_components(config: Dict[str, Any]) -> None:
    """Initialize all application components"""
    global config_manager, database_manager, service_manager, app_lifespan, api_integration
    
    logger.info("🚀 Starting LocalRecall RAG Application")
    
    # Initialize configuration manager
    config_manager = initialize_config_manager()
    config_manager.load_from_dict(config)
    config_manager.resolve_environment_variables()
    config_manager.validate_configuration()
    logger.info("✅ Configuration loaded and validated")
    
    # Initialize database manager
    database_manager = initialize_database_manager(config)
    await database_manager.initialize_all_databases()
    logger.info("✅ Databases initialized")
    
    # Initialize service manager
    service_manager = initialize_service_manager(config)
    await service_manager.initialize_all_services()
    logger.info("✅ All services initialized")
    
    # Initialize application lifespan
    app_lifespan = initialize_app_lifespan(config, service_manager)
    
    # Initialize API integration
    api_integration = initialize_api_integration(config, service_manager)
    logger.info("✅ API integration ready")


async def cleanup_application_components() -> None:
    """Cleanup all application components"""
    global config_manager, database_manager, service_manager, app_lifespan, api_integration
    
    logger.info("🛑 Shutting down LocalRecall")
    
    try:
        if app_lifespan:
            await app_lifespan.shutdown()
        
        if service_manager:
            await service_manager.cleanup_all_services()
        
        if database_manager:
            await database_manager.cleanup_all_databases()
        
        logger.info("✅ Application components cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    try:
        # Load configuration
        config = load_default_config()
        
        # Load configuration file if specified
        config_file = os.getenv("CONFIG_FILE")
        if config_file and os.path.exists(config_file):
            temp_config_manager = ConfigManager()
            temp_config_manager.load_from_file(config_file)
            file_config = temp_config_manager.export_to_dict()
            
            # Merge with default config
            temp_config_manager.load_from_dict(config)
            temp_config_manager.merge_configuration(file_config)
            config = temp_config_manager.export_to_dict()
        
        # Initialize all components
        await initialize_application_components(config)
        
        # Setup API routes after initialization
        if api_integration:
            # Include routers with proper service injection
            from app.api import auth, documents, query
            
            app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
            app.include_router(documents.router, prefix="/documents", tags=["Documents"])
            app.include_router(query.router, prefix="/query", tags=["Query"])
            
            # Initialize query router with services
            if hasattr(query, 'initialize_query_router') and service_manager:
                query_service = service_manager.get_service("query_service")
                streaming_service = service_manager.get_service("streaming_service")
                query.initialize_query_router(query_service, streaming_service)
        
        logger.info("🎉 LocalRecall RAG API startup completed")
        
        yield
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    finally:
        # Cleanup
        await cleanup_application_components()


# Create FastAPI application - will be properly configured by api_integration
app = FastAPI(
    title="LocalRecall RAG API",
    description="Private local RAG application with Phi-2 and FAISS",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for frontend compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# Health check endpoint (enhanced)
@app.get("/status")
async def get_status():
    """Enhanced health check endpoint for UI monitoring"""
    try:
        if service_manager:
            services_health = service_manager.get_services_health()
            initialization_status = service_manager.get_initialization_status()
            
            return {
                "status": "healthy" if all(services_health.values()) else "degraded",
                "version": "1.0.0",
                "services": services_health,
                "initialization": initialization_status,
                "model_loaded": services_health.get("model_manager", False)
            }
        else:
            return {
                "status": "starting",
                "version": "1.0.0",
                "message": "Application is initializing"
            }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


# Health check endpoint for frontend compatibility
@app.get("/api/health-check")
async def api_health_check():
    """Health check endpoint for frontend compatibility"""
    return await get_status()

@app.options("/api/health-check")
async def api_health_check_options():
    """CORS preflight for health check"""
    return {"message": "OK"}

@app.get("/api/backend-status")
async def api_backend_status():
    """Backend status endpoint for Electron frontend"""
    return {"status": "running", "ready": True}

@app.options("/api/backend-status")
async def api_backend_status_options():
    """CORS preflight for backend status"""
    return {"message": "OK"}


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "LocalRecall RAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "/status",
        "health": "/health"
    }


# Serve static files (HTML UI) if available
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="static")
    
    @app.get("/ui", response_class=HTMLResponse)
    async def serve_ui():
        """Serve main UI"""
        try:
            with open(os.path.join(static_dir, "index.html"), "r") as f:
                return f.read()
        except FileNotFoundError:
            return "<h1>LocalRecall RAG</h1><p>Static UI not found</p><p><a href='/docs'>API Documentation</a></p>"


async def create_application(config: Dict[str, Any] = None) -> FastAPI:
    """
    Create FastAPI application with all components initialized (for testing)
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured FastAPI application
    """
    if config is None:
        config = load_default_config()
    
    # Initialize components
    await initialize_application_components(config)
    
    # Create FastAPI app with integrated services
    if api_integration:
        return api_integration.setup_full_app()
    else:
        return app


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration
    config = load_default_config()
    api_config = config["api"]
    
    logger.info("Starting LocalRecall RAG API server...")
    logger.info(f"Environment: {config['app']['environment']}")
    logger.info(f"Host: {api_config['host']}")
    logger.info(f"Port: {api_config['port']}")
    logger.info(f"Model: {config['model']['path']}")
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=api_config["host"],
        port=api_config["port"],
        reload=config["app"]["environment"] == "development",
        log_level=config["logging"]["level"].lower(),
        access_log=config["logging"]["access_log"]
    )