#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const htmlPath = path.join(__dirname, '..', 'app', 'build', 'index.html');

console.log('Fixing frontend asset paths for Electron...');

// Read the HTML file
let html = fs.readFileSync(htmlPath, 'utf8');

// Replace absolute paths with relative paths
html = html.replace(/href="\/_next\//g, 'href="./_next/');
html = html.replace(/src="\/_next\//g, 'src="./_next/');

// Fix all other patterns that might reference /_next/
html = html.replace(/"\/_next\//g, '"./_next/');
html = html.replace(/'\/_next\//g, "'./_next/");

// Write back the modified HTML
fs.writeFileSync(htmlPath, html);

console.log('✅ Frontend paths fixed for Electron');