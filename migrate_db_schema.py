#!/usr/bin/env python3
"""
Database Migration Script for Web3Auth Schema Updates
Run this to add new Web3Auth fields to existing database
"""

import os
import sys
from pathlib import Path

# Add current directory to path so we can import the Flask app
sys.path.insert(0, str(Path(__file__).parent))

from ietf_data_viewer_simple import app, db, User

def migrate_database():
    """Add new Web3Auth columns to existing database"""

    with app.app_context():
        # Check current schema
        print("Checking current database schema...")
        try:
            # Try to query existing users to see current schema
            users = User.query.limit(1).all()
            print(f"Found {len(users)} users in database")
        except Exception as e:
            print(f"Database schema issue: {e}")
            print("Recreating database with new schema...")

            # Drop all tables and recreate
            db.drop_all()
            db.create_all()

            print("Database recreated successfully!")
            return

        # Check if new columns exist by trying to access them
        try:
            # Try to access new fields on a user
            if users:
                user = users[0]
                # Try to access new fields
                verifier_id = getattr(user, 'web3authVerifierId', None)
                display_name = getattr(user, 'displayName', None)
                print("New schema fields already exist")
                return
        except Exception as e:
            print(f"New schema fields missing: {e}")

        print("Adding new Web3Auth columns to existing database...")

        # For SQLite, we need to recreate the table with new schema
        # This is a simplified approach - in production you'd use proper migrations

        # Get existing user data
        existing_users = []
        for user in User.query.all():
            existing_users.append({
                'id': user.id,
                'username': user.username,
                'password_hash': user.password_hash,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'theme': user.theme,
                'created_at': user.created_at,
                'last_login': user.last_login,
            })

        # Drop and recreate tables
        db.drop_all()
        db.create_all()

        # Restore user data with default values for new fields
        for user_data in existing_users:
            user = User(
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                name=user_data['name'],
                email=user_data['email'],
                role=user_data['role'],
                theme=user_data['theme'],
                created_at=user_data['created_at'],
                last_login=user_data['last_login'],
                # New fields with defaults
                web3authVerifierId=None,
                typeOfLogin=None,
                displayName=None,
                displayNameSetAt=None,
                oauthName=None,
                profileImage=None,
                evmAddress=None,
                solanaAddress=None,
            )
            db.session.add(user)

        db.session.commit()
        print(f"Migrated {len(existing_users)} users successfully!")

if __name__ == '__main__':
    migrate_database()
    print("Migration complete!")