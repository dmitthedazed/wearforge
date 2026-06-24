#!/usr/bin/env bash

# WearForge Runner Script
# Automatically configures the Python virtual environment and launches the tool.

set -e

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color
BLUE='\033[0;34m'

echo -e "${BLUE}=== WearForge CLI Bootstrap ===${NC}"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

# Check for ADB
if ! command -v adb &> /dev/null; then
    echo -e "${YELLOW}Warning: Android Debug Bridge (adb) was not found in your PATH.${NC}"
    echo -e "${YELLOW}Please install adb (e.g., 'sudo apt install adb' or 'sudo pacman -S android-tools')${NC}"
    echo -e "${YELLOW}without it, the debloater won't be able to communicate with your watch.${NC}"
    echo ""
fi

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if venv exists, if not, create it
if [ ! -d ".venv" ]; then
    echo -e "Creating Python virtual environment in .venv..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install requirements
echo -e "Checking/installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Run the python app
echo -e "${GREEN}Dependencies OK. Starting WearForge...${NC}"
echo ""
python3 wearforge.py "$@"
