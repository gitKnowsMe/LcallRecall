# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Hidden imports for all dependencies
hidden_imports = [
    'llama_cpp',
    'llama_cpp._utils',
    'llama_cpp.llama_cpp',
    'faiss',
    'sentence_transformers',
    'sentence_transformers.models',
    'sentence_transformers.util',
    'transformers',
    'torch',
    'spacy',
    'spacy.lang.en',
    'PyMuPDF',
    'fitz',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'aiosqlite',
    'bcrypt',
    'jose',
    'jose.jwt',
    'jose.jws',
    'passlib',
    'passlib.handlers.bcrypt',
    'uvicorn',
    'uvicorn.lifespan.on',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'fastapi',
    'fastapi.security',
    'pydantic',
    'starlette',
    'starlette.applications',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.routing',
    'starlette.responses',
    'multipart',
    'python_multipart',
    'email_validator'
]

# Find llama-cpp shared libraries
import site
import glob

llama_libs = []
for site_dir in site.getsitepackages():
    # Look for llama shared libraries in multiple locations
    lib_patterns = [
        os.path.join(site_dir, 'llama_cpp', 'lib', '*.dylib'),
        os.path.join(site_dir, 'llama_cpp', 'lib', '*.so*'),
        os.path.join(site_dir, 'lib', '*.dylib'),
        os.path.join(site_dir, 'lib', '*llama*'),
        os.path.join(site_dir, 'llama_cpp', '*.dylib'),
        os.path.join(site_dir, 'llama_cpp', '*.so*'),
    ]
    for pattern in lib_patterns:
        libs = glob.glob(pattern)
        for lib in libs:
            if os.path.isfile(lib) and 'llama' in os.path.basename(lib):
                # Copy to both locations for compatibility
                llama_libs.append((lib, '.'))
                llama_libs.append((lib, 'llama_cpp'))
                llama_libs.append((lib, 'llama_cpp/lib'))

# Add llama-cpp libraries to binaries
binaries = llama_libs
print(f"Found llama libraries: {[lib[0] for lib in llama_libs]}")

# Data files to include
datas = [
    ('app', 'app'),
]

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='localrecall-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
