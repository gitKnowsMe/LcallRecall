#!/bin/bash

# LocalRecall Production Release Script
# Creates GitHub release with automated DMG distribution

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_step() {
    echo -e "${BLUE}📍 $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_info() {
    echo -e "${PURPLE}ℹ️  $1${NC}"
}

# Parse command line arguments
VERSION_TYPE=${1:-"patch"}
PRERELEASE=${2:-"false"}

if [[ "$VERSION_TYPE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # Direct version number provided
    VERSION="$VERSION_TYPE"
    VERSION_TYPE="manual"
else
    # Version type provided (patch, minor, major)
    if [[ ! "$VERSION_TYPE" =~ ^(patch|minor|major)$ ]]; then
        echo "Usage: $0 [patch|minor|major|x.y.z] [prerelease]"
        echo ""
        echo "Examples:"
        echo "  $0 patch           # 1.0.0 → 1.0.1"
        echo "  $0 minor           # 1.0.0 → 1.1.0"
        echo "  $0 major           # 1.0.0 → 2.0.0"
        echo "  $0 1.2.3           # Set specific version"
        echo "  $0 patch true      # Create pre-release"
        exit 1
    fi
fi

echo "🚀 LocalRecall Production Release"
echo "=================================="
log_info "Release type: $VERSION_TYPE"
log_info "Pre-release: $PRERELEASE"
echo ""

# Check prerequisites
log_step "Checking prerequisites..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    log_error "Not in a git repository"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    log_error "Uncommitted changes detected. Please commit or stash changes first."
    exit 1
fi

# Check if GitHub CLI is available
if ! command -v gh &> /dev/null; then
    log_error "GitHub CLI (gh) is required but not installed"
    echo "Install with: brew install gh"
    exit 1
fi

# Check if we're authenticated with GitHub
if ! gh auth status > /dev/null 2>&1; then
    log_error "Not authenticated with GitHub CLI"
    echo "Run: gh auth login"
    exit 1
fi

log_success "Prerequisites checked"

# Update version
log_step "Updating version..."

CURRENT_VERSION=$(node -p "require('./package.json').version")
log_info "Current version: $CURRENT_VERSION"

if [[ "$VERSION_TYPE" == "manual" ]]; then
    # Set specific version
    npm version "$VERSION" --no-git-tag-version
    NEW_VERSION="$VERSION"
else
    # Use npm version bump
    NEW_VERSION=$(npm version "$VERSION_TYPE" --no-git-tag-version | sed 's/^v//')
fi

log_success "Version updated to: $NEW_VERSION"

# Build production DMG
log_step "Building production DMG..."
npm run dist

# Verify build artifacts
log_step "Verifying build artifacts..."
if [[ ! -d "dist" ]]; then
    log_error "Build failed - no dist directory"
    exit 1
fi

DMG_FILE=$(find dist/ -name "*.dmg" | head -1)
if [[ -z "$DMG_FILE" ]]; then
    log_error "Build failed - no DMG file found"
    exit 1
fi

DMG_SIZE=$(du -h "$DMG_FILE" | cut -f1)
log_success "DMG built: $(basename "$DMG_FILE") ($DMG_SIZE)"

# Commit version change and create tag
log_step "Creating git tag..."
git add package.json
git commit -m "chore: release version $NEW_VERSION

🚀 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"

git tag "v$NEW_VERSION"
git push origin HEAD
git push origin "v$NEW_VERSION"

log_success "Git tag v$NEW_VERSION created and pushed"

# Create GitHub release
log_step "Creating GitHub release..."

RELEASE_NOTES="## LocalRecall v$NEW_VERSION

🎉 **Professional desktop RAG application with local AI**

### 📥 Installation
1. Download \`LocalRecall-$NEW_VERSION-arm64.dmg\` below
2. Open the DMG and drag LocalRecall to Applications
3. Launch LocalRecall and follow the setup wizard

### 🔧 Requirements
- macOS 11.0+ (Big Sur or later)
- Apple Silicon Mac (M1/M2/M3)
- 2GB+ available storage
- Phi-2 GGUF model (auto-detected or guided setup)

### 🚀 Features
- **Private & Local**: No data leaves your device
- **AI-Powered**: Chat with your documents using Phi-2
- **Smart Processing**: Advanced PDF document understanding
- **Fast Search**: Vector-based semantic search
- **Easy Setup**: Professional setup wizard

---

**Note**: This release includes download tracking for product improvements and built-in auto-update system."

PRERELEASE_FLAG=""
if [[ "$PRERELEASE" == "true" ]]; then
    PRERELEASE_FLAG="--prerelease"
fi

gh release create "v$NEW_VERSION" \
    --title "LocalRecall v$NEW_VERSION" \
    --notes "$RELEASE_NOTES" \
    $PRERELEASE_FLAG \
    dist/*.dmg \
    dist/*.dmg.blockmap \
    dist/latest-mac.yml

RELEASE_URL="https://github.com/$(gh repo view --json owner,name -q '.owner.login + "/" + .name')/releases/tag/v$NEW_VERSION"

log_success "GitHub release created"

# Release summary
echo ""
echo "🎉 Release Summary"
echo "=================="
echo "📱 Version: v$NEW_VERSION"
echo "📦 DMG Size: $DMG_SIZE"
echo "🔗 Release URL: $RELEASE_URL"
echo "📥 Download URL: ${RELEASE_URL/\/tag\//\/download\/}/$(basename "$DMG_FILE")"
echo ""

if [[ "$PRERELEASE" == "true" ]]; then
    log_warning "This is a pre-release - users will need to opt-in to see it"
else
    log_success "Public release - available to all users immediately"
fi

echo ""
log_success "LocalRecall v$NEW_VERSION released successfully!"
echo ""
echo "📍 Next Steps:"
echo "  1. Test the DMG download from GitHub releases"
echo "  2. Update your Vercel site to fetch the new version"
echo "  3. Monitor download analytics and user feedback"
echo "  4. Consider announcing the release on social media"
echo ""
echo "🌐 Share your release:"
echo "  Twitter: \"🚀 LocalRecall v$NEW_VERSION is out! Private desktop AI for your documents. Download: $RELEASE_URL\""
echo ""