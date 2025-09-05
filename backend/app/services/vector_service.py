import os
import pickle
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """Workspace-based FAISS vector store manager"""
    
    def __init__(self):
        self.embedding_model = None
        self.workspace_indices: Dict[str, faiss.Index] = {}
        self.workspace_metadata: Dict[str, List[Dict]] = {}
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension
        
    async def initialize(self):
        """Initialize embedding model"""
        if self.embedding_model is None:
            logger.info("Loading sentence-transformers model...")
            self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            logger.info("✅ Embedding model loaded")
    
    def get_workspace_path(self, workspace_id: str) -> str:
        """Get workspace directory path"""
        workspace_dir = f"data/workspaces/workspace_{int(workspace_id):03d}"
        os.makedirs(workspace_dir, exist_ok=True)
        return workspace_dir
    
    def get_index_path(self, workspace_id: str) -> str:
        """Get FAISS index file path"""
        return os.path.join(self.get_workspace_path(workspace_id), "faiss_index.bin")
    
    def get_metadata_path(self, workspace_id: str) -> str:
        """Get metadata file path"""
        return os.path.join(self.get_workspace_path(workspace_id), "metadata.pkl")
    
    async def load_workspace(self, workspace_id: str) -> bool:
        """Load workspace FAISS index and metadata"""
        try:
            if workspace_id in self.workspace_indices:
                logger.info(f"Workspace {workspace_id} already loaded")
                return True
            
            index_path = self.get_index_path(workspace_id)
            metadata_path = self.get_metadata_path(workspace_id)
            
            # Load or create FAISS index
            if os.path.exists(index_path):
                logger.info(f"Loading existing FAISS index for workspace {workspace_id}")
                self.workspace_indices[workspace_id] = faiss.read_index(index_path)
            else:
                logger.info(f"Creating new FAISS index for workspace {workspace_id}")
                # Create flat L2 index
                self.workspace_indices[workspace_id] = faiss.IndexFlatL2(self.embedding_dim)
            
            # Load or create metadata
            if os.path.exists(metadata_path):
                with open(metadata_path, 'rb') as f:
                    self.workspace_metadata[workspace_id] = pickle.load(f)
            else:
                self.workspace_metadata[workspace_id] = []
            
            logger.info(f"✅ Workspace {workspace_id} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load workspace {workspace_id}: {e}")
            return False
    
    async def unload_workspace(self, workspace_id: str):
        """Unload workspace from memory (save first)"""
        if workspace_id in self.workspace_indices:
            await self.save_workspace(workspace_id)
            del self.workspace_indices[workspace_id]
            del self.workspace_metadata[workspace_id]
            logger.info(f"Workspace {workspace_id} unloaded")
    
    async def save_workspace(self, workspace_id: str):
        """Save workspace FAISS index and metadata to disk"""
        try:
            if workspace_id not in self.workspace_indices:
                logger.warning(f"Workspace {workspace_id} not loaded")
                return
            
            index_path = self.get_index_path(workspace_id)
            metadata_path = self.get_metadata_path(workspace_id)
            
            # Save FAISS index
            faiss.write_index(self.workspace_indices[workspace_id], index_path)
            
            # Save metadata
            with open(metadata_path, 'wb') as f:
                pickle.dump(self.workspace_metadata[workspace_id], f)
            
            logger.info(f"✅ Workspace {workspace_id} saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save workspace {workspace_id}: {e}")
    
    async def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts"""
        if self.embedding_model is None:
            await self.initialize()
        
        embeddings = self.embedding_model.encode(texts, normalize_embeddings=True)
        return embeddings.astype(np.float32)
    
    async def add_documents(
        self, 
        workspace_id: str, 
        texts: List[str], 
        metadata: List[Dict[str, Any]]
    ) -> List[int]:
        """Add documents to workspace"""
        if workspace_id not in self.workspace_indices:
            await self.load_workspace(workspace_id)
        
        # Generate embeddings
        embeddings = await self.embed_texts(texts)
        
        # Get current index size for ID assignment
        current_size = self.workspace_indices[workspace_id].ntotal
        
        # Add to FAISS index
        self.workspace_indices[workspace_id].add(embeddings)
        
        # Add metadata
        document_ids = []
        for i, meta in enumerate(metadata):
            doc_id = current_size + i
            meta['id'] = doc_id
            meta['text'] = texts[i]
            self.workspace_metadata[workspace_id].append(meta)
            document_ids.append(doc_id)
        
        # Save workspace
        await self.save_workspace(workspace_id)
        
        logger.info(f"Added {len(texts)} documents to workspace {workspace_id}")
        return document_ids
    
    async def search(
        self, 
        workspace_id: str, 
        query: str, 
        k: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        if workspace_id not in self.workspace_indices:
            await self.load_workspace(workspace_id)
        
        # Generate query embedding
        query_embedding = await self.embed_texts([query])
        
        # Search FAISS index
        scores, indices = self.workspace_indices[workspace_id].search(query_embedding, k)
        
        # Prepare results
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx == -1:  # No more results
                break
                
            # Convert L2 distance to similarity score (0-1)
            similarity = 1 / (1 + score)
            
            if similarity >= score_threshold:
                metadata = self.workspace_metadata[workspace_id][idx].copy()
                metadata['similarity'] = float(similarity)
                metadata['rank'] = i + 1
                results.append(metadata)
        
        return results
    
    async def delete_document(self, workspace_id: str, document_id: int) -> bool:
        """Delete document from workspace"""
        try:
            if workspace_id not in self.workspace_indices:
                await self.load_workspace(workspace_id)
            
            # Find metadata entry
            metadata_list = self.workspace_metadata[workspace_id]
            doc_index = None
            for i, meta in enumerate(metadata_list):
                if meta.get('id') == document_id:
                    doc_index = i
                    break
            
            if doc_index is None:
                logger.warning(f"Document {document_id} not found in workspace {workspace_id}")
                return False
            
            # Remove from metadata
            del metadata_list[doc_index]
            
            # Note: FAISS doesn't support efficient single document deletion
            # For now, we mark as deleted in metadata and rebuild index periodically
            logger.info(f"Document {document_id} marked for deletion")
            
            await self.save_workspace(workspace_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False
    
    async def get_workspace_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get workspace statistics"""
        if workspace_id not in self.workspace_indices:
            await self.load_workspace(workspace_id)
        
        return {
            'workspace_id': workspace_id,
            'total_documents': len(self.workspace_metadata[workspace_id]),
            'faiss_vectors': self.workspace_indices[workspace_id].ntotal,
            'embedding_dimension': self.embedding_dim
        }

# Global instance
vector_store = VectorStoreManager()