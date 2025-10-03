#!/bin/bash
# aMonitoringHub Setup Script
# This script helps set up the development environment

set -e  # Exit on error

echo "🚀 aMonitoringHub Setup Script"
echo "================================"
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists. Skipping creation."
else
    echo "📝 Creating .env file from template..."
    cp .env.template .env

    # Generate a secure Flask secret key
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || openssl rand -hex 32)

    # Update .env with generated secret
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|your-secret-key-here-generate-with-python-secrets|$SECRET_KEY|g" .env
    else
        # Linux
        sed -i "s|your-secret-key-here-generate-with-python-secrets|$SECRET_KEY|g" .env
    fi

    echo "✅ .env file created with secure secret key"
    echo "⚠️  You still need to add your GEMINI_API_KEY to .env"
fi

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    echo "📁 Creating logs directory..."
    mkdir -p logs
    touch logs/backend.log
    echo "✅ Logs directory created"
fi

# Check for Python virtual environment
if [ ! -d "backend/venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    cd backend
    python3 -m venv venv
    echo "✅ Virtual environment created"
    cd ..
else
    echo "✅ Virtual environment already exists"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
source backend/venv/bin/activate
pip install -q --upgrade pip
pip install -q -r backend/requirements.txt
echo "✅ Dependencies installed"

# Check database
if [ ! -f "backend/monitoringhub.db" ]; then
    echo "🗄️  Database will be created on first run"
else
    echo "✅ Database already exists"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Edit .env and add your GEMINI_API_KEY"
echo "  2. Run the application:"
echo "     ./scripts/app.sh"
echo ""
echo "🔧 For development, set LOG_LEVEL=DEBUG in .env"
echo "🔒 For production, ensure all secrets are set via environment variables"
echo ""
echo "📖 See CODE_REVIEW_FIXES.md for detailed setup instructions"
