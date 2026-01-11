#!/usr/bin/env python3
"""
IETF Data Viewer - Shows the IETF datatracker data from test files
This displays the actual IETF data so you can see it working before we transform it to MLTF.
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import os
import re
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # For flash messages

# Store comments in memory (in a real app, this would be a database)
COMMENTS = {}

# Store submissions in memory (in a real app, this would be a database)
SUBMISSIONS = {}

# Store users in memory (in a real app, this would be a database)
USERS = {
    'admin': {'password': 'admin123', 'name': 'Admin User', 'email': 'admin@ietf.org'},
    'john': {'password': 'password123', 'name': 'John Doe', 'email': 'john@example.com'},
    'jane': {'password': 'password123', 'name': 'Jane Smith', 'email': 'jane@example.com'},
    'shiftshapr': {'password': 'mynewpassword123', 'name': 'Shift Shapr', 'email': 'shiftshapr@example.com'}
}

# Store document history in memory
DOCUMENT_HISTORY = {}

# Store comment likes in memory
COMMENT_LIKES = {}

# Store comment replies in memory
COMMENT_REPLIES = {}

# Store working group chairs in memory
WORKING_GROUP_CHAIRS = {}

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
    """Decorator to require specific user role"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login'))

            user = USERS.get(session['user'])
            if not user:
                flash('User not found.', 'error')
                return redirect(url_for('login'))

            # Check if user has required role
            user_role = user.get('role', 'user')
            if user_role not in ['admin', 'editor'] and session['user'] != 'admin':
                flash('Access denied. Admin privileges required.', 'error')
                return redirect(url_for('home'))

            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

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
    reply_key = f"{draft_name}:{parent_comment_id}"
    if reply_key not in COMMENT_REPLIES:
        COMMENT_REPLIES[reply_key] = []
    
    reply = {
        'id': f"reply_{len(COMMENT_REPLIES[reply_key]) + 1}",
        'author': user['name'],
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'comment': reply_text,
        'avatar': ''.join([word[0].upper() for word in user['name'].split()[:2]])
    }
    COMMENT_REPLIES[reply_key].append(reply)
    return reply

def get_comment_replies(draft_name, comment_id):
    """Get replies for a comment"""
    reply_key = f"{draft_name}:{comment_id}"
    return COMMENT_REPLIES.get(reply_key, [])

def render_replies(replies):
    """Render replies HTML"""
    if not replies:
        return ""
    
    replies_html = '<div class="ms-4 mt-2">'
    for reply in replies:
        replies_html += f"""
        <div class="card mb-2">
            <div class="card-body py-2">
                <div class="d-flex align-items-center mb-1">
                    <div class="avatar bg-secondary text-white rounded-circle me-2" style="width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px;">
                        {reply['avatar']}
                    </div>
                    <div>
                        <strong style="font-size: 14px;">{reply['author']}</strong>
                        <small class="text-muted ms-2">{reply['date']}</small>
                    </div>
                </div>
                <p class="mb-0" style="font-size: 14px;">{reply['comment']}</p>
            </div>
        </div>
        """
    replies_html += '</div>'
    return replies_html

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
    try:
        with open('/home/ubuntu/datatracker/test/data/group-aliases', 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                # Extract group name from the line
                match = re.search(r'xfilter-([^:]+):', line)
                if match:
                    group_name = match.group(1)
                    # Create realistic IETF working group data
                    group_title = group_name.replace('-', ' ').title()
                    groups.append({
                        'acronym': group_name,
                        'name': f'{group_title} Working Group',
                        'type': 'Working Group',
                        'state': 'Active',
                        'chairs': [f'Chair {i+1}' for i in range(1 + (hash(group_name) % 2))],  # 1-2 chairs
                        'description': f'The {group_title} Working Group focuses on {group_title.lower()} standards and protocols for the Internet.'
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
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>Initial Review</h6>
                                <p class="text-muted small">Pending</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            <div class="timeline-marker bg-light"></div>
                            <div class="timeline-content">
                                <h6>Working Group Review</h6>
                                <p class="text-muted small">Pending</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            <div class="timeline-marker bg-light"></div>
                            <div class="timeline-content">
                                <h6>IESG Review</h6>
                                <p class="text-muted small">Pending</p>
                            </div>
                        </div>
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

@app.route('/admin/')
@require_role('admin')
def admin_dashboard():
    current_user = get_current_user()
    current_theme = current_user.get('theme', 'dark') if current_user else 'dark'

    # Generate user menu
    user_menu = f"""
    <div class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
            {current_user['name'] if current_user else 'Admin'}
        </a>
        <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="/profile/">Profile</a></li>
            <li><a class="dropdown-item" href="/logout/">Logout</a></li>
        </ul>
    </div>
    """

    # Get statistics
    total_users = len(USERS)
    total_submissions = len(SUBMISSIONS)
    total_drafts = len(DRAFTS)
    pending_chairs = len([c for c in WORKING_GROUP_CHAIRS.values() if not c['approved']])
    total_chairs = len(WORKING_GROUP_CHAIRS)
    approved_chairs = len([c for c in WORKING_GROUP_CHAIRS.values() if c['approved']])

    # Recent activity
    recent_submissions = sorted(SUBMISSIONS.values(), key=lambda x: x['submitted_at'], reverse=True)[:5]
    # For users, we'll just show the first 5 (since we don't have creation dates in the simple dict)
    recent_users = list(USERS.keys())[:5]

    content = f"""
    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="mb-1">Admin Dashboard</h1>
                <p class="text-muted mb-0">Manage MLTF system and content</p>
            </div>
        </div>

        <!-- Statistics Cards -->
        <div class="row mb-4">
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-primary">{total_users}</h4>
                        <small class="text-muted">Users</small>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{total_submissions}</h4>
                        <small class="text-muted">Submissions</small>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{total_drafts}</h4>
                        <small class="text-muted">Drafts</small>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{total_chairs}</h4>
                        <small class="text-muted">Chairs</small>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{approved_chairs}</h4>
                        <small class="text-muted">Active Chairs</small>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-danger">{pending_chairs}</h4>
                        <small class="text-muted">Pending Chairs</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Management Cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <i class="fas fa-users-cog fa-3x text-primary mb-3"></i>
                        <h5>User Management</h5>
                        <p class="text-muted small">Manage user accounts, roles, and permissions</p>
                        <a href="/admin/users/" class="btn btn-outline-primary btn-sm">Manage Users</a>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <i class="fas fa-user-tie fa-3x text-success mb-3"></i>
                        <h5>Chair Management</h5>
                        <p class="text-muted small">Manage working group chairs and approvals</p>
                        <a href="/admin/chairs/" class="btn btn-outline-success btn-sm">Manage Chairs</a>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <i class="fas fa-file-alt fa-3x text-info mb-3"></i>
                        <h5>Submission Management</h5>
                        <p class="text-muted small">Review and manage draft submissions</p>
                        <a href="/admin/submissions/" class="btn btn-outline-info btn-sm">Manage Submissions</a>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <i class="fas fa-chart-bar fa-3x text-warning mb-3"></i>
                        <h5>Analytics</h5>
                        <p class="text-muted small">View system analytics and reports</p>
                        <a href="/admin/analytics/" class="btn btn-outline-warning btn-sm">View Analytics</a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Activity -->
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Recent Submissions</h5>
                    </div>
                    <div class="card-body p-0">
                        <div class="list-group list-group-flush">
                            {"".join([f'''
                            <a href="/submit/status/{s['id']}/" class="list-group-item list-group-item-action">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">{s['title'][:50]}{"..." if len(s['title']) > 50 else ""}</h6>
                                    <small>{s['submitted_at'].strftime("%m/%d")}</small>
                                </div>
                                <p class="mb-1">{", ".join(s['authors'][:2])}{"..." if len(s['authors']) > 2 else ""}</p>
                                <small class="text-muted">{s.get('group', 'No group')} • <span class="badge bg-{ "warning" if s['status'] == "submitted" else "success" if s['status'] == "approved" else "info"}">{s['status']}</span></small>
                            </a>
                            ''' for s in recent_submissions])}
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Recent Users</h5>
                    </div>
                    <div class="card-body p-0">
                        <div class="list-group list-group-flush">
                            {"".join([f'''
                            <div class="list-group-item">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">{USERS[u]['name']}</h6>
                                    <small>N/A</small>
                                </div>
                                <p class="mb-1">{USERS[u]['email']}</p>
                                <small class="text-muted"><span class="badge bg-secondary">{USERS[u].get('role', 'user')}</span></small>
                            </div>
                            ''' for u in recent_users])}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Admin Dashboard - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content
    )

@app.route('/admin/chairs/')
@require_role('admin')
def admin_chairs():
    current_user = get_current_user()
    current_theme = current_user.get('theme', 'dark') if current_user else 'dark'

    # Generate user menu
    user_menu = f"""
    <div class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
            {current_user['name'] if current_user else 'Admin'}
        </a>
        <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="/profile/">Profile</a></li>
            <li><a class="dropdown-item" href="/logout/">Logout</a></li>
        </ul>
    </div>
    """

    # Get filter parameters
    search_query = request.args.get('q', '').strip()
    group_filter = request.args.get('group', '').strip()
    status_filter = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Get all chairs from memory
    all_chairs = []
    for chair_id, chair_data in WORKING_GROUP_CHAIRS.items():
        chair_data['id'] = chair_id
        all_chairs.append(chair_data)

    # Apply filters
    if search_query:
        all_chairs = [c for c in all_chairs if
                     search_query.lower() in c['chair_name'].lower() or
                     search_query.lower() in (c.get('chair_email', '') or '').lower()]

    if group_filter:
        all_chairs = [c for c in all_chairs if c['group_acronym'] == group_filter]

    if status_filter:
        if status_filter == 'approved':
            all_chairs = [c for c in all_chairs if c['approved']]
        elif status_filter == 'pending':
            all_chairs = [c for c in all_chairs if not c['approved']]

    # Get statistics
    total_chairs = len(WORKING_GROUP_CHAIRS)
    approved_chairs = len([c for c in WORKING_GROUP_CHAIRS.values() if c['approved']])
    pending_chairs = total_chairs - approved_chairs

    # Get unique groups for filter dropdown
    group_options = list(set(c['group_acronym'] for c in WORKING_GROUP_CHAIRS.values()))

    # Sort and paginate
    all_chairs.sort(key=lambda x: x['set_at'], reverse=True)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    chairs_page = all_chairs[start_idx:end_idx]

    # Create a mock pagination object
    class MockPagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page

        @property
        def has_prev(self):
            return self.page > 1

        @property
        def has_next(self):
            return self.page < self.pages

        @property
        def prev_num(self):
            return self.page - 1

        @property
        def next_num(self):
            return self.page + 1

        def iter_pages(self):
            # Simple page iteration
            start_page = max(1, self.page - 2)
            end_page = min(self.pages, self.page + 2)
            for p in range(start_page, end_page + 1):
                yield p

    chairs = MockPagination(chairs_page, page, per_page, len(all_chairs))

    # Build chair rows
    chair_rows = ""
    for chair in chairs.items:
        status_badge = 'success' if chair['approved'] else 'warning'
        status_text = 'Active' if chair['approved'] else 'Pending'
        actions = f"""
        <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-primary btn-sm" onclick="editChair({chair['id']})" title="Edit Chair">
                <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-outline-secondary btn-sm" onclick="transferChair({chair['id']})" title="Transfer to Another Group">
                <i class="fas fa-exchange-alt"></i>
            </button>
            {'<button class="btn btn-outline-success btn-sm" onclick="approveChair(' + str(chair['id']) + ')" title="Approve Chair"><i class="fas fa-check"></i></button>' if not chair['approved'] else ''}
            <button class="btn btn-outline-danger btn-sm" onclick="deleteChair({chair['id']})" title="Remove Chair">
                <i class="fas fa-trash"></i>
            </button>
        </div>
        """
        chair_rows += f"""
        <tr>
            <td>
                <input type="checkbox" class="chair-checkbox" value="{chair['id']}" onchange="updateBulkActions()">
            </td>
            <td>{chair['chair_name']}</td>
            <td>{chair.get('chair_email', 'N/A') or 'N/A'}</td>
            <td><code>{chair['group_acronym']}</code></td>
            <td><span class="badge bg-{status_badge}">{status_text}</span></td>
            <td>{chair['set_at'].strftime('%Y-%m-%d')}</td>
            <td>{actions}</td>
        </tr>
        """

    # Build pagination
    pagination = ""
    if chairs.pages > 1:
        pagination = '<nav><ul class="pagination justify-content-center">'

        # Previous
        if chairs.has_prev:
            pagination += f'<li class="page-item"><a class="page-link" href="?page={chairs.prev_num}&q={search_query}&group={group_filter}&status={status_filter}">Previous</a></li>'
        else:
            pagination += '<li class="page-item disabled"><span class="page-link">Previous</span></li>'

        # Page numbers
        for page_num in chairs.iter_pages():
            if page_num:
                active_class = 'active' if page_num == chairs.page else ''
                pagination += f'<li class="page-item {active_class}"><a class="page-link" href="?page={page_num}&q={search_query}&group={group_filter}&status={status_filter}">{page_num}</a></li>'
            else:
                pagination += '<li class="page-item disabled"><span class="page-link">...</span></li>'

        # Next
        if chairs.has_next:
            pagination += f'<li class="page-item"><a class="page-link" href="?page={chairs.next_num}&q={search_query}&group={group_filter}&status={status_filter}">Next</a></li>'
        else:
            pagination += '<li class="page-item disabled"><span class="page-link">Next</span></li>'

        pagination += '</ul></nav>'

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">Chair Management</li>
            </ol>
        </nav>

        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="mb-1">Chair Management</h1>
                <p class="text-muted mb-0">Manage working group chairs across all groups</p>
            </div>
            <button class="btn btn-primary" onclick="addNewChair()">
                <i class="fas fa-plus me-2"></i>Add New Chair
            </button>
        </div>

        <!-- Statistics Cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-primary">{total_chairs}</h4>
                        <small class="text-muted">Total Chairs</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{approved_chairs}</h4>
                        <small class="text-muted">Active Chairs</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{pending_chairs}</h4>
                        <small class="text-muted">Pending Approval</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{len(group_options)}</h4>
                        <small class="text-muted">Working Groups</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Filters -->
        <div class="card mb-4">
            <div class="card-body">
                <form method="GET" class="row g-3">
                    <div class="col-md-4">
                        <input type="text" class="form-control" name="q" placeholder="Search chairs..." value="{search_query}">
                    </div>
                    <div class="col-md-3">
                        <select class="form-select" name="group">
                            <option value="">All Groups</option>
                            {"".join(f'<option value="{g}" {"selected" if g == group_filter else ""}>{g}</option>' for g in sorted(group_options))}
                        </select>
                    </div>
                    <div class="col-md-2">
                        <select class="form-select" name="status">
                            <option value="">All Status</option>
                            <option value="approved" {"selected" if status_filter == "approved" else ""}>Active</option>
                            <option value="pending" {"selected" if status_filter == "pending" else ""}>Pending</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <button type="submit" class="btn btn-outline-primary me-2">
                            <i class="fas fa-search me-1"></i>Search
                        </button>
                        <a href="/admin/chairs/" class="btn btn-outline-secondary">
                            <i class="fas fa-times me-1"></i>Clear
                        </a>
                    </div>
                </form>
            </div>
        </div>

        <!-- Bulk Actions -->
        <div class="d-flex justify-content-between align-items-center mb-3" id="bulk-actions" style="display: none;">
            <div>
                <span id="selected-count">0</span> chairs selected
            </div>
            <div>
                <button class="btn btn-outline-success btn-sm me-2" onclick="bulkApprove()">
                    <i class="fas fa-check me-1"></i>Approve Selected
                </button>
                <button class="btn btn-outline-danger btn-sm me-2" onclick="bulkDelete()">
                    <i class="fas fa-trash me-1"></i>Delete Selected
                </button>
                <button class="btn btn-outline-secondary btn-sm" onclick="clearSelection()">
                    <i class="fas fa-times me-1"></i>Clear
                </button>
            </div>
        </div>

        <!-- Chairs Table -->
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">Chairs ({chairs.total})</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th width="50"><input type="checkbox" onclick="toggleAllCheckboxes(this)"></th>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Group</th>
                                <th>Status</th>
                                <th>Added</th>
                                <th width="180">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {chair_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        {pagination}
    </div>

    <!-- Add/Edit Chair Modal -->
    <div class="modal fade" id="chairModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="chairModalTitle">Add New Chair</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="chairForm">
                        <input type="hidden" id="chairId" value="">
                        <div class="mb-3">
                            <label for="chairName" class="form-label">Chair Name *</label>
                            <input type="text" class="form-control" id="chairName" required>
                        </div>
                        <div class="mb-3">
                            <label for="chairEmail" class="form-label">Email</label>
                            <input type="email" class="form-control" id="chairEmail">
                        </div>
                        <div class="mb-3">
                            <label for="chairGroup" class="form-label">Working Group *</label>
                            <select class="form-select" id="chairGroup" required>
                                <option value="">Select Group</option>
                                {"".join(f'<option value="{g}">{g}</option>' for g in sorted(group_options))}
                            </select>
                        </div>
                        <div class="mb-3">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="chairApproved">
                                <label class="form-check-label" for="chairApproved">
                                    Approved (Active Chair)
                                </label>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="saveChair()">Save Chair</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Transfer Chair Modal -->
    <div class="modal fade" id="transferModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Transfer Chair</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="transferChairInfo" class="mb-3"></div>
                    <div class="mb-3">
                        <label for="transferGroup" class="form-label">New Working Group</label>
                        <select class="form-select" id="transferGroup" required>
                            <option value="">Select Group</option>
                            {"".join(f'<option value="{g}">{g}</option>' for g in sorted(group_options))}
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="confirmTransfer()">Transfer Chair</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentChairId = null;
        let currentTransferChairId = null;

        function addNewChair() {{
            document.getElementById('chairModalTitle').textContent = 'Add New Chair';
            document.getElementById('chairId').value = '';
            document.getElementById('chairName').value = '';
            document.getElementById('chairEmail').value = '';
            document.getElementById('chairGroup').value = '';
            document.getElementById('chairApproved').checked = false;
            new bootstrap.Modal(document.getElementById('chairModal')).show();
        }}

        function editChair(chairId) {{
            fetch(`/admin/chairs/${{chairId}}`)
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        const chair = data.chair;
                        document.getElementById('chairModalTitle').textContent = 'Edit Chair';
                        document.getElementById('chairId').value = chair.id;
                        document.getElementById('chairName').value = chair.chair_name;
                        document.getElementById('chairEmail').value = chair.chair_email || '';
                        document.getElementById('chairGroup').value = chair.group_acronym;
                        document.getElementById('chairApproved').checked = chair.approved;
                        new bootstrap.Modal(document.getElementById('chairModal')).show();
                    }} else {{
                        alert('Error loading chair data: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error loading chair data');
                }});
        }}

        function saveChair() {{
            const chairId = document.getElementById('chairId').value;
            const chairData = {{
                chair_name: document.getElementById('chairName').value.trim(),
                chair_email: document.getElementById('chairEmail').value.trim(),
                group_acronym: document.getElementById('chairGroup').value,
                approved: document.getElementById('chairApproved').checked
            }};

            if (!chairData.chair_name || !chairData.group_acronym) {{
                alert('Chair name and group are required');
                return;
            }}

            const method = chairId ? 'PUT' : 'POST';
            const url = chairId ? `/admin/chairs/${{chairId}}` : '/admin/chairs/';

            fetch(url, {{
                method: method,
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify(chairData)
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    bootstrap.Modal.getInstance(document.getElementById('chairModal')).hide();
                    location.reload();
                }} else {{
                    alert('Error saving chair: ' + data.message);
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error saving chair');
            }});
        }}

        function approveChair(chairId) {{
            if (confirm('Are you sure you want to approve this chair?')) {{
                fetch(`/admin/chairs/${{chairId}}/approve`, {{
                    method: 'POST'
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
        }}

        function transferChair(chairId) {{
            fetch(`/admin/chairs/${{chairId}}`)
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        const chair = data.chair;
                        document.getElementById('transferChairInfo').innerHTML = `
                            <strong>${{chair.chair_name}}</strong> from <code>${{chair.group_acronym}}</code>
                        `;
                        document.getElementById('transferGroup').value = '';
                        currentTransferChairId = chairId;
                        new bootstrap.Modal(document.getElementById('transferModal')).show();
                    }} else {{
                        alert('Error loading chair data: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error loading chair data');
                }});
        }}

        function confirmTransfer() {{
            const newGroup = document.getElementById('transferGroup').value;
            if (!newGroup) {{
                alert('Please select a new working group');
                return;
            }}

            fetch(`/admin/chairs/${{currentTransferChairId}}/transfer`, {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{ group_acronym: newGroup }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    bootstrap.Modal.getInstance(document.getElementById('transferModal')).hide();
                    location.reload();
                }} else {{
                    alert('Error transferring chair: ' + data.message);
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error transferring chair');
            }});
        }}

        function deleteChair(chairId) {{
            if (confirm('Are you sure you want to delete this chair? This action cannot be undone.')) {{
                fetch(`/admin/chairs/${{chairId}}`, {{
                    method: 'DELETE'
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        location.reload();
                    }} else {{
                        alert('Error deleting chair: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error deleting chair');
                }});
            }}
        }}

        function toggleAllCheckboxes(checkbox) {{
            const checkboxes = document.querySelectorAll('.chair-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
            updateBulkActions();
        }}

        function updateBulkActions() {{
            const checkedBoxes = document.querySelectorAll('.chair-checkbox:checked');
            const bulkActions = document.getElementById('bulk-actions');
            const selectedCount = document.getElementById('selected-count');

            if (checkedBoxes.length > 0) {{
                bulkActions.style.display = 'flex';
                selectedCount.textContent = checkedBoxes.length;
            }} else {{
                bulkActions.style.display = 'none';
            }}
        }}

        function bulkApprove() {{
            const checkedBoxes = document.querySelectorAll('.chair-checkbox:checked');
            const chairIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));

            if (chairIds.length === 0) {{
                alert('No chairs selected');
                return;
            }}

            if (confirm(`Are you sure you want to approve ${{chairIds.length}} chair(s)?`)) {{
                fetch('/admin/chairs/bulk-approve', {{
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
                        alert('Error approving chairs: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error approving chairs');
                }});
            }}
        }}

        function bulkDelete() {{
            const checkedBoxes = document.querySelectorAll('.chair-checkbox:checked');
            const chairIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));

            if (chairIds.length === 0) {{
                alert('No chairs selected');
                return;
            }}

            if (confirm(`Are you sure you want to delete ${{chairIds.length}} chair(s)? This action cannot be undone.`)) {{
                fetch('/admin/chairs/bulk-delete', {{
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
                        alert('Error deleting chairs: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error deleting chairs');
                }});
            }}
        }}

        function clearSelection() {{
            const checkboxes = document.querySelectorAll('.chair-checkbox');
            checkboxes.forEach(cb => cb.checked = false);
            updateBulkActions();
        }}
    </script>
    """

    return BASE_TEMPLATE.format(
        title="Chair Management - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content
    )

# Chair management API routes
@app.route('/admin/chairs/', methods=['POST'])
@require_role('admin')
def create_chair():
    data = request.get_json()
    chair_name = data.get('chair_name', '').strip()
    chair_email = data.get('chair_email', '').strip() or None
    group_acronym = data.get('group_acronym', '').strip()
    approved = data.get('approved', False)

    if not chair_name or not group_acronym:
        return jsonify({'success': False, 'message': 'Chair name and group are required'}), 400

    # Check if chair already exists in this group
    for chair_data in WORKING_GROUP_CHAIRS.values():
        if chair_data['group_acronym'] == group_acronym and chair_data['chair_name'] == chair_name:
            return jsonify({'success': False, 'message': 'Chair already exists in this group'}), 400

    # Get current user for audit logging
    current_user = get_current_user()

    # Generate unique ID
    chair_id = str(uuid.uuid4())

    # Create new chair
    WORKING_GROUP_CHAIRS[chair_id] = {
        'chair_name': chair_name,
        'chair_email': chair_email,
        'group_acronym': group_acronym,
        'approved': approved,
        'set_at': datetime.utcnow()
    }

    return jsonify({'success': True, 'message': 'Chair created successfully', 'chair_id': chair_id})

@app.route('/admin/chairs/<chair_id>', methods=['GET', 'PUT', 'DELETE'])
@require_role('admin')
def manage_chair(chair_id):
    if chair_id not in WORKING_GROUP_CHAIRS:
        return jsonify({'success': False, 'message': 'Chair not found'}), 404

    chair = WORKING_GROUP_CHAIRS[chair_id]
    current_user = get_current_user()

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'chair': {
                'id': chair_id,
                'chair_name': chair['chair_name'],
                'chair_email': chair['chair_email'],
                'group_acronym': chair['group_acronym'],
                'approved': chair['approved'],
                'set_at': chair['set_at'].isoformat()
            }
        })

    elif request.method == 'PUT':
        data = request.get_json()
        old_data = chair.copy()

        # Update chair
        chair['chair_name'] = data.get('chair_name', chair['chair_name']).strip()
        chair['chair_email'] = data.get('chair_email', '').strip() or None
        chair['group_acronym'] = data.get('group_acronym', chair['group_acronym']).strip()
        chair['approved'] = data.get('approved', chair['approved'])

        return jsonify({'success': True, 'message': 'Chair updated successfully'})

    elif request.method == 'DELETE':
        del WORKING_GROUP_CHAIRS[chair_id]
        return jsonify({'success': True, 'message': 'Chair deleted successfully'})

@app.route('/admin/chairs/<chair_id>/approve', methods=['POST'])
@require_role('admin')
def approve_chair(chair_id):
    if chair_id not in WORKING_GROUP_CHAIRS:
        return jsonify({'success': False, 'message': 'Chair not found'}), 404

    chair = WORKING_GROUP_CHAIRS[chair_id]
    current_user = get_current_user()

    if chair['approved']:
        return jsonify({'success': False, 'message': 'Chair is already approved'}), 400

    chair['approved'] = True

    return jsonify({'success': True, 'message': 'Chair approved successfully'})

@app.route('/admin/chairs/<chair_id>/transfer', methods=['POST'])
@require_role('admin')
def transfer_chair(chair_id):
    if chair_id not in WORKING_GROUP_CHAIRS:
        return jsonify({'success': False, 'message': 'Chair not found'}), 404

    chair = WORKING_GROUP_CHAIRS[chair_id]
    data = request.get_json()
    new_group = data.get('group_acronym', '').strip()

    if not new_group:
        return jsonify({'success': False, 'message': 'New group is required'}), 400

    if new_group == chair['group_acronym']:
        return jsonify({'success': False, 'message': 'Chair is already in this group'}), 400

    current_user = get_current_user()
    chair['group_acronym'] = new_group

    return jsonify({'success': True, 'message': 'Chair transferred successfully'})

@app.route('/admin/chairs/bulk-approve', methods=['POST'])
@require_role('admin')
def bulk_approve_chairs():
    data = request.get_json()
    chair_ids = data.get('chair_ids', [])

    if not chair_ids:
        return jsonify({'success': False, 'message': 'No chairs selected'}), 400

    current_user = get_current_user()

    # Update chairs
    approved_count = 0
    for chair_id in chair_ids:
        if chair_id in WORKING_GROUP_CHAIRS and not WORKING_GROUP_CHAIRS[chair_id]['approved']:
            WORKING_GROUP_CHAIRS[chair_id]['approved'] = True
            approved_count += 1

    return jsonify({'success': True, 'message': f'Approved {approved_count} chair(s) successfully'})

@app.route('/admin/chairs/bulk-delete', methods=['POST'])
@require_role('admin')
def bulk_delete_chairs():
    data = request.get_json()
    chair_ids = data.get('chair_ids', [])

    if not chair_ids:
        return jsonify({'success': False, 'message': 'No chairs selected'}), 400

    current_user = get_current_user()

    # Delete chairs
    deleted_count = 0
    for chair_id in chair_ids:
        if chair_id in WORKING_GROUP_CHAIRS:
            del WORKING_GROUP_CHAIRS[chair_id]
            deleted_count += 1

    return jsonify({'success': True, 'message': f'Deleted {deleted_count} chair(s) successfully'})

# Routes
@app.route('/')
def home():
    # Generate user menu
    current_user = get_current_user()
    if current_user:
        user_menu = f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                {current_user['name']}
            </a>
            <ul class="dropdown-menu">
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
                # Initialize comments list for this draft if it doesn't exist
                if draft_name not in COMMENTS:
                    COMMENTS[draft_name] = []
                
                # Add new comment with unique ID
                comment_id = f"comment_{len(COMMENTS[draft_name]) + 1}"
                new_comment = {
                    'id': comment_id,
                    'author': current_user['name'],
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'comment': comment_text,
                    'avatar': ''.join([word[0].upper() for word in current_user['name'].split()[:2]])
                }
                COMMENTS[draft_name].append(new_comment)
                
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
    
    # Get all comments for this draft
    all_comments = COMMENTS.get(draft_name, [])
    
    # Always include sample comments (real IETF-style comments)
    sample_comments = [
        {
            'id': 'sample_1',
            'author': 'John Smith',
            'date': '2024-01-15 14:30',
            'comment': 'This is a great draft! I think the approach is solid and the implementation details are well thought out.',
            'avatar': 'JS'
        },
        {
            'id': 'sample_2',
            'author': 'Alice Johnson',
            'date': '2024-01-16 09:15',
            'comment': 'I have some concerns about the security implications mentioned in section 3.2. Could we discuss this further?',
            'avatar': 'AJ'
        },
        {
            'id': 'sample_3',
            'author': 'Bob Wilson',
            'date': '2024-01-16 16:45',
            'comment': 'The performance metrics look promising. Have you considered the impact on legacy systems?',
            'avatar': 'BW'
        }
    ]
    
    # Combine sample comments with user comments
    all_comments = sample_comments + all_comments
    
    current_user = get_current_user()
    comments_html = ""
    for comment in all_comments:
        comment_id = comment.get('id', 'unknown')
        like_count = get_comment_likes(draft_name, comment_id)
        is_liked = is_comment_liked(draft_name, comment_id, current_user['name']) if current_user else False
        replies = get_comment_replies(draft_name, comment_id)
        
        # Like button class
        like_btn_class = "btn-outline-danger" if is_liked else "btn-outline-secondary"
        like_icon = "❤️" if is_liked else "🤍"
        
        comments_html += f"""
        <div class="card mb-3" id="comment-{comment_id}">
            <div class="card-body">
                <div class="d-flex align-items-center mb-2">
                    <div class="avatar bg-primary text-white rounded-circle me-2" style="width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-weight: bold;">
                        {comment['avatar']}
                    </div>
                    <div>
                        <strong>{comment['author']}</strong>
                        <small class="text-muted ms-2">{comment['date']}</small>
                    </div>
                </div>
                <p class="mb-2">{comment['comment']}</p>
                <div class="d-flex gap-2 align-items-center">
                    <button class="btn btn-sm {like_btn_class}" onclick="toggleLike('{comment_id}')">
                        {like_icon} {like_count}
                    </button>
                    <button class="btn btn-sm btn-outline-primary" onclick="toggleReply('{comment_id}')">
                        Reply
                    </button>
                </div>
                
                <!-- Reply form (hidden by default) -->
                <div id="reply-form-{comment_id}" class="mt-3" style="display: none;">
                    <form method="POST" class="d-flex gap-2">
                        <input type="hidden" name="action" value="reply">
                        <input type="hidden" name="parent_comment_id" value="{comment_id}">
                        <input type="text" name="reply_text" class="form-control" placeholder="Write a reply..." required>
                        <button type="submit" class="btn btn-primary btn-sm">Reply</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="toggleReply('{comment_id}')">Cancel</button>
                    </form>
                </div>
                
                <!-- Replies -->
                {render_replies(replies)}
            </div>
        </div>
        """
    
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
            // Create a form to submit the like
            const form = document.createElement('form');
            form.method = 'POST';
            form.innerHTML = `
                <input type="hidden" name="action" value="like">
                <input type="hidden" name="comment_id" value="${{commentId}}">
            `;
            document.body.appendChild(form);
            form.submit();
        }}
        
        function toggleReply(commentId) {{
            const replyForm = document.getElementById('reply-form-' + commentId);
            if (replyForm.style.display === 'none') {{
                replyForm.style.display = 'block';
            }} else {{
                replyForm.style.display = 'none';
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
    return "<h1>Meetings</h1><p>This would show IETF meetings information.</p>"

@app.route('/person/')
def people():
    return "<h1>People</h1><p>This would show IETF participants directory.</p>"

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
            flash('No file selected', 'error')
            return redirect(url_for('submit_draft'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('submit_draft'))
        
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
            
            # Store submission
            SUBMISSIONS[submission_id] = {
                'id': submission_id,
                'title': title,
                'authors': author_list,
                'abstract': abstract,
                'group': group,
                'filename': filename,
                'file_path': file_path,
                'draft_name': draft_name,
                'status': 'submitted',
                'submitted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'submitted_by': 'Anonymous User'
            }
            
            flash(f'Draft submitted successfully! Submission ID: {submission_id}', 'success')
            return redirect(url_for('submission_status', submission_id=submission_id))
        else:
            flash('Invalid file type. Please upload PDF, TXT, XML, DOC, or DOCX files.', 'error')
    
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
    
    return render_template_string(BASE_TEMPLATE.format(title="Submit Draft - IETF Datatracker", user_menu=user_menu, content=SUBMIT_TEMPLATE))

@app.route('/submit/status/<submission_id>/')
def submission_status(submission_id):
    """Submission status page"""
    submission = SUBMISSIONS.get(submission_id)
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('submit_draft'))
    
    return render_template_string(BASE_TEMPLATE.format(title=f"Submission Status - {submission_id}", content=SUBMISSION_STATUS_TEMPLATE), submission=submission)

if __name__ == '__main__':
    print("Starting IETF Data Viewer...")
    print(f"Loaded {len(DRAFTS)} drafts and {len(GROUPS)} groups")
    app.run(host='0.0.0.0', port=8000, debug=True)
