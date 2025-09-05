import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from jose import jwt

from app.auth.auth_service import AuthService, AuthError, UserAlreadyExistsError
from app.models.user import User


class TestAuthService:
    """Test suite for AuthService - User Authentication & Registration"""
    
    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance for testing"""
        return AuthService()
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = Mock()
        session.query.return_value = session
        session.filter.return_value = session
        session.first.return_value = None
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        return session

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing"""
        user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="$2b$12$hashed_password_here",
            workspace_id=1,
            is_active=True,
            created_at=datetime.utcnow()
        )
        return user

    # Registration Tests
    @pytest.mark.asyncio
    async def test_register_user_success(self, auth_service, mock_db_session):
        """Test successful user registration"""
        with patch('app.auth.auth_service.get_auth_db', return_value=iter([mock_db_session])), \
             patch('app.auth.auth_service.get_next_workspace_id', return_value=1), \
             patch('bcrypt.hashpw', return_value=b'hashed_password'):
            
            result = await auth_service.register_user(
                username="newuser",
                email="new@example.com", 
                password="password123"
            )
            
            assert result["username"] == "newuser"
            assert result["email"] == "new@example.com"
            assert result["workspace_id"] == 1
            assert "user_id" in result
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, auth_service, mock_db_session, sample_user):
        """Test registration fails with duplicate username"""
        mock_db_session.first.return_value = sample_user
        
        with patch('app.auth.auth_service.get_auth_db', return_value=iter([mock_db_session])):
            with pytest.raises(UserAlreadyExistsError, match="Username already exists"):
                await auth_service.register_user(
                    username="testuser",
                    email="different@example.com",
                    password="password123"
                )

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, auth_service, mock_db_session, sample_user):
        """Test registration fails with duplicate email"""
        # First query (username) returns None, second query (email) returns existing user
        mock_db_session.first.side_effect = [None, sample_user]
        
        with patch('app.auth.auth_service.get_auth_db', return_value=iter([mock_db_session])):
            with pytest.raises(UserAlreadyExistsError, match="Email already exists"):
                await auth_service.register_user(
                    username="differentuser",
                    email="test@example.com",
                    password="password123"
                )

    @pytest.mark.asyncio
    async def test_register_user_weak_password(self, auth_service):
        """Test registration fails with weak password"""
        with pytest.raises(AuthError, match="Password must be at least 8 characters"):
            await auth_service.register_user(
                username="newuser",
                email="new@example.com",
                password="weak"
            )

    @pytest.mark.asyncio
    async def test_register_user_invalid_email(self, auth_service):
        """Test registration fails with invalid email format"""
        with pytest.raises(AuthError, match="Invalid email format"):
            await auth_service.register_user(
                username="newuser",
                email="invalid-email",
                password="password123"
            )

    # Authentication Tests
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, mock_db_session, sample_user):
        """Test successful user authentication"""
        mock_db_session.first.return_value = sample_user
        
        with patch('app.auth.auth_service.get_auth_db', return_value=iter([mock_db_session])), \
             patch('bcrypt.checkpw', return_value=True):
            
            result = await auth_service.authenticate_user("testuser", "password123")
            
            assert result["user_id"] == sample_user.id
            assert result["username"] == sample_user.username
            assert result["workspace_id"] == sample_user.workspace_id
            assert "access_token" in result
            assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service, mock_db_session):
        """Test authentication fails with non-existent user"""
        mock_db_session.first.return_value = None
        
        with patch('app.auth.auth_service.get_auth_db', return_value=iter([mock_db_session])):
            with pytest.raises(AuthError, match="Invalid credentials"):
                await auth_service.authenticate_user("nonexistent", "password123")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, auth_service, mock_db_session, sample_user):
        """Test authentication fails with wrong password"""
        mock_db_session.first.return_value = sample_user
        
        with patch('app.auth.auth_service.get_auth_db', return_value=iter([mock_db_session])), \
             patch('bcrypt.checkpw', return_value=False):
            
            with pytest.raises(AuthError, match="Invalid credentials"):
                await auth_service.authenticate_user("testuser", "wrongpassword")

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self, auth_service, mock_db_session, sample_user):
        """Test authentication fails with inactive user"""
        sample_user.is_active = False
        mock_db_session.first.return_value = sample_user
        
        with patch('app.auth.auth_service.get_auth_db', return_value=iter([mock_db_session])):
            with pytest.raises(AuthError, match="User account is disabled"):
                await auth_service.authenticate_user("testuser", "password123")

    # JWT Token Tests
    def test_create_access_token(self, auth_service):
        """Test JWT access token creation"""
        user_data = {
            "user_id": 1,
            "username": "testuser",
            "workspace_id": 1
        }
        
        token = auth_service.create_access_token(user_data)
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long
        
        # Verify token can be decoded
        decoded = jwt.decode(token, auth_service.secret_key, algorithms=["HS256"])
        assert decoded["user_id"] == 1
        assert decoded["username"] == "testuser"
        assert decoded["workspace_id"] == 1
        assert "exp" in decoded
        assert "iat" in decoded

    def test_create_access_token_custom_expiry(self, auth_service):
        """Test JWT token creation with custom expiry"""
        user_data = {"user_id": 1, "username": "testuser"}
        expires_delta = timedelta(minutes=30)
        
        token = auth_service.create_access_token(user_data, expires_delta)
        decoded = jwt.decode(token, auth_service.secret_key, algorithms=["HS256"])
        
        # Check that custom expiry time was used (should be ~30 minutes from now)
        exp_timestamp = decoded["exp"]
        iat_timestamp = decoded["iat"]
        
        # Calculate the delta between issued and expiry times
        time_delta = exp_timestamp - iat_timestamp
        expected_seconds = expires_delta.total_seconds()
        
        # Should be very close to 30 minutes (1800 seconds)
        assert abs(time_delta - expected_seconds) < 5

    def test_verify_token_valid(self, auth_service):
        """Test valid JWT token verification"""
        user_data = {
            "user_id": 1,
            "username": "testuser",
            "workspace_id": 1
        }
        token = auth_service.create_access_token(user_data)
        
        result = auth_service.verify_token(token)
        
        assert result["user_id"] == 1
        assert result["username"] == "testuser"
        assert result["workspace_id"] == 1

    def test_verify_token_expired(self, auth_service):
        """Test expired JWT token verification"""
        user_data = {"user_id": 1, "username": "testuser"}
        # Create token that expires immediately
        token = auth_service.create_access_token(user_data, timedelta(seconds=-1))
        
        with pytest.raises(AuthError, match="Token has expired"):
            auth_service.verify_token(token)

    def test_verify_token_invalid(self, auth_service):
        """Test invalid JWT token verification"""
        invalid_token = "invalid.jwt.token"
        
        with pytest.raises(AuthError, match="Invalid token"):
            auth_service.verify_token(invalid_token)

    def test_verify_token_wrong_signature(self, auth_service):
        """Test JWT token with wrong signature"""
        # Create token with different secret
        user_data = {"user_id": 1, "username": "testuser"}
        wrong_token = jwt.encode(
            user_data,
            "wrong_secret", 
            algorithm="HS256"
        )
        
        with pytest.raises(AuthError, match="Invalid token"):
            auth_service.verify_token(wrong_token)

    # Password Validation Tests
    def test_validate_password_strength_valid(self, auth_service):
        """Test password strength validation - valid passwords"""
        valid_passwords = [
            "password123",
            "StrongP@ssw0rd",
            "verylongpasswordwithoutspecialchars",
            "12345678"
        ]
        
        for password in valid_passwords:
            # Should not raise exception
            auth_service._validate_password_strength(password)

    def test_validate_password_strength_invalid(self, auth_service):
        """Test password strength validation - invalid passwords"""
        invalid_passwords = [
            "short",      # Too short
            "1234567",    # Too short
            "",           # Empty
            " " * 8,      # Only spaces
        ]
        
        for password in invalid_passwords:
            with pytest.raises(AuthError, match="Password must be at least 8 characters"):
                auth_service._validate_password_strength(password)

    # Email Validation Tests
    def test_validate_email_format_valid(self, auth_service):
        """Test email format validation - valid emails"""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk", 
            "user+tag@example.org",
            "123@numbers.com"
        ]
        
        for email in valid_emails:
            # Should not raise exception
            auth_service._validate_email_format(email)

    def test_validate_email_format_invalid(self, auth_service):
        """Test email format validation - invalid emails"""
        invalid_emails = [
            "notanemail",
            "@domain.com", 
            "user@",
            "user@.com",
            "",
            "   "
        ]
        
        for email in invalid_emails:
            with pytest.raises(AuthError, match="Invalid email format"):
                auth_service._validate_email_format(email)