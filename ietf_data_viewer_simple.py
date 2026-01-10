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
from datetime import datetime
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
        'admin': {'password': 'admin123', 'name': 'Admin User', 'email': 'admin@ietf.org', 'role': 'admin', 'theme': 'light'},
        'daveed': {'password': 'admin123', 'name': 'Daveed', 'email': 'daveed@bridgit.io', 'role': 'admin', 'theme': 'light'},
        'john': {'password': 'password123', 'name': 'John Doe', 'email': 'john@example.com', 'role': 'editor', 'theme': 'light'},
        'jane': {'password': 'password123', 'name': 'Jane Smith', 'email': 'jane@example.com', 'role': 'user', 'theme': 'light'},
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
                theme=user_data.get('theme', 'light')
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
    theme = db.Column(db.String(10), default='light')  # light, dark, auto
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

class WorkingGroupChair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_acronym = db.Column(db.String(50), unique=True, index=True)
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
            background-color: var(--input-bg);
            border: 1px solid var(--input-border);
            border-radius: 8px;
            color: var(--text-primary);
            padding: 12px 16px;
            transition: all 0.2s ease;
        }}

        .form-control:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.1);
            background-color: var(--input-bg);
        }}

        .form-control::placeholder {{
            color: var(--text-muted);
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
        const userTheme = html.getAttribute('data-theme') || 'light';
        const savedTheme = userTheme !== 'light' && userTheme !== 'dark' && userTheme !== 'auto' ?
            (localStorage.getItem('theme') || 'light') : userTheme;
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
                theme='light'  # Default theme
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
            theme = request.form.get('theme', 'light').strip()
            if theme in ['light', 'dark', 'auto']:
                user.theme = theme
                db.session.commit()
                session['theme'] = theme  # Update session immediately
                flash('Theme preference updated successfully!', 'success')
            else:
                flash('Invalid theme selection.', 'error')
    
    # Generate user menu
    user_menu = generate_user_menu()
    
    current_theme = current_user.get('theme', 'light')
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

    # Get admin statistics
    total_users = User.query.count()
    total_groups = len(GROUPS)
    total_submissions = Submission.query.count()
    approved_drafts = PublishedDraft.query.count()
    pending_chairs = WorkingGroupChair.query.filter_by(approved=False).count()

    content = f"""
    <div class="container mt-4">
        <div class="row">
            <div class="col-12">
                <h1 class="mb-4">Admin Dashboard</h1>

                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-primary">{total_users}</h3>
                                <p class="mb-0">Total Users</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-success">{total_groups}</h3>
                                <p class="mb-0">Working Groups</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-warning">{total_submissions}</h3>
                                <p class="mb-0">Draft Submissions</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-info">{approved_drafts}</h3>
                                <p class="mb-0">Published Drafts</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Working Group Chairs</h5>
                            </div>
                            <div class="card-body">
                                <p>Pending Chair Approvals: <strong>{pending_chairs}</strong></p>
                                <a href="/group/" class="btn btn-primary">Manage Working Groups</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Draft Submissions</h5>
                            </div>
                            <div class="card-body">
                                <p>Review and approve draft submissions</p>
                                <a href="/submit/status/" class="btn btn-primary">View Submissions</a>
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
        theme=get_current_user().get('theme', 'light'),
        content=content,
        user_menu=user_menu
    )

# Routes
@app.route('/')
def home():
    # Generate user menu
    current_user = get_current_user()
    current_theme = current_user.get('theme', 'light') if current_user else 'light'

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
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Documents - MLTF Datatracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand {{ font-weight: bold; }}
        .document-card {{ margin-bottom: 1rem; }}
        .document-title {{ font-weight: bold; color: #0066cc; }}
        .document-meta {{ font-size: 0.9em; color: #666; }}
        .status-badge {{ font-size: 0.8em; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">MLTF</a>
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
        </div>
    </nav>
    
    <div class="container mt-4">
        <h1>All Documents</h1>
        <p>Showing {len(DRAFTS)} documents</p>
        
        <div class="row">
            {docs_html}
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Theme switching functionality
        const themeToggle = document.getElementById('theme-toggle');
        const html = document.documentElement;
        const icon = themeToggle.querySelector('i');

        // Load saved theme - prefer user preference over localStorage
        const userTheme = html.getAttribute('data-theme') || 'light';
        const savedTheme = userTheme !== 'light' && userTheme !== 'dark' && userTheme !== 'auto' ?
            (localStorage.getItem('theme') || 'light') : userTheme;
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

@app.route('/doc/draft/<draft_name>/')
def draft_detail(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{draft['name']} - MLTF Datatracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand {{ font-weight: bold; }}
        .document-card {{ margin-bottom: 1rem; }}
        .document-title {{ font-weight: bold; color: #0066cc; }}
        .document-meta {{ font-size: 0.9em; color: #666; }}
        .status-badge {{ font-size: 0.8em; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">MLTF</a>
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
        </div>
    </nav>
    
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
                        <h5>Document Content</h5>
                    </div>
                    <div class="card-body">
                        <p>This is a sample IETF document. In the real datatracker, this would contain the actual document content, including:</p>
                        <ul>
                            <li>Abstract</li>
                            <li>Introduction</li>
                            <li>Technical specifications</li>
                            <li>References</li>
                            <li>Author information</li>
                        </ul>
                        <p><strong>Abstract:</strong> This document describes the sample MLTF draft {draft['name']}. It provides a framework for understanding how MLTF documents are structured and managed within the datatracker system.</p>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Actions</h5>
                    </div>
                    <div class="card-body">
                        <a href="/doc/draft/{draft['name']}/comments/" class="btn btn-primary w-100 mb-2">View Comments</a>
                        <a href="/doc/draft/{draft['name']}/history/" class="btn btn-secondary w-100 mb-2">View History</a>
                        <a href="/doc/draft/{draft['name']}/revisions/" class="btn btn-info w-100 mb-2">View Revisions</a>
                        <a href="/doc/draft/{draft['name']}/" class="btn btn-outline-primary w-100">Download PDF</a>
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
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Theme switching functionality
        const themeToggle = document.getElementById('theme-toggle');
        const html = document.documentElement;
        const icon = themeToggle.querySelector('i');

        // Load saved theme - prefer user preference over localStorage
        const userTheme = html.getAttribute('data-theme') || 'light';
        const savedTheme = userTheme !== 'light' && userTheme !== 'dark' && userTheme !== 'auto' ?
            (localStorage.getItem('theme') || 'light') : userTheme;
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

@app.route('/group/')
def groups():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'light') if get_current_user() else 'light'
    groups_html = ""
    for group in GROUPS:
        # Get chair information from database
        chair_info = WorkingGroupChair.query.filter_by(group_acronym=group['acronym']).first()
        if chair_info:
            chair_display = chair_info.chair_name
            if not chair_info.approved:
                chair_display += " (Pending Approval)"
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
    current_theme = session.get('theme', 'light')

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
    chair_info = WorkingGroupChair.query.filter_by(group_acronym=full_acronym).first()
    chair_name = chair_info.chair_name if chair_info else "TBD"
    chair_approved = chair_info.approved if chair_info else False

    join_button = ""
    if current_user and not is_member:
        join_button = f'<button class="btn btn-primary" onclick="joinGroup(\'{full_acronym}\')">Join Working Group</button>'
    elif current_user and is_member:
        join_button = '<span class="badge bg-success">Member</span> <button class="btn btn-outline-danger btn-sm ms-2" onclick="leaveGroup(\'{full_acronym}\')">Leave</button>'

    # Admin chair management
    chair_management = ""
    if current_user and current_user.get('role') == 'admin':
        current_chair = chair_info.chair_name if chair_info else ""
        approve_button = f'<button class="btn btn-success btn-sm ms-2" onclick="approveChair(\\"{full_acronym}\\")">Approve Chair</button>' if chair_info and not chair_info.approved else ''
        remove_button = f'<button class="btn btn-danger btn-sm ms-2" onclick="removeChair(\\"{full_acronym}\\")">Remove Chair</button>' if chair_info else ''
        chair_management = f'''
        <div class="mt-4 p-3 border rounded">
            <h5>Chair Management</h5>
            <form method="POST" action="/group/{full_acronym}/set_chair" class="d-flex gap-2">
                <input type="text" name="chair_name" class="form-control" placeholder="Chair name" value="{current_chair}">
                <button type="submit" class="btn btn-warning">Set Chair</button>
            </form>
            {approve_button}
            {remove_button}
        </div>
        '''

    # Get theme from session or user preference
    current_theme = session.get('theme', current_user.get('theme', 'light') if current_user else 'light')

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

    function approveChair(acronym) {{
        fetch(`/group/${{acronym}}/approve_chair`, {{
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
                alert('Error approving chair: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error approving chair');
        }});
    }}

    function removeChair(acronym) {{
        if (confirm('Are you sure you want to remove the chair?')) {{
            fetch(`/group/${{acronym}}/remove_chair`, {{
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
                    alert('Error removing chair: ' + data.message);
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error removing chair');
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

@app.route('/group/<acronym>/set_chair', methods=['POST'])
@require_role('admin')
def set_group_chair(acronym):
    chair_name = request.form.get('chair_name', '').strip()
    if not chair_name:
        return jsonify({'success': False, 'message': 'Chair name required'}), 400

    # Remove existing chair if any
    existing = WorkingGroupChair.query.filter_by(group_acronym=acronym).first()
    if existing:
        db.session.delete(existing)

    # Add new chair (unapproved)
    chair = WorkingGroupChair(
        group_acronym=acronym,
        chair_name=chair_name,
        approved=False
    )
    db.session.add(chair)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Chair set successfully'})

@app.route('/group/<acronym>/approve_chair', methods=['POST'])
@require_role('admin')
def approve_group_chair(acronym):
    chair = WorkingGroupChair.query.filter_by(group_acronym=acronym).first()
    if not chair:
        return jsonify({'success': False, 'message': 'No chair set'}), 404

    chair.approved = True
    db.session.commit()

    return jsonify({'success': True, 'message': 'Chair approved successfully'})

@app.route('/group/<acronym>/remove_chair', methods=['POST'])
@require_role('admin')
def remove_group_chair(acronym):
    chair = WorkingGroupChair.query.filter_by(group_acronym=acronym).first()
    if not chair:
        return jsonify({'success': False, 'message': 'No chair set'}), 404

    db.session.delete(chair)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Chair removed successfully'})

@app.route('/person/')
def people():
    """People directory - coming soon"""
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'light')

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
        theme=session.get('theme', 'light'),
        content=content,
        user_menu=user_menu
    )

@app.route('/meeting/')
def meetings():
    """Meetings - coming soon"""
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'light')

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
        theme=session.get('theme', 'light'),
        content=content,
        user_menu=user_menu
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

