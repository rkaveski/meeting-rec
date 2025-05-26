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
            print(f"Cleaning {dir_name} directory...")
            shutil.rmtree(dir_name)
    
    # Run py2app with better error handling
    try:
        print("Running py2app build...")
        result = subprocess.run([
            'python3', 'setup.py', 'py2app', '--packages=meetingrec'
        ], check=True, capture_output=True, text=True)
        
        print("py2app completed successfully")
        if result.stdout:
            print("Build output:", result.stdout[-500:])  # Show last 500 chars
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with exit code {e.returncode}")
        print(f"Error output: {e.stderr}")
        if e.stdout:
            print(f"Standard output: {e.stdout}")
        return False
    except Exception as e:
        print(f"Unexpected error during build: {e}")
        return False
    
    # Verify build results
    app_path = Path('dist/MeetingRec.app')
    if not app_path.exists():
        print("ERROR: Application bundle was not created")
        print("Contents of dist directory:")
        if Path('dist').exists():
            for item in Path('dist').iterdir():
                print(f"  {item}")
        else:
            print("  dist directory does not exist")
        return False
    
    # Verify the app bundle structure
    required_paths = [
        app_path / 'Contents',
        app_path / 'Contents' / 'MacOS',
        app_path / 'Contents' / 'Resources',
        app_path / 'Contents' / 'Info.plist'
    ]
    
    for required_path in required_paths:
        if not required_path.exists():
            print(f"ERROR: Missing required app bundle component: {required_path}")
            return False
    
    # Check if our version file made it into the bundle
    version_file = app_path / 'Contents' / 'Resources' / 'lib' / 'python3.11' / 'meetingrec' / 'version.py'
    if version_file.exists():
        print(f"✓ Version file found in app bundle")
    else:
        print(f"WARNING: Version file not found at expected location: {version_file}")
    
    print(f"✓ Application bundle v{version} created successfully at: {app_path}")
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
    try:
        print("=" * 50)
        print("MeetingRec Build Script")
        print("=" * 50)
        
        if build_app():
            code_sign_app()
            print("\n" + "=" * 50)
            print("✓ Build completed successfully!")
            print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print("✗ Build failed!")
            print("=" * 50)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nBuild interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error in build script: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)