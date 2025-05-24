#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import re

from pathlib import Path

def get_version_from_setup():
    """Extract version from setup.py"""
    setup_path = Path("setup.py")
    try:
        with open(setup_path, 'r') as f:
            content = f.read()
            match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error extracting version: {e}")
    return "0.0.0"  # Fallback version

def inject_version():
    """Inject version from setup.py into meetingrec/version.py"""
    version = get_version_from_setup()
    print(f"Injecting version: {version}")
    
    # Read template
    template_path = Path("meetingrec/version.py.template")
    version_path = Path("meetingrec/version.py")
    
    if not template_path.exists():
        # If template doesn't exist, create a simple version file
        with open(version_path, 'w') as f:
            f.write('"""Version information for MeetingRec."""\n')
            f.write(f'VERSION = "{version}"\n')
    else:
        # Use template
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Replace placeholder with actual version
        content = template.replace("__VERSION__", version)
        
        # Write to version.py
        with open(version_path, 'w') as f:
            f.write(content)
    
    print(f"Version file created at: {version_path}")
    return version

def build_app():
    """Build the macOS app bundle using py2app."""
    print("Building MeetingRec macOS Application...")
    
    # Inject version before building
    version = inject_version()
    
    # Clean previous builds
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # Run py2app
    subprocess.run([
        'python3', 'setup.py', 'py2app', '--packages=meetingrec'
    ], check=True)
    
    # Check if build was successful
    app_path = Path('dist/MeetingRec.app')
    if not app_path.exists():
        print("Failed to build application bundle.")
        return False
    
    print(f"Application bundle v{version} created at: {app_path}")
    return True

def code_sign_app():
    """Code sign the app (optional, requires Apple Developer account)."""
    print("Code signing is optional and requires an Apple Developer account.")
    print("Skipping code signing.")
    should_sign = False
    
    if should_sign:
        identity = input("Enter your Developer ID Application identity: ")
        app_path = Path('dist/MeetingRec.app')
        
        # Sign the app
        subprocess.run([
            'codesign', 
            '--force', 
            '--deep', 
            '--sign', 
            identity, 
            str(app_path)
        ], check=True)
        
        print("Application signed successfully.")
    else:
        print("Skipping code signing.")

if __name__ == "__main__":
    if build_app():
        code_sign_app()
        print("Build completed successfully.")
    else:
        print("Build failed.")
        sys.exit(1)