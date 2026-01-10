#!/usr/bin/env python3
"""
MLTF Data Viewer - Shows the MLTF datatracker data from test files
This displays the Meta-Layer Task Force data so you can see it working.
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import re
import json
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Import file processing libraries
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    import docx
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False

# Database initialization
def init_db():
    """Initialize database and create tables"""
    with app.app_context():
        db.create_all()

        # Migrate hardcoded users to database if not already done
        if User.query.count() == 0:
            migrate_hardcoded_users()

        # Load published drafts from database into memory
        published_drafts = PublishedDraft.query.all()
        for draft in published_drafts:
            draft_entry = {
                'name': draft.name,
                'title': draft.title,
                'authors': draft.authors,
                'group': draft.group,
                'status': draft.status,
                'rev': draft.rev,
                'pages': draft.pages,
                'words': draft.words,
                'date': draft.date,
                'abstract': draft.abstract,
                'stream': draft.stream
            }
            DRAFTS.append(draft_entry)

        print(f"Database initialized: {User.query.count()} users, {len(published_drafts)} published drafts loaded")

def migrate_hardcoded_users():
    """Migrate hardcoded users to database"""
    hardcoded_users = {
        'admin': {'password': 'admin123', 'name': 'Admin User', 'email': 'admin@ietf.org', 'role': 'admin', 'theme': 'dark'},
        'daveed': {'password': 'admin123', 'name': 'Daveed', 'email': 'daveed@bridgit.io', 'role': 'admin', 'theme': 'dark'},
        'john': {'password': 'password123', 'name': 'John Doe', 'email': 'john@example.com', 'role': 'editor', 'theme': 'dark'},
        'jane': {'password': 'password123', 'name': 'Jane Smith', 'email': 'jane@example.com', 'role': 'user', 'theme': 'dark'},
        'shiftshapr': {'password': 'mynewpassword123', 'name': 'Shift Shapr', 'email': 'shiftshapr@example.com', 'role': 'editor', 'theme': 'dark'}
    }

    for username, user_data in hardcoded_users.items():
        if not User.query.filter_by(username=username).first():
            user = User(
                username=username,
                password_hash=generate_password_hash(user_data['password']),
                name=user_data['name'],
                email=user_data['email'],
                role=user_data.get('role', 'user'),
                theme=user_data.get('theme', 'dark')
            )
            db.session.add(user)

    db.session.commit()
    print(f"Migrated {len(hardcoded_users)} hardcoded users to database")

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # For flash messages

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///datatracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class Submission(db.Model):
    id = db.Column(db.String(8), primary_key=True)
    title = db.Column(db.String(255))
    authors = db.Column(db.JSON)  # List of author dicts
    abstract = db.Column(db.Text)
    group = db.Column(db.String(50))
    filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    draft_name = db.Column(db.String(255))
    status = db.Column(db.String(20), default='submitted')  # submitted, approved, rejected
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_by = db.Column(db.String(100), default='Anonymous User')
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)

class PublishedDraft(db.Model):
    """Store published/approved drafts separately from original test data"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, index=True)
    title = db.Column(db.String(255))
    authors = db.Column(db.JSON)
    group = db.Column(db.String(50))
    status = db.Column(db.String(20), default='active')
    rev = db.Column(db.String(5), default='00')
    pages = db.Column(db.Integer, default=1)
    words = db.Column(db.Integer, default=0)
    date = db.Column(db.String(10))  # YYYY-MM-DD
    abstract = db.Column(db.Text)
    stream = db.Column(db.String(20), default='ietf')
    submission_id = db.Column(db.String(8), db.ForeignKey('submission.id'), nullable=True)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    draft_name = db.Column(db.String(255), index=True)
    text = db.Column(db.Text)
    author = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

    # Relationship for replies
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)

class DocumentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    draft_name = db.Column(db.String(255), index=True)
    action = db.Column(db.String(50))
    user = db.Column(db.String(100))
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class WorkingGroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_acronym = db.Column(db.String(50), index=True)
    user_name = db.Column(db.String(100), index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, index=True)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, index=True)
    role = db.Column(db.String(20), default='user')  # admin, editor, user
    theme = db.Column(db.String(10), default='dark')  # light, dark, auto
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

class WorkingGroupChair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_acronym = db.Column(db.String(50), index=True)  # Remove unique constraint to allow multiple chairs
    chair_name = db.Column(db.String(100))
    approved = db.Column(db.Boolean, default=False)
    set_at = db.Column(db.DateTime, default=datetime.utcnow)

# Users are now stored in database - this dict is kept for backward compatibility during migration

# Store document history in memory
DOCUMENT_HISTORY = {}

# Store comments in memory
COMMENTS = {}

# Store comment likes in memory
COMMENT_LIKES = {}

# Store comment replies in memory
COMMENT_REPLIES = {}

# Configuration for file uploads
UPLOAD_FOLDER = '/home/ubuntu/data-tracker/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'xml', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_draft_name(title, authors):
    """Generate a draft name from title and authors"""
    # Extract first author's last name
    first_author = authors[0] if authors else "unknown"
    author_last = first_author.split()[-1].lower() if first_author else "unknown"
    
    # Create a slug from the title
    title_slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
    title_slug = re.sub(r'\s+', '-', title_slug.strip())
    title_slug = title_slug[:30]  # Limit length
    
    return f"draft-{author_last}-{title_slug}"

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_role(required_role):
    """Decorator to require a specific role"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login'))
            current_user = get_current_user()
            if not current_user or current_user.get('role') != required_role:
                return "Access denied", 403
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

def get_current_user():
    """Get current logged in user"""
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
        if user:
            return {
                'username': user.username,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'theme': user.theme
            }
    return None

def generate_user_menu():
    """Generate user menu HTML for navbar"""
    current_user = get_current_user()
    if current_user:
        user_role = current_user.get('role', 'user')
        return f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                {current_user['name']}
            </a>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="/admin/">Admin Dashboard</a></li>
                <li><a class="dropdown-item" href="/profile/">Profile</a></li>
                <li><a class="dropdown-item" href="/logout/">Logout</a></li>
            </ul>
        </div>
        """
    else:
        return """
        <div class="nav-item">
            <a class="nav-link" href="/login/">Sign In</a>
        </div>
        <div class="nav-item">
            <a class="nav-link" href="/register/">Register</a>
        </div>
        """

def add_to_document_history(draft_name, action, user, details=""):
    """Add an entry to document history"""
    if draft_name not in DOCUMENT_HISTORY:
        DOCUMENT_HISTORY[draft_name] = []
    
    entry = {
        'action': action,
        'user': user,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'details': details
    }
    DOCUMENT_HISTORY[draft_name].insert(0, entry)  # Add to beginning (most recent first)

def toggle_comment_like(draft_name, comment_id, user):
    """Toggle like on a comment"""
    like_key = f"{draft_name}:{comment_id}"
    if like_key not in COMMENT_LIKES:
        COMMENT_LIKES[like_key] = set()
    
    if user in COMMENT_LIKES[like_key]:
        COMMENT_LIKES[like_key].remove(user)
        return False  # Unliked
    else:
        COMMENT_LIKES[like_key].add(user)
        return True  # Liked

def get_comment_likes(draft_name, comment_id):
    """Get like count for a comment"""
    like_key = f"{draft_name}:{comment_id}"
    return len(COMMENT_LIKES.get(like_key, set()))

def is_comment_liked(draft_name, comment_id, user):
    """Check if user has liked a comment"""
    like_key = f"{draft_name}:{comment_id}"
    return user in COMMENT_LIKES.get(like_key, set())

def add_comment_reply(draft_name, parent_comment_id, reply_text, user):
    """Add a reply to a comment"""
    # Create reply in database
    reply = Comment(
        draft_name=draft_name,
        text=reply_text,
        author=user['name'],
        parent_id=int(parent_comment_id)
    )
    db.session.add(reply)
    db.session.commit()
    return reply

def build_comment_tree(draft_name):
    """Build a tree structure of comments with nested replies"""
    # Get all comments for this draft
    all_comments = Comment.query.filter_by(draft_name=draft_name).order_by(Comment.timestamp).all()

    # Create a dictionary for quick lookup
    comment_dict = {}
    for comment in all_comments:
        comment_dict[comment.id] = {
            'id': str(comment.id),
            'author': comment.author,
            'date': comment.timestamp.strftime('%Y-%m-%d %H:%M'),
            'comment': comment.text,
            'avatar': ''.join([word[0].upper() for word in comment.author.split()[:2]]),
            'replies': []
        }

    # Build the tree
    top_level_comments = []
    for comment in all_comments:
        if comment.parent_id is None:
            # Top-level comment
            top_level_comments.append(comment_dict[comment.id])
        else:
            # Reply - add to parent's replies
            if comment.parent_id in comment_dict:
                comment_dict[comment.parent_id]['replies'].append(comment_dict[comment.id])

    return top_level_comments

def render_comment_tree(comments, draft_name, level=0):
    """Recursively render comments and their nested replies"""
    if not comments:
        return ""

    indent_class = f"ms-{level * 4}" if level > 0 else ""
    html = f'<div class="{indent_class} mt-2">' if level > 0 else '<div class="mt-2">'

    for comment in comments:
        comment_id = comment.get('id', 'unknown')
        like_count = get_comment_likes(draft_name, comment_id)
        is_liked = is_comment_liked(draft_name, comment_id, get_current_user()['name']) if get_current_user() else False

        # Like button styling
        like_btn_class = "btn-outline-danger" if is_liked else "btn-outline-secondary"
        like_icon = "❤️" if is_liked else "🤍"

        # Size styling based on nesting level
        avatar_size = max(30 - level * 5, 20)  # Decrease avatar size for nested replies
        font_size = max(14 - level * 2, 12)    # Decrease font size for nested replies
        card_class = "mb-2" if level > 0 else "mb-3"

        html += f"""
        <div class="card {card_class}" id="comment-{comment_id}">
            <div class="card-body py-2">
                <div class="d-flex align-items-center mb-1">
                    <div class="avatar bg-{"secondary" if level > 0 else "primary"} text-white rounded-circle me-2" style="width: {avatar_size}px; height: {avatar_size}px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: {font_size - 2}px;">
                        {comment['avatar']}
                    </div>
                    <div>
                        <strong style="font-size: {font_size}px;">{comment['author']}</strong>
                        <small class="text-muted ms-2">{comment['date']}</small>
                    </div>
                </div>
                <p class="mb-2" style="font-size: {font_size}px;">{comment['comment']}</p>
                <div class="d-flex gap-2 align-items-center">
                    <button class="btn btn-sm {like_btn_class}" onclick="toggleLike('{comment_id}')" style="font-size: {font_size - 2}px;">
                        {like_icon} {like_count}
                    </button>
                    <button class="btn btn-sm btn-outline-primary" onclick="toggleReply('{comment_id}')" style="font-size: {font_size - 2}px;">
                        Reply
                    </button>
                </div>

                <!-- Reply form (hidden by default) -->
                <div id="reply-form-{comment_id}" class="mt-3" style="display: none;">
                    <form method="POST" class="d-flex gap-2">
                        <input type="hidden" name="action" value="reply">
                        <input type="hidden" name="parent_comment_id" value="{comment_id}">
                        <input type="text" name="reply_text" class="form-control" placeholder="Write a reply..." required style="font-size: {font_size}px;">
                        <button type="submit" class="btn btn-primary btn-sm" style="font-size: {font_size - 2}px;">Reply</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="toggleReply('{comment_id}')" style="font-size: {font_size - 2}px;">Cancel</button>
                    </form>
                </div>

                <!-- Nested replies -->
                {render_comment_tree(comment.get('replies', []), draft_name, level + 1)}
            </div>
        </div>
        """

    html += '</div>'
    return html


# Load MLTF data from test files
def load_draft_data():
    """Load draft data from test files"""
    drafts = []
    try:
        with open('/home/ubuntu/datatracker/test/data/draft-aliases', 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                # Extract draft name from the line
                match = re.search(r'xfilter-draft-([^:]+):', line)
                if match:
                    draft_name = match.group(1)
                    # Create realistic MLTF draft information
                    draft_title = draft_name.replace('-', ' ').title()
                    drafts.append({
                        'name': f'draft-{draft_name}',
                        'title': f'{draft_title} - A Protocol for {draft_title.split()[-1].title()}',
                        'rev': '00',
                        'pages': 15 + (hash(draft_name) % 20),  # Random pages 15-35
                        'words': 2000 + (hash(draft_name) % 3000),  # Random words 2000-5000
                        'date': '2024-01-15',
                        'status': 'Active',
                        'authors': ['John Doe', 'Jane Smith', 'Alice Brown'],
                        'group': f'{draft_name.split("-")[0].upper()} Working Group'
                    })
    except FileNotFoundError:
        print("Draft aliases file not found")
    return drafts

def load_group_data():
    """Load group data from test files"""
    groups = []

    # Desirable Properties mapping for better names and descriptions
    dp_descriptions = {
        'dp1-federated-auth': {
            'title': 'Federated Authentication & Accountability',
            'desc': 'Developing standards for federated authentication systems that enable cross-platform identity verification while maintaining accountability and audit trails.'
        },
        'dp2-participant-agency': {
            'title': 'Participant Agency and Empowerment',
            'desc': 'Creating frameworks that empower participants with full control over their digital presence, decision-making authority, and ability to shape their environment.'
        },
        'dp3-adaptive-governance': {
            'title': 'Adaptive Governance Supporting an Exponentially Growing Community',
            'desc': 'Designing governance systems that can scale with exponential community growth while maintaining fairness, participation, and adaptability to emerging challenges.'
        },
        'dp4-data-sovereignty': {
            'title': 'Data Sovereignty and Privacy',
            'desc': 'Establishing protocols for complete data ownership, privacy by design, and user-controlled data portability across the Meta-Layer ecosystem.'
        },
        'dp5-decentralized-namespace': {
            'title': 'Decentralized Namespace',
            'desc': 'Developing decentralized naming systems that provide persistent, user-controlled identifiers and namespaces independent of centralized authorities.'
        },
        'dp6-commerce': {
            'title': 'Commerce',
            'desc': 'Creating secure, transparent commerce protocols that enable value exchange, micropayments, and economic interactions within the Meta-Layer.'
        },
        'dp7-simplicity-interoperability': {
            'title': 'Simplicity and Interoperability',
            'desc': 'Designing systems that reduce complexity while ensuring seamless interoperability between different platforms, tools, and communities.'
        },
        'dp8-collaborative-environment': {
            'title': 'Collaborative Environment and Meta-Communities',
            'desc': 'Building frameworks for meta-communities that span multiple platforms and enable fluid collaboration across organizational boundaries.'
        },
        'dp9-developer-incentives': {
            'title': 'Developer and Community Incentives',
            'desc': 'Creating incentive structures that reward developers and communities for contributing to the ecosystem while aligning with long-term sustainability.'
        },
        'dp10-education': {
            'title': 'Education',
            'desc': 'Developing educational frameworks and tools that help participants understand and effectively use the Meta-Layer capabilities.'
        },
        'dp21-multi-modal': {
            'title': 'Multi-modal',
            'desc': 'Enabling seamless interaction across multiple communication modalities including text, voice, video, AR/VR, and emerging interaction paradigms.'
        },
        'dp11-safe-ethical-ai': {
            'title': 'Safe and Ethical AI',
            'desc': 'Establishing ethical frameworks and safety protocols for AI systems operating within the Meta-Layer to ensure alignment with human values.'
        },
        'dp12-community-ai-governance': {
            'title': 'Community-Based AI Governance',
            'desc': 'Creating community-driven governance models for AI systems that ensure transparency, accountability, and collective oversight.'
        },
        'dp13-ai-containment': {
            'title': 'AI Containment',
            'desc': 'Developing containment strategies and technical measures to prevent AI systems from exceeding intended boundaries or causing unintended consequences.'
        },
        'dp14-trust-transparency': {
            'title': 'Trust and Transparency',
            'desc': 'Building trust through transparent decision-making, auditable processes, and verifiable system behaviors throughout the Meta-Layer.'
        },
        'dp15-security-provenance': {
            'title': 'Security and Provenance',
            'desc': 'Ensuring security through comprehensive provenance tracking, secure infrastructure, and verifiable data lineage across all interactions.'
        },
        'dp16-roadmap-milestones': {
            'title': 'Roadmap and Milestones',
            'desc': 'Developing structured roadmaps with clear milestones that guide the evolution of the Meta-Layer while maintaining community alignment.'
        },
        'dp17-financial-sustainability': {
            'title': 'Financial Sustainability',
            'desc': 'Creating financial models and incentive structures that ensure the long-term sustainability and equitable growth of the Meta-Layer ecosystem.'
        },
        'dp18-feedback-reputation': {
            'title': 'Feedback Loops and Reputation',
            'desc': 'Implementing feedback mechanisms and reputation systems that reward positive contributions and maintain community standards.'
        },
        'dp19-community-engagement': {
            'title': 'Amplifying Presence and Community Engagement',
            'desc': 'Developing systems that amplify community participation, enhance visibility of contributions, and strengthen community bonds.'
        },
        'dp20-community-ownership': {
            'title': 'Community Ownership',
            'desc': 'Ensuring community ownership through decentralized governance, shared decision-making, and equitable distribution of value and control.'
        }
    }

    try:
        with open('/home/ubuntu/datatracker/test/data/group-aliases', 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                # Extract group name from the line
                match = re.search(r'xfilter-([^:]+):', line)
                if match:
                    group_name = match.group(1)

                    # Use specific DP description if available, otherwise generate generic one
                    if group_name in dp_descriptions:
                        dp_info = dp_descriptions[group_name]
                        group_title = dp_info['title']
                        description = dp_info['desc']
                    else:
                        # Fallback for non-DP groups
                        group_title = group_name.replace('-', ' ').title()
                        description = f'The {group_title} Working Group focuses on {group_title.lower()} standards and protocols for the Internet.'

                    groups.append({
                        'acronym': group_name,
                        'name': f'{group_title} Working Group',
                        'type': 'Working Group',
                        'state': 'Active',
                        'chairs': [f'Chair {i+1}' for i in range(1 + (hash(group_name) % 2))],  # 1-2 chairs
                        'description': description
                    })
    except FileNotFoundError:
        print("Group aliases file not found")
    return groups

# Load the data
DRAFTS = load_draft_data()
GROUPS = load_group_data()

# HTML Templates
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="{theme}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {{
            /* Light theme (default) */
            --bg-color: #ffffff;
            --bg-secondary: #f7f9fa;
            --bg-tertiary: #e1e8ed;
            --text-primary: #14171a;
            --text-secondary: #657786;
            --text-muted: #aab8c2;
            --border-color: #e1e8ed;
            --border-hover: #ccd6dd;
            --accent-color: #1d9bf0;
            --accent-hover: #1a8cd8;
            --success-color: #00ba7c;
            --warning-color: #f7b529;
            --error-color: #f4212e;
            --navbar-bg: #ffffff;
            --navbar-text: #14171a;
            --navbar-border: #e1e8ed;
            --card-bg: #ffffff;
            --card-border: #e1e8ed;
            --input-bg: #ffffff;
            --input-border: #657786;
            --shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            --shadow-hover: 0 2px 8px rgba(0, 0, 0, 0.15);
        }}

        [data-theme="dark"] {{
            /* Dark theme */
            --bg-color: #000000;
            --bg-secondary: #16181c;
            --bg-tertiary: #1d1f23;
            --text-primary: #ffffff;
            --text-secondary: #8b98a5;
            --text-muted: #6c7b8a;
            --border-color: #2f3336;
            --border-hover: #3d4043;
            --accent-color: #1d9bf0;
            --accent-hover: #1a8cd8;
            --success-color: #00ba7c;
            --warning-color: #f7b529;
            --error-color: #f4212e;
            --navbar-bg: #16181c;
            --navbar-text: #ffffff;
            --navbar-border: #2f3336;
            --card-bg: #16181c;
            --card-border: #2f3336;
            --input-bg: #16181c;
            --input-border: #3d4043;
            --shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
            --shadow-hover: 0 2px 8px rgba(0, 0, 0, 0.4);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            margin: 0;
            min-height: 100vh;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}

        /* Modern navbar similar to X */
        .navbar {{
            background-color: var(--navbar-bg) !important;
            border-bottom: 1px solid var(--navbar-border);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            box-shadow: var(--shadow);
            padding: 0;
            height: 53px;
            z-index: 2147483646 !important; /* Just below dropdown max */
            position: relative !important;
            overflow: visible !important;
        }}

        .navbar-brand {{
            color: var(--navbar-text) !important;
            font-weight: 700;
            font-size: 18px;
            padding: 16px 20px;
            margin: 0;
        }}

        .navbar-brand:hover {{
            color: var(--accent-color) !important;
        }}

        .navbar-nav {{
            align-items: center;
        }}

        .nav-link {{
            color: var(--text-secondary) !important;
            font-weight: 500;
            padding: 16px 20px;
            margin: 0;
            border-radius: 0;
            transition: all 0.2s ease;
        }}

        .nav-link:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color) !important;
        }}

        .nav-link.active {{
            color: var(--accent-color) !important;
            border-bottom: 3px solid var(--accent-color);
            background-color: transparent;
        }}

        /* Theme toggle button */
        .theme-toggle {{
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 18px;
            padding: 16px 20px;
            cursor: pointer;
            transition: color 0.2s ease;
        }}

        .theme-toggle:hover {{
            color: var(--accent-color);
        }}

        /* Cards with modern styling */
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            box-shadow: var(--shadow);
            transition: all 0.2s ease;
        }}

        .card:hover {{
            box-shadow: var(--shadow-hover);
            border-color: var(--border-hover);
        }}

        .card-header {{
            background-color: transparent;
            border-bottom: 1px solid var(--card-border);
            border-radius: 16px 16px 0 0 !important;
            padding: 16px 20px;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .card-body {{
            padding: 20px;
        }}

        /* Buttons styled like X */
        .btn {{
            border-radius: 20px;
            font-weight: 700;
            padding: 8px 16px;
            transition: all 0.2s ease;
        }}

        .btn-primary {{
            background-color: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }}

        .btn-primary:hover {{
            background-color: var(--accent-hover);
            border-color: var(--accent-hover);
            transform: translateY(-1px);
        }}

        .btn-outline-primary {{
            border-color: var(--text-secondary);
            color: var(--text-primary);
        }}

        .btn-outline-primary:hover {{
            background-color: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }}

        .btn-outline-secondary {{
            border-color: var(--border-color);
            color: var(--text-secondary);
        }}

        .btn-outline-secondary:hover {{
            background-color: var(--bg-secondary);
            border-color: var(--border-hover);
            color: var(--text-primary);
        }}

        /* Form inputs */
        .form-control {{
            background-color: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 8px;
            color: var(--text-primary) !important;
            padding: 12px 16px;
            transition: all 0.2s ease;
        }}

        input.form-control, textarea.form-control, select.form-control {{
            color: var(--text-primary) !important;
            background-color: var(--input-bg) !important;
            border-color: var(--input-border) !important;
        }}

        [data-theme="dark"] input,
        [data-theme="dark"] textarea,
        [data-theme="dark"] select,
        [data-theme="dark"] input.form-control,
        [data-theme="dark"] textarea.form-control,
        [data-theme="dark"] select.form-control {{
            color: #ffffff !important;
            background-color: #16181c !important;
            border-color: #3d4043 !important;
        }}

        .form-control:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.1);
            background-color: var(--input-bg);
        }}

        .form-control::placeholder {{
            color: var(--text-muted);
        }}

        .form-select {{
            background-color: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 8px;
            color: var(--text-primary) !important;
            padding: 12px 16px;
            transition: all 0.2s ease;
        }}

        [data-theme="dark"] .form-select {{
            color: #ffffff !important;
            background-color: #16181c !important;
            border-color: #3d4043 !important;
        }}

        /* Alerts */
        .alert {{
            border-radius: 12px;
            border: none;
            padding: 16px 20px;
        }}

        .alert-info {{
            background-color: rgba(29, 155, 240, 0.1);
            color: var(--accent-color);
        }}

        /* Badges */
        .badge {{
            border-radius: 12px;
            font-weight: 500;
            padding: 4px 8px;
        }}

        /* Breadcrumbs */
        .breadcrumb {{
            background-color: transparent;
            padding: 0;
            margin-bottom: 20px;
        }}

        .breadcrumb-item a {{
            color: var(--text-secondary);
        }}

        .breadcrumb-item.active {{
            color: var(--text-primary);
            font-weight: 500;
        }}

        /* Flash messages */
        #flash-messages {{
            position: fixed;
            top: 70px;
            right: 20px;
            z-index: 1000;
            max-width: 400px;
        }}

        .flash-message {{
            margin-bottom: 10px;
            padding: 12px 16px;
            border-radius: 12px;
            font-weight: 500;
            box-shadow: var(--shadow);
        }}

        .flash-success {{
            background-color: rgba(0, 186, 124, 0.1);
            color: var(--success-color);
            border: 1px solid rgba(0, 186, 124, 0.2);
        }}

        .flash-error {{
            background-color: rgba(244, 33, 46, 0.1);
            color: var(--error-color);
            border: 1px solid rgba(244, 33, 46, 0.2);
        }}

        .flash-info {{
            background-color: rgba(247, 181, 41, 0.1);
            color: var(--warning-color);
            border: 1px solid rgba(247, 181, 41, 0.2);
        }}

        /* Avatar styling */
        .avatar {{
            border-radius: 50%;
            object-fit: cover;
        }}

        /* Wider content layout for better readability */
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding-left: 24px;
            padding-right: 24px;
        }}

        /* Responsive adjustments */
        @media (max-width: 768px) {{
            .navbar-brand {{
                font-size: 16px;
                padding: 16px 15px;
            }}

            .nav-link {{
                padding: 16px 12px;
                font-size: 14px;
            }}

            .theme-toggle {{
                padding: 16px 15px;
            }}

            .card {{
                border-radius: 12px;
            }}

            .card-header {{
                border-radius: 12px 12px 0 0 !important;
            }}

            .container {{
                padding-left: 15px;
                padding-right: 15px;
            }}
        }}

        @media (min-width: 1200px) {{
            .container {{
                padding-left: 40px;
                padding-right: 40px;
            }}
        }}

        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: var(--bg-secondary);
        }}

        ::-webkit-scrollbar-thumb {{
            background: var(--border-color);
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: var(--border-hover);
        }}

        /* Dropdown menu z-index fix - maximum priority to ensure it's above everything */
        .dropdown-menu {{
            z-index: 2147483647 !important; /* Maximum possible z-index value */
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            background-color: var(--card-bg);
            margin-top: 8px;
            overflow: visible !important;
            position: absolute !important;
            top: 100% !important;
            left: 0 !important;
            min-width: 200px;
        }}

        /* Ensure dropdown container doesn't clip */
        .dropdown {{
            position: relative !important;
            overflow: visible !important;
        }}

        /* Prevent any parent from clipping the dropdown */
        .navbar .dropdown {{
            overflow: visible !important;
        }}

        /* Force dropdown to be on top of everything */
        .navbar .dropdown-menu {{
            z-index: 2147483647 !important;
            position: absolute !important;
            top: 100% !important;
            left: 0 !important;
        }}

        .dropdown-item {{
            color: var(--text-primary);
            padding: 12px 16px;
            transition: background-color 0.2s ease;
        }}

        .dropdown-item:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color);
        }}

        .dropdown-toggle {{
            border: none;
            background: none;
            color: var(--text-secondary);
            font-weight: 500;
            padding: 16px 12px;
            border-radius: 8px;
            transition: all 0.2s ease;
        }}

        .dropdown-toggle:hover {{
            background-color: var(--bg-secondary);
            color: var(--text-primary);
        }}

        .dropdown-toggle:focus {{
            box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.1);
        }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-layer-group me-2"></i>
                MLTF
            </a>
            <div class="navbar-nav">
                <a class="nav-link" href="/doc/all/">
                    <i class="fas fa-file-alt me-1"></i>Documents
                </a>
                <a class="nav-link" href="/group/">
                    <i class="fas fa-users me-1"></i>Working Groups
                </a>
                <!-- <a class="nav-link" href="/meeting/">
                    <i class="fas fa-calendar me-1"></i>Meetings
                </a>
                <a class="nav-link" href="/person/">
                    <i class="fas fa-user-friends me-1"></i>People
                </a> -->
                <a class="nav-link" href="/submit/">
                    <i class="fas fa-plus me-1"></i>Submit Draft
                </a>
            </div>
            <div class="navbar-nav ms-auto">
                {user_menu}
                <button class="theme-toggle" id="theme-toggle" title="Toggle theme">
                    <i class="fas fa-moon"></i>
                </button>
            </div>
        </div>
    </nav>

    <div id="flash-messages"></div>
    {content}

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Theme switching functionality
        const themeToggle = document.getElementById('theme-toggle');
        const html = document.documentElement;
        const icon = themeToggle.querySelector('i');

        // Load saved theme - prefer user preference over localStorage
        const userTheme = html.getAttribute('data-theme') || 'dark';
        const savedTheme = userTheme !== 'light' && userTheme !== 'dark' && userTheme !== 'auto' ?
            (localStorage.getItem('theme') || 'dark') : userTheme;
        html.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme);

        function updateThemeIcon(theme) {{
            if (theme === 'dark') {{
                icon.className = 'fas fa-sun';
                themeToggle.title = 'Switch to light mode';
            }} else {{
                icon.className = 'fas fa-moon';
                themeToggle.title = 'Switch to dark mode';
            }}
        }}

        themeToggle.addEventListener('click', () => {{
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        }});

        // Flash message auto-hide
        setTimeout(() => {{
            const flashMessages = document.querySelectorAll('.flash-message');
            flashMessages.forEach(msg => {{
                msg.style.opacity = '0';
                setTimeout(() => msg.remove(), 300);
            }});
        }}, 5000);
    </script>
</body>
</html>
"""

SUBMIT_TEMPLATE = """
<div class="container mt-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/">Home</a></li>
            <li class="breadcrumb-item active">Submit Draft</li>
        </ol>
    </nav>
    
    <h1>Submit Internet-Draft</h1>
    <p class="lead">Submit a new Meta-Layer Draft to the MLTF datatracker</p>
    
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5>Draft Submission Form</h5>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>

                    <form method="POST" enctype="multipart/form-data">
                        <div class="mb-3">
                            <label for="title" class="form-label">Document Title *</label>
                            <input type="text" class="form-control" id="title" name="title" required 
                                   placeholder="Enter the document title">
                        </div>
                        
                        <div class="mb-3">
                            <label for="authors" class="form-label">Authors *</label>
                            <input type="text" class="form-control" id="authors" name="authors" required 
                                   placeholder="Comma-separated list of authors (e.g., John Doe, Jane Smith)">
                        </div>
                        
                        <div class="mb-3">
                            <label for="abstract" class="form-label">Abstract</label>
                            <textarea class="form-control" id="abstract" name="abstract" rows="4" 
                                      placeholder="Brief description of the document"></textarea>
                        </div>
                        
                        <div class="mb-3">
                            <label for="group" class="form-label">Working Group (Optional)</label>
                            <select class="form-select" id="group" name="group">
                                <option value="">Select a Working Group</option>
                                <option value="httpbis">HTTP</option>
                                <option value="quic">QUIC</option>
                                <option value="tls">TLS</option>
                                <option value="dnsop">DNSOP</option>
                                <option value="rtgwg">RTGWG</option>
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label for="file" class="form-label">Document File *</label>
                            <input type="file" class="form-control" id="file" name="file" required 
                                   accept=".pdf,.txt,.xml,.doc,.docx">
                            <div class="form-text">Supported formats: PDF, TXT, XML, DOC, DOCX (max 16MB)</div>
                        </div>
                        
                        <div class="mb-3">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="terms" required>
                                <label class="form-check-label" for="terms">
                                    I agree to the <a href="#" target="_blank">MLTF submission terms</a>
                                </label>
                            </div>
                        </div>
                        
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                            <button type="submit" class="btn btn-primary">Submit Draft</button>
                            <a href="/" class="btn btn-secondary">Cancel</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Submission Guidelines</h5>
                </div>
                <div class="card-body">
                    <h6>File Requirements:</h6>
                    <ul class="small">
                        <li>PDF format preferred</li>
                        <li>Maximum 16MB file size</li>
                        <li>Use standard MLTF formatting</li>
                    </ul>

                    <h6>Content Requirements:</h6>
                    <ul class="small">
                        <li>Clear, descriptive title</li>
                        <li>Complete author information</li>
                        <li>Abstract describing the work</li>
                        <li>Proper MLTF document structure</li>
                    </ul>
                    
                    <h6>Review Process:</h6>
                    <ul class="small">
                        <li>Initial technical review</li>
                        <li>Working group consideration</li>
                        <li>IESG review (if applicable)</li>
                        <li>Publication decision</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>
"""

@app.route('/submit/', methods=['GET', 'POST'])
@require_auth
def submit_draft():
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    # Generate working group options dynamically
    group_options = '<option value="">Select a Working Group</option>'
    for group in GROUPS:
        group_options += f'<option value="{group["acronym"]}">{group["name"]}</option>'

    # Replace the hardcoded options in the template
    submit_template = SUBMIT_TEMPLATE.replace(
        '''<option value="">Select a Working Group</option>
                                <option value="httpbis">HTTP</option>
                                <option value="quic">QUIC</option>
                                <option value="tls">TLS</option>
                                <option value="dnsop">DNSOP</option>
                                <option value="rtgwg">RTGWG</option>''',
        group_options
    )

    if request.method == 'POST':
        # Handle form submission
        title = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        abstract = request.form.get('abstract', '').strip()
        group = request.form.get('group', '').strip()
        file = request.files.get('file')

        # Validation
        if not title or not authors or not file:
            flash('Title, authors, and file are required', 'error')
            return BASE_TEMPLATE.format(title="Submit Internet-Draft - MLTF", theme=current_theme, user_menu=user_menu, content=submit_template)

        # Process authors (comma-separated)
        authors_list = [a.strip() for a in authors.split(',') if a.strip()]

        # Generate submission ID (simple increment)
        import random
        import string
        submission_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # Save file
        filename = f"{submission_id}-{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Create submission record
        submission = Submission(
            id=submission_id,
            title=title,
            authors=authors_list,
            abstract=abstract,
            group=group,
            filename=filename,
            file_path=file_path,
            submitted_by=get_current_user()['name']
        )

        db.session.add(submission)
        db.session.commit()

        # Log the action
        add_to_document_history(f"draft-{submission_id}", "submitted", get_current_user()['name'], f"New draft submitted: {title}")

        flash('Draft submitted successfully!', 'success')
        return redirect(f'/submit/status/')

    return BASE_TEMPLATE.format(title="Submit Internet-Draft - MLTF", theme=current_theme, user_menu=user_menu, content=submit_template)

SUBMISSION_STATUS_TEMPLATE = """
<div class="container mt-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/">Home</a></li>
            <li class="breadcrumb-item"><a href="/submit/">Submit Draft</a></li>
            <li class="breadcrumb-item active">Submission Status</li>
        </ol>
    </nav>
    
    <h1>Submission Status</h1>
    <p class="lead">Track your Internet-Draft submission</p>

    <div id="flash-messages"></div>

    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5>Submission Details</h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Submission ID:</strong></div>
                        <div class="col-sm-9"><code>{{ submission.id }}</code></div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Status:</strong></div>
                        <div class="col-sm-9">
                            <span class="badge bg-primary">{{ submission.status.title() }}</span>
                        </div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Title:</strong></div>
                        <div class="col-sm-9">{{ submission.title }}</div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Authors:</strong></div>
                        <div class="col-sm-9">{{ submission.authors | join(', ') }}</div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Draft Name:</strong></div>
                        <div class="col-sm-9"><code>{{ submission.draft_name }}</code></div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Submitted:</strong></div>
                        <div class="col-sm-9">{{ submission.submitted_at }}</div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>File:</strong></div>
                        <div class="col-sm-9">
                            <code>{{ submission.filename }}</code>
                            <a href="/download/{{ submission.id }}" class="btn btn-sm btn-outline-primary ms-2">Download</a>
                        </div>
                    </div>
                    {% if submission.abstract %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Abstract:</strong></div>
                        <div class="col-sm-9">{{ submission.abstract }}</div>
                    </div>
                    {% endif %}

                    <h6 class="mt-4">File Preview</h6>
                    <div class="border rounded p-3 bg-light">
                        <pre class="mb-0" style="font-size: 0.9em; max-height: 400px; overflow-y: auto;">{{ file_content }}</pre>
                    </div>

                    {% if submission.status == 'submitted' and (current_user and (current_user.role in ['admin', 'editor'] or current_user.name in ['admin', 'Admin User'])) %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Actions:</strong></div>
                        <div class="col-sm-9">
                            <form method="POST" action="/submit/approve/{{ submission.id }}" style="display: inline;">
                                <button type="submit" class="btn btn-success btn-sm">Approve & Publish</button>
                            </form>
                            <form method="POST" action="/submit/reject/{{ submission.id }}" style="display: inline; margin-left: 10px;">
                                <button type="submit" class="btn btn-danger btn-sm">Reject</button>
                            </form>
                        </div>
                    </div>
                    {% endif %}
                    {% if submission.abstract %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Abstract:</strong></div>
                        <div class="col-sm-9">{{ submission.abstract }}</div>
                    </div>
                    {% endif %}
                </div>
            </div>
            
            <div class="card mt-3">
                <div class="card-header">
                    <h5>Review Timeline</h5>
                </div>
                <div class="card-body">
                    <div class="timeline">
                        <div class="timeline-item">
                            <div class="timeline-marker bg-success"></div>
                            <div class="timeline-content">
                                <h6>Submitted</h6>
                                <p class="text-muted small">{{ submission.submitted_at }}</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            {% if submission.status in ['approved', 'rejected'] %}
                            <div class="timeline-marker bg-success"></div>
                            <div class="timeline-content">
                                <h6>Initial Review</h6>
                                <p class="text-muted small">
                                    {{ 'Completed' if submission.status == 'approved' else 'Rejected' }}
                                    {% if submission.approved_at %}
                                    - {{ submission.approved_at }}
                                    {% elif submission.rejected_at %}
                                    - {{ submission.rejected_at }}
                                    {% endif %}
                                </p>
                            </div>
                            {% else %}
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>Initial Review</h6>
                                <p class="text-muted small">In Progress</p>
                            </div>
                            {% endif %}
                        </div>
                        {% if submission.status == 'approved' %}
                        <div class="timeline-item">
                            <div class="timeline-marker bg-primary"></div>
                            <div class="timeline-content">
                                <h6>Published</h6>
                                <p class="text-muted small">Available in document repository</p>
                            </div>
                        </div>
                        {% else %}
                        <div class="timeline-item">
                            <div class="timeline-marker bg-light"></div>
                            <div class="timeline-content">
                                <h6>Working Group Review</h6>
                                <p class="text-muted small">Pending initial approval</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            <div class="timeline-marker bg-light"></div>
                            <div class="timeline-content">
                                <h6>IESG Review</h6>
                                <p class="text-muted small">Pending working group review</p>
                            </div>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Actions</h5>
                </div>
                <div class="card-body">
                    <a href="/submit/" class="btn btn-primary w-100 mb-2">Submit Another Draft</a>
                    <a href="/doc/all/" class="btn btn-outline-secondary w-100 mb-2">View All Documents</a>
                    <a href="/" class="btn btn-outline-secondary w-100">Back to Home</a>
                </div>
            </div>
            
            <div class="card mt-3">
                <div class="card-header">
                    <h5>Need Help?</h5>
                </div>
                <div class="card-body">
                    <p class="small">If you have questions about your submission:</p>
                    <ul class="small">
                        <li>Check the <a href="#" target="_blank">submission guidelines</a></li>
                        <li>Contact the <a href="mailto:draft@metalayer.org">MLTF Secretariat</a></li>
                        <li>Join the <a href="#" target="_blank">MLTF discussion list</a></li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
.timeline {
    position: relative;
    padding-left: 30px;
}

.timeline-item {
    position: relative;
    margin-bottom: 20px;
}

.timeline-marker {
    position: absolute;
    left: -25px;
    top: 5px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 0 0 2px #dee2e6;
}

.timeline-content h6 {
    margin-bottom: 5px;
    font-weight: 600;
}

.timeline-content p {
    margin-bottom: 0;
}
</style>
"""

@app.route('/submit/status/')
@require_auth
def submission_status():
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    # Get user's submissions
    user_name = get_current_user()['name']
    submissions = Submission.query.filter_by(submitted_by=user_name).order_by(Submission.submitted_at.desc()).all()

    # Format submissions for template
    submissions_html = ""
    for submission in submissions:
        status_badge = {
            'submitted': 'badge bg-warning',
            'approved': 'badge bg-success',
            'rejected': 'badge bg-danger'
        }.get(submission.status, 'badge bg-secondary')

        submissions_html += f"""
        <div class="submission-item">
            <div class="card mb-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">{submission.title}</h6>
                    <span class="{status_badge}">{submission.status.title()}</span>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-8">
                            <p class="mb-2"><strong>Authors:</strong> {', '.join(submission.authors)}</p>
                            <p class="mb-2"><strong>Group:</strong> {submission.group or 'None'}</p>
                            <p class="mb-2"><strong>Submitted:</strong> {submission.submitted_at.strftime('%Y-%m-%d %H:%M')}</p>
                        </div>
                        <div class="col-md-4 text-end">
                            <a href="/doc/draft/{submission.id}/" class="btn btn-sm btn-outline-primary">View Draft</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/submit/">Submit Draft</a></li>
                <li class="breadcrumb-item active">Submission Status</li>
            </ol>
        </nav>

        <h1>My Submissions</h1>

        {f'<div class="alert alert-info">You have {len(submissions)} submission(s).</div>' if submissions else '<div class="alert alert-info">You have no submissions yet.</div>'}

        {submissions_html}

        <div class="mt-4">
            <a href="/submit/" class="btn btn-primary">Submit Another Draft</a>
            <a href="/" class="btn btn-secondary ms-2">Back to Home</a>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(title="Submission Status - MLTF", theme=current_theme, user_menu=user_menu, content=content)

LOGIN_TEMPLATE = """
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">Sign In</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>
                    
                    <form method="POST">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" id="password" name="password" required>
                        </div>
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Sign In</button>
                        </div>
                    </form>
                    
                    <hr>
                    <div class="text-center">
                        <p class="mb-0">Don't have an account? <a href="/register/">Create one</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

REGISTER_TEMPLATE = """
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">Create Account</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>
                    
                    <form method="POST">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name</label>
                            <input type="text" class="form-control" id="name" name="name" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" id="email" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" id="password" name="password" required minlength="6">
                        </div>
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Create Account</button>
                        </div>
                    </form>
                    
                    <hr>
                    <div class="text-center">
                        <p class="mb-0">Already have an account? <a href="/login/">Sign in</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

PROFILE_TEMPLATE = """
<div class="container mt-4">
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">User Profile</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>
                    
                    <!-- Profile Information -->
                    <h5>Profile Information</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_profile">
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name</label>
                            <input type="text" class="form-control" id="name" name="name" value="{current_user_name}" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" id="email" name="email" value="{current_user_email}" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" value="{session_user}" readonly>
                        </div>
                        <button type="submit" class="btn btn-primary">Update Profile</button>
                    </form>
                    
                    <hr>
                    
                    <!-- Password Change -->
                    <h5>Change Password</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_password">
                        <div class="mb-3">
                            <label for="old_password" class="form-label">Current Password</label>
                            <input type="password" class="form-control" id="old_password" name="old_password" required>
                        </div>
                        <div class="mb-3">
                            <label for="new_password" class="form-label">New Password</label>
                            <input type="password" class="form-control" id="new_password" name="new_password" required minlength="6">
                        </div>
                        <button type="submit" class="btn btn-warning">Change Password</button>
                    </form>

                    <hr>

                    <!-- Theme Preferences -->
                    <h5>Theme Preferences</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_theme">
                        <div class="mb-3">
                            <label class="form-label">Preferred Theme</label>
                            <select class="form-select" name="theme" id="theme-select">
                                <option value="light" {light_selected}>Light Mode</option>
                                <option value="dark" {dark_selected}>Dark Mode</option>
                                <option value="auto" {auto_selected}>Auto (System)</option>
                            </select>
                            <div class="form-text">Choose your preferred theme. Auto will follow your system's preference.</div>
                        </div>
                        <button type="submit" class="btn btn-secondary">Save Theme Preference</button>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Account Status</h5>
                </div>
                <div class="card-body">
                    <p><strong>Username:</strong> {session_user}</p>
                    <p><strong>Name:</strong> {current_user_name}</p>
                    <p><strong>Email:</strong> {current_user_email}</p>
                    <p><strong>Status:</strong> <span class="badge bg-success">Active</span></p>
                </div>
            </div>
        </div>
    </div>
</div>
"""

# Authentication routes
@app.route('/login/', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user'] = username
            # Set user's preferred theme in session
            session['theme'] = user.theme
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'error')
    
    # Generate user menu for login page
    user_menu = """
    <div class="nav-item">
        <a class="nav-link" href="/register/">Register</a>
    </div>
    """
    return render_template_string(BASE_TEMPLATE.format(title="Login - MLTF", theme="light", user_menu=user_menu, content=LOGIN_TEMPLATE))

@app.route('/logout/')
def logout():
    """User logout"""
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/register/', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()

        # Check if username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists.', 'error')
            else:
                flash('Email already registered.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            # Create new user in database
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                name=name,
                email=email,
                role='user',  # Default role
                theme='dark'  # Default theme
            )
            db.session.add(new_user)
            db.session.commit()

            session['user'] = username
            flash(f'Account created successfully! Welcome, {name}!', 'success')
            return redirect(url_for('home'))
    
    # Generate user menu for register page
    user_menu = """
    <div class="nav-item">
        <a class="nav-link" href="/login/">Sign In</a>
    </div>
    """
    return render_template_string(BASE_TEMPLATE.format(title="Register - MLTF", theme="light", user_menu=user_menu, content=REGISTER_TEMPLATE))

@app.route('/profile/', methods=['GET', 'POST'])
@require_auth
def profile():
    """User profile management"""
    current_user = get_current_user()
    
    if request.method == 'POST':
        action = request.form.get('action')
        user = User.query.filter_by(username=session['user']).first()

        if action == 'update_password':
            old_password = request.form.get('old_password', '').strip()
            new_password = request.form.get('new_password', '').strip()

            if check_password_hash(user.password_hash, old_password):
                if len(new_password) >= 6:
                    user.password_hash = generate_password_hash(new_password)
                    db.session.commit()
                    flash('Password updated successfully!', 'success')
                else:
                    flash('New password must be at least 6 characters.', 'error')
            else:
                flash('Current password is incorrect.', 'error')

        elif action == 'update_profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()

            # Check if email is already taken by another user
            existing_email = User.query.filter(User.email == email, User.username != session['user']).first()
            if existing_email:
                flash('Email already registered to another account.', 'error')
            else:
                if name:
                    user.name = name
                if email:
                    user.email = email
                db.session.commit()
                flash('Profile updated successfully!', 'success')

        elif action == 'update_theme':
            theme = request.form.get('theme', 'dark').strip()
            if theme in ['light', 'dark', 'auto']:
                user.theme = theme
                db.session.commit()
                session['theme'] = theme  # Update session immediately
                flash('Theme preference updated successfully!', 'success')
            else:
                flash('Invalid theme selection.', 'error')
    
    # Generate user menu
    user_menu = generate_user_menu()
    
    current_theme = current_user.get('theme', 'dark')
    light_selected = 'selected' if current_theme == 'light' else ''
    dark_selected = 'selected' if current_theme == 'dark' else ''
    auto_selected = 'selected' if current_theme == 'auto' else ''

    profile_content = PROFILE_TEMPLATE.format(
        current_user_name=current_user['name'],
        current_user_email=current_user['email'],
        current_user_theme=current_theme,
        light_selected=light_selected,
        dark_selected=dark_selected,
        auto_selected=auto_selected,
        session_user=session['user']
    )
    return render_template_string(BASE_TEMPLATE.format(title="Profile - MLTF", theme=current_theme, user_menu=user_menu, content=profile_content))

@app.route('/admin/')
@require_role('admin')
def admin_dashboard():
    user_menu = generate_user_menu()

    # Enhanced admin statistics
    total_users = User.query.count()
    total_groups = len(GROUPS)
    total_submissions = Submission.query.count()
    approved_drafts = PublishedDraft.query.count()
    pending_chairs = WorkingGroupChair.query.filter_by(approved=False).count()

    # Recent activity and alerts
    pending_submissions = Submission.query.filter_by(status='submitted').count()
    recent_submissions = Submission.query.order_by(Submission.submitted_at.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    # Get most active drafts (by comment count or views if we had them)
    # For now, just show recent submissions as proxy
    active_drafts = Submission.query.order_by(Submission.submitted_at.desc()).limit(10).all()

    # Most active users (by login frequency - simplified)
    active_users = User.query.order_by(User.last_login.desc()).limit(10).all()

    # Build recent activity feed
    activity_html = ""
    for submission in recent_submissions[:3]:  # Show last 3 submissions
        activity_html += f"""
        <div class="activity-item mb-2">
            <small class="text-muted">
                <i class="fas fa-file-alt me-1"></i>
                New submission: <strong>{submission.title[:50]}...</strong>
                by {submission.submitted_by}
                <span class="float-end">{submission.submitted_at.strftime('%m/%d %H:%M')}</span>
            </small>
        </div>
        """

    for user in recent_users[:2]:  # Show last 2 new users
        activity_html += f"""
        <div class="activity-item mb-2">
            <small class="text-muted">
                <i class="fas fa-user-plus me-1"></i>
                New user: <strong>{user.name}</strong> ({user.email})
                <span class="float-end">{user.created_at.strftime('%m/%d %H:%M')}</span>
            </small>
        </div>
        """

    # Build alerts section
    alerts_html = ""
    if pending_submissions > 0:
        alerts_html += f"""
        <div class="alert alert-warning alert-dismissible fade show" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>{pending_submissions}</strong> draft submission(s) pending review
            <a href="/admin/submissions/" class="alert-link">Review now</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    if pending_chairs > 0:
        alerts_html += f"""
        <div class="alert alert-info alert-dismissible fade show" role="alert">
            <i class="fas fa-users me-2"></i>
            <strong>{pending_chairs}</strong> working group chair(s) pending approval
            <a href="/group/" class="alert-link">Manage chairs</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <!-- Alerts Section -->
        <div id="admin-alerts" class="mb-4">
            {alerts_html}
        </div>

        <div class="row">
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1>Admin Dashboard</h1>
                    <div>
                        <a href="/admin/users/" class="btn btn-outline-primary me-2">Manage Users</a>
                        <a href="/admin/submissions/" class="btn btn-outline-success">Review Submissions</a>
                    </div>
                </div>

                <!-- Statistics Cards -->
                <div class="row mb-4">
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-primary mb-1">{total_users}</h4>
                                <p class="mb-0 small">Total Users</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-success mb-1">{total_groups}</h4>
                                <p class="mb-0 small">Working Groups</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-warning mb-1">{total_submissions}</h4>
                                <p class="mb-0 small">Total Submissions</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-info mb-1">{approved_drafts}</h4>
                                <p class="mb-0 small">Published Drafts</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-danger mb-1">{pending_submissions}</h4>
                                <p class="mb-0 small">Pending Review</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-secondary mb-1">{pending_chairs}</h4>
                                <p class="mb-0 small">Pending Chairs</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <!-- Recent Activity -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">Recent Activity</h5>
                                <span class="badge bg-primary">Live</span>
                            </div>
                            <div class="card-body">
                                {activity_html}
                                <hr>
                                <a href="/admin/activity/" class="btn btn-sm btn-outline-primary">View All Activity</a>
                            </div>
                        </div>
                    </div>

                    <!-- Quick Actions -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Quick Actions</h5>
                            </div>
                            <div class="card-body">
                                <div class="d-grid gap-2">
                                    <a href="/admin/submissions/" class="btn btn-success">
                                        <i class="fas fa-check-circle me-2"></i>Review Submissions ({pending_submissions} pending)
                                    </a>
                                    <a href="/admin/users/" class="btn btn-primary">
                                        <i class="fas fa-users me-2"></i>Manage Users ({total_users} total)
                                    </a>
                                    <a href="/group/" class="btn btn-info">
                                        <i class="fas fa-users-cog me-2"></i>Manage Working Groups ({pending_chairs} pending chairs)
                                    </a>
                                    <a href="/admin/analytics/" class="btn btn-secondary">
                                        <i class="fas fa-chart-bar me-2"></i>View Analytics
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Content Management Section -->
                <div class="row mt-4">
                    <div class="col-12">
                        <h3 class="mb-3">Content Management</h3>
                    </div>
                </div>

                <div class="row">
                    <!-- Most Active Drafts -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent Draft Submissions</h5>
                            </div>
                            <div class="card-body">
                                <div class="list-group list-group-flush">
                                    {"".join([f'''
                                    <a href="/doc/draft/{draft.id}/" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{draft.title[:40]}...</strong>
                                            <br><small class="text-muted">by {draft.submitted_by} • {draft.submitted_at.strftime('%m/%d')}</small>
                                        </div>
                                        <span class="badge bg-{'warning' if draft.status == 'submitted' else 'success'}">{draft.status}</span>
                                    </a>
                                    ''' for draft in active_drafts[:5]])}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Active Users -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent User Activity</h5>
                            </div>
                            <div class="card-body">
                                <div class="list-group list-group-flush">
                                    {"".join([f'''
                                    <div class="list-group-item d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{user.name}</strong>
                                            <br><small class="text-muted">{user.email} • {user.role}</small>
                                        </div>
                                        <small class="text-muted">
                                            {user.last_login.strftime('%m/%d %H:%M') if user.last_login else 'Never logged in'}
                                        </small>
                                    </div>
                                    ''' for user in active_users[:5]])}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Admin Dashboard - MLTF",
        theme=get_current_user().get('theme', 'dark'),
        content=content,
        user_menu=user_menu
    )

@app.route('/admin/users/')
@require_role('admin')
def admin_users():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    # Get all users with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')

    query = User.query

    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.name.contains(search),
                User.email.contains(search)
            )
        )

    if role_filter:
        query = query.filter_by(role=role_filter)

    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    total_users = query.count()

    # Build user rows
    user_rows = ""
    for user in users.items:
        role_badge = {
            'admin': 'badge bg-danger',
            'editor': 'badge bg-warning',
            'user': 'badge bg-secondary'
        }.get(user.role, 'badge bg-secondary')

        last_login = user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'

        user_rows += f"""
        <tr>
            <td>
                <strong>{user.name}</strong><br>
                <small class="text-muted">@{user.username}</small>
            </td>
            <td>{user.email}</td>
            <td><span class="{role_badge}">{user.role.title()}</span></td>
            <td>{user.theme.title()}</td>
            <td>{user.created_at.strftime('%Y-%m-%d')}</td>
            <td>{last_login}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary btn-sm" onclick="changeRole('{user.username}', '{user.role}')">
                        <i class="fas fa-user-edit"></i>
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteUser('{user.username}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
        """

    # Role filter options
    role_options = f"""
    <option value="">All Roles</option>
    <option value="admin" {'selected' if role_filter == 'admin' else ''}>Admin</option>
    <option value="editor" {'selected' if role_filter == 'editor' else ''}>Editor</option>
    <option value="user" {'selected' if role_filter == 'user' else ''}>User</option>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">User Management</li>
            </ol>
        </nav>

        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>User Management</h1>
            <div>
                <span class="badge bg-info me-2">Total: {total_users} users</span>
            </div>
        </div>

        <!-- Filters and Search -->
        <div class="card mb-4">
            <div class="card-body">
                <form method="GET" class="row g-3">
                    <div class="col-md-6">
                        <label for="search" class="form-label">Search Users</label>
                        <input type="text" class="form-control" id="search" name="search"
                               value="{search}" placeholder="Name, username, or email">
                    </div>
                    <div class="col-md-4">
                        <label for="role" class="form-label">Filter by Role</label>
                        <select class="form-select" id="role" name="role">
                            {role_options}
                        </select>
                    </div>
                    <div class="col-md-2 d-flex align-items-end">
                        <button type="submit" class="btn btn-primary me-2">
                            <i class="fas fa-search me-1"></i>Filter
                        </button>
                        <a href="/admin/users/" class="btn btn-outline-secondary">
                            <i class="fas fa-times"></i>
                        </a>
                    </div>
                </form>
            </div>
        </div>

        <!-- Users Table -->
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">Users ({users.total} total)</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Role</th>
                                <th>Theme</th>
                                <th>Joined</th>
                                <th>Last Login</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {user_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Pagination -->
        {f'''
        <nav aria-label="User pagination" class="mt-4">
            <ul class="pagination justify-content-center">
                {f'<li class="page-item {"disabled" if not users.has_prev else ""}"><a class="page-link" href="?page={users.prev_num}&search={search}&role={role_filter}">Previous</a></li>' if users.has_prev else ''}
                {''.join([f'<li class="page-item {"active" if i == users.page else ""}"><a class="page-link" href="?page={i}&search={search}&role={role_filter}">{i}</a></li>' for i in users.iter_pages()])}
                {f'<li class="page-item {"disabled" if not users.has_next else ""}"><a class="page-link" href="?page={users.next_num}&search={search}&role={role_filter}">Next</a></li>' if users.has_next else ''}
            </ul>
        </nav>
        ''' if users.pages > 1 else ''}
    </div>

    <script>
        function changeRole(username, currentRole) {{
            const roles = ['user', 'editor', 'admin'];
            const currentIndex = roles.indexOf(currentRole);
            const nextRole = roles[(currentIndex + 1) % roles.length];

            if (confirm('Change ' + username + '\'s role from ' + currentRole + ' to ' + nextRole + '?')) {{
                fetch('/admin/users/' + username + '/role', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{ role: nextRole }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error updating role');
                }});
            }}
        }}

        function deleteUser(username) {{
            if (confirm('Are you sure you want to delete user ' + username + '? This action cannot be undone.')) {{
                fetch('/admin/users/' + username + '/delete', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }}
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error deleting user');
                }});
            }}
        }}
    </script>
    """

    return BASE_TEMPLATE.format(
        title="User Management - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content
    )

@app.route('/admin/users/<username>/role', methods=['POST'])
@require_role('admin')
def change_user_role(username):
    data = request.get_json()
    new_role = data.get('role', '')

    if new_role not in ['user', 'editor', 'admin']:
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    # Prevent admin from demoting themselves
    current_admin = get_current_user()
    if user.id == current_admin['id'] and new_role != 'admin':
        return jsonify({'success': False, 'message': 'Cannot change your own admin role'}), 400

    user.role = new_role
    db.session.commit()

    # Log the action
    add_to_document_history(f"user-{user.id}", "role_changed", current_admin['name'],
                           f"Changed {user.name}'s role to {new_role}")

    return jsonify({'success': True, 'message': f'Role changed to {new_role}'})

@app.route('/admin/users/<username>/delete', methods=['POST'])
@require_role('admin')
def delete_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    # Prevent admin from deleting themselves
    current_admin = get_current_user()
    if user.id == current_admin['id']:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'}), 400

    # Log before deletion
    add_to_document_history(f"user-{user.id}", "user_deleted", current_admin['name'],
                           f"Deleted user {user.name} ({user.email})")

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'User deleted successfully'})

@app.route('/admin/submissions/')
@require_role('admin')
def admin_submissions():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    # Get submissions with filters
    status_filter = request.args.get('status', 'submitted')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Submission.query

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    submissions = query.order_by(Submission.submitted_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)

    # Build submission cards
    submission_cards = ""
    for submission in submissions.items:
        status_badge = {
            'submitted': 'badge bg-warning text-dark',
            'approved': 'badge bg-success',
            'rejected': 'badge bg-danger',
            'published': 'badge bg-info'
        }.get(submission.status, 'badge bg-secondary')

        # Get file size if file exists
        file_size = "N/A"
        if submission.file_path and os.path.exists(submission.file_path):
            file_size = f"{os.path.getsize(submission.file_path) / 1024:.1f} KB"

        action_buttons = ""
        if submission.status == 'submitted':
            action_buttons = f"""
            <button class="btn btn-success btn-sm me-2" onclick="approveSubmission('{submission.id}')">
                <i class="fas fa-check me-1"></i>Approve
            </button>
            <button class="btn btn-danger btn-sm me-2" onclick="rejectSubmission('{submission.id}')">
                <i class="fas fa-times me-1"></i>Reject
            </button>
            <button class="btn btn-info btn-sm" onclick="publishAsRFC('{submission.id}')">
                <i class="fas fa-star me-1"></i>Publish as RFC
            </button>
            """
        elif submission.status == 'approved':
            action_buttons = f"""
            <button class="btn btn-info btn-sm me-2" onclick="publishAsRFC('{submission.id}')">
                <i class="fas fa-star me-1"></i>Publish as RFC
            </button>
            <button class="btn btn-warning btn-sm" onclick="unapproveSubmission('{submission.id}')">
                <i class="fas fa-undo me-1"></i>Unapprove
            </button>
            """

        submission_cards += f"""
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <a href="/doc/draft/{submission.id}/" class="text-decoration-none">
                        {submission.title}
                    </a>
                </h6>
                <span class="{status_badge}">{submission.status.title()}</span>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-8">
                        <p class="mb-2"><strong>Authors:</strong> {', '.join(submission.authors)}</p>
                        <p class="mb-2"><strong>Group:</strong> {submission.group or 'None'}</p>
                        <p class="mb-2"><strong>Submitted:</strong> {submission.submitted_at.strftime('%Y-%m-%d %H:%M')} by {submission.submitted_by}</p>
                        <p class="mb-2"><strong>File:</strong> {submission.filename} ({file_size})</p>
                        {f'<p class="mb-2"><strong>Abstract:</strong> {submission.abstract[:200]}...</p>' if submission.abstract else ''}
                    </div>
                    <div class="col-md-4">
                        <div class="d-grid gap-2">
                            <a href="/doc/draft/{submission.id}/" class="btn btn-outline-primary btn-sm">
                                <i class="fas fa-eye me-1"></i>View Draft
                            </a>
                            {action_buttons}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    # Status filter options
    status_options = f"""
    <option value="all" {'selected' if status_filter == 'all' else ''}>All Submissions</option>
    <option value="submitted" {'selected' if status_filter == 'submitted' else ''}>Pending Review</option>
    <option value="approved" {'selected' if status_filter == 'approved' else ''}>Approved</option>
    <option value="rejected" {'selected' if status_filter == 'rejected' else ''}>Rejected</option>
    <option value="published" {'selected' if status_filter == 'published' else ''}>Published</option>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">Submission Management</li>
            </ol>
        </nav>

        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>Submission Management</h1>
            <div>
                <select class="form-select form-select-sm" onchange="changeStatusFilter(this.value)">
                    {status_options}
                </select>
            </div>
        </div>

        <!-- Statistics -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{Submission.query.filter_by(status='submitted').count()}</h4>
                        <p class="mb-0 small">Pending Review</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{Submission.query.filter_by(status='approved').count()}</h4>
                        <p class="mb-0 small">Approved</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-danger">{Submission.query.filter_by(status='rejected').count()}</h4>
                        <p class="mb-0 small">Rejected</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{Submission.query.filter_by(status='published').count()}</h4>
                        <p class="mb-0 small">Published as RFC</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Submissions -->
        <div id="submissions-container">
            {submission_cards}
        </div>

        <!-- Pagination -->
        {f'''
        <nav aria-label="Submission pagination" class="mt-4">
            <ul class="pagination justify-content-center">
                {f'<li class="page-item {"disabled" if not submissions.has_prev else ""}"><a class="page-link" href="?page={submissions.prev_num}&status={status_filter}">Previous</a></li>' if submissions.has_prev else ''}
                {''.join([f'<li class="page-item {"active" if i == submissions.page else ""}"><a class="page-link" href="?page={i}&status={status_filter}">{i}</a></li>' for i in submissions.iter_pages()])}
                {f'<li class="page-item {"disabled" if not submissions.has_next else ""}"><a class="page-link" href="?page={submissions.next_num}&status={status_filter}">Next</a></li>' if submissions.has_next else ''}
            </ul>
        </nav>
        ''' if submissions.pages > 1 else ''}
    </div>

    <script>
        function changeStatusFilter(status) {{
            window.location.href = '?status=' + status;
        }}

        function approveSubmission(submissionId) {{
            if (confirm('Approve this draft submission? It will be marked as approved and ready for publication.')) {{
                updateSubmissionStatus(submissionId, 'approved');
            }}
        }}

        function rejectSubmission(submissionId) {{
            const reason = prompt('Reason for rejection (optional):');
            updateSubmissionStatus(submissionId, 'rejected', reason);
        }}

        function unapproveSubmission(submissionId) {{
            if (confirm('Remove approval for this submission?')) {{
                updateSubmissionStatus(submissionId, 'submitted');
            }}
        }}

        function publishAsRFC(submissionId) {{
            const rfcNumber = prompt('Enter RFC number:');
            if (rfcNumber && confirm('Publish as RFC ' + rfcNumber + '?')) {{
                updateSubmissionStatus(submissionId, 'published', null, rfcNumber);
            }}
        }}

        function updateSubmissionStatus(submissionId, status, reason = null, rfcNumber = null) {{
            const data = {{ status: status }};
            if (reason) data.reason = reason;
            if (rfcNumber) data.rfc_number = rfcNumber;

                fetch('/admin/submissions/' + submissionId + '/status', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify(data)
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Error: ' + data.message);
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error updating submission status');
            }});
        }}
    </script>
    """

    return BASE_TEMPLATE.format(
        title="Submission Management - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content
    )

@app.route('/admin/submissions/<submission_id>/status', methods=['POST'])
@require_role('admin')
def update_submission_status(submission_id):
    data = request.get_json()
    new_status = data.get('status', '')
    reason = data.get('reason', '')
    rfc_number = data.get('rfc_number', '')

    if new_status not in ['submitted', 'approved', 'rejected', 'published']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400

    submission = Submission.query.filter_by(id=submission_id).first()
    if not submission:
        return jsonify({'success': False, 'message': 'Submission not found'}), 404

    old_status = submission.status
    submission.status = new_status

    if new_status == 'rejected' and reason:
        submission.rejected_at = datetime.utcnow()

    if new_status == 'published' and rfc_number:
        # Create a published RFC record
        published_draft = PublishedDraft(
            name=f"rfc{rfc_number}",
            title=submission.title,
            authors=submission.authors,
            group=submission.group,
            status='published',
            date=datetime.utcnow().strftime('%Y-%m-%d'),
            abstract=submission.abstract,
            submission_id=submission.id
        )
        db.session.add(published_draft)

    db.session.commit()

    # Log the action
    admin_user = get_current_user()
    action_details = f"Changed status from {old_status} to {new_status}"
    if reason:
        action_details += f" - Reason: {reason}"
    if rfc_number:
        action_details += f" - Published as RFC {rfc_number}"

    add_to_document_history(f"submission-{submission.id}", "status_changed",
                           admin_user['name'], action_details)

    return jsonify({'success': True, 'message': f'Status updated to {new_status}'})

@app.route('/admin/analytics/')
@require_role('admin')
def admin_analytics():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    # Most active drafts (recent submissions)
    active_drafts = Submission.query.order_by(Submission.submitted_at.desc()).limit(20).all()

    # Most active users (by recent logins and submissions)
    active_users = User.query.order_by(User.last_login.desc()).limit(20).all()

    # User role distribution
    role_stats = db.session.query(User.role, db.func.count(User.id)).group_by(User.role).all()
    role_data = {role: count for role, count in role_stats}

    # Submission status distribution
    status_stats = db.session.query(Submission.status, db.func.count(Submission.id)).group_by(Submission.status).all()
    status_data = {status: count for status, count in status_stats}

    # Recent activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_users = User.query.filter(User.created_at >= thirty_days_ago).count()
    recent_submissions = Submission.query.filter(Submission.submitted_at >= thirty_days_ago).count()

    # Build active drafts table
    draft_rows = ""
    for i, draft in enumerate(active_drafts, 1):
        draft_rows += f"""
        <tr>
            <td>{i}</td>
            <td>
                <a href="/doc/draft/{draft.id}/" class="text-decoration-none">
                    {draft.title[:60]}{'...' if len(draft.title) > 60 else ''}
                </a>
            </td>
            <td>{', '.join(draft.authors[:2])}{'...' if len(draft.authors) > 2 else ''}</td>
            <td>{draft.group or 'None'}</td>
            <td>{draft.submitted_at.strftime('%Y-%m-%d')}</td>
            <td><span class="badge bg-{ 'warning' if draft.status == 'submitted' else 'success' if draft.status == 'approved' else 'danger' if draft.status == 'rejected' else 'info'}">{draft.status}</span></td>
        </tr>
        """

    # Build active users table
    user_rows = ""
    for i, user in enumerate(active_users, 1):
        user_rows += f"""
        <tr>
            <td>{i}</td>
            <td>
                <strong>{user.name}</strong><br>
                <small class="text-muted">@{user.username}</small>
            </td>
            <td>{user.email}</td>
            <td><span class="badge bg-{ 'danger' if user.role == 'admin' else 'warning' if user.role == 'editor' else 'secondary'}">{user.role.title()}</span></td>
            <td>{user.created_at.strftime('%Y-%m-%d')}</td>
            <td>{user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'}</td>
        </tr>
        """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">Analytics</li>
            </ol>
        </nav>

        <h1 class="mb-4">Analytics Dashboard</h1>

        <!-- Overview Stats -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{recent_users}</h4>
                        <p class="mb-0 small">New Users (30 days)</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{recent_submissions}</h4>
                        <p class="mb-0 small">New Submissions (30 days)</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-primary">{len(active_drafts)}</h4>
                        <p class="mb-0 small">Total Submissions</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{len(active_users)}</h4>
                        <p class="mb-0 small">Registered Users</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <!-- Most Active Drafts -->
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Most Active Drafts</h5>
                        <small class="text-muted">Recent submissions and activity</small>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>#</th>
                                        <th>Title</th>
                                        <th>Authors</th>
                                        <th>Group</th>
                                        <th>Date</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {draft_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Most Active Users -->
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Most Active Users</h5>
                        <small class="text-muted">Users by recent login activity</small>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>#</th>
                                        <th>Name</th>
                                        <th>Email</th>
                                        <th>Role</th>
                                        <th>Joined</th>
                                        <th>Last Login</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {user_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Distribution Charts (Text-based) -->
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>User Role Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <strong>Admin:</strong> {role_data.get('admin', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-danger" style="width: {(role_data.get('admin', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Editor:</strong> {role_data.get('editor', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-warning" style="width: {(role_data.get('editor', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>User:</strong> {role_data.get('user', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-secondary" style="width: {(role_data.get('user', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Submission Status Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <strong>Submitted:</strong> {status_data.get('submitted', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-warning" style="width: {(status_data.get('submitted', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Approved:</strong> {status_data.get('approved', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-success" style="width: {(status_data.get('approved', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Published:</strong> {status_data.get('published', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-info" style="width: {(status_data.get('published', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Rejected:</strong> {status_data.get('rejected', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-danger" style="width: {(status_data.get('rejected', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Analytics - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content
    )

# Routes
@app.route('/')
def home():
    # Generate user menu
    current_user = get_current_user()
    current_theme = current_user.get('theme', 'dark') if current_user else 'light'

    if current_user:
        user_role = current_user.get('role', 'user')
        is_admin = user_role in ['admin', 'editor'] or current_user['name'] in ['admin', 'Admin User']

        admin_link = '<li><a class="dropdown-item" href="/admin/">Admin Dashboard</a></li>' if is_admin else ''

        user_menu = f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                {current_user['name']}
            </a>
            <ul class="dropdown-menu">
                {admin_link}
                <li><a class="dropdown-item" href="/profile/">Profile</a></li>
                <li><a class="dropdown-item" href="/logout/">Logout</a></li>
            </ul>
        </div>
        """
    else:
        user_menu = """
        <div class="nav-item">
            <a class="nav-link" href="/login/">Sign In</a>
        </div>
        <div class="nav-item">
            <a class="nav-link" href="/register/">Register</a>
        </div>
        """
    
    return BASE_TEMPLATE.format(title="MLTF", theme=current_theme, user_menu=user_menu, content=f"""
    
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8">
                <h1>MLTF</h1>
                <p class="lead">The day-to-day front-end to the MLTF database for people who work on Meta-Layer standards.</p>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent Documents</h5>
                            </div>
                            <div class="card-body">
                                <p>View the latest MLTF documents including drafts, RFCs, and other standards.</p>
                                <a href="/doc/all/" class="btn btn-primary">View All Documents</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Working Groups</h5>
                            </div>
                            <div class="card-body">
                                <p>Browse MLTF working groups and their activities.</p>
                                <a href="/group/" class="btn btn-primary">View Working Groups</a>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Meetings</h5>
                            </div>
                            <div class="card-body">
                                <p>Information about MLTF meetings and sessions.</p>
                                <a href="/meeting/" class="btn btn-primary">View Meetings</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>People</h5>
                            </div>
                            <div class="card-body">
                                <p>Directory of MLTF participants and contributors.</p>
                                <a href="/person/" class="btn btn-primary">View People</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Quick Stats</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Documents:</strong> {len(DRAFTS)}</p>
                        <p><strong>Working Groups:</strong> {len(GROUPS)}</p>
                        <p><strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """)

@app.route('/doc/active/')
def active_documents():
    """Show active documents (alias for all documents)"""
    return all_documents()

@app.route('/doc/all/')
def all_documents():
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    docs_html = ""
    for draft in DRAFTS:
        docs_html += f"""
        <div class="col-md-6 document-card">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title document-title">
                        <a href="/doc/draft/{draft['name']}/">{draft['name']}</a>
                    </h5>
                    <p class="card-text">{draft['title']}</p>
                    <div class="document-meta">
                        <span class="badge bg-secondary status-badge">{draft['status']}</span>
                        <span class="ms-2">Rev: {draft['rev']}</span>
                        <span class="ms-2">{draft['pages']} pages</span>
                        <span class="ms-2">{draft['words']} words</span>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            Authors: {', '.join(draft['authors'])}<br>
                            Group: {draft['group']}<br>
                            Date: {draft['date']}
                        </small>
                    </div>
                    <div class="mt-2">
                        <a href="/doc/draft/{draft['name']}/comments/" class="btn btn-sm btn-outline-primary">Comments</a>
                        <a href="/doc/draft/{draft['name']}/history/" class="btn btn-sm btn-outline-secondary">History</a>
                        <a href="/doc/draft/{draft['name']}/revisions/" class="btn btn-sm btn-outline-info">Revisions</a>
                    </div>
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <h1>All Documents</h1>
        <p>Showing {len(DRAFTS)} documents</p>

        <div class="row">
            {docs_html}
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(title="All Documents - MLTF", theme=current_theme, user_menu=user_menu, content=content)

@app.route('/doc/draft/<draft_name>/')
def draft_detail(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404
    
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    content = f"""
    <div class="container mt-4">
        <h1>{draft['name']}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Information</h5>
                    </div>
                    <div class="card-body">
                        <table class="table">
                            <tr><td><strong>Name:</strong></td><td>{draft['name']}</td></tr>
                            <tr><td><strong>Title:</strong></td><td>{draft['title']}</td></tr>
                            <tr><td><strong>Revision:</strong></td><td>{draft['rev']}</td></tr>
                            <tr><td><strong>Status:</strong></td><td><span class="badge bg-secondary">{draft['status']}</span></td></tr>
                            <tr><td><strong>Pages:</strong></td><td>{draft['pages']}</td></tr>
                            <tr><td><strong>Words:</strong></td><td>{draft['words']}</td></tr>
                            <tr><td><strong>Authors:</strong></td><td>{', '.join(draft['authors'])}</td></tr>
                            <tr><td><strong>Group:</strong></td><td>{draft['group']}</td></tr>
                            <tr><td><strong>Date:</strong></td><td>{draft['date']}</td></tr>
                        </table>
                    </div>
                </div>

                <div class="card mt-3">
                    <div class="card-header">
                        <h5>Abstract</h5>
                    </div>
                    <div class="card-body">
                        <p>{draft.get('abstract', 'Abstract not available for this draft.')}</p>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Actions</h5>
                    </div>
                    <div class="card-body">
                        <a href="/doc/draft/{draft['name']}/comments/" class="btn btn-primary w-100 mb-2">View Comments ({Comment.query.filter_by(draft_name=draft_name).count()})</a>
                        <a href="/doc/draft/{draft['name']}/history/" class="btn btn-secondary w-100 mb-2">View History</a>
                        <a href="/doc/draft/{draft['name']}/revisions/" class="btn btn-info w-100 mb-2">View Revisions</a>
                        <a href="/doc/draft/{draft['name']}/" class="btn btn-outline-primary w-100">Download PDF</a>
                    </div>
                </div>

                <div class="card mt-3">
                    <div class="card-header">
                        <h5>Quick Comment</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST" action="/doc/draft/{draft['name']}/comments/">
                            <div class="mb-3">
                                <textarea class="form-control" name="comment" rows="3" placeholder="Add a quick comment..." required></textarea>
                            </div>
                            <button type="submit" class="btn btn-success btn-sm w-100">Post Comment</button>
                        </form>
                    </div>
                </div>

                <div class="card mt-3">
                    <div class="card-header">
                        <h5>Related Documents</h5>
                    </div>
                    <div class="card-body">
                        <p>Related documents would appear here in the real datatracker.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(title=f"{draft['name']} - MLTF", theme=current_theme, user_menu=user_menu, content=content)

@app.route('/doc/draft/<draft_name>/comments/', methods=['GET', 'POST'])
@require_auth
def draft_comments(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    current_user = get_current_user()

    # Handle new comment submission
    if request.method == 'POST':
        action = request.form.get('action', 'comment')

        if action == 'comment':
            comment_text = request.form.get('comment', '').strip()
            if comment_text:
                # Create new comment in database
                new_comment = Comment(
                    draft_name=draft_name,
                    text=comment_text,
                    author=current_user['name']
                )
                db.session.add(new_comment)
                db.session.commit()

                # Add to document history
                add_to_document_history(draft_name, 'Comment added', current_user['name'], f'Added comment: {comment_text[:50]}...')

                flash('Comment added successfully!', 'success')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Please enter a comment.', 'error')

        elif action == 'like':
            comment_id = request.form.get('comment_id')
            if comment_id:
                liked = toggle_comment_like(draft_name, comment_id, current_user['name'])
                action_text = 'liked' if liked else 'unliked'
                flash(f'Comment {action_text}!', 'success')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Invalid comment ID.', 'error')

        elif action == 'reply':
            parent_comment_id = request.form.get('parent_comment_id')
            reply_text = request.form.get('reply_text', '').strip()
            if reply_text and parent_comment_id:
                add_comment_reply(draft_name, parent_comment_id, reply_text, current_user)
                flash('Reply added successfully!', 'success')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Please enter a reply.', 'error')

    # Get comments for this draft and build comment tree
    all_comments = build_comment_tree(draft_name)

    # Always include sample comments (real IETF-style comments)
    sample_comments = [
        {
            'id': 'sample_1',
            'author': 'John Smith',
            'date': '2024-01-15 14:30',
            'comment': 'This is a great draft! I think the approach is solid and the implementation details are well thought out.',
            'avatar': 'JS',
            'replies': []
        },
        {
            'id': 'sample_2',
            'author': 'Alice Johnson',
            'date': '2024-01-16 09:15',
            'comment': 'I have some concerns about the security implications mentioned in section 3.2. Could we discuss this further?',
            'avatar': 'AJ',
            'replies': []
        },
        {
            'id': 'sample_3',
            'author': 'Bob Wilson',
            'date': '2024-01-16 16:45',
            'comment': 'The performance metrics look promising. Have you considered the impact on legacy systems?',
            'avatar': 'BW',
            'replies': []
        }
    ]

    # Combine sample comments with user comments
    all_comments = sample_comments + all_comments

    # Render the comment tree with nested replies
    comments_html = render_comment_tree(all_comments, draft_name)

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{draft_name}</a></li>
                <li class="breadcrumb-item active">Comments</li>
            </ol>
        </nav>

        <h1>Comments for {draft_name}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary me-2">History</a>
            <a href="/doc/draft/{draft_name}/revisions/" class="btn btn-outline-secondary">Revisions</a>
        </div>

        <div class="row">
            <div class="col-md-8">
                <h3>Comments ({len(all_comments)})</h3>
                <div id="flash-messages"></div>
                {comments_html}

                <div class="card mt-4">
                    <div class="card-header">
                        <h5>Add a Comment</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label for="comment" class="form-label">Your Comment</label>
                                <textarea class="form-control" id="comment" name="comment" rows="4" placeholder="Enter your comment here..." required></textarea>
                            </div>
                            <button type="submit" class="btn btn-primary">Submit Comment</button>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Info</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Title:</strong> {draft['title']}</p>
                        <p><strong>Authors:</strong> {', '.join(draft['authors'])}</p>
                        <p><strong>Status:</strong> <span class="badge bg-secondary">{draft['status']}</span></p>
                        <p><strong>Last Updated:</strong> {draft['date']}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleLike(commentId) {{
            // Create a form to submit the like action
            const form = document.createElement('form');
            form.method = 'POST';
            form.style.display = 'none';

            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'like';

            const commentIdInput = document.createElement('input');
            commentIdInput.type = 'hidden';
            commentIdInput.name = 'comment_id';
            commentIdInput.value = commentId;

            form.appendChild(actionInput);
            form.appendChild(commentIdInput);
            document.body.appendChild(form);
            form.submit();
        }}

        function toggleReply(commentId) {{
            // Find the reply form for this comment
            const replyForm = document.getElementById('reply-form-' + commentId);
            if (replyForm) {{
                // Toggle visibility
                if (replyForm.style.display === 'none' || replyForm.style.display === '') {{
                    replyForm.style.display = 'block';
                }} else {{
                    replyForm.style.display = 'none';
                }}
            }}
        }}
    </script>
    """

    return BASE_TEMPLATE.format(title=f"Comments - {draft_name}", theme=current_theme, user_menu=user_menu, content=content)

@app.route('/doc/draft/<draft_name>/history/')
def draft_history(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    # Get history for this draft
    history = DocumentHistory.query.filter_by(draft_name=draft_name).order_by(DocumentHistory.timestamp.desc()).all()

    history_html = ""
    if history:
        for entry in history:
            history_html += f"""
            <div class="card mb-3">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="badge bg-primary">{entry.action}</span>
                        <small class="text-muted">{entry.timestamp.strftime('%Y-%m-%d %H:%M')}</small>
                    </div>
                    <p class="mb-1"><strong>User:</strong> {entry.user}</p>
                    <p class="mb-0">{entry.details}</p>
                </div>
            </div>
            """
    else:
        history_html = """
        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            No history available for this draft.
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{draft_name}</a></li>
                <li class="breadcrumb-item active">History</li>
            </ol>
        </nav>

        <h1>History for {draft_name}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
            <a href="/doc/draft/{draft_name}/revisions/" class="btn btn-outline-secondary">Revisions</a>
        </div>

        {history_html}
    </div>
    """

    return BASE_TEMPLATE.format(title=f"History - {draft_name}", theme=current_theme, user_menu=user_menu, content=content)

@app.route('/doc/draft/<draft_name>/revisions/')
def draft_revisions(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    # For now, show a simple revision history
    # In a real system, this would show actual revision differences
    revisions_html = f"""
    <div class="card">
        <div class="card-header">
            <h5>Current Revision: {draft['rev']}</h5>
        </div>
        <div class="card-body">
            <p>This draft is currently at revision {draft['rev']}.</p>
            <p><strong>Published:</strong> {draft['date']}</p>
            <p><strong>Pages:</strong> {draft['pages']}</p>
            <p><strong>Words:</strong> {draft['words']}</p>
        </div>
    </div>

    <div class="alert alert-info mt-3">
        <i class="fas fa-info-circle me-2"></i>
        Detailed revision history and diff viewing would be implemented in a full datatracker system.
    </div>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{draft_name}</a></li>
                <li class="breadcrumb-item active">Revisions</li>
            </ol>
        </nav>

        <h1>Revisions for {draft_name}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
            <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary">History</a>
        </div>

        {revisions_html}
    </div>
    """

    return BASE_TEMPLATE.format(title=f"Revisions - {draft_name}", theme=current_theme, user_menu=user_menu, content=content)

@app.route('/group/')
def groups():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark') if get_current_user() else 'light'
    groups_html = ""
    for group in GROUPS:
        # Get chair information from database
        all_chairs = WorkingGroupChair.query.filter_by(group_acronym=group['acronym']).all()
        if all_chairs:
            chair_names = []
            for chair in all_chairs:
                chair_name = chair.chair_name
                if not chair.approved:
                    chair_name += " (Pending)"
                chair_names.append(chair_name)
            chair_display = ", ".join(chair_names)
        else:
            chair_display = "TBD"

        groups_html += f"""
        <div class="col-md-6">
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">
                        <a href="/group/{group['acronym']}/">{group['acronym']}</a>
                    </h5>
                    <p class="card-text">{group['name']}</p>
                    <div class="document-meta">
                        <span class="badge bg-primary">{group['type']}</span>
                        <span class="badge bg-success ms-2">{group['state']}</span>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            Chair: {chair_display}<br>
                            {group['description']}
                        </small>
                    </div>
                </div>
            </div>
        </div>
        """

    # Get theme from session or user preference
    current_theme = session.get('theme', 'dark')

    content = f"""
    <div class="container mt-4">
        <div class="row">
            <div class="col-12">
                <h1 class="mb-4">Working Groups</h1>
                <p class="lead mb-4">Browse the Meta-Layer Desirable Properties working groups.</p>

                <div class="row">
                    {groups_html}
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Working Groups - MLTF",
        theme=current_theme,
        content=content,
        user_menu=user_menu
    )
@app.route('/group/<acronym>/')
def group_detail(acronym):
    """Display individual working group details"""
    # Find the group - handle both full acronyms and short forms (DP1, DP2, etc.)
    group = None
    full_acronym = acronym  # Default to the URL parameter

    for g in GROUPS:
        if g['acronym'] == acronym:
            group = g
            full_acronym = g['acronym']
            break
        # Also check for short form (dp1 -> dp1-federated-auth, DP1 -> dp1-federated-auth)
        if acronym.lower().startswith('dp') and g['acronym'].startswith(acronym.lower() + '-'):
            group = g
            full_acronym = g['acronym']
            break

    if not group:
        return f"Working group '{acronym}' not found. Available: {[g['acronym'] for g in GROUPS]}", 404

    user_menu = generate_user_menu()
    current_user = get_current_user()

    # Check if user is already a member
    is_member = False
    if current_user:
        membership = WorkingGroupMember.query.filter_by(
            group_acronym=full_acronym,
            user_name=current_user['name']
        ).first()
        is_member = membership is not None

    # Get chair information using the full acronym
    all_chairs = WorkingGroupChair.query.filter_by(group_acronym=full_acronym).all()
    if all_chairs:
        approved_chairs = [chair.chair_name for chair in all_chairs if chair.approved]
        pending_chairs = [chair.chair_name for chair in all_chairs if not chair.approved]

        if approved_chairs:
            chair_name = ", ".join(approved_chairs)
            if pending_chairs:
                chair_name += f" (Pending: {', '.join(pending_chairs)})"
        else:
            chair_name = f"Pending: {', '.join(pending_chairs)}"
        chair_approved = len(approved_chairs) > 0
    else:
        chair_name = "TBD"
        chair_approved = False

    join_button = ""
    if current_user and not is_member:
        join_button = f'<button class="btn btn-primary" onclick="joinGroup(\'{full_acronym}\')">Join Working Group</button>'
    elif current_user and is_member:
        join_button = '<span class="badge bg-success">Member</span> <button class="btn btn-outline-danger btn-sm ms-2" onclick="leaveGroup(\'{full_acronym}\')">Leave</button>'

    # Admin chair management
    chair_management = ""
    if current_user and current_user.get('role') == 'admin':
        # Get all chairs for this group
        all_chairs = WorkingGroupChair.query.filter_by(group_acronym=full_acronym).all()

        # Create options for the multi-select dropdown
        chair_options = ""
        selected_chairs = []
        for chair in all_chairs:
            chair_display = chair.chair_name
            if not chair.approved:
                chair_display += " (Pending)"
            chair_options += f'<option value="{chair.id}" {"selected" if chair.approved else ""}>{chair_display}</option>'
            if chair.approved:
                selected_chairs.append(chair.chair_name)

        # Convert selected chairs to JSON for JavaScript
        selected_chairs_json = json.dumps(selected_chairs)

        chair_management = f'''
        <div class="mt-4 p-3 border rounded">
            <h5>Chair Management</h5>
            <div class="mb-3">
                <label class="form-label">Current Chairs:</label>
                <select multiple class="form-select" id="chair-select-{full_acronym}" size="4">
                    {chair_options}
                </select>
                <div class="form-text">Select multiple chairs using Ctrl+Click (Cmd+Click on Mac)</div>
            </div>
            <div class="d-flex gap-2">
                <input type="text" id="new-chair-input-{full_acronym}" class="form-control" placeholder="Add new chair name">
                <button type="button" class="btn btn-success" onclick="addChair('{full_acronym}')">Add Chair</button>
                <button type="button" class="btn btn-warning" onclick="updateChairs('{full_acronym}')">Update Chairs</button>
            </div>
            <div class="mt-2">
                <small class="text-muted">Current approved chairs: {", ".join(selected_chairs) if selected_chairs else "None"}</small>
            </div>
        </div>
        '''

    # Get theme from session or user preference
    current_theme = session.get('theme', current_user.get('theme', 'dark') if current_user else 'dark')

    content = f"""
    <div class="container mt-4">
        <div class="row">
            <div class="col-12">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item"><a href="/">Home</a></li>
                        <li class="breadcrumb-item"><a href="/group/">Working Groups</a></li>
                        <li class="breadcrumb-item active">{group['name']}</li>
                    </ol>
                </nav>

                <div class="card mb-4">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h1 class="card-title mb-2">{group['name']}</h1>
                                <p class="text-muted mb-3">{group['acronym'].upper()}</p>
                                <p class="card-text">{group['description']}</p>
                            </div>
                            <div class="text-end">
                                {join_button}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-8">
                        <div class="card mb-4">
                            <div class="card-header">
                                <h5 class="mb-0">About</h5>
                            </div>
                            <div class="card-body">
                                <p>{group['description']}</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card mb-4">
                            <div class="card-header">
                                <h5 class="mb-0">Leadership</h5>
                            </div>
                            <div class="card-body">
                                <p><strong>Chair:</strong> {chair_name}</p>
                                {'<span class="badge bg-warning">Pending Approval</span>' if not chair_approved and chair_name != "TBD" else ''}
                            </div>
                        </div>

                        {chair_management}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
    function joinGroup(acronym) {{
        fetch(`/group/${{acronym}}/join`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }}
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error joining group: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error joining group');
        }});
    }}

    function leaveGroup(acronym) {{
        fetch(`/group/${{acronym}}/leave`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }}
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error leaving group: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error leaving group');
        }});
    }}

    function addChair(acronym) {{
        const input = document.getElementById(`new-chair-input-${{acronym}}`);
        const chairName = input.value.trim();
        if (!chairName) {{
            alert('Please enter a chair name');
            return;
        }}

        fetch(`/group/${{acronym}}/add_chair`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{ chair_name: chairName }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error adding chair: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error adding chair');
        }});
    }}

    function updateChairs(acronym) {{
        const select = document.getElementById(`chair-select-${{acronym}}`);
        const selectedOptions = Array.from(select.selectedOptions);
        const chairIds = selectedOptions.map(option => parseInt(option.value));

        fetch(`/group/${{acronym}}/update_chairs`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{ chair_ids: chairIds }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error updating chairs: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error updating chairs');
        }});
    }}

    function removeChair(acronym) {{
        const select = document.getElementById(`chair-select-${{acronym}}`);
        const selectedOptions = Array.from(select.selectedOptions);

        if (selectedOptions.length === 0) {{
            alert('Please select chairs to remove');
            return;
        }}

        if (confirm('Are you sure you want to remove ' + selectedOptions.length + ' chair(s)?')) {{
            const chairIds = selectedOptions.map(option => parseInt(option.value));

            fetch(`/group/${{acronym}}/remove_chairs`, {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{ chair_ids: chairIds }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Error removing chairs: ' + data.message);
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error removing chairs');
            }});
        }}
    }}
    </script>
    """

    return BASE_TEMPLATE.format(
        title=f"{group['name']} - MLTF",
        theme=current_theme,
        content=content,
        user_menu=user_menu
    )

@app.route('/group/<acronym>/join', methods=['POST'])
@require_auth
def join_group(acronym):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    # Check if already a member
    existing = WorkingGroupMember.query.filter_by(
        group_acronym=acronym,
        user_name=current_user['name']
    ).first()

    if existing:
        return jsonify({'success': False, 'message': 'Already a member'}), 400

    # Add membership
    membership = WorkingGroupMember(
        group_acronym=acronym,
        user_name=current_user['name']
    )
    db.session.add(membership)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Joined successfully'})

@app.route('/group/<acronym>/leave', methods=['POST'])
@require_auth
def leave_group(acronym):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    # Remove membership
    membership = WorkingGroupMember.query.filter_by(
        group_acronym=acronym,
        user_name=current_user['name']
    ).first()

    if not membership:
        return jsonify({'success': False, 'message': 'Not a member'}), 400

    db.session.delete(membership)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Left successfully'})

@app.route('/group/<acronym>/add_chair', methods=['POST'])
@require_role('admin')
def add_group_chair(acronym):
    data = request.get_json()
    chair_name = data.get('chair_name', '').strip()
    if not chair_name:
        return jsonify({'success': False, 'message': 'Chair name required'}), 400

    # Check if chair already exists
    existing = WorkingGroupChair.query.filter_by(group_acronym=acronym, chair_name=chair_name).first()
    if existing:
        return jsonify({'success': False, 'message': 'Chair already exists'}), 400

    # Add new chair (unapproved)
    chair = WorkingGroupChair(
        group_acronym=acronym,
        chair_name=chair_name,
        approved=False
    )
    db.session.add(chair)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Chair added successfully'})

@app.route('/group/<acronym>/update_chairs', methods=['POST'])
@require_role('admin')
def update_group_chairs(acronym):
    data = request.get_json()
    chair_ids = data.get('chair_ids', [])

    # Mark all chairs as unapproved first
    WorkingGroupChair.query.filter_by(group_acronym=acronym).update({'approved': False})

    # Approve selected chairs
    if chair_ids:
        WorkingGroupChair.query.filter(
            WorkingGroupChair.group_acronym == acronym,
            WorkingGroupChair.id.in_(chair_ids)
        ).update({'approved': True})

    db.session.commit()

    return jsonify({'success': True, 'message': 'Chairs updated successfully'})

@app.route('/group/<acronym>/remove_chairs', methods=['POST'])
@require_role('admin')
def remove_group_chairs(acronym):
    data = request.get_json()
    chair_ids = data.get('chair_ids', [])

    if not chair_ids:
        return jsonify({'success': False, 'message': 'No chairs selected'}), 400

    # Remove selected chairs
    WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == acronym,
        WorkingGroupChair.id.in_(chair_ids)
    ).delete()

    db.session.commit()

    return jsonify({'success': True, 'message': 'Chairs removed successfully'})

@app.route('/person/')
def people():
    """People directory - coming soon"""
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    content = """
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="text-center">
                    <i class="fas fa-user-friends fa-4x text-muted mb-4"></i>
                    <h1 class="mb-3">People Directory</h1>
                    <p class="lead text-muted mb-4">Coming Soon</p>
                    <p class="mb-4">We're building a comprehensive directory of MLTF participants and contributors. This feature will help you connect with other members of the community.</p>
                    <a href="/" class="btn btn-primary">Return to Home</a>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="People Directory - MLTF",
        theme=session.get('theme', 'dark'),
        content=content,
        user_menu=user_menu
    )

@app.route('/meeting/')
def meetings():
    """Meetings - coming soon"""
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    content = """
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="text-center">
                    <i class="fas fa-calendar fa-4x text-muted mb-4"></i>
                    <h1 class="mb-3">Meetings</h1>
                    <p class="lead text-muted mb-4">Coming Soon</p>
                    <p class="mb-4">Information about upcoming MLTF meetings and sessions will be available here. Stay tuned for announcements about our first events.</p>
                    <a href="/" class="btn btn-primary">Return to Home</a>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Meetings - MLTF",
        theme=session.get('theme', 'dark'),
        content=content,
        user_menu=user_menu
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

