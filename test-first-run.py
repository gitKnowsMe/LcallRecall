#!/usr/bin/env python3
"""
Test what happens on first run when embedding models need to be downloaded
"""

import os
import shutil
import tempfile
from pathlib import Path

def simulate_first_run():
    """Simulate first run by moving cached models temporarily"""
    
    # Create temporary backup of cache
    cache_dir = Path.home() / ".cache" / "huggingface"
    backup_dir = Path("/tmp") / "huggingface_backup"
    
    print("🧪 Simulating first-run scenario...")
    
    if cache_dir.exists():
        print(f"📦 Backing up existing cache: {cache_dir} -> {backup_dir}")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(cache_dir, backup_dir)
        shutil.rmtree(cache_dir)
    
    try:
        # Test what happens without cached models
        print("🔍 Testing embedding model download...")
        from sentence_transformers import SentenceTransformer
        
        print("📥 Attempting to load all-MiniLM-L6-v2...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("✅ Model loaded successfully!")
        print(f"📁 Model cached to: {cache_dir}")
        
        # Test encoding
        texts = ["Test document for embeddings"]
        embeddings = model.encode(texts)
        print(f"📊 Generated embeddings: shape {embeddings.shape}")
        
        # Check download size
        if cache_dir.exists():
            size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
            print(f"💾 Total cache size: {size / 1024 / 1024:.1f} MB")
        
    except Exception as e:
        print(f"❌ Error during model loading: {e}")
        
    finally:
        # Restore cache
        if backup_dir.exists():
            print(f"🔄 Restoring cache: {backup_dir} -> {cache_dir}")
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            shutil.copytree(backup_dir, cache_dir)
            shutil.rmtree(backup_dir)
            print("✅ Cache restored")

if __name__ == "__main__":
    simulate_first_run()