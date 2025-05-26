from setuptools import setup, find_packages

APP = ['run.py']
APP_NAME = "MeetingRec"
VERSION = "1.0.4"

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'resources/meetingrec.icns',
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': f"{APP_NAME} {VERSION}",
        'CFBundleIdentifier': "com.meetingrec",
        'CFBundleVersion': VERSION,
        'CFBundleShortVersionString': VERSION,
        'NSMicrophoneUsageDescription': 'MeetingRec needs access to your microphone to record meeting audio.',
        'NSRequiresAquaSystemAppearance': False,
        'LSMinimumSystemVersion': '10.14',
        'LSUIElement': True,  # This makes it a menu bar app without dock icon
    },
    'packages': ['meetingrec'],
    'includes': [
        'rumps',
        'pynput',
        'numpy',
        'pyobjc-core',
        'pyobjc-framework-Cocoa',
        'pyobjc-framework-Quartz',
        'yaml',
        'openai',
        'requests',
        'wave',
        'PIL',
    ],
}

setup(
    name=APP_NAME,
    app=APP,
    version=VERSION,
    author="MeetingRec Team",
    description="AI-powered meeting recorder and transcription tool",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'rumps>=0.4.0',
        'pynput>=1.7.6',
        'numpy>=1.20.0',
        'pyobjc-core>=8.0',
        'pyobjc-framework-Cocoa>=8.0',
        'pyobjc-framework-Quartz>=8.0',
        'pyyaml>=6.0',
        'openai>=1.0.0',
        'requests>=2.28.0',
        'Pillow>=9.0.0',
        'lameenc>=1.0.0'
    ],
    package_data={
        'meetingrec': ['resources/*'],
    },
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)