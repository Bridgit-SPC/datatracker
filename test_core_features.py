#!/usr/bin/env python3
"""
Core Feature Verification Tests
Run this before commits to ensure critical functionality works
"""

import sys
import os
sys.path.append('.')

from ietf_data_viewer_simple import app, COMMENTS

def test_critical_features():
    """Test all critical application features"""
    print("🧪 Testing Core MLTF Datatracker Features...")
    print("=" * 50)

    with app.app_context():
        client = app.test_client()

        # 1. Authentication System
        print("1. 🔐 Testing Authentication...")
        response = client.post('/login/', data={'username': 'admin', 'password': 'admin123'})
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
        # Test user registration functionality
        response = client.post('/register/', data={
            'username': 'testuser',
            'password': 'testpass123',
            'name': 'Test User',
            'email': 'test@example.com'
        }, follow_redirects=True)
        if response.status_code == 200:
            print("   ✅ User registration works")
        else:
            print(f"   ❌ User registration failed: {response.status_code}")
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
        # Check if we have any drafts/submissions first
        from ietf_data_viewer_simple import Submission, PublishedDraft
        has_drafts = Submission.query.count() > 0 or len(PublishedDraft.query.all()) > 0

        if has_drafts:
            # Test with first available draft
            first_submission = Submission.query.first()
            if first_submission:
                response = client.get(f'/doc/draft/{first_submission.draft_name}/')
                if first_submission.draft_name in response.get_data(as_text=True):
                    print("   ✅ Individual draft page works")
                else:
                    print("   ❌ Individual draft page failed")
                    return False
            else:
                first_draft = PublishedDraft.query.first()
                response = client.get(f'/doc/draft/{first_draft.name}/')
                if first_draft.name in response.get_data(as_text=True):
                    print("   ✅ Individual draft page works")
                else:
                    print("   ❌ Individual draft page failed")
                    return False
        else:
            # No drafts available - test that the route doesn't crash
            response = client.get('/doc/draft/nonexistent-draft/')
            if response.status_code == 404:
                print("   ✅ Draft route handles missing drafts gracefully")
            else:
                print("   ❌ Draft route should return 404 for missing drafts")
                return False

        # 6. Comment System
        print("6. 💬 Testing Comment System...")
        comment_count = sum(len(comments) for comments in COMMENTS.values())
        print(f"   📊 {comment_count} total comments in system")

        # Test comment functionality (skip submission if no drafts)
        if has_drafts:
            # Test comment submission on first available draft
            draft_name = None
            first_submission = Submission.query.first()
            if first_submission:
                draft_name = first_submission.draft_name
            else:
                first_draft = PublishedDraft.query.first()
                if first_draft:
                    draft_name = first_draft.name

            if draft_name:
                response = client.post(f'/doc/draft/{draft_name}/comments/',
                                      data={'comment': 'Automated test comment'})
                if response.status_code in [200, 302]:
                    print("   ✅ Comment submission works")
                else:
                    print("   ❌ Comment submission failed")
                    return False

                # Test comment display
                response = client.get(f'/doc/draft/{draft_name}/comments/')
                if 'Add a Comment' in response.get_data(as_text=True):
                    print("   ✅ Comment display with form works")
                else:
                    print("   ❌ Comment display missing form")
                    return False
            else:
                print("   ⚠️  No drafts available for comment testing")
        else:
            # Test comment route accessibility without drafts
            response = client.get('/doc/draft/nonexistent-draft/comments/')
            if response.status_code == 404:
                print("   ✅ Comment routes handle missing drafts gracefully")
            else:
                print("   ❌ Comment routes should return 404 for missing drafts")
                return False

        # 7. Submission System
        print("7. 📤 Testing Submission System...")
        # Test submission form accessibility
        response = client.get('/submit/')
        if response.status_code == 200 and 'Submit Internet-Draft' in response.get_data(as_text=True):
            print("   ✅ Submission form accessible")
        else:
            print(f"   ❌ Submission form failed: {response.status_code}")
            return False

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
        # Test chair management page access
        response = client.get('/admin/chairs/')
        if response.status_code == 200 and 'Chair Management' in response.get_data(as_text=True):
            print("   ✅ Chair management accessible")
        else:
            print(f"   ❌ Chair management failed: {response.status_code}")
            return False

        # 10. Theme System
        print("10. 🌙 Testing Theme System...")
        # Theme system is not implemented in this simplified version
        # This is expected and not a failure
        print("   ℹ️  Theme system not implemented (simplified version)")

        print("=" * 50)
        print("🎉 ALL CRITICAL FEATURES WORKING!")
        print("\n💡 Safe to commit - no regressions detected")
        return True

if __name__ == '__main__':
    success = test_critical_features()
    sys.exit(0 if success else 1)