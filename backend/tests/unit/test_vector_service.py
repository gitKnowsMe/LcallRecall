import pytest
from unittest.mock import Mock, patch, AsyncMock
import numpy as np
import tempfile
import os

from app.services.vector_service import VectorStoreManager


class TestVectorStoreManager:
    """Test suite for VectorStoreManager"""
    
    @pytest.fixture
    def vector_manager(self, mock_embedding_model):
        """Create VectorStoreManager instance with mocked embedding model"""
        manager = VectorStoreManager()
        manager.embedding_model = mock_embedding_model
        return manager
    
    def test_initialization(self):
        """Test VectorStoreManager initialization"""
        manager = VectorStoreManager()
        assert manager.embedding_model is None
        assert manager.workspace_indices == {}
        assert manager.workspace_metadata == {}
        assert manager.embedding_dim == 384
    
    @patch('app.services.vector_service.SentenceTransformer')
    async def test_initialize_embedding_model(self, mock_sentence_transformer):
        """Test embedding model initialization"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model
        
        manager = VectorStoreManager()
        await manager.initialize()
        
        assert manager.embedding_model is mock_model
        mock_sentence_transformer.assert_called_once_with('sentence-transformers/all-MiniLM-L6-v2')
    
    def test_get_workspace_path(self, vector_manager, test_data_dir):
        """Test workspace path generation"""
        with patch('os.makedirs') as mock_makedirs:
            path = vector_manager.get_workspace_path("123")
            expected = "data/workspaces/workspace_123"
            assert path == expected
            mock_makedirs.assert_called_once()
    
    def test_get_index_path(self, vector_manager):
        """Test FAISS index path generation"""
        path = vector_manager.get_index_path("123")
        expected = "data/workspaces/workspace_123/faiss_index.bin"
        assert path == expected
    
    def test_get_metadata_path(self, vector_manager):
        """Test metadata path generation"""
        path = vector_manager.get_metadata_path("123")
        expected = "data/workspaces/workspace_123/metadata.pkl"
        assert path == expected
    
    @patch('faiss.IndexFlatL2')
    @patch('os.path.exists')
    async def test_load_workspace_new(self, mock_exists, mock_faiss_constructor, vector_manager, mock_faiss_index):
        """Test loading new workspace (creates new index)"""
        mock_exists.return_value = False
        mock_faiss_constructor.return_value = mock_faiss_index
        
        result = await vector_manager.load_workspace("123")
        
        assert result is True
        assert "123" in vector_manager.workspace_indices
        assert "123" in vector_manager.workspace_metadata
        mock_faiss_constructor.assert_called_once_with(384)
    
    @patch('faiss.read_index')
    @patch('os.path.exists')
    @patch('builtins.open', create=True)
    @patch('pickle.load')
    async def test_load_workspace_existing(self, mock_pickle, mock_open, mock_exists, mock_read_index, vector_manager, mock_faiss_index):
        """Test loading existing workspace"""
        mock_exists.return_value = True
        mock_read_index.return_value = mock_faiss_index
        mock_pickle.return_value = [{"id": 1, "text": "test"}]
        
        result = await vector_manager.load_workspace("123")
        
        assert result is True
        assert "123" in vector_manager.workspace_indices
        mock_read_index.assert_called_once()
    
    async def test_embed_texts(self, vector_manager):
        """Test text embedding generation"""
        texts = ["This is test text 1", "This is test text 2"]
        
        embeddings = await vector_manager.embed_texts(texts)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (2, 384)  # 2 texts, 384 dimensions
        assert embeddings.dtype == np.float32
    
    @patch('faiss.IndexFlatL2')
    @patch('os.path.exists')
    async def test_add_documents(self, mock_exists, mock_faiss_constructor, vector_manager, mock_faiss_index):
        """Test adding documents to workspace"""
        mock_exists.return_value = False
        mock_faiss_constructor.return_value = mock_faiss_index
        mock_faiss_index.ntotal = 0
        
        texts = ["Document 1 content", "Document 2 content"]
        metadata = [
            {"filename": "doc1.pdf", "page": 1},
            {"filename": "doc2.pdf", "page": 1}
        ]
        
        with patch.object(vector_manager, 'save_workspace', new_callable=AsyncMock):
            doc_ids = await vector_manager.add_documents("123", texts, metadata)
        
        assert len(doc_ids) == 2
        assert doc_ids == [0, 1]
        mock_faiss_index.add.assert_called_once()
        assert len(vector_manager.workspace_metadata["123"]) == 2
    
    @patch('faiss.IndexFlatL2')
    @patch('os.path.exists')
    async def test_search(self, mock_exists, mock_faiss_constructor, vector_manager, mock_faiss_index):
        """Test vector similarity search"""
        mock_exists.return_value = False
        mock_faiss_constructor.return_value = mock_faiss_index
        
        # Setup mock search results
        mock_faiss_index.search.return_value = (
            np.array([[0.1, 0.2, 0.3]]),  # distances (L2)
            np.array([[0, 1, 2]])         # indices
        )
        
        # Setup workspace metadata
        vector_manager.workspace_indices["123"] = mock_faiss_index
        vector_manager.workspace_metadata["123"] = [
            {"id": 0, "text": "First document", "filename": "doc1.pdf"},
            {"id": 1, "text": "Second document", "filename": "doc2.pdf"},
            {"id": 2, "text": "Third document", "filename": "doc3.pdf"}
        ]
        
        results = await vector_manager.search("123", "test query", k=3)
        
        assert len(results) <= 3
        assert all("similarity" in result for result in results)
        assert all("rank" in result for result in results)
    
    async def test_get_workspace_stats(self, vector_manager, mock_faiss_index):
        """Test workspace statistics retrieval"""
        vector_manager.workspace_indices["123"] = mock_faiss_index
        vector_manager.workspace_metadata["123"] = [{"id": 1}, {"id": 2}]
        mock_faiss_index.ntotal = 2
        
        stats = await vector_manager.get_workspace_stats("123")
        
        assert stats["workspace_id"] == "123"
        assert stats["total_documents"] == 2
        assert stats["faiss_vectors"] == 2
        assert stats["embedding_dimension"] == 384