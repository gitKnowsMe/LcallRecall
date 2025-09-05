import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import numpy as np

# Test configuration
@pytest.fixture(scope="session")
def test_data_dir():
    """Create temporary test data directory"""
    temp_dir = tempfile.mkdtemp(prefix="localrecall_test_")
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture(scope="session")
def mock_phi2_model():
    """Mock Phi-2 model for testing"""
    mock_model = Mock()
    mock_model.return_value = {
        'choices': [{'text': 'This is a test response from Phi-2'}]
    }
    return mock_model

@pytest.fixture
def mock_embedding_model():
    """Mock embedding model for testing"""
    mock_model = Mock()
    # Return consistent embeddings for testing
    mock_model.encode.return_value = np.array([
        [0.1, 0.2, 0.3] * 128,  # 384 dimensions for all-MiniLM-L6-v2
        [0.4, 0.5, 0.6] * 128
    ], dtype=np.float32)
    return mock_model

@pytest.fixture
def sample_pdf_content():
    """Sample PDF text content for testing"""
    return """
    Chapter 1: Introduction
    
    This is a test document for the LocalRecall RAG system.
    It contains multiple paragraphs and sections to test
    the semantic chunking functionality.
    
    The document discusses various topics including:
    - Machine learning concepts
    - Vector databases
    - Text processing techniques
    
    Chapter 2: Implementation Details
    
    The implementation uses several key components:
    1. FastAPI for the web framework
    2. FAISS for vector similarity search
    3. Phi-2 for language generation
    4. SQLite for metadata storage
    
    This allows for efficient document retrieval and generation.
    """

@pytest.fixture
def test_user_data():
    """Sample user data for testing"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123",
        "workspace_id": 1
    }

@pytest.fixture
def test_document_metadata():
    """Sample document metadata for testing"""
    return {
        "filename": "test_document.pdf",
        "original_filename": "test_document.pdf",
        "file_path": "/tmp/test_document.pdf",
        "file_size": 1024,
        "content_hash": "abc123def456",
        "mime_type": "application/pdf",
        "total_pages": 2,
        "workspace_id": 1
    }

@pytest.fixture
def mock_faiss_index():
    """Mock FAISS index for testing"""
    mock_index = Mock()
    mock_index.ntotal = 0
    mock_index.add = Mock()
    mock_index.search = Mock(return_value=(
        np.array([[0.1, 0.2, 0.3]]),  # distances
        np.array([[0, 1, 2]])         # indices
    ))
    return mock_index