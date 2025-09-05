import pytest
from unittest.mock import Mock, patch

from app.services.llm_service import ModelManager


class TestModelManager:
    """Test suite for ModelManager singleton"""
    
    def setup_method(self):
        """Reset singleton for each test"""
        ModelManager._instance = None
        ModelManager._model = None
        ModelManager._executor = None
    
    def test_singleton_pattern(self):
        """Test that ModelManager follows singleton pattern"""
        manager1 = ModelManager()
        manager2 = ModelManager()
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    @patch('os.path.exists')
    @patch('app.services.llm_service.Llama')
    async def test_initialize_success(self, mock_llama, mock_exists, mock_phi2_model):
        """Test successful model initialization"""
        # Setup mocks
        mock_exists.return_value = True
        mock_llama.return_value = mock_phi2_model
        
        # Test
        manager = ModelManager()
        result = await manager.initialize()
        
        # Assertions
        assert result is True
        assert manager.is_loaded() is True
        mock_llama.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('os.path.exists')
    async def test_initialize_model_not_found(self, mock_exists):
        """Test initialization failure when model file not found"""
        mock_exists.return_value = False
        
        manager = ModelManager()
        result = await manager.initialize()
        
        assert result is False
        assert manager.is_loaded() is False
    
    @pytest.mark.asyncio
    @patch('os.path.exists')
    @patch('app.services.llm_service.Llama')
    async def test_initialize_load_error(self, mock_llama, mock_exists):
        """Test initialization failure when model loading fails"""
        mock_exists.return_value = True
        mock_llama.side_effect = Exception("Model loading failed")
        
        manager = ModelManager()
        result = await manager.initialize()
        
        assert result is False
        assert manager.is_loaded() is False
    
    @pytest.mark.asyncio
    async def test_generate_without_model(self):
        """Test generate fails when model not loaded"""
        manager = ModelManager()
        
        with pytest.raises(RuntimeError, match="Model not loaded"):
            await manager.generate("test prompt")
    
    @pytest.mark.asyncio
    @patch('os.path.exists')
    @patch('app.services.llm_service.Llama')
    async def test_generate_success(self, mock_llama, mock_exists, mock_phi2_model):
        """Test successful text generation"""
        # Setup
        mock_exists.return_value = True
        mock_llama.return_value = mock_phi2_model
        
        manager = ModelManager()
        await manager.initialize()
        
        # Test
        result = await manager.generate("test prompt", max_tokens=100)
        
        # Assertions
        assert isinstance(result, str)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_generate_stream_without_model(self):
        """Test streaming generate fails when model not loaded"""
        manager = ModelManager()
        
        with pytest.raises(RuntimeError, match="Model not loaded"):
            async for _ in manager.generate_stream("test prompt"):
                pass
    
    def test_create_rag_prompt(self):
        """Test RAG prompt creation"""
        manager = ModelManager()
        
        query = "What is machine learning?"
        context = "Machine learning is a subset of AI..."
        
        prompt = manager.create_rag_prompt(query, context)
        
        assert "<|system|>" in prompt
        assert "<|user|>" in prompt
        assert "<|assistant|>" in prompt
        assert query in prompt
        assert context in prompt
    
    @pytest.mark.asyncio
    @patch('os.path.exists')
    @patch('app.services.llm_service.Llama')
    async def test_cleanup(self, mock_llama, mock_exists, mock_phi2_model):
        """Test proper cleanup of resources"""
        mock_exists.return_value = True
        mock_llama.return_value = mock_phi2_model
        
        manager = ModelManager()
        await manager.initialize()
        
        # Should not raise an error
        await manager.cleanup()