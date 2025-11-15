#!/bin/bash
# Script to remove secrets from git history
# WARNING: This rewrites git history. Use with caution!

set -e

echo "⚠️  WARNING: This script will rewrite git history!"
echo "⚠️  This is a destructive operation that cannot be undone!"
echo ""
echo "Before proceeding:"
echo "1. Make sure you have a backup of your repository"
echo "2. Coordinate with your team (if working with others)"
echo "3. All team members will need to re-clone after this"
echo ""
read -p "Do you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# Check if git-filter-repo is installed (preferred method)
if command -v git-filter-repo &> /dev/null; then
    echo "✅ Using git-filter-repo (recommended method)"
    
    # Remove secrets from config.json files
    echo "Removing Gemini API key from config.json..."
    git filter-repo --path backend/config.json --path config.json \
        --invert-paths \
        --force
    
    # Re-add config.json without secrets
    git checkout HEAD -- backend/config.json config.json 2>/dev/null || true
    
    echo "✅ Secrets removed from history using git-filter-repo"
    
elif command -v git-filter-branch &> /dev/null; then
    echo "⚠️  Using git-filter-branch (legacy method)"
    echo "⚠️  Consider installing git-filter-repo for better performance"
    
    # Create a script to remove the API key
    cat > /tmp/remove-api-key.sh << 'EOF'
#!/bin/bash
# Remove API key from config.json if it exists
if [ -f backend/config.json ]; then
    # Remove the api_key line containing the exposed key
    sed -i '/"api_key":\s*"AIzaSyDespY3Ix8nhn-luPOXNQTLJlQyyGjx7uI"/d' backend/config.json
    # Also remove any api_key that's not empty (to be safe)
    sed -i 's/"api_key":\s*"[^"]*"/"api_key": ""/g' backend/config.json
fi
if [ -f config.json ]; then
    sed -i '/"api_key":\s*"AIzaSyDespY3Ix8nhn-luPOXNQTLJlQyyGjx7uI"/d' config.json
    sed -i 's/"api_key":\s*"[^"]*"/"api_key": ""/g' config.json
fi
git add backend/config.json config.json 2>/dev/null || true
EOF
    
    chmod +x /tmp/remove-api-key.sh
    
    # Remove hardcoded secret key from app.py
    cat > /tmp/remove-secret-key.sh << 'EOF'
#!/bin/bash
# Remove hardcoded secret key from app.py
if [ -f backend/app.py ]; then
    sed -i "s/app.config\['SECRET_KEY'\] = 'temperature-monitoring-graphql-2025'/app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())/g" backend/app.py
    git add backend/app.py
fi
EOF
    
    chmod +x /tmp/remove-secret-key.sh
    
    # Run filter-branch for config.json
    echo "Removing API key from config.json history..."
    git filter-branch --force --index-filter \
        'if [ -f backend/config.json ]; then
            sed -i "s/\"api_key\":\s*\"AIzaSyDespY3Ix8nhn-luPOXNQTLJlQyyGjx7uI\"/\"api_key\": \"\"/g" backend/config.json
            git add backend/config.json
        fi
        if [ -f config.json ]; then
            sed -i "s/\"api_key\":\s*\"AIzaSyDespY3Ix8nhn-luPOXNQTLJlQyyGjx7uI\"/\"api_key\": \"\"/g" config.json
            git add config.json
        fi' \
        --prune-empty --tag-name-filter cat -- --all
    
    # Run filter-branch for app.py secret key
    echo "Removing hardcoded secret key from app.py history..."
    git filter-branch --force --index-filter \
        'if [ -f backend/app.py ]; then
            sed -i "s/app.config\[.SECRET_KEY.\] = .temperature-monitoring-graphql-2025./app.config[\x27SECRET_KEY\x27] = os.environ.get(\x27FLASK_SECRET_KEY\x27, os.urandom(32).hex())/g" backend/app.py
            git add backend/app.py
        fi' \
        --prune-empty --tag-name-filter cat -- --all
    
    # Clean up backup refs
    echo "Cleaning up backup refs..."
    git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d 2>/dev/null || true
    
    # Expire reflog and garbage collect
    echo "Expiring reflog and running garbage collection..."
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive
    
    echo "✅ Secrets removed from history using git-filter-branch"
    
else
    echo "❌ Error: Neither git-filter-repo nor git-filter-branch found"
    echo ""
    echo "Install git-filter-repo (recommended):"
    echo "  pip install git-filter-repo"
    echo ""
    echo "Or install git-filter-branch (legacy):"
    echo "  sudo apt-get install git"
    echo ""
    exit 1
fi

echo ""
echo "✅ Done! Secrets have been removed from git history."
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Rotate your Gemini API key at: https://ai.google.dev/"
echo "2. Set environment variables:"
echo "   export FLASK_SECRET_KEY=\"\$(python3 -c 'import secrets; print(secrets.token_hex(32))')\""
echo "   export GEMINI_API_KEY=\"your-new-api-key\""
echo "   export ALLOWED_ORIGINS=\"http://localhost:5000,https://yourdomain.com\""
echo "3. Force push to remote (if working with remote repo):"
echo "   git push --force --all"
echo "   git push --force --tags"
echo "4. Inform your team to re-clone the repository"
echo "5. Verify secrets are gone: git log --all --full-history -- backend/config.json"

