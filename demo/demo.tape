# SPDX-License-Identifier: CC0-1.0
# SPDX-FileCopyrightText: 2026 Max Mehl <https://mehl.mx>
#
# VHS tape for recording meta/demo.gif. Install VHS (https://github.com/charmbracelet/vhs)
# and run from the repo root:
#
#   uv run python demo/generate_demo_data.py
#   vhs demo/demo.tape
#
# This regenerates meta/demo.gif in place.

Output meta/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 750
Set Padding 10
Set TypingSpeed 80ms

Hide
Type "KIRO_DEMO_DIR=demo/data uv run kiro-cli-history"
Enter
Sleep 1500ms
Show

Sleep 1000ms

# Search for a specific past conversation (search input is focused by default)
# and let the background fuzzy search settle
Type "aurora"
Sleep 1500ms

# Clear the search, back to the full list
Escape
Sleep 1000ms

# Move into the session list and step down through a few sessions
Tab
Sleep 600ms
Down
Sleep 600ms
Down
Sleep 600ms
Down
Sleep 1000ms

# Switch into the conversation preview pane for the selected session
Tab
Sleep 2500ms

Escape
