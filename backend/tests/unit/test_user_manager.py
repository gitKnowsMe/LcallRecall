import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.auth.user_manager import UserManager, WorkspaceError
from app.services.vector_service import vector_store


class TestUserManager:
    """Test suite for UserManager - Workspace Management & User Sessions"""
    
    @pytest.fixture
    def user_manager(self):
        """Create UserManager instance for testing"""
        return UserManager()
    
    @pytest.fixture
    def sample_user_session(self):
        """Sample user session data"""
        return {
            "user_id": 1,
            "username": "testuser",
            "workspace_id": 1,
            "email": "test@example.com"
        }

    # Workspace Mounting Tests
    @pytest.mark.asyncio
    async def test_mount_user_workspace_success(self, user_manager, sample_user_session):
        """Test successful workspace mounting"""
        with patch.object(vector_store, 'load_workspace', return_value=True) as mock_load:
            result = await user_manager.mount_user_workspace(sample_user_session)
            
            assert result is True
            assert user_manager.current_user == sample_user_session
            assert user_manager.current_workspace_id == 1
            mock_load.assert_called_once_with("1")

    @pytest.mark.asyncio
    async def test_mount_user_workspace_load_failure(self, user_manager, sample_user_session):
        """Test workspace mounting fails when FAISS load fails"""
        with patch.object(vector_store, 'load_workspace', return_value=False) as mock_load:
            with pytest.raises(WorkspaceError, match="Failed to load workspace"):
                await user_manager.mount_user_workspace(sample_user_session)
            
            mock_load.assert_called_once_with("1")

    @pytest.mark.asyncio
    async def test_mount_user_workspace_already_mounted(self, user_manager, sample_user_session):
        """Test mounting workspace when another is already mounted"""
        # First mount
        with patch.object(vector_store, 'load_workspace', return_value=True), \
             patch.object(vector_store, 'unload_workspace') as mock_unload:
            await user_manager.mount_user_workspace(sample_user_session)
            
            # Mount different workspace
            different_user = sample_user_session.copy()
            different_user["workspace_id"] = 2
            different_user["user_id"] = 2
            
            await user_manager.mount_user_workspace(different_user)
            
            # Should unload previous workspace
            mock_unload.assert_called_once_with("1")
            assert user_manager.current_workspace_id == 2

    @pytest.mark.asyncio
    async def test_mount_user_workspace_same_workspace(self, user_manager, sample_user_session):
        """Test mounting same workspace twice (should be no-op)"""
        with patch.object(vector_store, 'load_workspace', return_value=True) as mock_load:
            await user_manager.mount_user_workspace(sample_user_session)
            await user_manager.mount_user_workspace(sample_user_session)
            
            # Should only load once
            mock_load.assert_called_once_with("1")

    # Workspace Unmounting Tests
    @pytest.mark.asyncio
    async def test_unmount_user_workspace_success(self, user_manager, sample_user_session):
        """Test successful workspace unmounting"""
        # First mount a workspace
        with patch.object(vector_store, 'load_workspace', return_value=True):
            await user_manager.mount_user_workspace(sample_user_session)
        
        # Then unmount
        with patch.object(vector_store, 'unload_workspace') as mock_unload:
            await user_manager.unmount_user_workspace()
            
            assert user_manager.current_user is None
            assert user_manager.current_workspace_id is None
            mock_unload.assert_called_once_with("1")

    @pytest.mark.asyncio
    async def test_unmount_user_workspace_not_mounted(self, user_manager):
        """Test unmounting when no workspace is mounted"""
        with patch.object(vector_store, 'unload_workspace') as mock_unload:
            await user_manager.unmount_user_workspace()
            
            # Should not call unload if nothing mounted
            mock_unload.assert_not_called()

    # Session Management Tests
    def test_get_current_user_with_session(self, user_manager, sample_user_session):
        """Test getting current user when session exists"""
        user_manager.current_user = sample_user_session
        
        result = user_manager.get_current_user()
        
        assert result == sample_user_session

    def test_get_current_user_no_session(self, user_manager):
        """Test getting current user when no session exists"""
        result = user_manager.get_current_user()
        
        assert result is None

    def test_is_authenticated_with_user(self, user_manager, sample_user_session):
        """Test authentication status with logged in user"""
        user_manager.current_user = sample_user_session
        
        assert user_manager.is_authenticated() is True

    def test_is_authenticated_no_user(self, user_manager):
        """Test authentication status with no user"""
        assert user_manager.is_authenticated() is False

    def test_get_current_workspace_id_with_session(self, user_manager, sample_user_session):
        """Test getting workspace ID when session exists"""
        user_manager.current_workspace_id = sample_user_session["workspace_id"]
        
        result = user_manager.get_current_workspace_id()
        
        assert result == 1

    def test_get_current_workspace_id_no_session(self, user_manager):
        """Test getting workspace ID when no session exists"""
        result = user_manager.get_current_workspace_id()
        
        assert result is None

    # Workspace Validation Tests
    @pytest.mark.asyncio
    async def test_validate_workspace_access_valid(self, user_manager, sample_user_session):
        """Test workspace access validation for valid user"""
        user_manager.current_user = sample_user_session
        user_manager.current_workspace_id = 1
        
        # Should not raise exception
        await user_manager.validate_workspace_access(1)

    @pytest.mark.asyncio
    async def test_validate_workspace_access_no_user(self, user_manager):
        """Test workspace access validation with no authenticated user"""
        with pytest.raises(WorkspaceError, match="No user authenticated"):
            await user_manager.validate_workspace_access(1)

    @pytest.mark.asyncio
    async def test_validate_workspace_access_wrong_workspace(self, user_manager, sample_user_session):
        """Test workspace access validation for wrong workspace"""
        user_manager.current_user = sample_user_session
        user_manager.current_workspace_id = 1
        
        with pytest.raises(WorkspaceError, match="Access denied to workspace"):
            await user_manager.validate_workspace_access(2)

    # User Session Stats Tests
    @pytest.mark.asyncio
    async def test_get_user_session_stats_with_user(self, user_manager, sample_user_session):
        """Test getting session stats with authenticated user"""
        user_manager.current_user = sample_user_session
        user_manager.current_workspace_id = 1
        user_manager.session_start_time = datetime.utcnow()
        
        with patch.object(vector_store, 'get_workspace_stats', return_value={
            "total_documents": 5,
            "faiss_vectors": 100,
            "workspace_id": "1"
        }) as mock_stats:
            
            result = await user_manager.get_user_session_stats()
            
            assert result["user"]["username"] == "testuser"
            assert result["user"]["workspace_id"] == 1
            assert result["workspace"]["total_documents"] == 5
            assert result["workspace"]["faiss_vectors"] == 100
            assert "session_duration_minutes" in result
            mock_stats.assert_called_once_with("1")

    @pytest.mark.asyncio
    async def test_get_user_session_stats_no_user(self, user_manager):
        """Test getting session stats with no authenticated user"""
        result = await user_manager.get_user_session_stats()
        
        assert result["user"] is None
        assert result["workspace"] is None
        assert result["session_duration_minutes"] == 0

    # User Session Cleanup Tests
    @pytest.mark.asyncio
    async def test_cleanup_user_session(self, user_manager, sample_user_session):
        """Test complete user session cleanup"""
        # Setup active session
        user_manager.current_user = sample_user_session
        user_manager.current_workspace_id = 1
        user_manager.session_start_time = datetime.utcnow()
        
        with patch.object(vector_store, 'unload_workspace') as mock_unload:
            await user_manager.cleanup_user_session()
            
            assert user_manager.current_user is None
            assert user_manager.current_workspace_id is None
            assert user_manager.session_start_time is None
            mock_unload.assert_called_once_with("1")

    # Workspace Directory Management Tests
    def test_get_workspace_directory_exists(self, user_manager):
        """Test getting workspace directory path"""
        with patch('os.path.exists', return_value=True):
            result = user_manager.get_workspace_directory(1)
            
            expected = "data/workspaces/workspace_001"
            assert result == expected

    def test_get_workspace_directory_not_exists(self, user_manager):
        """Test getting non-existent workspace directory"""
        with patch('os.path.exists', return_value=False):
            with pytest.raises(WorkspaceError, match="Workspace directory not found"):
                user_manager.get_workspace_directory(999)

    @pytest.mark.asyncio
    async def test_initialize_workspace_directory(self, user_manager):
        """Test initializing new workspace directory"""
        with patch('os.makedirs') as mock_makedirs, \
             patch('os.path.exists', return_value=False):
            
            result = await user_manager.initialize_workspace_directory(1)
            
            assert result == "data/workspaces/workspace_001"
            mock_makedirs.assert_called_once_with("data/workspaces/workspace_001", exist_ok=True)

    # Session Security Tests
    def test_generate_session_id(self, user_manager):
        """Test session ID generation"""
        session_id = user_manager.generate_session_id()
        
        assert isinstance(session_id, str)
        assert len(session_id) == 32  # UUID4 without hyphens
        
        # Generate another and ensure they're different
        session_id2 = user_manager.generate_session_id()
        assert session_id != session_id2

    @pytest.mark.asyncio
    async def test_refresh_user_session(self, user_manager, sample_user_session):
        """Test refreshing user session timestamps"""
        user_manager.current_user = sample_user_session
        user_manager.session_start_time = datetime.utcnow()
        original_time = user_manager.session_start_time
        
        # Wait a bit then refresh
        import asyncio
        await asyncio.sleep(0.001)
        
        await user_manager.refresh_user_session()
        
        # Session start time should be updated
        assert user_manager.session_start_time > original_time