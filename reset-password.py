#!/usr/bin/env python3
"""Reset daveed password in both databases"""

import sys
import os

from werkzeug.security import generate_password_hash

# Reset in production
os.environ['FLASK_ENV'] = 'production'
from ietf_data_viewer_simple import app as app_prod, db as db_prod, User as User_prod

with app_prod.app_context():
    user = User_prod.query.filter_by(username='daveed').first()
    if user:
        user.password_hash = generate_password_hash('admin123')
        db_prod.session.commit()
        print("✓ Production password reset")

# Reset in development
os.environ['FLASK_ENV'] = 'development'
from ietf_data_viewer_simple import app as app_dev, db as db_dev, User as User_dev

with app_dev.app_context():
    user = User_dev.query.filter_by(username='daveed').first()
    if user:
        user.password_hash = generate_password_hash('admin123')
        db_dev.session.commit()
        print("✓ Development password reset")

print("\nPassword reset complete for both environments.")
print("Username: daveed")
print("Password: admin123")
