import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import json

from app.main import app
from app.models.user import User


class TestAuthAPI:
    """Integration tests for authentication API endpoints"""
    
    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_auth_service(self):
        """Mock AuthService for testing"""
        service = Mock()
        service.register_user = AsyncMock()
        service.authenticate_user = AsyncMock()
        service.verify_token = Mock()
        return service
    
    @pytest.fixture
    def mock_user_manager(self):
        """Mock UserManager for testing"""
        manager = Mock()
        manager.mount_user_workspace = AsyncMock()
        manager.unmount_user_workspace = AsyncMock()
        manager.get_current_user = Mock()
        manager.is_authenticated = Mock()
        return manager
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing"""
        return {
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        }

    # User Registration Tests
    def test_register_success(self, client, mock_auth_service, sample_user_data):
        """Test successful user registration"""
        mock_auth_service.register_user.return_value = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "workspace_id": 1
        }
        
        with patch('app.api.auth.auth_service', mock_auth_service):
            response = client.post("/auth/register", json=sample_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["workspace_id"] == 1
        assert "user_id" in data
        
        mock_auth_service.register_user.assert_called_once_with(
            username="testuser",
            email="test@example.com", 
            password="password123"
        )

    def test_register_duplicate_user(self, client, mock_auth_service, sample_user_data):
        """Test registration with duplicate user"""
        from app.auth.auth_service import UserAlreadyExistsError
        mock_auth_service.register_user.side_effect = UserAlreadyExistsError("Username already exists")
        
        with patch('app.api.auth.auth_service', mock_auth_service):
            response = client.post("/auth/register", json=sample_user_data)
        
        assert response.status_code == 409
        assert "Username already exists" in response.json()["detail"]

    def test_register_weak_password(self, client, mock_auth_service):
        """Test registration with weak password"""
        from app.auth.auth_service import AuthError
        mock_auth_service.register_user.side_effect = AuthError("Password must be at least 8 characters")
        
        user_data = {
            "username": "testuser",
            "email": "test@example.com", 
            "password": "weak"
        }
        
        with patch('app.api.auth.auth_service', mock_auth_service):
            response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "Password must be at least 8 characters" in response.json()["detail"]

    def test_register_missing_fields(self, client):
        """Test registration with missing required fields"""
        incomplete_data = {
            "username": "testuser"
            # Missing email and password
        }
        
        response = client.post("/auth/register", json=incomplete_data)
        
        assert response.status_code == 422  # FastAPI validation error

    def test_register_invalid_email_format(self, client, mock_auth_service):
        """Test registration with invalid email format"""
        from app.auth.auth_service import AuthError
        mock_auth_service.register_user.side_effect = AuthError("Invalid email format")
        
        user_data = {
            "username": "testuser",
            "email": "invalid-email",
            "password": "password123"
        }
        
        with patch('app.api.auth.auth_service', mock_auth_service):
            response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "Invalid email format" in response.json()["detail"]

    # User Login Tests
    def test_login_success(self, client, mock_auth_service, mock_user_manager):
        """Test successful user login"""
        mock_auth_service.authenticate_user.return_value = {
            "user_id": 1,
            "username": "testuser",
            "workspace_id": 1,
            "access_token": "fake_jwt_token",
            "token_type": "bearer"
        }
        
        login_data = {
            "username": "testuser",
            "password": "password123"
        }
        
        with patch('app.api.auth.auth_service', mock_auth_service), \
             patch('app.api.auth.user_manager', mock_user_manager):
            
            response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "fake_jwt_token"
        assert data["token_type"] == "bearer"
        assert data["username"] == "testuser"
        assert data["workspace_id"] == 1
        
        # Verify workspace mounting was called
        mock_user_manager.mount_user_workspace.assert_called_once()

    def test_login_invalid_credentials(self, client, mock_auth_service):
        """Test login with invalid credentials"""
        from app.auth.auth_service import AuthError
        mock_auth_service.authenticate_user.side_effect = AuthError("Invalid credentials")
        
        login_data = {
            "username": "testuser",
            "password": "wrongpassword"
        }
        
        with patch('app.api.auth.auth_service', mock_auth_service):
            response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_workspace_mount_failure(self, client, mock_auth_service, mock_user_manager):
        """Test login with workspace mounting failure"""
        from app.auth.user_manager import WorkspaceError
        
        mock_auth_service.authenticate_user.return_value = {
            "user_id": 1,
            "username": "testuser",
            "workspace_id": 1,
            "access_token": "fake_jwt_token",
            "token_type": "bearer"
        }
        
        mock_user_manager.mount_user_workspace.side_effect = WorkspaceError("Failed to load workspace")
        
        login_data = {
            "username": "testuser",
            "password": "password123"
        }
        
        with patch('app.api.auth.auth_service', mock_auth_service), \
             patch('app.api.auth.user_manager', mock_user_manager):
            
            response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == 500
        assert "Failed to load workspace" in response.json()["detail"]

    def test_login_missing_credentials(self, client):
        """Test login with missing credentials"""
        incomplete_data = {
            "username": "testuser"
            # Missing password
        }
        
        response = client.post("/auth/login", json=incomplete_data)
        
        assert response.status_code == 422  # FastAPI validation error

    # User Logout Tests
    def test_logout_success(self, client, mock_user_manager):
        """Test successful user logout"""
        with patch('app.api.auth.user_manager', mock_user_manager):
            response = client.post("/auth/logout")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"
        
        mock_user_manager.cleanup_user_session.assert_called_once()

    def test_logout_with_workspace_cleanup_error(self, client, mock_user_manager):
        """Test logout with workspace cleanup error"""
        mock_user_manager.cleanup_user_session.side_effect = Exception("Cleanup failed")
        
        with patch('app.api.auth.user_manager', mock_user_manager):
            response = client.post("/auth/logout")
        
        # Should still return success even if cleanup fails
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    # Current User Tests
    def test_get_current_user_authenticated(self, client, mock_user_manager):
        """Test getting current user when authenticated"""
        mock_user_manager.get_current_user.return_value = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "workspace_id": 1
        }
        
        # Mock JWT token validation
        with patch('app.api.auth.user_manager', mock_user_manager), \
             patch('app.api.auth.auth_service') as mock_auth_service, \
             patch('app.api.auth.security') as mock_security:
            
            mock_security.return_value = Mock(credentials="fake_token")
            mock_auth_service.verify_token.return_value = {
                "user_id": 1, "username": "testuser"
            }
            
            response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer fake_token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["workspace_id"] == 1

    def test_get_current_user_not_authenticated(self, client):
        """Test getting current user when not authenticated"""
        response = client.get("/auth/me")
        
        assert response.status_code == 403  # Forbidden - no token

    def test_get_current_user_invalid_token(self, client, mock_user_manager):
        """Test getting current user with invalid token"""
        from app.auth.auth_service import AuthError
        
        with patch('app.api.auth.user_manager', mock_user_manager), \
             patch('app.api.auth.auth_service') as mock_auth_service, \
             patch('app.api.auth.security') as mock_security:
            
            mock_security.return_value = Mock(credentials="invalid_token")
            mock_auth_service.verify_token.side_effect = AuthError("Invalid token")
            
            response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer invalid_token"}
            )
        
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    # User Session Status Tests  
    def test_get_session_status_authenticated(self, client, mock_user_manager):
        """Test getting session status when authenticated"""
        mock_user_manager.is_authenticated.return_value = True
        mock_user_manager.get_user_session_stats.return_value = {
            "user": {
                "username": "testuser",
                "workspace_id": 1
            },
            "workspace": {
                "total_documents": 5,
                "faiss_vectors": 100
            },
            "session_duration_minutes": 15
        }
        
        with patch('app.api.auth.user_manager', mock_user_manager):
            response = client.get("/auth/session/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["username"] == "testuser"
        assert data["workspace"]["total_documents"] == 5
        assert data["session_duration_minutes"] == 15

    def test_get_session_status_not_authenticated(self, client, mock_user_manager):
        """Test getting session status when not authenticated"""
        mock_user_manager.is_authenticated.return_value = False
        mock_user_manager.get_user_session_stats.return_value = {
            "user": None,
            "workspace": None,
            "session_duration_minutes": 0
        }
        
        with patch('app.api.auth.user_manager', mock_user_manager):
            response = client.get("/auth/session/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["user"] is None
        assert data["workspace"] is None