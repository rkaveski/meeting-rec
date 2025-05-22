#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

from pathlib import Path

def build_app():
    """Build the macOS app bundle using py2app."""
    print("Building MeetingRec macOS Application...")
    
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
    
    print(f"Application bundle created at: {app_path}")
    return True

def code_sign_app():
    """Code sign the app (optional, requires Apple Developer account)."""
    print("Code signing is optional and requires an Apple Developer account.")
    should_sign = input("Do you want to code sign the app? (y/n): ").lower() == 'y'
    
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