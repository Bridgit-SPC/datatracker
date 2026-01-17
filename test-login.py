#!/usr/bin/env python3
"""Test login functionality"""

import sys
import os

# Set environment
env = sys.argv[1] if len(sys.argv) > 1 else 'production'
os.environ['FLASK_ENV'] = env

from ietf_data_viewer_simple import app, db, User
from werkzeug.security import check_password_hash, generate_password_hash

with app.app_context():
    username = 'daveed'
    password = 'admin123'
    
    user = User.query.filter_by(username=username).first()
    
    if not user:
        print(f"ERROR: User '{username}' not found in {env} database")
        sys.exit(1)
    
    print(f"User found: {user.username}")
    print(f"Email: {user.email}")
    print(f"Role: {user.role}")
    print(f"Password hash: {user.password_hash[:50]}...")
    
    # Test password
    if check_password_hash(user.password_hash, password):
        print(f"✓ Password 'admin123' is CORRECT")
    else:
        print(f"✗ Password 'admin123' is INCORRECT")
        print("Resetting password...")
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        print("✓ Password reset complete")
        
        # Verify new password
        if check_password_hash(user.password_hash, password):
            print("✓ New password verified")
        else:
            print("✗ Password reset failed!")
