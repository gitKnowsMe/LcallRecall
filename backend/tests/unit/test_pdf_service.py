import pytest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os
from io import BytesIO

from app.services.pdf_service import PDFService, PDFError, UnsupportedFileError


class TestPDFService:
    """Test suite for PDF text extraction service"""
    
    @pytest.fixture
    def pdf_service(self):
        """Create PDFService instance for testing"""
        return PDFService()
    
    @pytest.fixture
    def sample_pdf_content(self):
        """Sample PDF text content for testing"""
        return """Chapter 1: Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data. 
It has revolutionized many industries and continues to grow in importance.

Key concepts include:
- Supervised learning
- Unsupervised learning  
- Reinforcement learning

Chapter 2: Deep Learning

Deep learning uses neural networks with multiple layers to model complex patterns in data.
Popular frameworks include TensorFlow, PyTorch, and Keras.

Applications of deep learning:
1. Image recognition
2. Natural language processing
3. Speech recognition
4. Autonomous vehicles

Chapter 3: Implementation

When implementing machine learning models, consider the following steps:

Data Collection → Data Preprocessing → Model Training → Evaluation → Deployment

Each step is crucial for building effective ML systems."""

    @pytest.fixture
    def mock_pdf_document(self, sample_pdf_content):
        """Mock PyMuPDF document"""
        mock_doc = Mock()
        mock_doc.page_count = 3
        
        # Mock pages with text content
        pages = []
        content_parts = sample_pdf_content.split("Chapter ")
        for i, content in enumerate(content_parts[1:], 1):  # Skip first empty part
            mock_page = Mock()
            mock_page.number = i - 1  # 0-indexed
            mock_page.get_text.return_value = f"Chapter {content}"
            pages.append(mock_page)
        
        mock_doc.__iter__ = lambda self: iter(pages)
        mock_doc.close = Mock()
        return mock_doc

    # PDF File Validation Tests
    def test_validate_pdf_file_valid_extension(self, pdf_service):
        """Test PDF file validation with valid .pdf extension"""
        assert pdf_service._validate_pdf_file("document.pdf") is True
        assert pdf_service._validate_pdf_file("test.PDF") is True
        assert pdf_service._validate_pdf_file("file.with.dots.pdf") is True

    def test_validate_pdf_file_invalid_extension(self, pdf_service):
        """Test PDF file validation with invalid extensions"""
        invalid_files = [
            "document.txt",
            "image.jpg", 
            "spreadsheet.xlsx",
            "presentation.pptx",
            "document.docx",
            "file_without_extension",
            "",
            "pdf.txt"  # Extension in wrong place
        ]
        
        for filename in invalid_files:
            with pytest.raises(UnsupportedFileError, match="Only PDF files are supported"):
                pdf_service._validate_pdf_file(filename)

    def test_validate_pdf_file_none_or_empty(self, pdf_service):
        """Test PDF file validation with None or empty filename"""
        with pytest.raises(UnsupportedFileError, match="Only PDF files are supported"):
            pdf_service._validate_pdf_file(None)
        
        with pytest.raises(UnsupportedFileError, match="Only PDF files are supported"):
            pdf_service._validate_pdf_file("")

    # PDF Content Extraction Tests
    @patch('app.services.pdf_service.fitz.open')
    def test_extract_text_from_pdf_success(self, mock_fitz_open, pdf_service, mock_pdf_document, sample_pdf_content):
        """Test successful PDF text extraction"""
        mock_fitz_open.return_value = mock_pdf_document
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(b"mock pdf content")
            tmp_file.flush()
            
            try:
                result = pdf_service.extract_text_from_pdf(tmp_file.name)
                
                assert isinstance(result, dict)
                assert "text" in result
                assert "metadata" in result
                assert len(result["text"]) > 0
                assert result["metadata"]["page_count"] == 3
                assert result["metadata"]["total_chars"] > 0
                assert "Chapter 1" in result["text"]
                assert "Chapter 2" in result["text"]
                assert "Chapter 3" in result["text"]
                
                mock_pdf_document.close.assert_called_once()
                
            finally:
                os.unlink(tmp_file.name)

    def test_extract_text_from_pdf_file_not_found(self, pdf_service):
        """Test PDF extraction with non-existent file"""
        with pytest.raises(PDFError, match="File not found"):
            pdf_service.extract_text_from_pdf("nonexistent.pdf")

    def test_extract_text_from_pdf_invalid_extension(self, pdf_service):
        """Test PDF extraction with invalid file extension"""
        with pytest.raises(UnsupportedFileError, match="Only PDF files are supported"):
            pdf_service.extract_text_from_pdf("document.txt")

    @patch('app.services.pdf_service.fitz.open')
    def test_extract_text_from_pdf_corrupted_file(self, mock_fitz_open, pdf_service):
        """Test PDF extraction with corrupted PDF file"""
        mock_fitz_open.side_effect = Exception("Invalid PDF structure")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(b"corrupted content")
            tmp_file.flush()
            
            try:
                with pytest.raises(PDFError, match="Failed to extract text from PDF"):
                    pdf_service.extract_text_from_pdf(tmp_file.name)
            finally:
                os.unlink(tmp_file.name)

    @patch('app.services.pdf_service.fitz.open')
    def test_extract_text_from_pdf_empty_document(self, mock_fitz_open, pdf_service):
        """Test PDF extraction with empty document"""
        mock_doc = Mock()
        mock_doc.page_count = 0
        mock_doc.__iter__ = lambda self: iter([])
        mock_doc.close = Mock()
        mock_fitz_open.return_value = mock_doc
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            try:
                result = pdf_service.extract_text_from_pdf(tmp_file.name)
                
                assert result["text"] == ""
                assert result["metadata"]["page_count"] == 0
                assert result["metadata"]["total_chars"] == 0
                
            finally:
                os.unlink(tmp_file.name)

    # PDF Bytes Processing Tests
    @patch('app.services.pdf_service.fitz.open')
    def test_extract_text_from_pdf_bytes(self, mock_fitz_open, pdf_service, mock_pdf_document):
        """Test PDF extraction from bytes content"""
        mock_fitz_open.return_value = mock_pdf_document
        
        pdf_bytes = b"mock pdf binary content"
        result = pdf_service.extract_text_from_pdf_bytes(pdf_bytes)
        
        assert isinstance(result, dict)
        assert "text" in result
        assert "metadata" in result
        assert result["metadata"]["page_count"] == 3
        
        # Verify fitz.open was called with bytes stream
        mock_fitz_open.assert_called_once()
        args = mock_fitz_open.call_args[0]
        assert isinstance(args[0], (BytesIO, type(pdf_bytes)))

    def test_extract_text_from_pdf_bytes_empty(self, pdf_service):
        """Test PDF extraction with empty bytes"""
        with pytest.raises(PDFError, match="PDF content is empty"):
            pdf_service.extract_text_from_pdf_bytes(b"")
        
        with pytest.raises(PDFError, match="PDF content is empty"):
            pdf_service.extract_text_from_pdf_bytes(None)

    @patch('app.services.pdf_service.fitz.open')
    def test_extract_text_from_pdf_bytes_invalid(self, mock_fitz_open, pdf_service):
        """Test PDF extraction with invalid bytes content"""
        mock_fitz_open.side_effect = Exception("Invalid PDF format")
        
        with pytest.raises(PDFError, match="Failed to extract text from PDF bytes"):
            pdf_service.extract_text_from_pdf_bytes(b"invalid pdf content")

    # Metadata Extraction Tests
    @patch('app.services.pdf_service.fitz.open')
    def test_get_pdf_metadata(self, mock_fitz_open, pdf_service):
        """Test PDF metadata extraction"""
        mock_doc = Mock()
        mock_doc.page_count = 5
        mock_doc.metadata = {
            'title': 'Test Document',
            'author': 'Test Author',
            'subject': 'Testing',
            'creator': 'Test Creator',
            'producer': 'Test Producer',
            'creationDate': "D:20240101120000+00'00'",
            'modDate': "D:20240101120000+00'00'"
        }
        mock_doc.close = Mock()
        mock_fitz_open.return_value = mock_doc
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            try:
                metadata = pdf_service.get_pdf_metadata(tmp_file.name)
                
                assert metadata["page_count"] == 5
                assert metadata["title"] == "Test Document"
                assert metadata["author"] == "Test Author"
                assert metadata["subject"] == "Testing"
                assert metadata["file_size"] > 0
                
            finally:
                os.unlink(tmp_file.name)

    def test_get_pdf_metadata_file_not_found(self, pdf_service):
        """Test metadata extraction with non-existent file"""
        with pytest.raises(PDFError, match="File not found"):
            pdf_service.get_pdf_metadata("nonexistent.pdf")

    # Text Statistics Tests
    def test_calculate_text_statistics(self, pdf_service):
        """Test text statistics calculation"""
        text = """This is a test document. It contains multiple sentences.
        
        And multiple paragraphs with various content types.
        
        Numbers: 123, 456, 789
        Special characters: @#$%^&*()
        """
        
        stats = pdf_service._calculate_text_statistics(text)
        
        assert stats["total_chars"] > 0
        assert stats["total_words"] > 0
        assert stats["total_sentences"] > 0
        assert stats["total_paragraphs"] > 0
        assert stats["total_chars"] == len(text)
        assert stats["total_words"] > 10  # Should have multiple words
        assert stats["total_sentences"] >= 2  # Should detect sentences
        assert stats["total_paragraphs"] >= 2  # Should detect paragraphs

    def test_calculate_text_statistics_empty(self, pdf_service):
        """Test text statistics with empty text"""
        stats = pdf_service._calculate_text_statistics("")
        
        assert stats["total_chars"] == 0
        assert stats["total_words"] == 0
        assert stats["total_sentences"] == 0
        assert stats["total_paragraphs"] == 0

    def test_calculate_text_statistics_whitespace_only(self, pdf_service):
        """Test text statistics with only whitespace"""
        stats = pdf_service._calculate_text_statistics("   \n\n\t  ")
        
        assert stats["total_chars"] > 0  # Whitespace counts as characters
        assert stats["total_words"] == 0
        assert stats["total_sentences"] == 0
        assert stats["total_paragraphs"] == 0

    # PDF Security and Permissions Tests
    @patch('app.services.pdf_service.fitz.open')
    def test_extract_text_password_protected_pdf(self, mock_fitz_open, pdf_service):
        """Test PDF extraction with password-protected file"""
        mock_fitz_open.side_effect = Exception("Password required")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            try:
                with pytest.raises(PDFError, match="Failed to extract text from PDF"):
                    pdf_service.extract_text_from_pdf(tmp_file.name)
            finally:
                os.unlink(tmp_file.name)

    # File Size and Validation Tests
    def test_validate_file_size_within_limit(self, pdf_service):
        """Test file size validation within limits"""
        max_size = 100 * 1024 * 1024  # 100MB
        pdf_service.max_file_size = max_size
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            # Write small content
            tmp_file.write(b"small content")
            tmp_file.flush()
            
            try:
                # Should not raise exception
                pdf_service._validate_file_size(tmp_file.name)
            finally:
                os.unlink(tmp_file.name)

    def test_validate_file_size_exceeds_limit(self, pdf_service):
        """Test file size validation exceeding limits"""
        pdf_service.max_file_size = 100  # Very small limit for testing
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            # Write content exceeding limit
            tmp_file.write(b"x" * 200)
            tmp_file.flush()
            
            try:
                with pytest.raises(PDFError, match="File size exceeds maximum limit"):
                    pdf_service._validate_file_size(tmp_file.name)
            finally:
                os.unlink(tmp_file.name)

    # Error Handling and Edge Cases
    def test_extract_text_with_special_characters(self, pdf_service):
        """Test PDF extraction with special unicode characters"""
        # This would need actual PDF content with special chars
        # For now, test the text processing part
        text_with_unicode = "Test with émojis 🚀 and spëcial chars: áéíóú"
        stats = pdf_service._calculate_text_statistics(text_with_unicode)
        
        assert stats["total_chars"] > 0
        assert stats["total_words"] > 0

    def test_service_cleanup_resources(self, pdf_service):
        """Test that service properly cleans up resources"""
        # Test that cleanup methods exist and work
        assert hasattr(pdf_service, 'cleanup')
        
        # Should not raise exception
        pdf_service.cleanup()

    @patch('app.services.pdf_service.fitz.open')
    def test_extract_text_memory_management(self, mock_fitz_open, pdf_service, mock_pdf_document):
        """Test that PDF documents are properly closed after processing"""
        mock_fitz_open.return_value = mock_pdf_document
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            try:
                pdf_service.extract_text_from_pdf(tmp_file.name)
                # Verify document was closed
                mock_pdf_document.close.assert_called_once()
            finally:
                os.unlink(tmp_file.name)