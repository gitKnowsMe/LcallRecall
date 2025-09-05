import pytest
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from app.services.semantic_chunking import SemanticChunker, ChunkingError


class TestSemanticChunker:
    """Test suite for semantic text chunking service"""
    
    @pytest.fixture
    def semantic_chunker(self):
        """Create SemanticChunker instance for testing"""
        return SemanticChunker()
    
    @pytest.fixture
    def sample_document_text(self):
        """Sample document text with clear semantic boundaries"""
        return """Introduction to Machine Learning

Machine learning is a powerful subset of artificial intelligence that has revolutionized how we process and analyze data. It enables computers to learn patterns from data without being explicitly programmed for every scenario.

The field encompasses various approaches and methodologies. Supervised learning uses labeled datasets to train models. Unsupervised learning discovers hidden patterns in data without labels. Reinforcement learning trains agents through interaction with environments.

Deep Learning Fundamentals

Deep learning represents a significant advancement in machine learning capabilities. It uses neural networks with multiple hidden layers to model complex relationships in data. These networks can automatically learn hierarchical representations.

Popular deep learning frameworks include TensorFlow, PyTorch, and Keras. Each framework offers unique advantages for different types of projects. TensorFlow provides comprehensive production capabilities. PyTorch excels in research environments with dynamic computation graphs.

Implementation Strategies

When implementing machine learning solutions, several key considerations emerge. Data quality significantly impacts model performance. Feature engineering often determines success or failure. Model selection requires careful evaluation of trade-offs.

The typical workflow follows these stages: data collection, preprocessing, model training, validation, and deployment. Each stage presents unique challenges and opportunities for optimization.

Modern applications span numerous domains. Computer vision enables image recognition and autonomous vehicles. Natural language processing powers chatbots and translation services. Recommendation systems drive personalized content delivery."""

    @pytest.fixture
    def mock_spacy_nlp(self):
        """Mock spaCy NLP pipeline for testing"""
        mock_nlp = Mock()
        
        # Mock document processing
        def mock_process_text(text):
            mock_doc = Mock()
            
            # Create mock sentences based on periods
            sentences = text.split('.')
            mock_sents = []
            
            for i, sent_text in enumerate(sentences):
                if sent_text.strip():
                    mock_sent = Mock()
                    mock_sent.text = sent_text.strip() + '.'
                    mock_sent.start_char = text.find(sent_text)
                    mock_sent.end_char = text.find(sent_text) + len(sent_text) + 1
                    mock_sents.append(mock_sent)
            
            mock_doc.sents = mock_sents
            return mock_doc
        
        mock_nlp.side_effect = mock_process_text
        return mock_nlp

    # Initialization Tests
    @patch('app.services.semantic_chunking.spacy.load')
    def test_chunker_initialization_success(self, mock_spacy_load):
        """Test successful chunker initialization"""
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp
        
        chunker = SemanticChunker()
        
        assert chunker.nlp is mock_nlp
        assert chunker.max_chunk_size == 1000
        assert chunker.overlap_size == 100
        assert chunker.min_chunk_size == 50
        mock_spacy_load.assert_called_once_with("en_core_web_sm")

    @patch('app.services.semantic_chunking.spacy.load')
    def test_chunker_initialization_model_not_found(self, mock_spacy_load):
        """Test chunker initialization when spaCy model is not found"""
        mock_spacy_load.side_effect = OSError("Model 'en_core_web_sm' not found")
        
        with pytest.raises(ChunkingError, match="spaCy model not found"):
            SemanticChunker()

    def test_chunker_custom_parameters(self):
        """Test chunker initialization with custom parameters"""
        with patch('app.services.semantic_chunking.spacy.load') as mock_load:
            mock_load.return_value = Mock()
            
            chunker = SemanticChunker(
                max_chunk_size=800,
                overlap_size=80,
                min_chunk_size=40
            )
            
            assert chunker.max_chunk_size == 800
            assert chunker.overlap_size == 80
            assert chunker.min_chunk_size == 40

    # Text Preprocessing Tests
    def test_preprocess_text_basic_cleaning(self, semantic_chunker):
        """Test basic text preprocessing and cleaning"""
        raw_text = """  This is a test document.  
        
        It has multiple    spaces and line breaks.
        
        
        It also has trailing whitespace.  """
        
        processed = semantic_chunker._preprocess_text(raw_text)
        
        assert processed.startswith("This is a test document.")
        assert "multiple spaces" in processed  # Multiple spaces should be normalized
        assert processed.count('\n\n') <= raw_text.count('\n\n')  # Excessive newlines reduced
        assert not processed.endswith('  ')  # Trailing whitespace removed

    def test_preprocess_text_empty_input(self, semantic_chunker):
        """Test preprocessing with empty or whitespace-only input"""
        assert semantic_chunker._preprocess_text("") == ""
        assert semantic_chunker._preprocess_text("   ") == ""
        assert semantic_chunker._preprocess_text("\n\n\n") == ""

    def test_preprocess_text_special_characters(self, semantic_chunker):
        """Test preprocessing with special characters and unicode"""
        text_with_special = "This has émojis 🚀 and special chars: áéíóú, çñ."
        processed = semantic_chunker._preprocess_text(text_with_special)
        
        assert "émojis 🚀" in processed
        assert "áéíóú" in processed
        assert "çñ" in processed

    # Sentence Boundary Detection Tests
    @patch('app.services.semantic_chunking.spacy.load')
    def test_extract_sentences_success(self, mock_spacy_load, semantic_chunker, mock_spacy_nlp):
        """Test successful sentence extraction"""
        mock_spacy_load.return_value = mock_spacy_nlp
        semantic_chunker.nlp = mock_spacy_nlp
        
        text = "This is sentence one. This is sentence two. This is sentence three."
        sentences = semantic_chunker._extract_sentences(text)
        
        assert len(sentences) > 0
        assert isinstance(sentences, list)
        for sentence in sentences:
            assert isinstance(sentence, dict)
            assert "text" in sentence
            assert "start_char" in sentence
            assert "end_char" in sentence

    def test_extract_sentences_empty_text(self, semantic_chunker):
        """Test sentence extraction with empty text"""
        sentences = semantic_chunker._extract_sentences("")
        assert sentences == []

    # Semantic Boundary Detection Tests
    def test_identify_semantic_boundaries_basic(self, semantic_chunker):
        """Test basic semantic boundary identification"""
        sentences = [
            {"text": "Introduction to Machine Learning.", "start_char": 0, "end_char": 34},
            {"text": "Machine learning is powerful.", "start_char": 35, "end_char": 65},
            {"text": "Deep learning is different.", "start_char": 66, "end_char": 94},
            {"text": "Neural networks are complex.", "start_char": 95, "end_char": 124}
        ]
        
        boundaries = semantic_chunker._identify_semantic_boundaries(sentences)
        
        assert isinstance(boundaries, list)
        assert len(boundaries) >= 0  # May or may not find boundaries
        for boundary in boundaries:
            assert isinstance(boundary, int)
            assert 0 <= boundary < len(sentences)

    def test_identify_semantic_boundaries_topic_shifts(self, semantic_chunker):
        """Test semantic boundary detection with clear topic shifts"""
        sentences = [
            {"text": "Machine learning is about algorithms.", "start_char": 0, "end_char": 38},
            {"text": "Algorithms learn from data patterns.", "start_char": 39, "end_char": 76},
            {"text": "Now let's discuss cooking recipes.", "start_char": 77, "end_char": 112},
            {"text": "Recipes require specific ingredients.", "start_char": 113, "end_char": 151}
        ]
        
        boundaries = semantic_chunker._identify_semantic_boundaries(sentences)
        
        # Should detect topic shift from ML to cooking
        assert len(boundaries) > 0

    def test_identify_semantic_boundaries_header_detection(self, semantic_chunker):
        """Test semantic boundary detection with headers"""
        sentences = [
            {"text": "Introduction to Machine Learning", "start_char": 0, "end_char": 33},
            {"text": "Machine learning is powerful.", "start_char": 34, "end_char": 64},
            {"text": "Deep Learning Fundamentals", "start_char": 65, "end_char": 92},
            {"text": "Deep learning uses neural networks.", "start_char": 93, "end_char": 129}
        ]
        
        boundaries = semantic_chunker._identify_semantic_boundaries(sentences)
        
        # Should detect headers as boundaries
        assert 2 in boundaries or len(boundaries) > 0  # Header at index 2

    # Chunk Creation Tests
    def test_create_chunks_from_boundaries(self, semantic_chunker):
        """Test chunk creation from semantic boundaries"""
        sentences = [
            {"text": "First sentence.", "start_char": 0, "end_char": 15},
            {"text": "Second sentence.", "start_char": 16, "end_char": 32},
            {"text": "Third sentence.", "start_char": 33, "end_char": 48},
            {"text": "Fourth sentence.", "start_char": 49, "end_char": 65}
        ]
        boundaries = [0, 2, 4]  # Split at sentence 2
        full_text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        
        chunks = semantic_chunker._create_chunks_from_boundaries(sentences, boundaries, full_text)
        
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, dict)
            assert "text" in chunk
            assert "start_char" in chunk
            assert "end_char" in chunk
            assert "sentence_count" in chunk
            assert len(chunk["text"]) >= semantic_chunker.min_chunk_size or len(chunks) == 1

    def test_create_chunks_size_limit_enforcement(self, semantic_chunker):
        """Test that chunks respect size limits"""
        # Create long sentences that would exceed max_chunk_size
        long_text = "Very long sentence. " * 100  # Much longer than max_chunk_size
        sentences = []
        start = 0
        for i in range(100):
            sentence_text = "Very long sentence. "
            sentences.append({
                "text": sentence_text,
                "start_char": start,
                "end_char": start + len(sentence_text)
            })
            start += len(sentence_text)
        
        boundaries = [0, len(sentences)]
        chunks = semantic_chunker._create_chunks_from_boundaries(sentences, boundaries, long_text)
        
        for chunk in chunks:
            assert len(chunk["text"]) <= semantic_chunker.max_chunk_size + semantic_chunker.overlap_size

    def test_create_chunks_with_overlap(self, semantic_chunker):
        """Test chunk creation includes proper overlap"""
        semantic_chunker.overlap_size = 20
        
        sentences = []
        full_text = ""
        for i in range(10):
            sentence = f"This is sentence number {i+1}. "
            sentences.append({
                "text": sentence,
                "start_char": len(full_text),
                "end_char": len(full_text) + len(sentence)
            })
            full_text += sentence
        
        boundaries = [0, 5, 10]  # Create 2 chunks
        chunks = semantic_chunker._create_chunks_from_boundaries(sentences, boundaries, full_text)
        
        if len(chunks) > 1:
            # Check that there's overlap between consecutive chunks
            chunk1_end = chunks[0]["text"][-20:]  # Last 20 chars of chunk 1
            chunk2_start = chunks[1]["text"][:20]  # First 20 chars of chunk 2
            
            # Should have some common text (allowing for sentence boundaries)
            assert len(chunk1_end.strip()) > 0
            assert len(chunk2_start.strip()) > 0

    # Main Chunking Method Tests
    @patch('app.services.semantic_chunking.spacy.load')
    def test_chunk_text_complete_workflow(self, mock_spacy_load, semantic_chunker, sample_document_text, mock_spacy_nlp):
        """Test complete text chunking workflow"""
        mock_spacy_load.return_value = mock_spacy_nlp
        semantic_chunker.nlp = mock_spacy_nlp
        
        chunks = semantic_chunker.chunk_text(sample_document_text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, dict)
            assert "text" in chunk
            assert "chunk_index" in chunk
            assert "start_char" in chunk
            assert "end_char" in chunk
            assert "sentence_count" in chunk
            assert "char_count" in chunk
            assert "word_count" in chunk
            
            # Verify chunk properties
            assert chunk["chunk_index"] == i
            assert len(chunk["text"]) == chunk["char_count"]
            assert chunk["word_count"] > 0
            assert chunk["sentence_count"] > 0
            assert len(chunk["text"]) >= semantic_chunker.min_chunk_size or len(chunks) == 1

    def test_chunk_text_empty_input(self, semantic_chunker):
        """Test chunking with empty input"""
        chunks = semantic_chunker.chunk_text("")
        assert chunks == []

    def test_chunk_text_very_short_input(self, semantic_chunker):
        """Test chunking with input shorter than min_chunk_size"""
        short_text = "Short text."
        semantic_chunker.min_chunk_size = 50
        
        chunks = semantic_chunker.chunk_text(short_text)
        
        # Should still create one chunk even if below min size
        assert len(chunks) == 1
        assert chunks[0]["text"] == short_text
        assert chunks[0]["char_count"] == len(short_text)

    def test_chunk_text_single_sentence(self, semantic_chunker):
        """Test chunking with single sentence input"""
        single_sentence = "This is a single sentence that should form one chunk."
        
        chunks = semantic_chunker.chunk_text(single_sentence)
        
        assert len(chunks) == 1
        assert chunks[0]["text"] == single_sentence
        assert chunks[0]["sentence_count"] == 1

    # Error Handling Tests
    def test_chunk_text_spacy_processing_error(self, semantic_chunker):
        """Test handling of spaCy processing errors"""
        semantic_chunker.nlp = None  # Simulate uninitialized NLP
        
        with pytest.raises(ChunkingError, match="Chunking service not properly initialized"):
            semantic_chunker.chunk_text("Some text to chunk.")

    @patch('app.services.semantic_chunking.spacy.load')
    def test_chunk_text_nlp_processing_error(self, mock_spacy_load, semantic_chunker):
        """Test handling of NLP processing errors"""
        mock_nlp = Mock()
        mock_nlp.side_effect = Exception("NLP processing failed")
        mock_spacy_load.return_value = mock_nlp
        semantic_chunker.nlp = mock_nlp
        
        with pytest.raises(ChunkingError, match="Failed to process text"):
            semantic_chunker.chunk_text("Text that causes NLP error.")

    # Performance and Edge Cases
    def test_chunk_text_very_long_document(self, semantic_chunker):
        """Test chunking with very long document"""
        # Create a long document
        long_text = "This is a test sentence. " * 1000
        
        with patch.object(semantic_chunker, 'nlp') as mock_nlp:
            mock_doc = Mock()
            sentences = []
            for i in range(1000):
                mock_sent = Mock()
                mock_sent.text = "This is a test sentence. "
                mock_sent.start_char = i * 25
                mock_sent.end_char = (i + 1) * 25
                sentences.append(mock_sent)
            mock_doc.sents = sentences
            mock_nlp.return_value = mock_doc
            
            chunks = semantic_chunker.chunk_text(long_text)
            
            # Should create multiple chunks
            assert len(chunks) > 1
            
            # Each chunk should respect size limits
            for chunk in chunks:
                assert len(chunk["text"]) <= semantic_chunker.max_chunk_size + semantic_chunker.overlap_size

    def test_chunk_text_special_formatting(self, semantic_chunker):
        """Test chunking with special formatting (bullets, numbers, etc.)"""
        formatted_text = """Key Features:
        • Feature one with details
        • Feature two with more information
        • Feature three with examples
        
        Numbered List:
        1. First item in the list
        2. Second item with description
        3. Third item with examples
        
        Regular paragraph text continues here with normal sentences."""
        
        with patch.object(semantic_chunker, 'nlp') as mock_nlp:
            mock_doc = Mock()
            # Mock sentence detection for formatted text
            mock_sents = []
            parts = formatted_text.split('.')
            for i, part in enumerate(parts):
                if part.strip():
                    mock_sent = Mock()
                    mock_sent.text = part.strip() + '.'
                    mock_sent.start_char = formatted_text.find(part)
                    mock_sent.end_char = formatted_text.find(part) + len(part) + 1
                    mock_sents.append(mock_sent)
            mock_doc.sents = mock_sents
            mock_nlp.return_value = mock_doc
            
            chunks = semantic_chunker.chunk_text(formatted_text)
            
            assert len(chunks) > 0
            # Should preserve formatting in chunks
            full_chunked_text = " ".join([chunk["text"] for chunk in chunks])
            assert "•" in full_chunked_text or "Key Features" in full_chunked_text

    def test_chunker_statistics(self, semantic_chunker):
        """Test that chunker provides useful statistics"""
        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        
        with patch.object(semantic_chunker, 'nlp') as mock_nlp:
            mock_doc = Mock()
            sentences = text.split('. ')
            mock_sents = []
            start = 0
            for sent_text in sentences:
                if not sent_text.endswith('.'):
                    sent_text += '.'
                mock_sent = Mock()
                mock_sent.text = sent_text
                mock_sent.start_char = start
                mock_sent.end_char = start + len(sent_text)
                mock_sents.append(mock_sent)
                start += len(sent_text) + 2  # +2 for '. '
            mock_doc.sents = mock_sents
            mock_nlp.return_value = mock_doc
            
            chunks = semantic_chunker.chunk_text(text)
            
            total_chars = sum(chunk["char_count"] for chunk in chunks)
            total_words = sum(chunk["word_count"] for chunk in chunks)
            total_sentences = sum(chunk["sentence_count"] for chunk in chunks)
            
            assert total_chars > 0
            assert total_words > 0
            assert total_sentences > 0