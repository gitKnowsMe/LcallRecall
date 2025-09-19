#!/bin/bash

echo "Installing LocalRecall..."

# Copy app to Applications
cp -R "dist/mac-arm64/LocalRecall.app" "/Applications/"

# Remove quarantine
xattr -rd com.apple.quarantine "/Applications/LocalRecall.app" 2>/dev/null || true

echo "✅ LocalRecall installed successfully!"
echo "You can now launch it from Applications or Spotlight."