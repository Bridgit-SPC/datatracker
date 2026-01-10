#!/bin/bash
#
# Safe Development Workflow Script
# Use this for major changes to prevent breaking functionality
#

set -e  # Exit on any error

echo "🔧 MLTF Datatracker - Safe Development Workflow"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. Backup current state
echo ""
echo "1. 📦 Creating backup..."
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$BACKUP_FILE" --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' .
print_status "Backup created: $BACKUP_FILE"

# 2. Run pre-change tests
echo ""
echo "2. 🧪 Running pre-change verification..."
if python3 test_core_features.py; then
    print_status "All features working before changes"
else
    print_error "Pre-change tests failed! Fix issues before proceeding."
    exit 1
fi

# 3. Show current git status
echo ""
echo "3. 📊 Current git status:"
git status --short

# 4. Handle command line arguments
if [ "$1" = "--verify" ]; then
    echo "🔍 Running verification only..."
    if python3 test_core_features.py; then
        print_status "All features verified and working!"
        exit 0
    else
        print_error "Verification failed!"
        exit 1
    fi
fi

# 4. Make changes (interactive)
echo ""
echo "4. ✏️  Make your changes now..."
echo "   Edit files as needed, then run:"
echo "   $ ./dev_workflow.sh --verify"
echo ""
read -p "Press Enter when you've made your changes..."

# 5. Run post-change verification
echo ""
echo "5. 🔍 Running post-change verification..."
if python3 test_core_features.py; then
    print_status "All features still working after changes!"
    echo ""
    echo "🎉 SAFE TO COMMIT!"
    echo "Run: git add . && git commit -m \"Your message\""
else
    print_error "POST-CHANGE TESTS FAILED!"
    echo ""
    echo "🔧 Options:"
    echo "   1. Fix the issues and re-run this script"
    echo "   2. Restore from backup: tar -xzf $BACKUP_FILE"
    echo "   3. Check git diff to see what changed"
    echo ""
    exit 1
fi

echo ""
print_status "Development workflow completed successfully!"