import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import tempfile
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.core.app_lifespan import AppLifespan, LifespanError, LifespanState
from app.core.service_manager import ServiceManager


class TestAppLifespan:
    """Test suite for application startup and lifespan management"""
    
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
                "preload": True,
                "max_context_length": 4096
            },
            "vector_store": {
                "workspace_dir": os.path.join(temp_config_dir, "workspaces")
            },
            "logging": {
                "level": "INFO",
                "file": os.path.join(temp_config_dir, "app.log")
            }
        }
    
    @pytest.fixture
    def mock_service_manager(self):
        """Mock service manager"""
        manager = Mock(spec=ServiceManager)
        manager.initialize_all_services = AsyncMock()
        manager.cleanup_all_services = AsyncMock()
        manager.is_fully_initialized = Mock(return_value=False)
        manager.get_services_health = Mock(return_value={})
        manager.get_initialization_status = Mock(return_value={})
        return manager
    
    @pytest.fixture
    def app_lifespan(self, mock_config, mock_service_manager):
        """Create AppLifespan instance for testing"""
        return AppLifespan(
            config=mock_config,
            service_manager=mock_service_manager
        )

    # AppLifespan Initialization Tests
    def test_app_lifespan_init(self, mock_config, mock_service_manager):
        """Test AppLifespan initialization"""
        lifespan = AppLifespan(
            config=mock_config,
            service_manager=mock_service_manager
        )
        
        assert lifespan.config == mock_config
        assert lifespan.service_manager == mock_service_manager
        assert lifespan.state == LifespanState.NOT_STARTED
        assert lifespan._startup_tasks == []
        assert lifespan._shutdown_tasks == []

    def test_app_lifespan_init_no_config(self, mock_service_manager):
        """Test AppLifespan initialization without config"""
        with pytest.raises(LifespanError, match="Configuration is required"):
            AppLifespan(config=None, service_manager=mock_service_manager)

    def test_app_lifespan_init_no_service_manager(self, mock_config):
        """Test AppLifespan initialization without service manager"""
        with pytest.raises(LifespanError, match="Service manager is required"):
            AppLifespan(config=mock_config, service_manager=None)

    # Startup Task Registration Tests
    def test_register_startup_task(self, app_lifespan):
        """Test registering startup task"""
        async def test_task():
            pass
        
        app_lifespan.register_startup_task("test_task", test_task)
        
        assert len(app_lifespan._startup_tasks) == 1
        assert app_lifespan._startup_tasks[0]["name"] == "test_task"
        assert app_lifespan._startup_tasks[0]["task"] == test_task
        assert app_lifespan._startup_tasks[0]["critical"] == True

    def test_register_startup_task_non_critical(self, app_lifespan):
        """Test registering non-critical startup task"""
        async def test_task():
            pass
        
        app_lifespan.register_startup_task("test_task", test_task, critical=False)
        
        assert app_lifespan._startup_tasks[0]["critical"] == False

    def test_register_startup_task_duplicate(self, app_lifespan):
        """Test registering duplicate startup task"""
        async def test_task():
            pass
        
        app_lifespan.register_startup_task("test_task", test_task)
        
        with pytest.raises(LifespanError, match="Startup task 'test_task' already registered"):
            app_lifespan.register_startup_task("test_task", test_task)

    def test_register_startup_task_invalid_name(self, app_lifespan):
        """Test registering startup task with invalid name"""
        async def test_task():
            pass
        
        invalid_names = ["", None, " ", "task with spaces"]
        
        for invalid_name in invalid_names:
            with pytest.raises(LifespanError, match="Invalid task name"):
                app_lifespan.register_startup_task(invalid_name, test_task)

    def test_register_startup_task_not_coroutine(self, app_lifespan):
        """Test registering non-async startup task"""
        def sync_task():
            pass
        
        with pytest.raises(LifespanError, match="Task must be a coroutine function"):
            app_lifespan.register_startup_task("sync_task", sync_task)

    # Shutdown Task Registration Tests
    def test_register_shutdown_task(self, app_lifespan):
        """Test registering shutdown task"""
        async def test_task():
            pass
        
        app_lifespan.register_shutdown_task("test_task", test_task)
        
        assert len(app_lifespan._shutdown_tasks) == 1
        assert app_lifespan._shutdown_tasks[0]["name"] == "test_task"
        assert app_lifespan._shutdown_tasks[0]["task"] == test_task

    def test_register_shutdown_task_duplicate(self, app_lifespan):
        """Test registering duplicate shutdown task"""
        async def test_task():
            pass
        
        app_lifespan.register_shutdown_task("test_task", test_task)
        
        with pytest.raises(LifespanError, match="Shutdown task 'test_task' already registered"):
            app_lifespan.register_shutdown_task("test_task", test_task)

    # Application Startup Tests
    @pytest.mark.asyncio
    async def test_startup_success(self, app_lifespan, mock_service_manager):
        """Test successful application startup"""
        startup_called = False
        
        async def test_startup_task():
            nonlocal startup_called
            startup_called = True
        
        app_lifespan.register_startup_task("test_task", test_startup_task)
        
        await app_lifespan.startup()
        
        assert app_lifespan.state == LifespanState.RUNNING
        assert startup_called == True
        mock_service_manager.initialize_all_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_already_running(self, app_lifespan):
        """Test startup when already running"""
        app_lifespan.state = LifespanState.RUNNING
        
        with pytest.raises(LifespanError, match="Application is already running"):
            await app_lifespan.startup()

    @pytest.mark.asyncio
    async def test_startup_service_initialization_failure(self, app_lifespan, mock_service_manager):
        """Test startup with service initialization failure"""
        mock_service_manager.initialize_all_services.side_effect = Exception("Service init failed")
        
        with pytest.raises(LifespanError, match="Application startup failed"):
            await app_lifespan.startup()
        
        assert app_lifespan.state == LifespanState.FAILED

    @pytest.mark.asyncio
    async def test_startup_critical_task_failure(self, app_lifespan, mock_service_manager):
        """Test startup with critical task failure"""
        async def failing_task():
            raise Exception("Critical task failed")
        
        app_lifespan.register_startup_task("critical_task", failing_task, critical=True)
        
        with pytest.raises(LifespanError, match="Critical startup task failed"):
            await app_lifespan.startup()
        
        assert app_lifespan.state == LifespanState.FAILED

    @pytest.mark.asyncio
    async def test_startup_non_critical_task_failure(self, app_lifespan, mock_service_manager):
        """Test startup with non-critical task failure"""
        async def failing_task():
            raise Exception("Non-critical task failed")
        
        app_lifespan.register_startup_task("non_critical_task", failing_task, critical=False)
        
        # Should not raise exception
        await app_lifespan.startup()
        
        assert app_lifespan.state == LifespanState.RUNNING

    @pytest.mark.asyncio 
    async def test_startup_task_execution_order(self, app_lifespan, mock_service_manager):
        """Test startup tasks execute in registration order"""
        execution_order = []
        
        async def task1():
            execution_order.append(1)
        
        async def task2():
            execution_order.append(2)
        
        async def task3():
            execution_order.append(3)
        
        app_lifespan.register_startup_task("task1", task1)
        app_lifespan.register_startup_task("task2", task2)
        app_lifespan.register_startup_task("task3", task3)
        
        await app_lifespan.startup()
        
        assert execution_order == [1, 2, 3]

    # Application Shutdown Tests
    @pytest.mark.asyncio
    async def test_shutdown_success(self, app_lifespan, mock_service_manager):
        """Test successful application shutdown"""
        app_lifespan.state = LifespanState.RUNNING
        shutdown_called = False
        
        async def test_shutdown_task():
            nonlocal shutdown_called
            shutdown_called = True
        
        app_lifespan.register_shutdown_task("test_task", test_shutdown_task)
        
        await app_lifespan.shutdown()
        
        assert app_lifespan.state == LifespanState.STOPPED
        assert shutdown_called == True
        mock_service_manager.cleanup_all_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_not_running(self, app_lifespan):
        """Test shutdown when not running"""
        # Should not raise exception
        await app_lifespan.shutdown()
        
        assert app_lifespan.state == LifespanState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_with_task_failure(self, app_lifespan, mock_service_manager):
        """Test shutdown with task failure"""
        app_lifespan.state = LifespanState.RUNNING
        
        async def failing_task():
            raise Exception("Shutdown task failed")
        
        app_lifespan.register_shutdown_task("failing_task", failing_task)
        
        # Should not raise exception, but log error
        await app_lifespan.shutdown()
        
        assert app_lifespan.state == LifespanState.STOPPED
        mock_service_manager.cleanup_all_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_service_cleanup_failure(self, app_lifespan, mock_service_manager):
        """Test shutdown with service cleanup failure"""
        app_lifespan.state = LifespanState.RUNNING
        mock_service_manager.cleanup_all_services.side_effect = Exception("Cleanup failed")
        
        # Should not raise exception, but log error
        await app_lifespan.shutdown()
        
        assert app_lifespan.state == LifespanState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_task_execution_order(self, app_lifespan):
        """Test shutdown tasks execute in reverse registration order"""
        app_lifespan.state = LifespanState.RUNNING
        execution_order = []
        
        async def task1():
            execution_order.append(1)
        
        async def task2():
            execution_order.append(2)
        
        async def task3():
            execution_order.append(3)
        
        app_lifespan.register_shutdown_task("task1", task1)
        app_lifespan.register_shutdown_task("task2", task2)
        app_lifespan.register_shutdown_task("task3", task3)
        
        await app_lifespan.shutdown()
        
        # Should execute in reverse order
        assert execution_order == [3, 2, 1]

    # Lifespan Context Manager Tests
    @pytest.mark.asyncio
    async def test_lifespan_context_manager_success(self, app_lifespan, mock_service_manager):
        """Test lifespan as async context manager"""
        startup_called = False
        shutdown_called = False
        
        async def startup_task():
            nonlocal startup_called
            startup_called = True
        
        async def shutdown_task():
            nonlocal shutdown_called
            shutdown_called = True
        
        app_lifespan.register_startup_task("startup", startup_task)
        app_lifespan.register_shutdown_task("shutdown", shutdown_task)
        
        async with app_lifespan:
            assert app_lifespan.state == LifespanState.RUNNING
            assert startup_called == True
        
        assert app_lifespan.state == LifespanState.STOPPED
        assert shutdown_called == True

    @pytest.mark.asyncio
    async def test_lifespan_context_manager_startup_failure(self, app_lifespan, mock_service_manager):
        """Test lifespan context manager with startup failure"""
        mock_service_manager.initialize_all_services.side_effect = Exception("Init failed")
        
        with pytest.raises(LifespanError):
            async with app_lifespan:
                pass
        
        assert app_lifespan.state == LifespanState.FAILED

    @pytest.mark.asyncio
    async def test_lifespan_context_manager_exception_in_context(self, app_lifespan, mock_service_manager):
        """Test lifespan context manager with exception in context"""
        shutdown_called = False
        
        async def shutdown_task():
            nonlocal shutdown_called
            shutdown_called = True
        
        app_lifespan.register_shutdown_task("shutdown", shutdown_task)
        
        with pytest.raises(ValueError):
            async with app_lifespan:
                assert app_lifespan.state == LifespanState.RUNNING
                raise ValueError("Test exception")
        
        # Should still shutdown properly
        assert app_lifespan.state == LifespanState.STOPPED
        assert shutdown_called == True

    # Health Check Tests
    def test_is_healthy(self, app_lifespan, mock_service_manager):
        """Test health check"""
        app_lifespan.state = LifespanState.RUNNING
        mock_service_manager.get_services_health.return_value = {
            "service1": True,
            "service2": True
        }
        
        assert app_lifespan.is_healthy() == True

    def test_is_healthy_not_running(self, app_lifespan):
        """Test health check when not running"""
        app_lifespan.state = LifespanState.NOT_STARTED
        
        assert app_lifespan.is_healthy() == False

    def test_is_healthy_unhealthy_service(self, app_lifespan, mock_service_manager):
        """Test health check with unhealthy service"""
        app_lifespan.state = LifespanState.RUNNING
        mock_service_manager.get_services_health.return_value = {
            "service1": True,
            "service2": False  # Unhealthy service
        }
        
        assert app_lifespan.is_healthy() == False

    def test_get_health_status(self, app_lifespan, mock_service_manager):
        """Test getting detailed health status"""
        app_lifespan.state = LifespanState.RUNNING
        mock_service_manager.get_services_health.return_value = {
            "service1": True,
            "service2": True
        }
        mock_service_manager.get_initialization_status.return_value = {
            "initialized": True,
            "service_count": 2
        }
        
        status = app_lifespan.get_health_status()
        
        assert status["state"] == LifespanState.RUNNING
        assert status["healthy"] == True
        assert status["services"]["service1"] == True
        assert status["services"]["service2"] == True
        assert status["initialization"]["initialized"] == True

    # Restart Tests
    @pytest.mark.asyncio
    async def test_restart_success(self, app_lifespan, mock_service_manager):
        """Test application restart"""
        app_lifespan.state = LifespanState.RUNNING
        
        restart_count = 0
        
        async def counting_task():
            nonlocal restart_count
            restart_count += 1
        
        app_lifespan.register_startup_task("counting", counting_task)
        app_lifespan.register_shutdown_task("counting", counting_task)
        
        await app_lifespan.restart()
        
        assert app_lifespan.state == LifespanState.RUNNING
        assert restart_count == 2  # One shutdown, one startup

    @pytest.mark.asyncio
    async def test_restart_not_running(self, app_lifespan):
        """Test restart when not running"""
        with pytest.raises(LifespanError, match="Application is not running"):
            await app_lifespan.restart()

    # Graceful Shutdown Tests
    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_timeout(self, app_lifespan, mock_service_manager):
        """Test graceful shutdown with timeout"""
        app_lifespan.state = LifespanState.RUNNING
        
        async def slow_task():
            await asyncio.sleep(0.5)  # Longer than timeout
        
        app_lifespan.register_shutdown_task("slow_task", slow_task)
        
        # Should complete within timeout and not raise exception
        await app_lifespan.graceful_shutdown(timeout=0.1)
        
        assert app_lifespan.state == LifespanState.STOPPED

    @pytest.mark.asyncio
    async def test_force_shutdown(self, app_lifespan, mock_service_manager):
        """Test force shutdown"""
        app_lifespan.state = LifespanState.RUNNING
        
        # Should shutdown immediately regardless of running tasks
        await app_lifespan.force_shutdown()
        
        assert app_lifespan.state == LifespanState.STOPPED

    # State Management Tests
    def test_state_transitions(self, app_lifespan):
        """Test valid state transitions"""
        # Initial state
        assert app_lifespan.state == LifespanState.NOT_STARTED
        
        # Valid transitions
        app_lifespan._set_state(LifespanState.STARTING)
        assert app_lifespan.state == LifespanState.STARTING
        
        app_lifespan._set_state(LifespanState.RUNNING)
        assert app_lifespan.state == LifespanState.RUNNING
        
        app_lifespan._set_state(LifespanState.STOPPING)
        assert app_lifespan.state == LifespanState.STOPPING
        
        app_lifespan._set_state(LifespanState.STOPPED)
        assert app_lifespan.state == LifespanState.STOPPED

    def test_invalid_state_transition(self, app_lifespan):
        """Test invalid state transitions"""
        # Can't go from NOT_STARTED to RUNNING directly
        with pytest.raises(LifespanError, match="Invalid state transition"):
            app_lifespan._set_state(LifespanState.RUNNING)

    # Configuration Validation Tests
    def test_validate_config_success(self, app_lifespan):
        """Test configuration validation success"""
        # Should not raise exception
        app_lifespan._validate_config()

    def test_validate_config_missing_sections(self, mock_service_manager):
        """Test configuration validation with missing sections"""
        invalid_config = {
            "database": {}  # Missing other sections
        }
        
        with pytest.raises(LifespanError, match="Invalid configuration"):
            AppLifespan(config=invalid_config, service_manager=mock_service_manager)

    # Logging Integration Tests
    @patch('app.core.app_lifespan.logging')
    def test_logging_setup(self, mock_logging, app_lifespan):
        """Test logging setup during startup"""
        app_lifespan._setup_logging()
        
        # Should configure logging
        mock_logging.basicConfig.assert_called_once()

    @patch('app.core.app_lifespan.logging')
    @pytest.mark.asyncio
    async def test_startup_logging(self, mock_logging, app_lifespan, mock_service_manager):
        """Test logging during startup"""
        with patch.object(app_lifespan, '_setup_logging') as mock_setup:
            await app_lifespan.startup()
            
            mock_setup.assert_called_once()

    # Error Handling and Recovery Tests
    @pytest.mark.asyncio
    async def test_startup_partial_failure_recovery(self, app_lifespan, mock_service_manager):
        """Test recovery from partial startup failure"""
        task_results = []
        
        async def success_task():
            task_results.append("success")
        
        async def failure_task():
            task_results.append("failure")
            raise Exception("Task failed")
        
        app_lifespan.register_startup_task("success", success_task, critical=False)
        app_lifespan.register_startup_task("failure", failure_task, critical=False)
        
        await app_lifespan.startup()
        
        assert "success" in task_results
        assert "failure" in task_results
        assert app_lifespan.state == LifespanState.RUNNING