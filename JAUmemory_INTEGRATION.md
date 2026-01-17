# JAUmemory Integration Guide

## Overview

JAUmemory is integrated into the agent workflow to:
- Learn from past implementations
- Store decisions and patterns
- Avoid repeating mistakes
- Maintain consistency across features

## When to Query JAUmemory

### Before Starting a Feature

**Query for similar implementations**:
```
"How was [similar feature] implemented in MLTF datatracker?"
"What patterns were used for [component type]?"
"What issues were encountered with [related feature]?"
```

**Query for best practices**:
```
"What is the standard approach for [task type]?"
"How are [component type] typically structured?"
"What testing patterns are used for [feature type]?"
```

### During Development

**Query when stuck**:
```
"How was [problem] solved before?"
"What approach worked for [similar situation]?"
```

**Query for consistency**:
```
"How are [similar components] structured?"
"What naming conventions are used for [component type]?"
```

### After Completion

**Store learnings**:
```
"Feature [name]: Implemented [what], used [how], learned [insights]"
"Pattern: [pattern name] - Used for [purpose], benefits [why]"
"Issue: [problem] - Solved with [solution], avoid [pitfall]"
```

## What to Store in JAUmemory

### 1. Feature Implementations

**Format**:
```
Feature: [Feature Name]
- Purpose: [What it does]
- Implementation: [How it was built]
- Components: [What files/components involved]
- Patterns: [Design patterns used]
- Lessons: [What was learned]
- Related: [Related features]
```

**Example**:
```
Feature: Comment Edit/Delete
- Purpose: Allow users to edit/delete their own comments within 15 minutes
- Implementation: Added edited_at, is_deleted, original_text columns to Comment model. Added can_edit_delete_comment() function. Added routes for edit/delete.
- Components: ietf_data_viewer_simple.py (Comment model, routes, render_comment_tree)
- Patterns: Time-based permission check, soft delete pattern
- Lessons: Need to check both author and time limit. Store original_text for audit.
- Related: Comment system, User permissions
```

### 2. Design Patterns

**Format**:
```
Pattern: [Pattern Name]
- Use Case: [When to use]
- Implementation: [How to implement]
- Benefits: [Why use it]
- Example: [Code example or reference]
```

**Example**:
```
Pattern: Environment-based Configuration
- Use Case: Different settings for dev/prod
- Implementation: Use FLASK_ENV environment variable. Set paths, ports, debug based on ENV.
- Benefits: Same codebase, different behavior. Easy to switch environments.
- Example: See ietf_data_viewer_simple.py lines 89-104
```

### 3. Common Issues and Solutions

**Format**:
```
Issue: [Problem Description]
- Symptoms: [How to recognize]
- Cause: [Root cause]
- Solution: [How to fix]
- Prevention: [How to avoid]
```

**Example**:
```
Issue: Code changes not appearing after deployment
- Symptoms: Changes in file but not visible in browser
- Cause: Python cache (.pyc files) or service not restarting properly
- Solution: Clear __pycache__ directories, kill processes, restart service
- Prevention: Always use deploy.py script which clears cache automatically
```

### 4. Database Patterns

**Format**:
```
Database Pattern: [Pattern Name]
- Use Case: [When to use]
- Schema: [Table structure]
- Queries: [Common queries]
- Migrations: [How to migrate]
```

### 5. API Patterns

**Format**:
```
API Pattern: [Pattern Name]
- Route: [Route pattern]
- Method: [HTTP method]
- Auth: [Authentication required]
- Response: [Response format]
- Testing: [How to test]
```

## JAUmemory Query Templates

### Starting a New Feature

```python
# Query template
queries = [
    "How was [similar feature] implemented?",
    "What patterns are used for [component type]?",
    "What issues were encountered with [related feature]?",
    "What testing approach is used for [feature type]?"
]

# Store template
store = {
    "feature": "[Feature Name]",
    "purpose": "[What it does]",
    "implementation": "[How built]",
    "patterns_used": ["[pattern1]", "[pattern2]"],
    "lessons": "[What learned]"
}
```

### During Development

```python
# When making decisions
store_decision = {
    "decision": "[What was decided]",
    "context": "[Why this decision]",
    "alternatives": ["[option1]", "[option2]"],
    "rationale": "[Why chosen]"
}

# When encountering issues
store_issue = {
    "issue": "[Problem]",
    "solution": "[How fixed]",
    "prevention": "[How to avoid]"
}
```

### After Completion

```python
# Store completion
store_completion = {
    "feature": "[Feature Name]",
    "status": "completed",
    "components": ["[file1]", "[file2]"],
    "tests": ["[test1]", "[test2]"],
    "deployment": "[dev/prod]",
    "verification": "[passed/failed]",
    "notes": "[Any important notes]"
}
```

## Integration Points

### 1. In Deployment Scripts

```python
# deploy.py
def deploy(env):
    # Before deployment
    query_jaumemory("How was deployment to {} done before?".format(env))
    
    # After successful deployment
    store_jaumemory({
        "event": "deployment",
        "environment": env,
        "git_commit": get_commit_hash(),
        "status": "success",
        "timestamp": datetime.now()
    })
```

### 2. In Verification Scripts

```python
# verify.py
def verify(env):
    # Query for known issues
    known_issues = query_jaumemory("What verification issues occurred in {}?".format(env))
    
    # Store verification results
    store_jaumemory({
        "event": "verification",
        "environment": env,
        "results": verification_results,
        "status": "passed/failed"
    })
```

### 3. In Feature Development

```python
# When starting feature
def start_feature(feature_name):
    # Query for similar features
    similar = query_jaumemory("How was {} implemented?".format(similar_feature))
    
    # Store feature start
    store_jaumemory({
        "event": "feature_start",
        "feature": feature_name,
        "timestamp": datetime.now()
    })
```

## Best Practices

1. **Query before coding**: Always check JAUmemory for similar work
2. **Store decisions**: Document why you chose an approach
3. **Store issues**: Help future you avoid same problems
4. **Store patterns**: Build up a library of reusable patterns
5. **Update regularly**: Keep JAUmemory current with latest work

## Example Workflow

### Starting "Add Email Notifications" Feature

1. **Query JAUmemory**:
   ```
   "How was notification system implemented?"
   "What patterns are used for background tasks?"
   "How are email features structured?"
   ```

2. **Store feature start**:
   ```
   Feature: Email Notifications
   - Purpose: Send email alerts for document follows
   - Status: In progress
   ```

3. **During development**:
   ```
   Decision: Using Flask-Mail instead of Celery for simplicity
   Pattern: Notification level system (all/significant/major/comments/none)
   ```

4. **After completion**:
   ```
   Feature: Email Notifications - Completed
   - Implementation: Flask-Mail integration, notification levels, email templates
   - Components: ietf_data_viewer_simple.py, email templates
   - Lessons: Start simple, can add Celery later if needed
   ```

## Integration with Agent System Prompt

The agent system prompt includes JAUmemory queries at key points:
- Before starting: Query for similar implementations
- During development: Store decisions and patterns
- After completion: Document what was done

This creates a feedback loop where the system learns and improves over time.
