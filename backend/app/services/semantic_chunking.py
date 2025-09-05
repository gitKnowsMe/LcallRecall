"""
Semantic chunking service for document processing
"""
import logging
from typing import List, Dict, Any
import spacy

logger = logging.getLogger(__name__)


class SemanticChunking:
    """Handles semantic chunking of text documents"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize semantic chunking service
        
        Args:
            chunk_size: Target size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._nlp = None
        
        logger.info(f"SemanticChunking initialized with chunk_size={chunk_size}, overlap={chunk_overlap}")
    
    def _load_spacy_model(self):
        """Load spaCy model lazily"""
        if self._nlp is None:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                # Fallback to simple splitting if spaCy model not available
                logger.warning("spaCy model not available, using simple text splitting")
                self._nlp = False
    
    def chunk_text(self, text: str, document_id: str = None) -> List[Dict[str, Any]]:
        """
        Split text into semantic chunks
        
        Args:
            text: Input text to chunk
            document_id: Optional document identifier
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or not text.strip():
            return []
        
        self._load_spacy_model()
        
        if self._nlp is False:
            # Simple fallback chunking
            return self._simple_chunk(text, document_id)
        
        try:
            # Use spaCy for semantic chunking
            return self._semantic_chunk(text, document_id)
        except Exception as e:
            logger.error(f"Semantic chunking failed: {e}")
            # Fallback to simple chunking
            return self._simple_chunk(text, document_id)
    
    def _simple_chunk(self, text: str, document_id: str = None) -> List[Dict[str, Any]]:
        """Simple text chunking based on character count"""
        chunks = []
        text = text.strip()
        
        start = 0
        chunk_id = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings nearby
                search_start = max(start + self.chunk_size - 100, start)
                search_end = min(end + 100, len(text))
                
                best_break = end
                for i in range(search_end - 1, search_start - 1, -1):
                    if text[i] in '.!?':
                        if i + 1 < len(text) and text[i + 1] == ' ':
                            best_break = i + 1
                            break
                
                end = best_break
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk = {
                    'text': chunk_text,
                    'chunk_id': chunk_id,
                    'start_char': start,
                    'end_char': end,
                    'length': len(chunk_text)
                }
                
                if document_id:
                    chunk['document_id'] = document_id
                
                chunks.append(chunk)
                chunk_id += 1
            
            # Move start position with overlap
            start = max(end - self.chunk_overlap, start + 1)
            if start >= len(text):
                break
        
        logger.info(f"Created {len(chunks)} simple chunks")
        return chunks
    
    def _semantic_chunk(self, text: str, document_id: str = None) -> List[Dict[str, Any]]:
        """Semantic chunking using spaCy"""
        doc = self._nlp(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_id = 0
        start_char = 0
        
        for sent in doc.sents:
            sent_text = sent.text.strip()
            sent_length = len(sent_text)
            
            # If adding this sentence would exceed chunk size
            if current_length + sent_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunk = {
                    'text': chunk_text,
                    'chunk_id': chunk_id,
                    'start_char': start_char,
                    'end_char': start_char + len(chunk_text),
                    'length': len(chunk_text),
                    'sentence_count': len(current_chunk)
                }
                
                if document_id:
                    chunk['document_id'] = document_id
                
                chunks.append(chunk)
                chunk_id += 1
                
                # Start new chunk with overlap
                overlap_sentences = max(1, len(current_chunk) * self.chunk_overlap // self.chunk_size)
                current_chunk = current_chunk[-overlap_sentences:] if overlap_sentences > 0 else []
                current_length = sum(len(s) for s in current_chunk)
                start_char = sent.start_char if not current_chunk else chunks[-1]['start_char'] + len(' '.join(current_chunk))
            
            current_chunk.append(sent_text)
            current_length += sent_length
        
        # Add final chunk if any content remains
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk = {
                'text': chunk_text,
                'chunk_id': chunk_id,
                'start_char': start_char,
                'end_char': start_char + len(chunk_text),
                'length': len(chunk_text),
                'sentence_count': len(current_chunk)
            }
            
            if document_id:
                chunk['document_id'] = document_id
            
            chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} semantic chunks using spaCy")
        return chunks
    
    def is_healthy(self) -> bool:
        """Check service health"""
        return True
    
    def cleanup(self):
        """Cleanup resources"""
        self._nlp = None
        logger.info("SemanticChunking service cleaned up")