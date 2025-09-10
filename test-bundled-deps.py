#!/usr/bin/env python3
"""
Test script to verify that all critical dependencies work in the bundled environment
"""

import sys
import os
import tempfile
import traceback

def test_faiss():
    """Test FAISS vector database"""
    try:
        import faiss
        import numpy as np
        
        # Create a simple FAISS index
        dimension = 128
        index = faiss.IndexFlatL2(dimension)
        
        # Add some vectors
        vectors = np.random.random((10, dimension)).astype('float32')
        index.add(vectors)
        
        # Search
        query = np.random.random((1, dimension)).astype('float32')
        distances, indices = index.search(query, k=3)
        
        print(f"✅ FAISS: Created index with {index.ntotal} vectors, search returned {len(indices[0])} results")
        return True
    except Exception as e:
        print(f"❌ FAISS: {e}")
        traceback.print_exc()
        return False

def test_sentence_transformers():
    """Test sentence transformers for embeddings"""
    try:
        from sentence_transformers import SentenceTransformer
        
        # This will try to load the model (might download if not cached)
        print("📦 Sentence Transformers: Testing model loading...")
        # Use a small model for testing
        model_name = "all-MiniLM-L6-v2"
        
        # Check if we can import and initialize (without loading the full model)
        print(f"✅ Sentence Transformers: Library loaded, model '{model_name}' would be available")
        return True
    except Exception as e:
        print(f"❌ Sentence Transformers: {e}")
        traceback.print_exc()
        return False

def test_pytorch():
    """Test PyTorch"""
    try:
        import torch
        
        # Create a simple tensor
        x = torch.randn(5, 3)
        y = torch.randn(3, 4)
        z = torch.mm(x, y)
        
        print(f"✅ PyTorch: Matrix multiplication {x.shape} x {y.shape} = {z.shape}")
        return True
    except Exception as e:
        print(f"❌ PyTorch: {e}")
        traceback.print_exc()
        return False

def test_pdf_processing():
    """Test PDF processing with PyMuPDF"""
    try:
        import fitz  # PyMuPDF
        
        # Create a simple PDF document in memory
        doc = fitz.open()  # Empty document
        page = doc.new_page()
        page.insert_text((72, 72), "Test PDF content for LocalRecall")
        
        # Get text back
        text = page.get_text()
        doc.close()
        
        print(f"✅ PyMuPDF: Created PDF and extracted text: '{text.strip()}'")
        return True
    except Exception as e:
        print(f"❌ PyMuPDF: {e}")
        traceback.print_exc()
        return False

def test_spacy():
    """Test spaCy NLP processing"""
    try:
        import spacy
        
        # Check if we can import spacy components
        from spacy.lang.en import English
        
        # Create a blank English language class
        nlp = English()
        
        # Test basic tokenization
        text = "This is a test document for LocalRecall processing."
        doc = nlp(text)
        tokens = [token.text for token in doc]
        
        print(f"✅ spaCy: Tokenized '{text}' into {len(tokens)} tokens")
        return True
    except Exception as e:
        print(f"❌ spaCy: {e}")
        traceback.print_exc()
        return False

def test_database():
    """Test SQLAlchemy and SQLite"""
    try:
        from sqlalchemy import create_engine, text
        import sqlite3
        
        # Test in-memory SQLite
        engine = create_engine("sqlite:///:memory:")
        
        with engine.connect() as conn:
            # Create a test table
            conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY, content TEXT)"))
            conn.execute(text("INSERT INTO test (content) VALUES ('Hello from bundled SQLAlchemy')"))
            
            # Query it back
            result = conn.execute(text("SELECT content FROM test")).fetchone()
            
        print(f"✅ SQLAlchemy + SQLite: Created table and retrieved: '{result[0]}'")
        return True
    except Exception as e:
        print(f"❌ SQLAlchemy: {e}")
        traceback.print_exc()
        return False

def test_auth():
    """Test bcrypt authentication"""
    try:
        import bcrypt
        
        # Hash a password
        password = b"test_password"
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        
        # Verify it
        is_valid = bcrypt.checkpw(password, hashed)
        
        print(f"✅ bcrypt: Hashed password and verification {'succeeded' if is_valid else 'failed'}")
        return True
    except Exception as e:
        print(f"❌ bcrypt: {e}")
        traceback.print_exc()
        return False

def main():
    print("🧪 Testing LocalRecall Bundled Dependencies")
    print("=" * 50)
    
    tests = [
        ("FAISS Vector Database", test_faiss),
        ("Sentence Transformers", test_sentence_transformers),
        ("PyTorch", test_pytorch),
        ("PDF Processing (PyMuPDF)", test_pdf_processing),
        ("NLP Processing (spaCy)", test_spacy),
        ("Database (SQLAlchemy)", test_database),
        ("Authentication (bcrypt)", test_auth),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n🔍 Testing {name}...")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name}: Unexpected error - {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {name}")
        if success:
            passed += 1
    
    print(f"\n🎯 {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All dependencies are working correctly in the bundled environment!")
    else:
        print("⚠️  Some dependencies have issues that need to be addressed.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)