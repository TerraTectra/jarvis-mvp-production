#!/bin/bash
# Setup script for local CI environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Setting up Jarvis MVP CI environment...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed. Please install Python 3.8+ and try again.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} is installed${NC}"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip is required but not installed. Please install pip and try again.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ pip is installed${NC}"

# Install development dependencies
echo -e "\n${YELLOW}📦 Installing development dependencies...${NC}
pip3 install --upgrade pip
pip3 install -r requirements-dev.txt

# Install pre-commit hooks
echo -e "\n${YELLOW}🔧 Setting up pre-commit hooks...${NC}
pre-commit install

# Create logs directory
mkdir -p ci/logs

# Set up environment variables
echo -e "\n${YELLOW}⚙️  Setting up environment variables...${NC}"
if [ ! -f ".env" ]; then
    echo "# CI Configuration" > .env
    echo "CI_TELEGRAM_NOTIFY=false" >> .env
    echo "TELEGRAM_CHAT_ID=your_chat_id" >> .env
    echo "TELEGRAM_BOT_TOKEN=your_bot_token" >> .env
    echo -e "${YELLOW}⚠️  Created .env file. Please update it with your configuration.${NC}
"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo -e "\n${YELLOW}⚠️  Docker is not installed. Some CI features may not work.${NC}"
    echo -e "   Please install Docker from https://docs.docker.com/get-docker/"
else
    echo -e "\n${GREEN}✓ Docker is installed${NC}
    Docker version: $(docker --version)
    
    # Test Docker daemon
    if docker info &> /dev/null; then
        echo -e "${GREEN}✓ Docker daemon is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker daemon is not running. Please start Docker and try again.${NC}"
    fi
fi

# Summary
echo -e "\n${GREEN}✅ Setup complete!${NC}"
echo -e "\nNext steps:"
echo -e "1. Update the .env file with your configuration"
echo -e "2. Run 'make check' to verify everything is working"
echo -e "3. Commit your changes: git add . && git commit -m 'chore: set up CI system'"
echo -e "\nHappy coding! 🚀\n"
