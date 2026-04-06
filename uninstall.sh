#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/share/kiro-cli-history"
BIN_DIR="$HOME/.local/bin"

echo "Uninstalling kiro-cli-history..."

rm -f "$BIN_DIR/kiro-cli-history"
rm -rf "$INSTALL_DIR"

echo "Done. kiro-cli-history has been removed."
