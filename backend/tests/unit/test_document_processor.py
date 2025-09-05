import pytest
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os
import hashlib
from datetime import datetime

from app.services.document_processor import DocumentProcessor, DocumentProcessingError
from app.models.document import Document, DocumentChunk


class TestDocumentProcessor:
    """Test suite for document processing pipeline"""
    
    @pytest.fixture
    def document_processor(self):
        """Create DocumentProcessor instance for testing"""
        return DocumentProcessor()
    
    @pytest.fixture
    def mock_pdf_service(self):
        """Mock PDF service"""
        service = Mock()
        service.extract_text_from_pdf.return_value = {
            "text": "Sample extracted text from PDF document. This contains multiple sentences for testing.",
            "metadata": {
                "page_count": 2,
                "total_chars": 85,
                "total_words": 12,
                "total_sentences": 2,
                "total_paragraphs": 1
            }
        }
        service.get_pdf_metadata.return_value = {
            "title": "Test Document",
            "author": "Test Author",
            "page_count": 2,
            "file_size": 1024
        }
        return service
    
    @pytest.fixture
    def mock_chunker_service(self):
        """Mock semantic chunking service"""
        service = Mock()
        service.chunk_text.return_value = [
            {
                "text": "Sample extracted text from PDF document.",
                "chunk_index": 0,
                "start_char": 0,
                "end_char": 42,
                "sentence_count": 1,
                "char_count": 42,
                "word_count": 7
            },
            {
                "text": "This contains multiple sentences for testing.",
                "chunk_index": 1,
                "start_char": 43,
                "end_char": 88,
                "sentence_count": 1,
                "char_count": 45,
                "word_count": 7
            }
        ]
        return service
    
    @pytest.fixture
    def mock_vector_service(self):
        """Mock vector store service"""
        service = Mock()
        service.add_documents = AsyncMock(return_value=[1, 2])
        return service
    
    @pytest.fixture
    def mock_metadata_db(self):
        """Mock metadata database session"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.close = Mock()
        return db
    
    @pytest.fixture
    def sample_pdf_file(self):
        """Create a temporary PDF file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(b"Mock PDF content for testing")
            tmp_file.flush()
            yield tmp_file.name
        os.unlink(tmp_file.name)

    # Initialization Tests
    def test_processor_initialization(self, document_processor):
        """Test document processor initialization"""
        assert document_processor.pdf_service is not None
        assert document_processor.chunker_service is not None
        assert hasattr(document_processor, 'max_file_size')
        assert hasattr(document_processor, 'supported_extensions')

    def test_processor_custom_configuration(self):
        """Test processor with custom configuration"""
        config = {
            'max_file_size': 50 * 1024 * 1024,  # 50MB
            'max_chunk_size': 800,
            'chunk_overlap': 80
        }
        
        processor = DocumentProcessor(config=config)
        
        assert processor.max_file_size == 50 * 1024 * 1024
        assert processor.chunker_service.max_chunk_size == 800
        assert processor.chunker_service.overlap_size == 80

    # File Validation Tests
    def test_validate_file_valid_pdf(self, document_processor, sample_pdf_file):
        """Test file validation with valid PDF"""
        result = document_processor._validate_file(sample_pdf_file, "document.pdf")
        
        assert result["is_valid"] is True
        assert result["file_size"] > 0
        assert result["content_hash"] is not None
        assert len(result["content_hash"]) == 64  # SHA256 hash

    def test_validate_file_invalid_extension(self, document_processor):
        """Test file validation with invalid extension"""
        with pytest.raises(DocumentProcessingError, match="Unsupported file type"):
            document_processor._validate_file("/fake/path.txt", "document.txt")

    def test_validate_file_not_found(self, document_processor):
        """Test file validation with non-existent file"""
        with pytest.raises(DocumentProcessingError, match="File not found"):
            document_processor._validate_file("/nonexistent/file.pdf", "document.pdf")

    def test_validate_file_size_limit(self, document_processor, sample_pdf_file):
        """Test file validation with size limit exceeded"""
        document_processor.max_file_size = 10  # Very small limit
        
        with pytest.raises(DocumentProcessingError, match="File size exceeds maximum limit"):
            document_processor._validate_file(sample_pdf_file, "document.pdf")

    def test_calculate_file_hash(self, document_processor, sample_pdf_file):
        """Test file hash calculation"""
        hash1 = document_processor._calculate_file_hash(sample_pdf_file)
        hash2 = document_processor._calculate_file_hash(sample_pdf_file)
        
        assert hash1 == hash2  # Same file should have same hash
        assert len(hash1) == 64  # SHA256 hash length
        assert isinstance(hash1, str)

    def test_calculate_file_hash_different_files(self, document_processor):
        """Test that different files have different hashes"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp1:
            tmp1.write(b"Content 1")
            tmp1.flush()
            tmp1_name = tmp1.name
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp2:
            tmp2.write(b"Content 2")
            tmp2.flush()
            tmp2_name = tmp2.name
        
        try:
            hash1 = document_processor._calculate_file_hash(tmp1_name)
            hash2 = document_processor._calculate_file_hash(tmp2_name)
            
            assert hash1 != hash2
        finally:
            os.unlink(tmp1_name)
            os.unlink(tmp2_name)

    # Document Processing Tests
    @patch('app.services.document_processor.get_metadata_db')
    async def test_process_document_success(self, mock_get_db, document_processor, sample_pdf_file, 
                                          mock_pdf_service, mock_chunker_service, mock_vector_service, mock_metadata_db):
        """Test successful document processing"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_metadata_db])
        document_processor.pdf_service = mock_pdf_service
        document_processor.chunker_service = mock_chunker_service
        
        with patch.object(document_processor, 'vector_service', mock_vector_service):
            result = await document_processor.process_document(
                file_path=sample_pdf_file,
                filename="test_document.pdf",
                workspace_id=1,
                user_id=1
            )
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "document_id" in result
        assert "filename" in result
        assert "total_chunks" in result
        assert "processing_status" in result
        assert "metadata" in result
        
        assert result["filename"] == "test_document.pdf"
        assert result["total_chunks"] == 2
        assert result["processing_status"] == "completed"
        
        # Verify service calls
        mock_pdf_service.extract_text_from_pdf.assert_called_once_with(sample_pdf_file)
        mock_chunker_service.chunk_text.assert_called_once()
        mock_vector_service.add_documents.assert_called_once()
        
        # Verify database operations
        mock_metadata_db.add.assert_called()
        mock_metadata_db.commit.assert_called()

    @patch('app.services.document_processor.get_metadata_db')
    async def test_process_document_pdf_extraction_failure(self, mock_get_db, document_processor, 
                                                         sample_pdf_file, mock_metadata_db):
        """Test document processing with PDF extraction failure"""
        mock_get_db.return_value = iter([mock_metadata_db])
        
        # Mock PDF service to raise exception
        document_processor.pdf_service = Mock()
        document_processor.pdf_service.extract_text_from_pdf.side_effect = Exception("PDF extraction failed")
        
        with pytest.raises(DocumentProcessingError, match="Failed to extract text from PDF"):
            await document_processor.process_document(
                file_path=sample_pdf_file,
                filename="test_document.pdf",
                workspace_id=1,
                user_id=1
            )

    @patch('app.services.document_processor.get_metadata_db')
    async def test_process_document_chunking_failure(self, mock_get_db, document_processor, 
                                                   sample_pdf_file, mock_pdf_service, mock_metadata_db):
        """Test document processing with chunking failure"""
        mock_get_db.return_value = iter([mock_metadata_db])
        document_processor.pdf_service = mock_pdf_service
        
        # Mock chunker service to raise exception
        document_processor.chunker_service = Mock()
        document_processor.chunker_service.chunk_text.side_effect = Exception("Chunking failed")
        
        with pytest.raises(DocumentProcessingError, match="Failed to chunk document text"):
            await document_processor.process_document(
                file_path=sample_pdf_file,
                filename="test_document.pdf",
                workspace_id=1,
                user_id=1
            )

    @patch('app.services.document_processor.get_metadata_db')
    async def test_process_document_vector_storage_failure(self, mock_get_db, document_processor, 
                                                         sample_pdf_file, mock_pdf_service, 
                                                         mock_chunker_service, mock_metadata_db):
        """Test document processing with vector storage failure"""
        mock_get_db.return_value = iter([mock_metadata_db])
        document_processor.pdf_service = mock_pdf_service
        document_processor.chunker_service = mock_chunker_service
        
        # Mock vector service to raise exception
        mock_vector_service = Mock()
        mock_vector_service.add_documents = AsyncMock(side_effect=Exception("Vector storage failed"))
        
        with patch.object(document_processor, 'vector_service', mock_vector_service):
            with pytest.raises(DocumentProcessingError, match="Failed to store document vectors"):
                await document_processor.process_document(
                    file_path=sample_pdf_file,
                    filename="test_document.pdf",
                    workspace_id=1,
                    user_id=1
                )

    # Document Metadata Creation Tests
    def test_create_document_metadata(self, document_processor, sample_pdf_file):
        """Test document metadata creation"""
        pdf_metadata = {
            "page_count": 3,
            "title": "Test Document",
            "author": "Test Author"
        }
        
        document = document_processor._create_document_metadata(
            filename="test.pdf",
            original_filename="original_test.pdf",
            file_path=sample_pdf_file,
            file_size=1024,
            content_hash="abc123",
            workspace_id=1,
            pdf_metadata=pdf_metadata
        )
        
        assert isinstance(document, Document)
        assert document.filename == "test.pdf"
        assert document.original_filename == "original_test.pdf"
        assert document.file_path == sample_pdf_file
        assert document.file_size == 1024
        assert document.content_hash == "abc123"
        assert document.workspace_id == 1
        assert document.total_pages == 3
        assert document.mime_type == "application/pdf"
        assert document.processing_status == "pending"

    def test_create_document_chunks_metadata(self, document_processor):
        """Test document chunks metadata creation"""
        chunks_data = [
            {
                "text": "First chunk text",
                "chunk_index": 0,
                "start_char": 0,
                "end_char": 16,
                "sentence_count": 1,
                "char_count": 16,
                "word_count": 3
            },
            {
                "text": "Second chunk text",
                "chunk_index": 1,
                "start_char": 17,
                "end_char": 34,
                "sentence_count": 1,
                "char_count": 17,
                "word_count": 3
            }
        ]
        
        vector_ids = [10, 11]
        
        chunks = document_processor._create_document_chunks_metadata(
            document_id=1,
            workspace_id=1,
            chunks_data=chunks_data,
            vector_ids=vector_ids
        )
        
        assert len(chunks) == 2
        
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, DocumentChunk)
            assert chunk.document_id == 1
            assert chunk.workspace_id == 1
            assert chunk.chunk_index == i
            assert chunk.vector_id == vector_ids[i]
            assert chunk.char_count == chunks_data[i]["char_count"]
            assert chunk.embedding_model == "all-MiniLM-L6-v2"

    # Document Status Management Tests
    @patch('app.services.document_processor.get_metadata_db')
    async def test_update_document_status_success(self, mock_get_db, document_processor, mock_metadata_db):
        """Test updating document processing status to success"""
        mock_get_db.return_value = iter([mock_metadata_db])
        
        mock_document = Mock(spec=Document)
        mock_metadata_db.query().filter().first.return_value = mock_document
        
        await document_processor._update_document_status(
            document_id=1,
            status="completed",
            total_chunks=5,
            error_message=None
        )
        
        assert mock_document.processing_status == "completed"
        assert mock_document.total_chunks == 5
        assert mock_document.error_message is None
        assert mock_document.processed_at is not None
        mock_metadata_db.commit.assert_called_once()

    @patch('app.services.document_processor.get_metadata_db')
    async def test_update_document_status_failure(self, mock_get_db, document_processor, mock_metadata_db):
        """Test updating document processing status to failed"""
        mock_get_db.return_value = iter([mock_metadata_db])
        
        mock_document = Mock(spec=Document)
        mock_metadata_db.query().filter().first.return_value = mock_document
        
        await document_processor._update_document_status(
            document_id=1,
            status="failed",
            error_message="Processing failed"
        )
        
        assert mock_document.processing_status == "failed"
        assert mock_document.error_message == "Processing failed"
        mock_metadata_db.commit.assert_called_once()

    # Duplicate Document Detection Tests
    @patch('app.services.document_processor.get_metadata_db')
    async def test_check_duplicate_document_exists(self, mock_get_db, document_processor, mock_metadata_db):
        """Test duplicate document detection when document exists"""
        mock_get_db.return_value = iter([mock_metadata_db])
        
        existing_doc = Mock()
        existing_doc.id = 123
        existing_doc.filename = "existing.pdf"
        mock_metadata_db.query().filter().first.return_value = existing_doc
        
        result = await document_processor._check_duplicate_document(
            content_hash="abc123",
            workspace_id=1
        )
        
        assert result is not None
        assert result.id == 123
        assert result.filename == "existing.pdf"

    @patch('app.services.document_processor.get_metadata_db')
    async def test_check_duplicate_document_not_exists(self, mock_get_db, document_processor, mock_metadata_db):
        """Test duplicate document detection when document doesn't exist"""
        mock_get_db.return_value = iter([mock_metadata_db])
        mock_metadata_db.query().filter().first.return_value = None
        
        result = await document_processor._check_duplicate_document(
            content_hash="xyz789",
            workspace_id=1
        )
        
        assert result is None

    # Document Deletion Tests
    @patch('app.services.document_processor.get_metadata_db')
    async def test_delete_document_success(self, mock_get_db, document_processor, mock_metadata_db):
        """Test successful document deletion"""
        mock_get_db.return_value = iter([mock_metadata_db])
        
        # Mock document and chunks
        mock_document = Mock()
        mock_document.id = 1
        mock_document.file_path = "/tmp/test.pdf"
        mock_metadata_db.query().filter().first.return_value = mock_document
        
        mock_chunks = [Mock(vector_id=10), Mock(vector_id=11)]
        mock_metadata_db.query().filter_by().all.return_value = mock_chunks
        
        # Mock vector service
        mock_vector_service = Mock()
        mock_vector_service.delete_document = AsyncMock(return_value=True)
        
        with patch.object(document_processor, 'vector_service', mock_vector_service), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:
            
            result = await document_processor.delete_document(
                document_id=1,
                workspace_id=1
            )
        
        assert result is True
        mock_remove.assert_called_once_with("/tmp/test.pdf")
        mock_metadata_db.delete.assert_called()
        mock_metadata_db.commit.assert_called()

    @patch('app.services.document_processor.get_metadata_db')
    async def test_delete_document_not_found(self, mock_get_db, document_processor, mock_metadata_db):
        """Test document deletion when document not found"""
        mock_get_db.return_value = iter([mock_metadata_db])
        mock_metadata_db.query().filter().first.return_value = None
        
        result = await document_processor.delete_document(
            document_id=999,
            workspace_id=1
        )
        
        assert result is False

    # Batch Processing Tests
    @patch('app.services.document_processor.get_metadata_db')
    async def test_process_multiple_documents(self, mock_get_db, document_processor, 
                                            mock_pdf_service, mock_chunker_service, 
                                            mock_vector_service, mock_metadata_db):
        """Test processing multiple documents in batch"""
        mock_get_db.return_value = iter([mock_metadata_db])
        document_processor.pdf_service = mock_pdf_service
        document_processor.chunker_service = mock_chunker_service
        
        # Create multiple temporary files
        files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(f"Content {i}".encode())
                files.append((tmp.name, f"doc_{i}.pdf"))
        
        try:
            with patch.object(document_processor, 'vector_service', mock_vector_service):
                results = []
                for file_path, filename in files:
                    result = await document_processor.process_document(
                        file_path=file_path,
                        filename=filename,
                        workspace_id=1,
                        user_id=1
                    )
                    results.append(result)
            
            assert len(results) == 3
            for result in results:
                assert result["processing_status"] == "completed"
                assert "document_id" in result
            
        finally:
            for file_path, _ in files:
                os.unlink(file_path)

    # Error Recovery and Cleanup Tests
    @patch('app.services.document_processor.get_metadata_db')
    async def test_process_document_cleanup_on_failure(self, mock_get_db, document_processor, 
                                                     sample_pdf_file, mock_metadata_db):
        """Test that resources are cleaned up on processing failure"""
        mock_get_db.return_value = iter([mock_metadata_db])
        
        # Mock services to fail at different stages
        document_processor.pdf_service = Mock()
        document_processor.pdf_service.extract_text_from_pdf.side_effect = Exception("Extraction failed")
        
        # Mock database operations
        mock_document = Mock()
        mock_metadata_db.add.return_value = None
        mock_metadata_db.refresh.return_value = None
        mock_document.id = 1
        
        try:
            await document_processor.process_document(
                file_path=sample_pdf_file,
                filename="test.pdf",
                workspace_id=1,
                user_id=1
            )
        except DocumentProcessingError:
            pass  # Expected to fail
        
        # Verify cleanup was attempted
        mock_metadata_db.close.assert_called()

    # Configuration and Settings Tests
    def test_processor_configuration_validation(self):
        """Test processor configuration validation"""
        valid_config = {
            'max_file_size': 100 * 1024 * 1024,
            'max_chunk_size': 1000,
            'chunk_overlap': 100,
            'min_chunk_size': 50
        }
        
        processor = DocumentProcessor(config=valid_config)
        
        assert processor.max_file_size == 100 * 1024 * 1024
        assert processor.chunker_service.max_chunk_size == 1000

    def test_processor_invalid_configuration(self):
        """Test processor with invalid configuration"""
        invalid_config = {
            'max_file_size': -1,  # Invalid negative size
            'max_chunk_size': 0   # Invalid zero size
        }
        
        with pytest.raises(DocumentProcessingError, match="Invalid configuration"):
            DocumentProcessor(config=invalid_config)