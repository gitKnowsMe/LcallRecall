#!/bin/bash

# Complete production build script for LocalRecall
# Creates a production-ready macOS DMG with bundled backend

set -e  # Exit on any error

echo "🚀 Building LocalRecall for production..."
echo "=========================================="

# Check if we're in the right directory
if [[ ! -f "package.json" ]]; then
    echo "❌ Error: Must run from LocalRecall root directory"
    exit 1
fi

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Step 1: Clean previous builds
log_step "Cleaning previous builds..."
rm -rf dist/ build/ || true
rm -rf app/build/ app/.next/ || true
log_success "Build directories cleaned"

# Step 2: Check dependencies
log_step "Checking dependencies..."

# Check Node.js dependencies
if [[ ! -d "node_modules" ]]; then
    log_warning "Node.js dependencies not found, installing..."
    npm install
fi

# Check frontend dependencies
if [[ ! -d "app/node_modules" ]]; then
    log_warning "Frontend dependencies not found, installing..."
    cd app && npm install && cd ..
fi

# Check Python backend dependencies
if ! python3 -c "import fastapi, llama_cpp, faiss" 2>/dev/null; then
    log_error "Backend Python dependencies not found"
    echo "Please install backend dependencies:"
    echo "  cd backend && pip install -r requirements.txt"
    exit 1
fi

log_success "All dependencies verified"

# Step 3: Build frontend
log_step "Building React frontend..."
cd app
npm run build
if [[ ! -d "build" ]]; then
    log_error "Frontend build failed - no build directory created"
    exit 1
fi
cd ..
log_success "Frontend built successfully"

# Step 4: Build backend
log_step "Bundling Python backend with PyInstaller..."
if [[ ! -x "scripts/build-backend.sh" ]]; then
    chmod +x scripts/build-backend.sh
fi
./scripts/build-backend.sh

if [[ ! -f "build/backend/localrecall-backend" ]]; then
    log_error "Backend bundling failed - executable not found"
    exit 1
fi

backend_size=$(du -h build/backend/localrecall-backend | cut -f1)
log_success "Backend bundled successfully (${backend_size})"

# Step 5: Prepare resources
log_step "Preparing build resources..."

# Create resources directory if needed
mkdir -p resources

# Check for required resources
if [[ ! -f "resources/icon.png" ]]; then
    log_warning "Icon file not found, using placeholder"
    # Create a simple colored square as placeholder
    echo "Creating placeholder icon..."
    # This would normally be a proper icon file
    touch resources/icon.png
fi

if [[ ! -f "resources/icon.icns" ]]; then
    log_warning "ICNS icon not found for macOS"
    # In production, convert PNG to ICNS with iconutil
    # For now, copy the PNG as placeholder
    if [[ -f "resources/icon.png" ]]; then
        cp resources/icon.png resources/icon.icns
    fi
fi

if [[ ! -f "resources/dmg-background.png" ]]; then
    log_warning "DMG background not found, will use default"
    # Create a simple placeholder
    touch resources/dmg-background.png
fi

log_success "Resources prepared"

# Step 6: Build Electron app
log_step "Building Electron application..."

# Verify build configuration
if ! npm run electron:dist --dry-run 2>/dev/null; then
    log_warning "Dry run not supported, proceeding with actual build..."
fi

# Build the application
npm run electron:dist

if [[ ! -d "dist" ]]; then
    log_error "Electron build failed - no dist directory created"
    exit 1
fi

log_success "Electron application built"

# Step 7: Verify build output
log_step "Verifying build output..."

# Find the DMG file
dmg_file=$(find dist/ -name "*.dmg" | head -1)
if [[ -n "$dmg_file" ]]; then
    dmg_size=$(du -h "$dmg_file" | cut -f1)
    log_success "DMG created: $dmg_file ($dmg_size)"
else
    log_warning "No DMG file found, checking for other artifacts..."
    ls -la dist/
fi

# Check for app bundle
app_bundle=$(find dist/ -name "*.app" | head -1)
if [[ -n "$app_bundle" ]]; then
    app_size=$(du -sh "$app_bundle" | cut -f1)
    log_success "App bundle created: $app_bundle ($app_size)"
fi

# Step 8: Build summary
log_step "Build Summary"
echo "=========================================="

total_size=$(du -sh dist/ | cut -f1)
echo "📦 Total build size: $total_size"

if [[ -n "$dmg_file" ]]; then
    echo "💿 DMG installer: $(basename "$dmg_file")"
fi

if [[ -n "$app_bundle" ]]; then
    echo "📱 App bundle: $(basename "$app_bundle")"
fi

echo ""
echo "🎯 Production build artifacts:"
ls -la dist/ | grep -E '\.(dmg|app)' || echo "  No primary artifacts found"

echo ""
echo "🔧 Build configuration:"
echo "  • Backend: Bundled Python executable ($(du -h build/backend/localrecall-backend | cut -f1))"
echo "  • Frontend: Static React build"
echo "  • Platform: macOS (x64 + ARM64)"
echo "  • Code signing: Configured but not signed"
echo ""

log_success "Production build complete!"
echo ""
echo "📍 Next Steps:"
echo "  1. Test the DMG installer on a clean macOS system"
echo "  2. Verify model detection and setup wizard work"
echo "  3. Test all core features (document upload, AI chat, etc.)"
echo "  4. For distribution: Set up Apple Developer certificates"
echo ""
echo "🎉 LocalRecall is ready for production deployment!"