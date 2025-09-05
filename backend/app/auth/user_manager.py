import os
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from ..services.vector_service import vector_store

logger = logging.getLogger(__name__)

# Custom exceptions
class WorkspaceError(Exception):
    """Workspace management error"""
    pass

class UserManager:
    """User session and workspace management"""
    
    def __init__(self):
        self.current_user: Optional[Dict[str, Any]] = None
        self.current_workspace_id: Optional[int] = None
        self.session_start_time: Optional[datetime] = None
        self.session_id: Optional[str] = None
    
    async def mount_user_workspace(self, user_data: Dict[str, Any]) -> bool:
        """
        Mount user's workspace (load FAISS index and setup session)
        
        Args:
            user_data: User information from authentication
            
        Returns:
            True if successful
            
        Raises:
            WorkspaceError: If workspace loading fails
        """
        try:
            workspace_id = str(user_data["workspace_id"])
            
            # Check if already mounted to same workspace
            if self.current_workspace_id == user_data["workspace_id"]:
                logger.info(f"Workspace {workspace_id} already mounted")
                return True
            
            # Unmount previous workspace if exists
            if self.current_workspace_id is not None:
                await self.unmount_user_workspace()
            
            # Load user's workspace
            if not await vector_store.load_workspace(workspace_id):
                raise WorkspaceError(f"Failed to load workspace {workspace_id}")
            
            # Setup user session
            self.current_user = user_data
            self.current_workspace_id = user_data["workspace_id"]
            self.session_start_time = datetime.utcnow()
            self.session_id = self.generate_session_id()
            
            logger.info(f"User workspace mounted: {user_data['username']} -> workspace_{workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mount workspace for {user_data.get('username')}: {e}")
            raise WorkspaceError(f"Failed to mount workspace: {str(e)}")
    
    async def unmount_user_workspace(self) -> None:
        """
        Unmount current user's workspace and cleanup session
        """
        try:
            if self.current_workspace_id is not None:
                workspace_id = str(self.current_workspace_id)
                await vector_store.unload_workspace(workspace_id)
                logger.info(f"Workspace {workspace_id} unmounted")
            
            # Clear session data
            self.current_user = None
            self.current_workspace_id = None
            self.session_start_time = None
            self.session_id = None
            
        except Exception as e:
            logger.error(f"Error during workspace unmount: {e}")
            # Continue cleanup even if unmounting fails
            self.current_user = None
            self.current_workspace_id = None
            self.session_start_time = None
            self.session_id = None
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get currently authenticated user
        
        Returns:
            Current user data or None if not authenticated
        """
        return self.current_user
    
    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated
        
        Returns:
            True if user is authenticated and session is active
        """
        return self.current_user is not None and self.current_workspace_id is not None
    
    def get_current_workspace_id(self) -> Optional[int]:
        """
        Get current workspace ID
        
        Returns:
            Current workspace ID or None if not mounted
        """
        return self.current_workspace_id
    
    async def validate_workspace_access(self, workspace_id: int) -> None:
        """
        Validate user has access to specified workspace
        
        Args:
            workspace_id: Workspace ID to validate access for
            
        Raises:
            WorkspaceError: If user doesn't have access
        """
        if not self.is_authenticated():
            raise WorkspaceError("No user authenticated")
        
        if self.current_workspace_id != workspace_id:
            raise WorkspaceError(f"Access denied to workspace {workspace_id}")
    
    async def get_user_session_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive user session statistics
        
        Returns:
            Dict containing user, workspace, and session info
        """
        try:
            if not self.is_authenticated():
                return {
                    "user": None,
                    "workspace": None,
                    "session_duration_minutes": 0
                }
            
            # Get workspace stats
            workspace_stats = await vector_store.get_workspace_stats(str(self.current_workspace_id))
            
            # Calculate session duration
            session_duration = 0
            if self.session_start_time:
                duration_delta = datetime.utcnow() - self.session_start_time
                session_duration = int(duration_delta.total_seconds() / 60)  # minutes
            
            return {
                "user": {
                    "user_id": self.current_user.get("user_id"),
                    "username": self.current_user.get("username"),
                    "email": self.current_user.get("email"),
                    "workspace_id": self.current_workspace_id
                },
                "workspace": workspace_stats,
                "session_duration_minutes": session_duration,
                "session_id": self.session_id,
                "session_start_time": self.session_start_time.isoformat() if self.session_start_time else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                "user": self.current_user,
                "workspace": None,
                "session_duration_minutes": 0
            }
    
    async def cleanup_user_session(self) -> None:
        """
        Complete cleanup of user session and resources
        """
        try:
            if self.current_user:
                logger.info(f"Cleaning up session for user: {self.current_user.get('username')}")
            
            await self.unmount_user_workspace()
            
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
    
    def get_workspace_directory(self, workspace_id: int) -> str:
        """
        Get workspace directory path
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Workspace directory path
            
        Raises:
            WorkspaceError: If workspace directory doesn't exist
        """
        workspace_dir = f"data/workspaces/workspace_{workspace_id:03d}"
        
        if not os.path.exists(workspace_dir):
            raise WorkspaceError(f"Workspace directory not found: {workspace_dir}")
        
        return workspace_dir
    
    async def initialize_workspace_directory(self, workspace_id: int) -> str:
        """
        Initialize workspace directory structure
        
        Args:
            workspace_id: Workspace ID to initialize
            
        Returns:
            Created workspace directory path
        """
        workspace_dir = f"data/workspaces/workspace_{workspace_id:03d}"
        
        try:
            os.makedirs(workspace_dir, exist_ok=True)
            logger.info(f"Workspace directory initialized: {workspace_dir}")
            return workspace_dir
            
        except Exception as e:
            logger.error(f"Failed to initialize workspace directory {workspace_dir}: {e}")
            raise WorkspaceError(f"Failed to initialize workspace: {str(e)}")
    
    def generate_session_id(self) -> str:
        """
        Generate unique session ID
        
        Returns:
            UUID-based session ID
        """
        return str(uuid.uuid4()).replace('-', '')
    
    async def refresh_user_session(self) -> None:
        """
        Refresh user session timestamp (keep session alive)
        """
        if self.is_authenticated():
            self.session_start_time = datetime.utcnow()
            logger.debug(f"Session refreshed for user: {self.current_user.get('username')}")
    
    async def switch_workspace(self, new_workspace_id: int) -> bool:
        """
        Switch user to different workspace (admin feature)
        
        Args:
            new_workspace_id: Target workspace ID
            
        Returns:
            True if successful
            
        Raises:
            WorkspaceError: If workspace switching fails
        """
        if not self.is_authenticated():
            raise WorkspaceError("No user authenticated")
        
        try:
            # Create temporary user data for new workspace
            user_data = self.current_user.copy()
            user_data["workspace_id"] = new_workspace_id
            
            # Mount new workspace
            await self.mount_user_workspace(user_data)
            
            logger.info(f"User {self.current_user.get('username')} switched to workspace {new_workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch workspace to {new_workspace_id}: {e}")
            raise WorkspaceError(f"Failed to switch workspace: {str(e)}")

# Global instance
user_manager = UserManager()