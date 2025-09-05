import asyncio
import logging
from typing import Dict, Any, List, Callable, Optional
from enum import Enum
import signal
import time
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class LifespanState(Enum):
    """Application lifespan states"""
    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class LifespanError(Exception):
    """Application lifespan error"""
    pass


class AppLifespan:
    """Manages application startup, shutdown, and lifespan events"""
    
    def __init__(self, config: Dict[str, Any], service_manager):
        """
        Initialize application lifespan manager
        
        Args:
            config: Application configuration
            service_manager: Service manager instance
        """
        if not config:
            raise LifespanError("Configuration is required")
        
        if not service_manager:
            raise LifespanError("Service manager is required")
        
        self._validate_config(config)
        
        self.config = config
        self.service_manager = service_manager
        self.state = LifespanState.NOT_STARTED
        
        self._startup_tasks: List[Dict[str, Any]] = []
        self._shutdown_tasks: List[Dict[str, Any]] = []
        
        self._setup_signal_handlers()
        
        logger.info("AppLifespan initialized")
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration"""
        required_sections = ["database", "model", "vector_store"]
        
        for section in required_sections:
            if section not in config:
                raise LifespanError(f"Invalid configuration: missing section '{section}'")
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            logger.debug("Signal handlers configured")
        except (ValueError, OSError) as e:
            logger.warning(f"Could not setup signal handlers: {e}")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        
        # Create shutdown task if we're in an event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.graceful_shutdown(timeout=30))
        except RuntimeError:
            logger.warning("No event loop running, cannot schedule graceful shutdown")
    
    def register_startup_task(self, name: str, task: Callable, critical: bool = True) -> None:
        """
        Register startup task
        
        Args:
            name: Task name
            task: Async callable task
            critical: Whether task failure should prevent startup
        """
        if not name or not name.strip():
            raise LifespanError("Invalid task name")
        
        if not callable(task):
            raise LifespanError("Task must be a coroutine function")
        
        if not asyncio.iscoroutinefunction(task):
            raise LifespanError("Task must be a coroutine function")
        
        # Check for duplicates
        if any(t["name"] == name for t in self._startup_tasks):
            raise LifespanError(f"Startup task '{name}' already registered")
        
        self._startup_tasks.append({
            "name": name,
            "task": task,
            "critical": critical
        })
        
        logger.debug(f"Registered startup task: {name} (critical={critical})")
    
    def register_shutdown_task(self, name: str, task: Callable) -> None:
        """
        Register shutdown task
        
        Args:
            name: Task name
            task: Async callable task
        """
        if not name or not name.strip():
            raise LifespanError("Invalid task name")
        
        if not callable(task):
            raise LifespanError("Task must be a coroutine function")
        
        if not asyncio.iscoroutinefunction(task):
            raise LifespanError("Task must be a coroutine function")
        
        # Check for duplicates
        if any(t["name"] == name for t in self._shutdown_tasks):
            raise LifespanError(f"Shutdown task '{name}' already registered")
        
        self._shutdown_tasks.append({
            "name": name,
            "task": task
        })
        
        logger.debug(f"Registered shutdown task: {name}")
    
    def _set_state(self, new_state: LifespanState) -> None:
        """Set application state with validation"""
        valid_transitions = {
            LifespanState.NOT_STARTED: [LifespanState.STARTING, LifespanState.FAILED],
            LifespanState.STARTING: [LifespanState.RUNNING, LifespanState.FAILED],
            LifespanState.RUNNING: [LifespanState.STOPPING, LifespanState.FAILED],
            LifespanState.STOPPING: [LifespanState.STOPPED, LifespanState.FAILED],
            LifespanState.STOPPED: [LifespanState.STARTING],
            LifespanState.FAILED: [LifespanState.STARTING, LifespanState.STOPPED]
        }
        
        if new_state not in valid_transitions.get(self.state, []):
            raise LifespanError(f"Invalid state transition from {self.state} to {new_state}")
        
        old_state = self.state
        self.state = new_state
        logger.info(f"State transition: {old_state} -> {new_state}")
    
    def _setup_logging(self) -> None:
        """Setup application logging"""
        try:
            log_config = self.config.get("logging", {})
            log_level = log_config.get("level", "INFO")
            log_file = log_config.get("file")
            
            # Configure logging
            logging.basicConfig(
                level=getattr(logging, log_level.upper()),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(log_file) if log_file else logging.NullHandler()
                ]
            )
            
            logger.info(f"Logging configured: level={log_level}, file={log_file}")
            
        except Exception as e:
            logger.error(f"Failed to setup logging: {e}")
    
    async def startup(self) -> None:
        """Start the application"""
        if self.state == LifespanState.RUNNING:
            raise LifespanError("Application is already running")
        
        if self.state not in [LifespanState.NOT_STARTED, LifespanState.STOPPED, LifespanState.FAILED]:
            raise LifespanError(f"Cannot start application from state: {self.state}")
        
        try:
            self._set_state(LifespanState.STARTING)
            logger.info("Starting application...")
            
            # Setup logging first
            self._setup_logging()
            
            # Initialize services
            logger.info("Initializing services...")
            await self.service_manager.initialize_all_services()
            
            # Execute startup tasks
            logger.info("Executing startup tasks...")
            for task_info in self._startup_tasks:
                try:
                    logger.debug(f"Executing startup task: {task_info['name']}")
                    await task_info["task"]()
                    logger.debug(f"Completed startup task: {task_info['name']}")
                    
                except Exception as e:
                    if task_info["critical"]:
                        logger.error(f"Critical startup task failed: {task_info['name']} - {e}")
                        self._set_state(LifespanState.FAILED)
                        raise LifespanError(f"Critical startup task failed: {task_info['name']}")
                    else:
                        logger.warning(f"Non-critical startup task failed: {task_info['name']} - {e}")
            
            self._set_state(LifespanState.RUNNING)
            logger.info("Application started successfully")
            
        except Exception as e:
            self._set_state(LifespanState.FAILED)
            logger.error(f"Application startup failed: {e}")
            raise LifespanError(f"Application startup failed: {str(e)}")
    
    async def shutdown(self) -> None:
        """Shutdown the application"""
        if self.state == LifespanState.STOPPED:
            logger.info("Application already stopped")
            return
        
        if self.state == LifespanState.NOT_STARTED:
            self._set_state(LifespanState.STOPPED)
            return
        
        try:
            self._set_state(LifespanState.STOPPING)
            logger.info("Shutting down application...")
            
            # Execute shutdown tasks in reverse order
            logger.info("Executing shutdown tasks...")
            for task_info in reversed(self._shutdown_tasks):
                try:
                    logger.debug(f"Executing shutdown task: {task_info['name']}")
                    await task_info["task"]()
                    logger.debug(f"Completed shutdown task: {task_info['name']}")
                    
                except Exception as e:
                    # Shutdown tasks should not prevent shutdown
                    logger.error(f"Shutdown task failed: {task_info['name']} - {e}")
            
            # Cleanup services
            logger.info("Cleaning up services...")
            try:
                await self.service_manager.cleanup_all_services()
            except Exception as e:
                logger.error(f"Service cleanup failed: {e}")
            
            self._set_state(LifespanState.STOPPED)
            logger.info("Application shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            # Force stopped state even if there were errors
            self.state = LifespanState.STOPPED
    
    async def restart(self) -> None:
        """Restart the application"""
        if self.state != LifespanState.RUNNING:
            raise LifespanError("Application is not running")
        
        logger.info("Restarting application...")
        await self.shutdown()
        await self.startup()
        logger.info("Application restarted")
    
    async def graceful_shutdown(self, timeout: float = 30) -> None:
        """Perform graceful shutdown with timeout"""
        logger.info(f"Starting graceful shutdown with {timeout}s timeout")
        
        try:
            await asyncio.wait_for(self.shutdown(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Graceful shutdown timed out after {timeout}s")
            await self.force_shutdown()
    
    async def force_shutdown(self) -> None:
        """Force immediate shutdown"""
        logger.warning("Forcing immediate shutdown")
        
        # Cancel all running tasks
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        for task in tasks:
            task.cancel()
        
        # Wait briefly for cancellation
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.state = LifespanState.STOPPED
        logger.info("Force shutdown completed")
    
    def is_healthy(self) -> bool:
        """Check if application is healthy"""
        if self.state != LifespanState.RUNNING:
            return False
        
        try:
            # Check service health
            services_health = self.service_manager.get_services_health()
            return all(services_health.values())
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status"""
        try:
            services_health = self.service_manager.get_services_health()
            initialization_status = self.service_manager.get_initialization_status()
            
            return {
                "state": self.state,
                "healthy": self.is_healthy(),
                "services": services_health,
                "initialization": initialization_status,
                "uptime": self._get_uptime()
            }
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                "state": self.state,
                "healthy": False,
                "error": str(e)
            }
    
    def _get_uptime(self) -> Optional[float]:
        """Get application uptime in seconds"""
        # This would track startup time in a real implementation
        return None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.startup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.shutdown()
        
        # Don't suppress exceptions
        return False


@asynccontextmanager
async def lifespan_context(config: Dict[str, Any], service_manager):
    """
    Context manager for application lifespan
    
    Args:
        config: Application configuration
        service_manager: Service manager instance
        
    Yields:
        AppLifespan instance
    """
    app_lifespan = AppLifespan(config=config, service_manager=service_manager)
    
    try:
        await app_lifespan.startup()
        yield app_lifespan
    finally:
        await app_lifespan.shutdown()


# Global lifespan instance
app_lifespan: Optional[AppLifespan] = None


def initialize_app_lifespan(config: Dict[str, Any], service_manager) -> AppLifespan:
    """Initialize global app lifespan instance"""
    global app_lifespan
    app_lifespan = AppLifespan(config=config, service_manager=service_manager)
    return app_lifespan


def get_app_lifespan() -> Optional[AppLifespan]:
    """Get global app lifespan instance"""
    return app_lifespan