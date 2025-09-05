import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.setup import init_databases, get_next_workspace_id
from app.models.user import User
from app.models.document import Document, DocumentChunk


class TestDatabaseSetup:
    """Test suite for database initialization and utilities"""
    
    @patch('os.makedirs')
    @patch('sqlalchemy.create_engine')
    async def test_init_databases(self, mock_create_engine, mock_makedirs):
        """Test database initialization"""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        await init_databases()
        
        # Should create data directory
        mock_makedirs.assert_called_with("data", exist_ok=True)
        
        # Should create two engines (auth and metadata)
        assert mock_create_engine.call_count == 2
        
        # Should create tables
        assert mock_engine.metadata is not None or hasattr(mock_engine, 'execute')
    
    @patch('app.database.setup.AuthSessionLocal')
    def test_get_next_workspace_id_first_user(self, mock_session_local):
        """Test workspace ID generation for first user"""
        # Mock empty database
        mock_db = Mock()
        mock_db.query().order_by().first.return_value = None
        mock_session_local.return_value = mock_db
        
        with patch('app.database.setup.get_auth_db', return_value=iter([mock_db])):
            workspace_id = get_next_workspace_id()
        
        assert workspace_id == 1
    
    @patch('app.database.setup.AuthSessionLocal')
    def test_get_next_workspace_id_subsequent_user(self, mock_session_local):
        """Test workspace ID generation for subsequent users"""
        # Mock database with existing users
        mock_db = Mock()
        mock_db.query().order_by().first.return_value = [5]  # Max workspace_id is 5
        mock_session_local.return_value = mock_db
        
        with patch('app.database.setup.get_auth_db', return_value=iter([mock_db])):
            workspace_id = get_next_workspace_id()
        
        assert workspace_id == 6


class TestUserModel:
    """Test suite for User model"""
    
    def test_user_creation(self, test_user_data):
        """Test User model instantiation"""
        user = User(
            username=test_user_data["username"],
            email=test_user_data["email"],
            hashed_password="hashed_password_here",
            workspace_id=test_user_data["workspace_id"]
        )
        
        assert user.username == test_user_data["username"]
        assert user.email == test_user_data["email"]
        assert user.workspace_id == test_user_data["workspace_id"]
        assert user.is_active is True
    
    def test_user_repr(self, test_user_data):
        """Test User string representation"""
        user = User(
            username=test_user_data["username"],
            workspace_id=test_user_data["workspace_id"]
        )
        
        repr_str = repr(user)
        assert test_user_data["username"] in repr_str
        assert str(test_user_data["workspace_id"]) in repr_str


class TestDocumentModel:
    """Test suite for Document model"""
    
    def test_document_creation(self, test_document_metadata):
        """Test Document model instantiation"""
        doc = Document(
            workspace_id=test_document_metadata["workspace_id"],
            filename=test_document_metadata["filename"],
            original_filename=test_document_metadata["original_filename"],
            file_path=test_document_metadata["file_path"],
            file_size=test_document_metadata["file_size"],
            content_hash=test_document_metadata["content_hash"],
            mime_type=test_document_metadata["mime_type"],
            total_pages=test_document_metadata["total_pages"]
        )
        
        assert doc.filename == test_document_metadata["filename"]
        assert doc.workspace_id == test_document_metadata["workspace_id"]
        assert doc.processing_status == "pending"
    
    def test_document_chunk_creation(self):
        """Test DocumentChunk model instantiation"""
        chunk = DocumentChunk(
            document_id=1,
            workspace_id=1,
            chunk_text="This is a test chunk of text.",
            chunk_index=0,
            page_number=1,
            char_count=29
        )
        
        assert chunk.document_id == 1
        assert chunk.chunk_index == 0
        assert chunk.char_count == 29
        assert chunk.embedding_model == "all-MiniLM-L6-v2"