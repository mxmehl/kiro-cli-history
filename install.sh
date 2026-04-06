#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/share/kiro-cli-history"
BIN_DIR="$HOME/.local/bin"

echo "kiro-cli-history installer"
echo "======================"
echo ""

# Check dependencies
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is required but not found."
    echo "Install it via: brew install python3"
    exit 1
fi

# Check textual
if ! python3 -c "import textual" 2>/dev/null; then
    echo "Installing textual (TUI framework)..."
    pip3 install textual --quiet
fi

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Copy files
echo "Installing to $INSTALL_DIR..."
cp "$(dirname "$0")/kiro_history.py" "$INSTALL_DIR/kiro_history.py"

# Create wrapper script
cat > "$BIN_DIR/kiro-cli-history" << 'EOF'
#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.expanduser("~/.local/share/kiro-cli-history"))
from kiro_history import main
main()
EOF
chmod +x "$BIN_DIR/kiro-cli-history"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "NOTE: $BIN_DIR is not in your PATH."
    echo "Add this to your ~/.zshrc or ~/.bashrc:"
    echo ""
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

echo ""
echo "Installed! Run: kiro-cli-history"
echo ""
echo "To uninstall: bash $(dirname "$0")/uninstall.sh"
