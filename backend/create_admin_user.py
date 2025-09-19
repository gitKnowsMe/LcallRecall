#!/usr/bin/env python3
"""
Create admin user for LocalRecall application
"""
import sqlite3
import bcrypt
from datetime import datetime
import os

def create_admin_user():
    """Create admin user with username 'admin' and password 'admin123'"""
    try:
        print("Creating admin user...")
        
        # Connect to the auth database
        db_path = os.path.join(os.path.dirname(__file__), 'data', 'auth.db')
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist (username-only, no email)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                workspace_id VARCHAR(36) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if admin user already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        if cursor.fetchone():
            print("❌ User 'admin' already exists!")
            print("You can login with existing admin credentials.")
            return
            
        # Hash password
        password = "admin123"
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        # Get next workspace ID
        cursor.execute("SELECT MAX(CAST(workspace_id AS INTEGER)) FROM users WHERE workspace_id GLOB '[0-9]*'")
        result = cursor.fetchone()
        workspace_id = (result[0] + 1) if result[0] is not None else 1
        
        # Insert admin user (username-only, no email)
        cursor.execute('''
            INSERT INTO users (username, password_hash, workspace_id, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            "admin",
            password_hash,
            str(workspace_id),
            True,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Admin user created successfully!")
        print(f"   Username: admin")
        print(f"   User ID: {user_id}")
        print(f"   Workspace ID: {workspace_id}")
        print()
        print("You can now login with:")
        print("   Username: admin")
        print("   Password: admin123")
        
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")

if __name__ == "__main__":
    create_admin_user()