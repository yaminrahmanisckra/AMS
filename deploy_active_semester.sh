#!/bin/bash

# Active Semester Management Feature Deployment Script for cPanel
# Usage: chmod +x deploy_active_semester.sh && ./deploy_active_semester.sh
# 
# Configuration:
# - Project Path: /home/gronthon/kulawams.xyz
# - Virtual Environment: /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

set -e  # Exit on error

# Configuration
PROJECT_DIR="/home/gronthon/kulawams.xyz"
VENV_PATH="/home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate"

echo "🚀 Starting Active Semester Management Deployment..."
echo "=================================================="
echo "Project: $PROJECT_DIR"
echo "Virtual Env: $VENV_PATH"
echo "=================================================="

# Navigate to project directory
cd "$PROJECT_DIR" || {
    echo "❌ Error: Cannot navigate to $PROJECT_DIR"
    exit 1
}

# Step 1: Handle local changes and pull latest code
echo ""
echo "📥 Step 1: Handling local changes and pulling latest code..."

# Check if there are local changes
if git diff --quiet && git diff --cached --quiet; then
    echo "   No local changes detected"
    CHANGES_EXIST=false
else
    echo "   ⚠️  Local changes detected, stashing them..."
    git stash push -m "Auto-stash before deployment $(date +%Y%m%d_%H%M%S)"
    CHANGES_EXIST=true
fi

# Remove untracked files that might conflict
echo "   Checking for conflicting untracked files..."
if git ls-files --others --exclude-standard | grep -q .; then
    echo "   ⚠️  Untracked files found, backing up..."
    UNTRACKED_FILES=$(git ls-files --others --exclude-standard)
    echo "$UNTRACKED_FILES" > /tmp/untracked_files_backup_$(date +%Y%m%d_%H%M%S).txt
    git clean -fd
    echo "   Untracked files removed (backup in /tmp if needed)"
fi

# Pull latest code
if git pull origin main; then
    echo "✅ Code pulled successfully"
    
    # If we had local changes, try to reapply them
    if [ "$CHANGES_EXIST" = true ]; then
        echo "   Attempting to reapply stashed changes..."
        if git stash pop; then
            echo "   ✅ Stashed changes reapplied"
        else
            echo "   ⚠️  Warning: Could not reapply stashed changes automatically"
            echo "   Check 'git stash list' and apply manually if needed"
        fi
    fi
else
    echo "⚠️  Warning: Git pull failed or not a git repository"
    echo "   Please manually ensure all files are updated"
fi

# Step 2: Activate virtual environment
echo ""
echo "🔧 Step 2: Activating virtual environment..."
if [ -f "$VENV_PATH" ]; then
    echo "   Activating virtual environment from: $VENV_PATH"
    source "$VENV_PATH"
    echo "✅ Virtual environment activated"
    echo "   Python: $(which python)"
    echo "   Python version: $(python --version)"
else
    echo "⚠️  Warning: Virtual environment not found at $VENV_PATH"
    echo "   Using system Python: $(which python)"
fi

# Step 3: Check if required files exist
echo ""
echo "📋 Step 3: Verifying required files..."
REQUIRED_FILES=(
    "blueprints/course_management/models.py"
    "utils/semester_utils.py"
    "app.py"
    "templates/admin/active_semester.html"
    "migrations/versions/add_active_semester_config_model.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file exists"
    else
        echo "   ❌ ERROR: $file not found!"
        exit 1
    fi
done

# Step 4: Run database migration
echo ""
echo "🗄️  Step 4: Running database migration..."
if command -v flask &> /dev/null; then
    echo "   Running: flask db upgrade"
    if flask db upgrade; then
        echo "✅ Database migration completed"
    else
        echo "⚠️  Flask migration failed, trying alternative method..."
        if [ -f "$PROJECT_DIR/run_migration.py" ]; then
            echo "   Running: python run_migration.py"
            python run_migration.py || echo "⚠️  Migration script also failed, please run manually"
        fi
    fi
else
    echo "⚠️  Flask command not found, trying Python script..."
    if [ -f "$PROJECT_DIR/run_migration.py" ]; then
        echo "   Running: python run_migration.py"
        python run_migration.py || echo "⚠️  Please run migration manually"
    else
        echo "⚠️  Please run migration manually: flask db upgrade"
        echo "   Or: source $VENV_PATH && cd $PROJECT_DIR && flask db upgrade"
    fi
fi

# Step 5: Set file permissions
echo ""
echo "📝 Step 5: Setting file permissions..."
cd "$PROJECT_DIR"
chmod 644 utils/semester_utils.py 2>/dev/null || true
chmod 644 templates/admin/active_semester.html 2>/dev/null || true
chmod 755 utils/ 2>/dev/null || true
chmod 755 templates/admin/ 2>/dev/null || true
echo "✅ Permissions set"

# Step 6: Verify database table
echo ""
echo "🔍 Step 6: Verifying database setup..."
# This will be checked manually or via Python script
echo "   Please verify in phpMyAdmin that 'active_semester_config' table exists"

# Step 7: Restart application
echo ""
echo "🔄 Step 7: Restarting application..."
cd "$PROJECT_DIR"
if [ -f "passenger_wsgi.py" ]; then
    touch passenger_wsgi.py
    echo "✅ Application restart signal sent (passenger_wsgi.py touched)"
else
    echo "⚠️  passenger_wsgi.py not found at $PROJECT_DIR/passenger_wsgi.py"
    echo "   Please restart application manually from cPanel Python App"
    echo "   Or create passenger_wsgi.py if missing"
fi

# Final summary
echo ""
echo "=================================================="
echo "✅ Deployment Script Completed!"
echo ""
echo "📋 Next Steps:"
echo "   1. Check error logs: tail -f logs/app_errors.log"
echo "   2. Visit: /admin/active-semester"
echo "   3. Set an active semester"
echo "   4. Test filtering in different modules"
echo ""
echo "🔍 Verification:"
echo "   - Database table: SELECT * FROM active_semester_config;"
echo "   - Admin page: https://yourdomain.com/admin/active-semester"
echo "   - Check logs: logs/app_errors.log"
echo ""
echo "If you encounter any issues, check CPANEL_DEPLOY_ACTIVE_SEMESTER.md for troubleshooting"
echo "=================================================="

