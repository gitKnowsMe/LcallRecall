import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import bcrypt
from jose import JWTError, jwt

from .database_service import database_service

logger = logging.getLogger(__name__)

# Custom exceptions
class AuthError(Exception):
    """Base authentication error"""
    pass

class UserAlreadyExistsError(AuthError):
    """User already exists error"""
    pass

class AuthService:
    """Authentication service with encryption and JWT support"""
    
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60 * 24  # 24 hours
        
    
    async def register_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Register new user with encrypted password and workspace assignment
        
        Args:
            username: Unique username
            password: Plain text password
            
        Returns:
            Dict containing user info and workspace_id
            
        Raises:
            UserAlreadyExistsError: If username already exists
            AuthError: If validation fails
        """
        try:
            # Validate input
            self._validate_password_strength(password)
            
            # Check for existing username
            existing_user = database_service.execute_query(
                "SELECT id FROM users WHERE username = ?", (username,)
            )
            if existing_user:
                raise UserAlreadyExistsError("Username already exists")
            
            # Hash password
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            # Get next available workspace
            workspace_id = database_service.get_next_workspace_id()
            
            # Create new user
            user_id = database_service.execute_insert(
                """INSERT INTO users (username, password_hash, workspace_id, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, hashed_password.decode('utf-8'), str(workspace_id), True, 
                 datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )
            
            logger.info(f"User registered successfully: {username} (workspace: {workspace_id})")
            
            return {
                "user_id": user_id,
                "username": username,
                "workspace_id": workspace_id
            }
            
        except (UserAlreadyExistsError, AuthError):
            raise
        except Exception as e:
            logger.error(f"Registration failed for {username}: {e}")
            raise AuthError(f"Auth database not initialized")
    
    async def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with username/password
        
        Args:
            username: Username or email
            password: Plain text password
            
        Returns:
            Dict containing user info and access token
            
        Raises:
            AuthError: If authentication fails
        """
        try:
            # Find user by username
            user = database_service.execute_query(
                "SELECT id, username, password_hash, workspace_id, is_active FROM users WHERE username = ?",
                (username,)
            )
            
            if not user:
                raise AuthError("Invalid credentials")
            
            # Check if user is active
            if not user['is_active']:
                raise AuthError("User account is disabled")
            
            # Verify password
            if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                raise AuthError("Invalid credentials")
            
            # Update last login
            database_service.execute_update(
                "UPDATE users SET updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), user['id'])
            )
            
            # Create access token
            token_data = {
                "user_id": user['id'],
                "username": user['username'],
                "workspace_id": int(user['workspace_id'])
            }
            access_token = self.create_access_token(token_data)
            
            logger.info(f"User authenticated successfully: {username}")
            
            return {
                "user_id": user['id'],
                "username": user['username'],
                "workspace_id": int(user['workspace_id']),
                "access_token": access_token,
                "token_type": "bearer"
            }
            
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"Authentication failed for {username}: {e}")
            raise AuthError("Authentication failed")
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token
        
        Args:
            data: Token payload data
            expires_delta: Optional custom expiration time
            
        Returns:
            JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow()
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
            
        except jwt.ExpiredSignatureError:
            raise AuthError("Token has expired")
        except JWTError:
            raise AuthError("Invalid token")
    
    def _validate_password_strength(self, password: str) -> None:
        """
        Validate password strength requirements
        
        Args:
            password: Password to validate
            
        Raises:
            AuthError: If password is too weak
        """
        if not password or len(password.strip()) < 8:
            raise AuthError("Password must be at least 8 characters")
    
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user information by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User information dict or None if not found
        """
        try:
            user = database_service.execute_query(
                "SELECT id, username, workspace_id, is_active, created_at, updated_at FROM users WHERE id = ?",
                (user_id,)
            )
            
            if user:
                return {
                    "user_id": user['id'],
                    "username": user['username'],
                    "workspace_id": int(user['workspace_id']),
                    "is_active": user['is_active'],
                    "created_at": user['created_at'],
                    "last_login": user['updated_at']
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    async def deactivate_user(self, user_id: int) -> bool:
        """
        Deactivate user account
        
        Args:
            user_id: User ID to deactivate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = next(get_auth_db())
            user = db.query(User).filter(User.id == user_id).first()
            
            if user:
                user.is_active = False
                db.commit()
                logger.info(f"User {user_id} deactivated")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to deactivate user {user_id}: {e}")
            return False
        finally:
            db.close()

# Global service instance
auth_service = AuthService()