#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('🚀 Building LocalRecall Desktop App...\n');

// Check if required directories exist
const requiredDirs = ['app', 'backend', 'electron'];
for (const dir of requiredDirs) {
  if (!fs.existsSync(path.join(__dirname, '..', dir))) {
    console.error(`❌ Required directory missing: ${dir}`);
    process.exit(1);
  }
}

try {
  // 1. Install frontend dependencies
  console.log('📦 Installing frontend dependencies...');
  execSync('npm install', { cwd: path.join(__dirname, '..', 'app'), stdio: 'inherit' });

  // 2. Build frontend
  console.log('🏗️  Building frontend...');
  execSync('npm run build', { cwd: path.join(__dirname, '..', 'app'), stdio: 'inherit' });

  // 3. Install backend dependencies
  console.log('🐍 Installing backend dependencies...');
  try {
    execSync('pip install -r requirements.txt', { 
      cwd: path.join(__dirname, '..', 'backend'), 
      stdio: 'inherit' 
    });
  } catch (error) {
    console.warn('⚠️  Backend dependencies installation failed. Make sure Python and pip are available.');
  }

  // 4. Run backend tests
  console.log('🧪 Running backend tests...');
  try {
    execSync('python -m pytest tests/ -v', { 
      cwd: path.join(__dirname, '..', 'backend'), 
      stdio: 'inherit' 
    });
    console.log('✅ All tests passed!');
  } catch (error) {
    console.warn('⚠️  Some tests failed. Build continuing...');
  }

  // 5. Package Electron app
  console.log('📱 Packaging Electron app...');
  execSync('npm run electron:pack', { stdio: 'inherit' });

  console.log('\n✅ Build completed successfully!');
  console.log('\nNext steps:');
  console.log('  • Run: npm run electron:dist  (to create distributable)');
  console.log('  • Or: npm run electron       (to test the built app)');

} catch (error) {
  console.error('\n❌ Build failed:', error.message);
  process.exit(1);
}