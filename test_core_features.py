#!/usr/bin/env python3
"""
Core Feature Verification Tests
Run this before commits to ensure critical functionality works
"""

import sys
import os
sys.path.append('.')

from ietf_data_viewer_simple import app, db, User, Comment, Submission, WorkingGroupChair

def test_critical_features():
    """Test all critical application features"""
    print("🧪 Testing Core MLTF Datatracker Features...")
    print("=" * 50)

    with app.app_context():
        client = app.test_client()

        # 1. Authentication System
        print("1. 🔐 Testing Authentication...")
        response = client.post('/login/', data={'username': 'daveed', 'password': 'admin123'})
        if response.status_code == 302:  # Redirect to home
            print("   ✅ Login works")
        else:
            print("   ❌ Login failed")
            return False

        # 2. Admin Dashboard
        print("2. 📊 Testing Admin Dashboard...")
        response = client.get('/admin/')
        if 'Admin Dashboard' in response.get_data(as_text=True):
            print("   ✅ Admin dashboard accessible")
        else:
            print("   ❌ Admin dashboard failed")
            return False

        # 3. User Management
        print("3. 👥 Testing User Management...")
        user_count = User.query.count()
        if user_count > 0:
            print(f"   ✅ {user_count} users in system")
        else:
            print("   ❌ No users found")
            return False

        # 4. Document System
        print("4. 📄 Testing Document System...")
        response = client.get('/doc/all/')
        if 'All Documents' in response.get_data(as_text=True):
            print("   ✅ Document listing works")
        else:
            print("   ❌ Document listing failed")
            return False

        # 5. Individual Draft Pages
        print("5. 📋 Testing Individual Draft Pages...")
        response = client.get('/doc/draft/draft-aazam-cdni-inter-cloud-architecture/')
        if 'draft-aazam-cdni-inter-cloud-architecture' in response.get_data(as_text=True):
            print("   ✅ Individual draft page works")
        else:
            print("   ❌ Individual draft page failed")
            return False

        # 6. Comment System
        print("6. 💬 Testing Comment System...")
        comment_count = Comment.query.count()
        print(f"   📊 {comment_count} total comments in system")

        # Test comment submission
        response = client.post('/doc/draft/draft-aazam-cdni-inter-cloud-architecture/comments/',
                              data={'comment': 'Automated test comment'})
        if response.status_code in [200, 302]:
            print("   ✅ Comment submission works")
        else:
            print("   ❌ Comment submission failed")
            return False

        # Test comment display
        response = client.get('/doc/draft/draft-aazam-cdni-inter-cloud-architecture/comments/')
        if 'Add a Comment' in response.get_data(as_text=True):
            print("   ✅ Comment display with form works")
        else:
            print("   ❌ Comment display missing form")
            return False

        # 7. Submission System
        print("7. 📤 Testing Submission System...")
        submission_count = Submission.query.count()
        print(f"   📊 {submission_count} total submissions in system")

        response = client.get('/submit/')
        if 'Submit Internet-Draft' in response.get_data(as_text=True):
            print("   ✅ Submission form accessible")
        else:
            print("   ❌ Submission form failed")
            return False

        # 8. Working Groups
        print("8. 🏢 Testing Working Groups...")
        response = client.get('/group/')
        if 'Working Groups' in response.get_data(as_text=True):
            print("   ✅ Working groups page works")
        else:
            print("   ❌ Working groups page failed")
            return False

        # 9. Chair Management
        print("9. 👑 Testing Chair Management...")
        chair_count = WorkingGroupChair.query.count()
        approved_chairs = WorkingGroupChair.query.filter_by(approved=True).count()
        print(f"   📊 {chair_count} total chairs, {approved_chairs} approved")

        # 10. Theme System
        print("10. 🌙 Testing Theme System...")
        response = client.get('/')
        html = response.get_data(as_text=True)
        if 'data-theme' in html and 'theme-toggle' in html:
            print("   ✅ Theme system works")
        else:
            print("   ❌ Theme system failed")
            return False

        print("=" * 50)
        print("🎉 ALL CRITICAL FEATURES WORKING!")
        print("\n💡 Safe to commit - no regressions detected")
        return True

if __name__ == '__main__':
    success = test_critical_features()
    sys.exit(0 if success else 1)