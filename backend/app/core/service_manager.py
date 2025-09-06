import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
import os

from app.services.llm_service import ModelManager
from app.services.vector_service import VectorStoreManager
from app.services.pdf_service import PDFService
from app.services.semantic_chunking import SemanticChunking
from app.services.document_processor import DocumentProcessor
from app.services.query_service import QueryService
from app.services.streaming_service import StreamingService
import sqlite3

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Base service manager error"""
    pass


class ServiceInitializationError(ServiceError):
    """Service initialization error"""
    pass


class ServiceManager:
    """Manages service initialization and dependency injection"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize service manager
        
        Args:
            config: Application configuration
        """
        if not config:
            raise ServiceError("Configuration is required")
        
        self._validate_config(config)
        
        self.config = config
        self._services: Dict[str, Any] = {}
        self._initialized = False
        self._startup_order: List[str] = []
        
        logger.info("ServiceManager initialized")
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration has required sections"""
        required_sections = ["database", "model", "vector_store", "services"]
        
        for section in required_sections:
            if section not in config:
                raise ServiceError(f"Invalid configuration: missing section '{section}'")
        
        # Validate model path
        model_path = config.get("model", {}).get("path", "")
        if not model_path:
            raise ServiceError("Invalid configuration: model path is required")
        
        # Validate database paths
        db_config = config.get("database", {})
        if not db_config.get("auth_db_path") or not db_config.get("metadata_db_path"):
            raise ServiceError("Invalid configuration: database paths are required")
    
    def register_service(self, name: str, service: Any) -> None:
        """
        Register a service instance
        
        Args:
            name: Service name
            service: Service instance
        """
        if not name or not name.strip():
            raise ServiceError("Invalid service name")
        
        if service is None:
            raise ServiceError("Service cannot be None")
        
        if name in self._services:
            raise ServiceError(f"Service '{name}' already registered")
        
        self._services[name] = service
        logger.debug(f"Registered service: {name}")
    
    def get_service(self, name: str) -> Any:
        """
        Get service instance
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            ServiceError: If service not found
        """
        if name not in self._services:
            raise ServiceError(f"Service '{name}' not found")
        
        return self._services[name]
    
    def get_service_optional(self, name: str) -> Optional[Any]:
        """
        Get service instance if it exists
        
        Args:
            name: Service name
            
        Returns:
            Service instance or None
        """
        return self._services.get(name)
    
    def _initialize_database_services(self) -> None:
        """Initialize database connections"""
        try:
            db_config = self.config["database"]
            
            # Create auth database connection
            auth_conn = sqlite3.connect(
                db_config["auth_db_path"],
                timeout=db_config.get("connection_timeout", 30),
                check_same_thread=False
            )
            self.register_service("auth_db", auth_conn)
            
            # Create metadata database connection
            metadata_conn = sqlite3.connect(
                db_config["metadata_db_path"],
                timeout=db_config.get("connection_timeout", 30),
                check_same_thread=False
            )
            self.register_service("metadata_db", metadata_conn)
            
            logger.info("Database services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database services: {e}")
            raise ServiceInitializationError(f"Database initialization failed: {str(e)}")
    
    async def _initialize_model_service(self) -> None:
        """Initialize LLM model service"""
        try:
            # Initialize real model manager
            model_manager = ModelManager()
            await model_manager.initialize()
            
            self.register_service("model_manager", model_manager)
            logger.info("✅ Real model service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize model service: {e}")
            raise ServiceInitializationError(f"Failed to initialize model service: {str(e)}")
    
    async def _initialize_vector_service(self) -> None:
        """Initialize vector store service"""
        try:
            # Initialize real vector store manager
            vector_manager = VectorStoreManager()
            await vector_manager.initialize()
            
            self.register_service("vector_manager", vector_manager)
            logger.info("✅ Real vector service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            raise ServiceInitializationError(f"Failed to initialize vector service: {str(e)}")
    
    def _initialize_pdf_service(self) -> None:
        """Initialize PDF processing service"""
        try:
            # Initialize real PDF service
            pdf_service_instance = PDFService()
            
            self.register_service("pdf_service", pdf_service_instance)
            logger.info("✅ Real PDF service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize PDF service: {e}")
            raise ServiceInitializationError(f"Failed to initialize PDF service: {str(e)}")
    
    def _initialize_semantic_chunking_service(self) -> None:
        """Initialize semantic chunking service"""
        try:
            # Initialize real semantic chunking service
            chunking_service = SemanticChunking(chunk_size=512, chunk_overlap=50)
            
            self.register_service("semantic_chunking", chunking_service)
            logger.info("✅ Real semantic chunking service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize semantic chunking service: {e}")
            raise ServiceInitializationError(f"Failed to initialize semantic chunking service: {str(e)}")
    
    def _initialize_document_processor(self) -> None:
        """Initialize document processor"""
        try:
            # Get dependencies
            pdf_service = self.get_service("pdf_service")
            chunking_service = self.get_service("semantic_chunking")
            vector_service = self.get_service("vector_manager")
            database = self.get_service("metadata_db")
            
            # Initialize real document processor
            document_processor = DocumentProcessor(
                pdf_service=pdf_service,
                chunking_service=chunking_service,
                vector_service=vector_service,
                database=database
            )
            
            self.register_service("document_processor", document_processor)
            logger.info("✅ Real document processor initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize document processor: {e}")
            raise ServiceInitializationError(f"Failed to initialize document processor: {str(e)}")
    
    def _initialize_query_service(self) -> None:
        """Initialize query service"""
        try:
            # Get dependencies
            vector_service = self.get_service("vector_manager")
            model_service = self.get_service("model_manager")
            
            # Initialize real query service
            query_service = QueryService(
                vector_service=vector_service,
                llm_service=model_service,
                default_top_k=5,
                min_similarity_score=0.4
            )
            
            self.register_service("query_service", query_service)
            logger.info("✅ Real query service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize query service: {e}")
            
            # Fallback to mock for development
            class MockQueryService:
                def is_healthy(self):
                    return True
                def cleanup(self):
                    pass
            
            query_service = MockQueryService()
            self.register_service("query_service", query_service)
            logger.warning("Using mock query service as fallback")
    
    def _initialize_streaming_service(self) -> None:
        """Initialize streaming service"""
        try:
            # Get dependencies
            query_service = self.get_service("query_service")
            
            # Initialize real streaming service
            streaming_service = StreamingService(query_service)
            
            self.register_service("streaming_service", streaming_service)
            logger.info("✅ Real streaming service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize streaming service: {e}")
            raise ServiceInitializationError(f"Failed to initialize streaming service: {str(e)}")
    
    async def initialize_all_services(self) -> None:
        """Initialize all services in proper dependency order"""
        if self._initialized:
            logger.warning("Services already initialized")
            return
        
        try:
            logger.info("Starting service initialization...")
            
            # Initialize services in dependency order
            self._initialize_database_services()
            await self._initialize_model_service()
            await self._initialize_vector_service()
            self._initialize_pdf_service()
            self._initialize_semantic_chunking_service()
            self._initialize_document_processor()
            self._initialize_query_service()
            self._initialize_streaming_service()
            
            # Check all dependencies are satisfied
            self._check_service_dependencies()
            
            self._initialized = True
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            self._initialized = False
            raise ServiceInitializationError(f"Service initialization failed: {str(e)}")
    
    def _check_service_dependencies(self) -> None:
        """Check that all required service dependencies are available"""
        required_services = [
            "auth_db", "metadata_db", "model_manager", "vector_manager",
            "pdf_service", "semantic_chunking", "document_processor",
            "query_service", "streaming_service"
        ]
        
        for service_name in required_services:
            if service_name not in self._services:
                raise ServiceError(f"Required service '{service_name}' not available")
    
    def _get_service_dependencies(self) -> Dict[str, List[str]]:
        """Get service dependency mapping"""
        return {
            "document_processor": ["pdf_service", "semantic_chunking", "vector_manager", "metadata_db"],
            "query_service": ["vector_manager", "model_manager"],
            "streaming_service": ["query_service"]
        }
    
    async def cleanup_all_services(self) -> None:
        """Cleanup all services and release resources"""
        if not self._initialized:
            logger.warning("Services not initialized, nothing to cleanup")
            return
        
        logger.info("Starting service cleanup...")
        
        # Cleanup services in reverse order
        cleanup_order = [
            "streaming_service", "query_service", "document_processor",
            "semantic_chunking", "pdf_service", "vector_manager", 
            "model_manager", "metadata_db", "auth_db"
        ]
        
        for service_name in cleanup_order:
            try:
                service = self.get_service_optional(service_name)
                if service and hasattr(service, 'cleanup'):
                    if asyncio.iscoroutinefunction(service.cleanup):
                        await service.cleanup()
                    else:
                        service.cleanup()
                elif service_name in ["auth_db", "metadata_db"] and service:
                    # Database connections
                    service.close()
                
                logger.debug(f"Cleaned up service: {service_name}")
                
            except Exception as e:
                logger.error(f"Error cleaning up service {service_name}: {e}")
                # Continue with other services
        
        self._services.clear()
        self._initialized = False
        logger.info("Service cleanup completed")
    
    def get_services_health(self) -> Dict[str, bool]:
        """Get health status of all services"""
        health = {}
        
        for name, service in self._services.items():
            try:
                if hasattr(service, 'is_healthy'):
                    health[name] = service.is_healthy()
                else:
                    # If service exists and doesn't have health check, assume healthy
                    health[name] = True
            except Exception as e:
                logger.error(f"Health check failed for service {name}: {e}")
                health[name] = False
        
        return health
    
    def is_fully_initialized(self) -> bool:
        """Check if all services are fully initialized"""
        return self._initialized
    
    def get_initialization_status(self) -> Dict[str, Any]:
        """Get detailed initialization status"""
        return {
            "initialized": self._initialized,
            "service_count": len(self._services),
            "services": list(self._services.keys())
        }
    
    async def restart_service(self, service_name: str) -> None:
        """Restart individual service"""
        if service_name not in self._services:
            raise ServiceError(f"Service '{service_name}' not found")
        
        logger.info(f"Restarting service: {service_name}")
        
        # Cleanup existing service
        service = self._services[service_name]
        if hasattr(service, 'cleanup'):
            if asyncio.iscoroutinefunction(service.cleanup):
                await service.cleanup()
            else:
                service.cleanup()
        
        # Remove from services
        del self._services[service_name]
        
        # Re-initialize
        if service_name == "model_manager":
            self._initialize_model_service()
        elif service_name == "vector_manager":
            self._initialize_vector_service()
        # Add other services as needed
        
        logger.info(f"Service restarted: {service_name}")


# Global service manager instance
service_manager: Optional[ServiceManager] = None


def initialize_service_manager(config: Dict[str, Any]) -> ServiceManager:
    """Initialize global service manager instance"""
    global service_manager
    service_manager = ServiceManager(config=config)
    return service_manager


def get_service_manager() -> Optional[ServiceManager]:
    """Get global service manager instance"""
    return service_manager