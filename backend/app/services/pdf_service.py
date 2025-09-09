import os
import re
import logging
from typing import Dict, Any, Optional
from io import BytesIO
import fitz  # PyMuPDF
import hashlib

logger = logging.getLogger(__name__)

# Custom exceptions
class PDFError(Exception):
    """Base PDF processing error"""
    pass

class UnsupportedFileError(PDFError):
    """Unsupported file type error"""
    pass

class PDFService:
    """PDF text extraction service using PyMuPDF"""
    
    def __init__(self, max_file_size: int = 100 * 1024 * 1024):  # 100MB default
        self.max_file_size = max_file_size
        self.supported_extensions = {'.pdf'}
        
    def extract_text_from_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text content from PDF file
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dict containing extracted text and metadata
            
        Raises:
            PDFError: If PDF processing fails
            UnsupportedFileError: If file type not supported
        """
        try:
            # Validate file
            self._validate_pdf_file(file_path)
            self._validate_file_size(file_path)
            
            if not os.path.exists(file_path):
                raise PDFError("File not found")
            
            # Open and process PDF
            doc = None
            try:
                doc = fitz.open(file_path)
                
                # Extract text from all pages with page tracking
                pages_text = []
                full_text = ""
                for page_num, page in enumerate(doc, 1):
                    page_text = page.get_text()
                    pages_text.append({"page_number": page_num, "text": page_text})
                    full_text += page_text
                
                # Calculate statistics
                stats = self._calculate_text_statistics(full_text)
                
                # Prepare metadata
                metadata = {
                    "page_count": doc.page_count,
                    "total_chars": stats["total_chars"],
                    "total_words": stats["total_words"],
                    "total_sentences": stats["total_sentences"],
                    "total_paragraphs": stats["total_paragraphs"]
                }
                
                return {
                    "text": full_text,
                    "pages": pages_text,
                    "metadata": metadata
                }
                
            finally:
                if doc:
                    doc.close()
                    
        except (UnsupportedFileError, PDFError):
            raise
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {file_path}: {e}")
            raise PDFError(f"Failed to extract text from PDF: {str(e)}")
    
    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extract text content from PDF bytes
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            Dict containing extracted text and metadata
            
        Raises:
            PDFError: If PDF processing fails
        """
        try:
            if not pdf_bytes:
                raise PDFError("PDF content is empty")
            
            # Open PDF from bytes
            doc = None
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                # Extract text from all pages with page tracking
                pages_text = []
                full_text = ""
                for page_num, page in enumerate(doc, 1):
                    page_text = page.get_text()
                    pages_text.append({"page_number": page_num, "text": page_text})
                    full_text += page_text
                
                # Calculate statistics
                stats = self._calculate_text_statistics(full_text)
                
                # Prepare metadata
                metadata = {
                    "page_count": doc.page_count,
                    "total_chars": stats["total_chars"],
                    "total_words": stats["total_words"],
                    "total_sentences": stats["total_sentences"],
                    "total_paragraphs": stats["total_paragraphs"]
                }
                
                return {
                    "text": full_text,
                    "pages": pages_text,
                    "metadata": metadata
                }
                
            finally:
                if doc:
                    doc.close()
                    
        except Exception as e:
            logger.error(f"Failed to extract text from PDF bytes: {e}")
            raise PDFError(f"Failed to extract text from PDF bytes: {str(e)}")
    
    def get_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from PDF file
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dict containing PDF metadata
            
        Raises:
            PDFError: If PDF processing fails
        """
        try:
            if not os.path.exists(file_path):
                raise PDFError("File not found")
            
            doc = None
            try:
                doc = fitz.open(file_path)
                
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Extract metadata
                metadata = {
                    "page_count": doc.page_count,
                    "file_size": file_size,
                    "title": doc.metadata.get("title", ""),
                    "author": doc.metadata.get("author", ""),
                    "subject": doc.metadata.get("subject", ""),
                    "creator": doc.metadata.get("creator", ""),
                    "producer": doc.metadata.get("producer", ""),
                    "creation_date": doc.metadata.get("creationDate", ""),
                    "modification_date": doc.metadata.get("modDate", "")
                }
                
                return metadata
                
            finally:
                if doc:
                    doc.close()
                    
        except Exception as e:
            logger.error(f"Failed to extract PDF metadata {file_path}: {e}")
            raise PDFError(f"Failed to extract PDF metadata: {str(e)}")
    
    def _validate_pdf_file(self, filename: Optional[str]) -> bool:
        """
        Validate that file is a PDF
        
        Args:
            filename: Name of file to validate
            
        Returns:
            True if valid PDF file
            
        Raises:
            UnsupportedFileError: If not a PDF file
        """
        if not filename:
            raise UnsupportedFileError("Only PDF files are supported")
        
        # Check file extension
        file_ext = os.path.splitext(filename.lower())[1]
        if file_ext not in self.supported_extensions:
            raise UnsupportedFileError("Only PDF files are supported")
        
        return True
    
    def _validate_file_size(self, file_path: str) -> None:
        """
        Validate file size against limits
        
        Args:
            file_path: Path to file to validate
            
        Raises:
            PDFError: If file size exceeds limit
        """
        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                raise PDFError(f"File size exceeds maximum limit of {self.max_file_size} bytes")
        except OSError as e:
            raise PDFError(f"Could not check file size: {str(e)}")
    
    def _calculate_text_statistics(self, text: str) -> Dict[str, int]:
        """
        Calculate basic text statistics
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with text statistics
        """
        if not text:
            return {
                "total_chars": 0,
                "total_words": 0,
                "total_sentences": 0,
                "total_paragraphs": 0
            }
        
        # Character count
        total_chars = len(text)
        
        # Word count (split by whitespace, filter empty strings)
        words = [word for word in text.split() if word.strip()]
        total_words = len(words)
        
        # Sentence count (approximate using period, exclamation, question mark)
        sentence_endings = re.findall(r'[.!?]+', text)
        total_sentences = len(sentence_endings)
        
        # Paragraph count (split by double newlines, filter empty)
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        total_paragraphs = len(paragraphs)
        
        return {
            "total_chars": total_chars,
            "total_words": total_words,
            "total_sentences": total_sentences,
            "total_paragraphs": total_paragraphs
        }
    
    def cleanup(self) -> None:
        """
        Cleanup resources (placeholder for future use)
        """
        pass

# Global service instance
pdf_service = PDFService()