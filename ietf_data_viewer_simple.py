#!/usr/bin/env python3
"""
IETF Data Viewer - Shows the IETF datatracker data from test files
This displays the actual IETF data so you can see it working before we transform it to MLTF.
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, session, send_file
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

        print(f"Database initialized: {len(published_drafts)} published drafts loaded")

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

# Store users in memory (in a real app, this would be a database)
USERS = {
    'admin': {'password': 'admin123', 'name': 'Admin User', 'email': 'admin@ietf.org', 'role': 'admin'},
    'john': {'password': 'password123', 'name': 'John Doe', 'email': 'john@example.com', 'role': 'editor'},
    'jane': {'password': 'password123', 'name': 'Jane Smith', 'email': 'jane@example.com', 'role': 'user'},
    'shiftshapr': {'password': 'mynewpassword123', 'name': 'Shift Shapr', 'email': 'shiftshapr@example.com', 'role': 'editor'}
}

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

def get_current_user():
    """Get current logged in user"""
    if 'user' in session:
        return USERS.get(session['user'])
    return None

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

# Real IETF participant names (from actual IETF community)
IETF_PARTICIPANTS = [
    "Henrik Levkowetz", "John Klensin", "Dave Crocker", "Marshall Rose", "Erik Nordmark",
    "Scott Bradner", "Brian Carpenter", "Fred Baker", "Harald Alvestrand", "Vint Cerf",
    "Bob Hinden", "Steve Deering", "Randy Bush", "Geoff Huston", "Tony Hain",
    "Mark Handley", "Sally Floyd", "Vern Paxson", "Craig Partridge", "Jon Postel",
    "David Clark", "Radia Perlman", "Paul Mockapetris", "Tim Berners-Lee", "Dan Bernstein",
    "Wietse Venema", "Theo de Raadt", "Linus Torvalds", "Richard Stallman", "Eric Raymond",
    "Alan Cox", "Andrew Tridgell", "Larry Wall", "Guido van Rossum", "Bjarne Stroustrup",
    "Dennis Ritchie", "Ken Thompson", "Brian Kernighan", "Rob Pike", "Russ Cox"
]

# Load IETF data from test files
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
                    # Create realistic IETF draft information
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand {{ font-weight: bold; }}
        .avatar {{ font-size: 14px; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
                <a class="nav-link" href="/submit/">Submit Draft</a>
            </div>
            <div class="navbar-nav ms-auto">
                {user_menu}
            </div>
        </div>
    </nav>
    <div id="flash-messages"></div>
    {content}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
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
    <p class="lead">Submit a new Internet-Draft to the IETF datatracker</p>
    
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
                                    I agree to the <a href="#" target="_blank">IETF submission terms</a>
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
                        <li>Use standard IETF formatting</li>
                    </ul>
                    
                    <h6>Content Requirements:</h6>
                    <ul class="small">
                        <li>Clear, descriptive title</li>
                        <li>Complete author information</li>
                        <li>Abstract describing the work</li>
                        <li>Proper IETF document structure</li>
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
                        <li>Contact the <a href="mailto:ietf-draft@ietf.org">IETF Secretariat</a></li>
                        <li>Join the <a href="#" target="_blank">IETF discussion list</a></li>
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
        
        if username in USERS and USERS[username]['password'] == password:
            session['user'] = username
            flash(f'Welcome back, {USERS[username]["name"]}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'error')
    
    # Generate user menu for login page
    user_menu = """
    <div class="nav-item">
        <a class="nav-link" href="/register/">Register</a>
    </div>
    """
    return render_template_string(BASE_TEMPLATE.format(title="Login - IETF Datatracker", user_menu=user_menu, content=LOGIN_TEMPLATE))

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
        
        if username in USERS:
            flash('Username already exists.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            USERS[username] = {
                'password': password,
                'name': name,
                'email': email
            }
            session['user'] = username
            flash(f'Account created successfully! Welcome, {name}!', 'success')
            return redirect(url_for('home'))
    
    # Generate user menu for register page
    user_menu = """
    <div class="nav-item">
        <a class="nav-link" href="/login/">Sign In</a>
    </div>
    """
    return render_template_string(BASE_TEMPLATE.format(title="Register - IETF Datatracker", user_menu=user_menu, content=REGISTER_TEMPLATE))

@app.route('/profile/', methods=['GET', 'POST'])
@require_auth
def profile():
    """User profile management"""
    current_user = get_current_user()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_password':
            old_password = request.form.get('old_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            
            if USERS[session['user']]['password'] == old_password:
                if len(new_password) >= 6:
                    USERS[session['user']]['password'] = new_password
                    flash('Password updated successfully!', 'success')
                else:
                    flash('New password must be at least 6 characters.', 'error')
            else:
                flash('Current password is incorrect.', 'error')
        
        elif action == 'update_profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            
            if name:
                USERS[session['user']]['name'] = name
            if email:
                USERS[session['user']]['email'] = email
            flash('Profile updated successfully!', 'success')
    
    # Generate user menu
    user_menu = f"""
    <div class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
            {current_user['name']}
        </a>
        <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="/profile/">Profile</a></li>
            <li><a class="dropdown-item" href="/logout/">Logout</a></li>
        </ul>
    </div>
    """
    
    profile_content = PROFILE_TEMPLATE.format(
        current_user_name=current_user['name'],
        current_user_email=current_user['email'],
        session_user=session['user']
    )
    return render_template_string(BASE_TEMPLATE.format(title="Profile - IETF Datatracker", user_menu=user_menu, content=profile_content))

# Routes
@app.route('/')
def home():
    # Generate user menu
    current_user = get_current_user()
    if current_user:
        user_role = current_user.get('role', 'user')
        is_admin = user_role in ['admin', 'editor'] or current_user['name'] in ['admin', 'Admin User']

        admin_link = '<li><a class="dropdown-item" href="/admin/">Admin Dashboard</a></li>' if is_admin else ''

        user_menu = f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                {current_user['name']} {f'({user_role})' if user_role != 'user' else ''}
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
    
    return BASE_TEMPLATE.format(title="IETF Datatracker", user_menu=user_menu, content=f"""
    
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8">
                <h1>IETF Datatracker</h1>
                <p class="lead">The day-to-day front-end to the IETF database for people who work on IETF standards.</p>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent Documents</h5>
                            </div>
                            <div class="card-body">
                                <p>View the latest IETF documents including drafts, RFCs, and other standards.</p>
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
                                <p>Browse IETF working groups and their activities.</p>
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
                                <p>Information about IETF meetings and sessions.</p>
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
                                <p>Directory of IETF participants and contributors.</p>
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
    <title>All Documents - IETF Datatracker</title>
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
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
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
    <title>{draft['name']} - IETF Datatracker</title>
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
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
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
                        <p><strong>Abstract:</strong> This document describes the sample IETF draft {draft['name']}. It provides a framework for understanding how IETF documents are structured and managed within the datatracker system.</p>
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
</body>
</html>
"""

@app.route('/group/')
def groups():
    groups_html = ""
    for group in GROUPS:
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
                            Chairs: {', '.join(group['chairs'])}<br>
                            {group['description']}
                        </small>
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
    <title>Working Groups - IETF Datatracker</title>
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
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <h1>Working Groups</h1>
        <p>Showing {len(GROUPS)} working groups</p>
        
        <div class="row">
            {groups_html}
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/doc/draft/<draft_name>/comments/', methods=['GET', 'POST'])
@require_auth
def draft_comments(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404
    
    # Handle new comment submission, likes, and replies
    if request.method == 'POST':
        current_user = get_current_user()
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
                return redirect(url_for('draft_comments', draft_name=draft_name))
            else:
                flash('Please enter a comment.', 'error')
        
        elif action == 'like':
            comment_id = request.form.get('comment_id')
            if comment_id and current_user:
                liked = toggle_comment_like(draft_name, comment_id, current_user['name'])
                action_text = 'liked' if liked else 'unliked'
                flash(f'Comment {action_text}!', 'success')
                return redirect(url_for('draft_comments', draft_name=draft_name))
            else:
                flash('Please log in to like comments.', 'error')
                return redirect(url_for('login'))
        
        elif action == 'reply':
            parent_comment_id = request.form.get('parent_comment_id')
            reply_text = request.form.get('reply_text', '').strip()
            if reply_text and parent_comment_id and current_user:
                add_comment_reply(draft_name, parent_comment_id, reply_text, current_user)
                flash('Reply added successfully!', 'success')
                return redirect(url_for('draft_comments', draft_name=draft_name))
            elif not current_user:
                flash('Please log in to reply to comments.', 'error')
                return redirect(url_for('login'))
            else:
                flash('Please enter a reply.', 'error')
    
    # Build comment tree with nested replies
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
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comments for {draft_name} - IETF Datatracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand {{ font-weight: bold; }}
        .avatar {{ font-size: 14px; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
            </div>
        </div>
    </nav>
    
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
        
        <div class="row">
            <div class="col-md-8">
                <h3>Comments ({len(all_comments)})</h3>
                {comments_html}
                
                <div class="card">
                    <div class="card-header">
                        <h5>Add a Comment</h5>
                    </div>
                    <div class="card-body">
                        <div id="flash-messages"></div>

                        <form method="POST">
                            <div class="mb-3">
                                <label for="author" class="form-label">Your Name</label>
                                <input type="text" class="form-control" id="author" name="author" placeholder="Enter your name (optional)">
                            </div>
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
                        <p><strong>Name:</strong> {draft['name']}</p>
                        <p><strong>Title:</strong> {draft['title']}</p>
                        <p><strong>Status:</strong> <span class="badge bg-secondary">{draft['status']}</span></p>
                        <p><strong>Authors:</strong> {', '.join(draft['authors'])}</p>
                        <a href="/doc/draft/{draft_name}/" class="btn btn-outline-primary w-100">Back to Document</a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
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
</body>
</html>
"""

@app.route('/doc/draft/<draft_name>/history/')
def draft_history(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404
    
    # Get real history data
    real_history = DOCUMENT_HISTORY.get(draft_name, [])
    
    # Add sample history if no real history exists
    if not real_history:
        add_to_document_history(draft_name, 'Document created', 'System', 'Initial version of the document created')
        real_history = DOCUMENT_HISTORY.get(draft_name, [])
    
    history_html = ""
    
    for event in real_history:
        history_html += f"""
        <div class="timeline-item mb-3">
            <div class="d-flex">
                <div class="flex-shrink-0">
                    <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center" style="width: 40px; height: 40px;">
                        <i class="fas fa-circle" style="font-size: 8px;"></i>
                    </div>
                </div>
                <div class="flex-grow-1 ms-3">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start">
                                <h6 class="card-title mb-1">{event['action']}</h6>
                                <small class="text-muted">{event['timestamp']}</small>
                            </div>
                            <p class="card-text mb-1">{event['details']}</p>
                            <small class="text-muted">by {event['user']}</small>
                        </div>
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
    <title>History for {draft_name} - IETF Datatracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .navbar-brand {{ font-weight: bold; }}
        .timeline-item {{ position: relative; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
            </div>
        </div>
    </nav>
    
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
        
        <div class="row">
            <div class="col-md-8">
                <h3>Document History</h3>
                {history_html}
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Info</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Name:</strong> {draft['name']}</p>
                        <p><strong>Title:</strong> {draft['title']}</p>
                        <p><strong>Status:</strong> <span class="badge bg-secondary">{draft['status']}</span></p>
                        <p><strong>Authors:</strong> {', '.join(draft['authors'])}</p>
                        <a href="/doc/draft/{draft_name}/" class="btn btn-outline-primary w-100">Back to Document</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/doc/draft/<draft_name>/revisions/')
def draft_revisions(draft_name):
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    if not draft:
        return "Document not found", 404
    
    revisions_html = ""
    sample_revisions = [
        {
            'rev': '00',
            'date': '2024-01-15',
            'size': '45 KB',
            'author': 'John Smith',
            'changes': 'Initial version'
        },
        {
            'rev': '01',
            'date': '2024-01-16',
            'size': '47 KB',
            'author': 'Alice Johnson',
            'changes': 'Added security section, updated references'
        },
        {
            'rev': '02',
            'date': '2024-01-17',
            'size': '49 KB',
            'author': 'Bob Wilson',
            'changes': 'Updated performance metrics, fixed typos'
        }
    ]
    
    for revision in sample_revisions:
        revisions_html += f"""
        <tr>
            <td><a href="/doc/draft/{draft_name}/" class="text-decoration-none">{revision['rev']}</a></td>
            <td>{revision['date']}</td>
            <td>{revision['size']}</td>
            <td>{revision['author']}</td>
            <td>{revision['changes']}</td>
            <td>
                <a href="/doc/draft/{draft_name}/" class="btn btn-sm btn-outline-primary">View</a>
                <a href="/doc/draft/{draft_name}/" class="btn btn-sm btn-outline-secondary">Download</a>
            </td>
        </tr>
        """
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Revisions for {draft_name} - IETF Datatracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand {{ font-weight: bold; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
            </div>
        </div>
    </nav>
    
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
        
        <div class="row">
            <div class="col-md-8">
                <h3>Document Revisions</h3>
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Revision</th>
                                <th>Date</th>
                                <th>Size</th>
                                <th>Author</th>
                                <th>Changes</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {revisions_html}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Info</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Name:</strong> {draft['name']}</p>
                        <p><strong>Title:</strong> {draft['title']}</p>
                        <p><strong>Status:</strong> <span class="badge bg-secondary">{draft['status']}</span></p>
                        <p><strong>Authors:</strong> {', '.join(draft['authors'])}</p>
                        <a href="/doc/draft/{draft_name}/" class="btn btn-outline-primary w-100">Back to Document</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/meeting/')
def meetings():
    """Display meetings coming soon message"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meetings - IETF Datatracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand { font-weight: bold; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link active" href="/meeting/">Meetings</a>
                <a class="nav-link" href="/person/">People</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item active">Meetings</li>
            </ol>
        </nav>

        <div class="text-center mt-5">
            <div class="card">
                <div class="card-body">
                    <h1 class="card-title">Meetings</h1>
                    <div class="alert alert-info">
                        <h4 class="alert-heading">Coming Soon</h4>
                        <p>The Meta-Layer meetings section will provide information about community gatherings, technical discussions, and collaborative events.</p>
                        <hr>
                        <p class="mb-0">This feature is currently under development and will be available soon.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/person/')
def people():
    """Display people coming soon message"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>People - IETF Datatracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand { font-weight: bold; }
        .avatar { font-size: 14px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">IETF Datatracker</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Home</a>
                <a class="nav-link" href="/doc/all/">All Documents</a>
                <a class="nav-link" href="/doc/active/">Active Documents</a>
                <a class="nav-link" href="/group/">Working Groups</a>
                <a class="nav-link" href="/meeting/">Meetings</a>
                <a class="nav-link active" href="/person/">People</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item active">People</li>
            </ol>
        </nav>

        <div class="text-center mt-5">
            <div class="card">
                <div class="card-body">
                    <h1 class="card-title">People</h1>
                    <div class="alert alert-info">
                        <h4 class="alert-heading">Coming Soon</h4>
                        <p>The Meta-Layer people directory will showcase community members, contributors, and participants in the Meta-Layer ecosystem.</p>
                        <hr>
                        <p class="mb-0">This feature is currently under development and will be available soon.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/submit/', methods=['GET', 'POST'])
def submit_draft():
    """Draft submission page"""
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        abstract = request.form.get('abstract', '').strip()
        group = request.form.get('group', '').strip()
        
        # Handle file upload
        if 'file' not in request.files:
            return redirect(url_for('submit_draft') + '?error=No file selected')

        file = request.files['file']
        if file.filename == '':
            return redirect(url_for('submit_draft') + '?error=No file selected')
        
        if file and allowed_file(file.filename):
            # Generate submission ID
            submission_id = str(uuid.uuid4())[:8]
            
            # Save file
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, f"{submission_id}_{filename}")
            file.save(file_path)
            
            # Generate draft name
            author_list = [a.strip() for a in authors.split(',') if a.strip()]
            draft_name = generate_draft_name(title, author_list)
            
            # Store submission in database
            submission = Submission(
                id=submission_id,
                title=title,
                authors=author_list,
                abstract=abstract,
                group=group,
                filename=filename,
                file_path=file_path,
                draft_name=draft_name,
                status='submitted',
                submitted_by='Anonymous User'
            )
            db.session.add(submission)
            db.session.commit()
            
            return redirect(url_for('submission_status', submission_id=submission_id) + f'?message=Draft submitted successfully! Submission ID: {submission_id}')
        else:
            return redirect(url_for('submit_draft') + '?error=Invalid file type. Please upload PDF, TXT, XML, DOC, or DOCX files.')
    
    # Generate user menu
    current_user = get_current_user()
    if current_user:
        user_menu = f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                {current_user['name']}
            </a>
            <ul class="dropdown-menu">
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
        """
    
    # Check for flash messages in URL params
    from urllib.parse import unquote
    message = request.args.get('message')
    error = request.args.get('error')
    if message:
        message = unquote(message)
    if error:
        error = unquote(error)

    content = SUBMIT_TEMPLATE
    if error:
        content = content.replace('<div id="flash-messages"></div>',
                                 '<div class="alert alert-danger alert-dismissible fade show" role="alert">' + error + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>')
    elif message:
        content = content.replace('<div id="flash-messages"></div>',
                                 '<div class="alert alert-success alert-dismissible fade show" role="alert">' + message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>')

    return render_template_string(BASE_TEMPLATE.format(title="Submit Draft - IETF Datatracker", user_menu=user_menu, content=content))

@app.route('/submit/status/<submission_id>/')
def submission_status(submission_id):
    """Submission status page"""
    submission = Submission.query.get(submission_id)
    if not submission:
        return redirect(url_for('submit_draft') + '?error=Submission not found')

    # Generate user menu
    current_user = get_current_user()
    if current_user:
        user_menu = f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                {current_user['name']}
            </a>
            <ul class="dropdown-menu">
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
        """

    # Check for flash messages in URL params
    from urllib.parse import unquote
    message = request.args.get('message')
    if message:
        message = unquote(message)
        content = SUBMISSION_STATUS_TEMPLATE.replace('<div id="flash-messages"></div>',
                                                   '<div class="alert alert-success alert-dismissible fade show" role="alert">' + message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>')
    else:
        content = SUBMISSION_STATUS_TEMPLATE

    # Read file content for preview (support multiple formats)
    file_content = ""
    file_extension = submission.filename.lower().split('.')[-1] if '.' in submission.filename else ''

    if os.path.exists(submission.file_path):
        if file_extension in ['txt', 'xml', 'md']:
            # Plain text files
            try:
                with open(submission.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read()
            except Exception as e:
                file_content = f"Error reading file: {e}"

        elif file_extension == 'pdf' and PDF_SUPPORT:
            # PDF text extraction
            try:
                with open(submission.file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ''
                    for page in pdf_reader.pages[:3]:  # First 3 pages only
                        page_text = page.extract_text()
                        if page_text.strip():
                            text += page_text + '\n'
                    if text.strip():
                        file_content = text.strip()
                    else:
                        file_content = "PDF appears to contain no extractable text (may be image-based)."
            except Exception as e:
                file_content = f"Error extracting PDF text: {e}"

        elif file_extension == 'docx' and DOCX_SUPPORT:
            # DOCX text extraction
            try:
                doc = docx.Document(submission.file_path)
                text = ''
                for para in doc.paragraphs[:20]:  # First 20 paragraphs
                    if para.text.strip():
                        text += para.text + '\n'
                if text.strip():
                    file_content = text.strip()
                else:
                    file_content = "DOCX appears to contain no extractable text."
            except Exception as e:
                file_content = f"Error extracting DOCX text: {e}"

        elif file_extension in ['pdf', 'doc', 'docx']:
            # Fallback for unsupported formats
            file_content = f"This is a {file_extension.upper()} file. Text extraction not available (library not installed)."
        else:
            file_content = f"File type .{file_extension} - preview not supported."

    return render_template_string(BASE_TEMPLATE.format(title=f"Submission Status - {submission_id}", user_menu=user_menu, content=content), submission=submission, file_content=file_content, current_user=current_user)

@app.route('/submit/approve/<submission_id>', methods=['POST'])
def approve_submission(submission_id):
    """Approve and publish a submission - requires admin/editor permissions"""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('login') + '?next=' + url_for('submission_status', submission_id=submission_id))

    # Check if user has permission to approve (admin or editor role)
    user_role = current_user.get('role', 'user')
    if user_role not in ['admin', 'editor'] and current_user['name'] not in ['admin', 'Admin User']:
        return redirect(url_for('submission_status', submission_id=submission_id) + '?error=You do not have permission to approve submissions.')

    submission = Submission.query.get(submission_id)
    if not submission:
        return redirect(url_for('submit_draft') + '?error=Submission not found')

    # Create a published draft entry in database
    published_draft = PublishedDraft(
        name=submission.draft_name,
        title=submission.title,
        authors=submission.authors,
        group=submission.group,
        status='active',
        rev='00',
        pages=1,  # Placeholder
        words=len(submission.abstract.split()) if submission.abstract else 0,
        date=datetime.now().strftime('%Y-%m-%d'),
        abstract=submission.abstract or '',
        stream='ietf',
        submission_id=submission.id
    )
    db.session.add(published_draft)

    # Also add to in-memory drafts list for immediate access
    draft_entry = {
        'name': submission.draft_name,
        'title': submission.title,
        'authors': submission.authors,
        'group': submission.group,
        'status': 'active',
        'rev': '00',
        'pages': 1,
        'words': len(submission.abstract.split()) if submission.abstract else 0,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'abstract': submission.abstract or '',
        'stream': 'ietf'
    }
    DRAFTS.append(draft_entry)

    # Update submission status
    submission.status = 'approved'
    submission.approved_at = datetime.utcnow()

    # Add to document history
    history_entry = DocumentHistory(
        draft_name=submission.draft_name,
        action='draft_approved',
        user=current_user['name'],
        details=f'Draft approved and published from submission {submission_id}'
    )
    db.session.add(history_entry)

    db.session.commit()

    return redirect(url_for('submission_status', submission_id=submission_id) + '?message=Draft approved and published successfully!')

@app.route('/submit/reject/<submission_id>', methods=['POST'])
def reject_submission(submission_id):
    """Reject a submission"""
    submission = Submission.query.get(submission_id)
    if not submission:
        return redirect(url_for('submit_draft') + '?error=Submission not found')

    # Update submission status
    submission.status = 'rejected'
    submission.rejected_at = datetime.utcnow()

    db.session.commit()

    return redirect(url_for('submission_status', submission_id=submission_id) + '?message=Submission rejected.')

@app.route('/admin/')
def admin_dashboard():
    """Admin dashboard showing pending submissions"""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('login') + '?next=' + url_for('admin_dashboard'))

    user_role = current_user.get('role', 'user')
    if user_role not in ['admin', 'editor'] and current_user['name'] not in ['admin', 'Admin User']:
        return redirect(url_for('home') + '?error=Access denied. Admin or editor role required.')

    # Get pending submissions
    pending_submissions = Submission.query.filter_by(status='submitted').all()

    # Generate user menu
    if current_user:
        user_menu = f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                {current_user['name']} ({user_role})
            </a>
            <ul class="dropdown-menu">
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
        """

    # Build the admin dashboard content
    submissions_html = ""
    for submission in pending_submissions:
        submissions_html += f"""
        <div class="card mb-3">
            <div class="card-header">
                <h6 class="mb-0">
                    <a href="/submit/status/{submission.id}/">{submission.title}</a>
                    <span class="badge bg-warning ms-2">Pending Review</span>
                </h6>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>Authors:</strong> {', '.join(submission.authors)}</p>
                        <p><strong>Group:</strong> {submission.group}</p>
                        <p><strong>Submitted:</strong> {submission.submitted_at}</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>File:</strong> {submission.filename}</p>
                        <p><strong>Draft Name:</strong> {submission.draft_name}</p>
                        <div class="btn-group">
                            <a href="/submit/status/{submission.id}/" class="btn btn-outline-primary btn-sm">Review</a>
                            <form method="POST" action="/submit/approve/{submission.id}" style="display: inline;">
                                <button type="submit" class="btn btn-success btn-sm">Approve</button>
                            </form>
                            <form method="POST" action="/submit/reject/{submission.id}" style="display: inline;">
                                <button type="submit" class="btn btn-danger btn-sm">Reject</button>
                            </form>
                        </div>
                    </div>
                </div>
                {f'<div class="mt-2"><strong>Abstract:</strong> {submission.abstract}</div>' if submission.abstract else ''}
            </div>
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-12">
                <h1>Admin Dashboard</h1>
                <p class="lead">Manage pending submissions and system administration</p>

                <div class="row mb-4">
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-warning">{len(pending_submissions)}</h3>
                                <p class="mb-0">Pending Reviews</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-success">{Submission.query.filter_by(status='approved').count()}</h3>
                                <p class="mb-0">Approved</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-danger">{Submission.query.filter_by(status='rejected').count()}</h3>
                                <p class="mb-0">Rejected</p>
                            </div>
                        </div>
                    </div>
                </div>

                <h3>Pending Submissions</h3>
                {submissions_html if submissions_html else '<div class="alert alert-info">No pending submissions to review.</div>'}

                <div class="mt-4">
                    <a href="/" class="btn btn-secondary">Back to Home</a>
                    <a href="/doc/all/" class="btn btn-outline-primary ms-2">View All Documents</a>
                </div>
            </div>
        </div>
    </div>
    """

    return render_template_string(BASE_TEMPLATE.format(title="Admin Dashboard - IETF Datatracker", user_menu=user_menu, content=content))

@app.route('/download/<submission_id>')
def download_file(submission_id):
    """Download a submitted file"""
    submission = Submission.query.get(submission_id)
    if not submission or not os.path.exists(submission.file_path):
        return "File not found", 404

    return send_file(submission.file_path, as_attachment=True, download_name=submission.filename)

if __name__ == '__main__':
    with app.app_context():
        print("Starting IETF Data Viewer...")
        init_db()  # Initialize database tables
        print(f"Loaded {len(DRAFTS)} drafts and {len(GROUPS)} groups")

        # Count database records
        submission_count = Submission.query.count()
        comment_count = Comment.query.count()
        history_count = DocumentHistory.query.count()
        print(f"Database: {submission_count} submissions, {comment_count} comments, {history_count} history entries")

    app.run(host='0.0.0.0', port=8000, debug=True)
