from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from ..auth.auth_service import auth_service, AuthError, UserAlreadyExistsError
from ..auth.user_manager import user_manager, WorkspaceError
from ..core.database_manager import get_database_manager

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    workspace_id: int
    username: str
    user_id: int

class UserInfo(BaseModel):
    user_id: int
    username: str
    workspace_id: int

class SessionStatus(BaseModel):
    authenticated: bool
    user: Optional[Dict[str, Any]]
    workspace: Optional[Dict[str, Any]]
    session_duration_minutes: int

# Dependency to get current user from JWT token
async def get_current_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Extract and validate current user from JWT token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated"
        )
    
    try:
        payload = auth_service.verify_token(credentials.credentials)
        current_user = user_manager.get_current_user()
        
        if not current_user or current_user.get("user_id") != payload.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        return current_user
        
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@router.get("/debug/database-status")
async def debug_database_status():
    """Debug endpoint to check database manager status"""
    db_manager = get_database_manager()
    return {
        "database_manager_exists": db_manager is not None,
        "database_manager_type": type(db_manager).__name__ if db_manager else None,
        "is_initialized": getattr(db_manager, '_initialized', None) if db_manager else None,
    }

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Register new user with encrypted storage"""
    try:
        logger.info(f"Registration request for user: {user_data.username}")
        
        result = await auth_service.register_user(
            username=user_data.username,
            password=user_data.password
        )
        
        logger.info(f"User registered successfully: {user_data.username}")
        return result
        
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration failed for {user_data.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=AuthResponse)
async def login(credentials: UserLogin):
    """Authenticate user and mount workspace"""
    try:
        logger.info(f"Login request for user: {credentials.username}")
        
        # Authenticate user
        auth_result = await auth_service.authenticate_user(
            username=credentials.username,
            password=credentials.password
        )
        
        # Mount user workspace
        await user_manager.mount_user_workspace(auth_result)
        
        logger.info(f"User logged in successfully: {credentials.username}")
        return AuthResponse(**auth_result)
        
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except WorkspaceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Login failed for {credentials.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/logout")
async def logout():
    """Logout user and unmount workspace"""
    try:
        logger.info("Logout request")
        await user_manager.cleanup_user_session()
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Return success even if cleanup fails
        return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserInfo)
async def get_current_user(current_user: Dict[str, Any] = Depends(get_current_user_from_token)):
    """Get current authenticated user info"""
    return UserInfo(
        user_id=current_user["user_id"],
        username=current_user["username"],
        workspace_id=current_user["workspace_id"]
    )

@router.get("/session/status", response_model=SessionStatus)
async def get_session_status():
    """Get current session status and statistics"""
    try:
        stats = await user_manager.get_user_session_stats()
        
        return SessionStatus(
            authenticated=user_manager.is_authenticated(),
            user=stats.get("user"),
            workspace=stats.get("workspace"),
            session_duration_minutes=stats.get("session_duration_minutes", 0)
        )
        
    except Exception as e:
        logger.error(f"Failed to get session status: {e}")
        return SessionStatus(
            authenticated=False,
            user=None,
            workspace=None,
            session_duration_minutes=0
        )

# OPTIONS handlers for CORS preflight
@router.options("/register")
async def register_options():
    """CORS preflight for register"""
    return {"message": "OK"}

@router.options("/login")
async def login_options():
    """CORS preflight for login"""
    return {"message": "OK"}

@router.options("/logout")
async def logout_options():
    """CORS preflight for logout"""
    return {"message": "OK"}

@router.options("/me")
async def me_options():
    """CORS preflight for me"""
    return {"message": "OK"}