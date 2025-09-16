#!/bin/bash

# Build verification script for LocalRecall production artifacts
# Tests the built application without requiring installation

set -e

echo "🧪 Testing LocalRecall production build..."
echo "========================================"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_test() {
    echo -e "${BLUE}🔍 $1${NC}"
}

log_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_fail() {
    echo -e "${RED}❌ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if build exists
if [[ ! -d "dist" ]]; then
    log_fail "No dist directory found. Run 'npm run dist' first."
    exit 1
fi

# Test 1: Verify DMG exists
log_test "Checking for DMG installer..."
dmg_file=$(find dist/ -name "*.dmg" | head -1)
if [[ -n "$dmg_file" ]]; then
    log_pass "DMG found: $(basename "$dmg_file")"
    dmg_size=$(du -h "$dmg_file" | cut -f1)
    echo "    Size: $dmg_size"
else
    log_fail "No DMG file found"
fi

# Test 2: Verify app bundle exists
log_test "Checking for app bundle..."
app_bundle=$(find dist/ -name "*.app" | head -1)
if [[ -n "$app_bundle" ]]; then
    log_pass "App bundle found: $(basename "$app_bundle")"
    app_size=$(du -sh "$app_bundle" | cut -f1)
    echo "    Size: $app_size"
else
    log_fail "No app bundle found"
fi

# Test 3: Verify backend is bundled
log_test "Checking backend executable..."
if [[ -n "$app_bundle" ]]; then
    backend_path="$app_bundle/Contents/Resources/backend/localrecall-backend"
    if [[ -f "$backend_path" ]]; then
        log_pass "Backend executable found in app bundle"
        backend_size=$(du -h "$backend_path" | cut -f1)
        echo "    Size: $backend_size"
        
        # Check if executable is valid
        if file "$backend_path" | grep -q "executable"; then
            log_pass "Backend is a valid executable"
        else
            log_warning "Backend may not be a valid executable"
        fi
    else
        log_fail "Backend executable not found in app bundle"
    fi
fi

# Test 4: Verify frontend is bundled
log_test "Checking frontend assets..."
if [[ -n "$app_bundle" ]]; then
    frontend_path="$app_bundle/Contents/Resources/app/build"
    if [[ -d "$frontend_path" ]]; then
        log_pass "Frontend build directory found"
        
        # Check for index.html
        if [[ -f "$frontend_path/index.html" ]]; then
            log_pass "Frontend index.html found"
        else
            log_fail "Frontend index.html missing"
        fi
        
        # Check for static assets
        if [[ -d "$frontend_path/static" ]]; then
            log_pass "Frontend static assets found"
        else
            log_warning "Frontend static assets directory not found"
        fi
    else
        log_fail "Frontend build directory not found in app bundle"
    fi
fi

# Test 5: Check Electron main files
log_test "Checking Electron main files..."
if [[ -n "$app_bundle" ]]; then
    main_js="$app_bundle/Contents/Resources/electron/main.js"
    if [[ -f "$main_js" ]]; then
        log_pass "Electron main.js found"
        
        # Check if it references our model manager
        if grep -q "model-manager" "$main_js"; then
            log_pass "Model manager integration found"
        else
            log_warning "Model manager not referenced in main.js"
        fi
    else
        log_fail "Electron main.js not found"
    fi
fi

# Test 6: Verify entitlements
log_test "Checking macOS entitlements..."
if [[ -f "resources/entitlements.mac.plist" ]]; then
    log_pass "Entitlements file found"
    
    # Check for key entitlements
    if grep -q "com.apple.security.cs.allow-jit" resources/entitlements.mac.plist; then
        log_pass "JIT compilation entitlement found"
    else
        log_warning "JIT entitlement may be missing"
    fi
else
    log_fail "Entitlements file not found"
fi

# Test 7: Size analysis
log_test "Analyzing build sizes..."
if [[ -d "dist" ]]; then
    total_size=$(du -sh dist/ | cut -f1)
    echo "    Total dist size: $total_size"
    
    if [[ -n "$dmg_file" ]]; then
        dmg_size_bytes=$(du -b "$dmg_file" | cut -f1)
        if [[ $dmg_size_bytes -lt 500000000 ]]; then  # Less than 500MB
            log_pass "DMG size is reasonable for distribution"
        else
            log_warning "DMG size is quite large (>500MB)"
        fi
    fi
fi

echo ""
echo "📊 Build Test Summary"
echo "===================="

# Count tests
total_tests=7
echo "Tests completed: $total_tests"

echo ""
echo "🎯 Manual Testing Checklist:"
echo "  □ Mount the DMG and drag to Applications"
echo "  □ Launch LocalRecall from Applications"
echo "  □ Verify setup wizard appears on first run"
echo "  □ Test model auto-detection"
echo "  □ Complete setup and test document upload"
echo "  □ Test AI chat functionality"
echo "  □ Verify all features work without development dependencies"

echo ""
echo "✨ Build verification complete!"

if [[ -n "$dmg_file" ]]; then
    echo ""
    echo "🚀 Ready for distribution:"
    echo "   $dmg_file"
fi