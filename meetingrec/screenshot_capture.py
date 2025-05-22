import os
import sys
import time
import tempfile
import subprocess
import logging

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from meetingrec.config_manager import ConfigManager

# macOS-specific imports
from Cocoa import NSWorkspace
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    CGWindowListCreateImage,
    CGRectNull,
    kCGWindowImageDefault,
)
from Foundation import NSArray
from AppKit import NSImage, NSBitmapImageRep, NSPNGFileType
from PyObjCTools import AppHelper

logger = logging.getLogger("meetingrec.screenshot_capture")

class ScreenshotCapture:
    """Captures screenshots of active windows on macOS."""
    
    # List of common meeting applications to detect
    MEETING_APPS = {
        "zoom.us": "Zoom",
        "Microsoft Teams": "Teams",
        "meet.google.com": "Google Meet",
        "Webex": "Cisco Webex",
        "BlueJeans": "BlueJeans",
        "GoToMeeting": "GoToMeeting",
        "Discord": "Discord",
        "Slack": "Slack",
        "Teamviewer": "Teamviewer"
    }
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the screenshot capture with configuration.
        
        Args:
            config_manager: Configuration manager instance. If None, a new one is created.
        """
        self.config_manager = config_manager or ConfigManager()
        self.screenshot_config = self.config_manager.get_screenshot_config()
        
        self.output_dir = Path(self.config_manager.get_output_dir())
        self.format = self.screenshot_config.get("format", "png").lower()
        self.quality = self.screenshot_config.get("quality", 85)
        self.current_meeting_path = None
        self.screenshot_count = 0
        
        # Check if meeting app detection is enabled in config
        self.meeting_app_detection = self.config_manager.get_config().get(
            "meetingrec", {}).get("meeting_app_detection", {}).get("enabled", True)
    
    def set_meeting_path(self, meeting_path: str) -> None:
        """Set the current meeting path for organizing screenshots.
        
        Args:
            meeting_path: Path to the current meeting directory
        """
        self.current_meeting_path = Path(meeting_path)
        self.screenshot_count = 0
        
        # Ensure screenshots directory exists
        screenshots_dir = self.current_meeting_path / "screenshots"
        screenshots_dir.mkdir(exist_ok=True, parents=True)
    
    def get_active_window_info(self) -> Dict[str, Any]:
        """Get information about the currently active window.
        
        Returns:
            Dict containing window information
        """
        try:
            # Get the active application
            active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            app_name = active_app.localizedName()
            pid = active_app.processIdentifier()
            
            # Get window information
            window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
            
            # Find windows matching the active application's PID
            for window in window_list:
                if window.get('kCGWindowOwnerPID', 0) == pid:
                    window_name = window.get('kCGWindowName', '')
                    window_bounds = window.get('kCGWindowBounds', {})
                    return {
                        'success': True,
                        'app_name': app_name,
                        'window_name': window_name,
                        'pid': pid,
                        'bounds': window_bounds
                    }
            
            # If we didn't find a specific window, return just the app info
            return {
                'success': True,
                'app_name': app_name,
                'window_name': '',
                'pid': pid,
                'bounds': {}
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Failed to get active window info: {str(e)}"
            }
    
    def detect_meeting_apps(self) -> List[Dict[str, Any]]:
        """Detect running meeting applications.
        
        Returns:
            List of dictionaries containing meeting app information
        """
        try:
            meeting_apps = []
            
            # Get all running applications
            workspace = NSWorkspace.sharedWorkspace()
            running_apps = workspace.runningApplications()
            
            # Get all window information
            window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
            
            # Check each running application
            for app in running_apps:
                app_name = app.localizedName()
                app_bundle = app.bundleIdentifier()
                pid = app.processIdentifier()
                
                # Check if this app is a meeting app
                is_meeting_app = False
                matched_name = None
                
                # Check app name against our list of meeting apps
                for meeting_app_id, meeting_app_name in self.MEETING_APPS.items():
                    if (meeting_app_id.lower() in (app_name.lower() if app_name else "") or
                        meeting_app_id.lower() in (app_bundle.lower() if app_bundle else "")):
                        is_meeting_app = True
                        matched_name = meeting_app_name
                        break
                
                if is_meeting_app:
                    # Find windows belonging to this app
                    for window in window_list:
                        if window.get('kCGWindowOwnerPID', 0) == pid:
                            window_name = window.get('kCGWindowName', '')
                            window_bounds = window.get('kCGWindowBounds', {})
                            
                            meeting_app_info = {
                                'app_name': app_name,
                                'meeting_app_name': matched_name,
                                'window_name': window_name,
                                'pid': pid,
                                'bounds': window_bounds
                            }
                            
                            # Only add if it has valid bounds (i.e., it's a visible window)
                            if window_bounds:
                                meeting_apps.append(meeting_app_info)
            
            return meeting_apps
            
        except Exception as e:
            print(f"Error detecting meeting apps: {e}")
            return []
    
    def capture_active_window(self, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Capture a screenshot of the currently active window."""
        if not self.current_meeting_path:
            return {
                'success': False,
                'message': "No active meeting. Start recording first."
            }
        
        # Check for macOS screen recording permission
        if sys.platform == 'darwin':
            try:
                # This will trigger the permission prompt if needed
                test_capture = subprocess.run(
                    ['/usr/sbin/screencapture', '-x', '-c'],
                    capture_output=True, 
                    timeout=1
                )
            except (subprocess.SubprocessError, FileNotFoundError):
                # Just continue if this fails - it's just a permission check
                pass
        
        try:
            # Get current timestamp if not provided
            if timestamp is None:
                timestamp = time.time()
            
            time_str = datetime.fromtimestamp(timestamp).strftime("%H-%M-%S")
            formatted_count = f"{self.screenshot_count:05d}"
            filename = f"screenshot_{formatted_count}_{time_str}.{self.format}"
            filepath = self.current_meeting_path / "screenshots" / filename
            
            # Check for meeting apps if enabled
            if self.meeting_app_detection:
                meeting_apps = self.detect_meeting_apps()
                if meeting_apps:
                    # Pick the first meeting app window we found
                    meeting_app = meeting_apps[0]
                    result = self._capture_specific_window(meeting_app, filepath)
                    
                    if result.get('success', False):
                        # Increment counter for next screenshot
                        self.screenshot_count += 1
                        
                        # Add meeting app info to result
                        result.update({
                            'app_name': meeting_app.get('app_name', ''),
                            'window_name': meeting_app.get('window_name', ''),
                            'meeting_app': meeting_app.get('meeting_app_name', ''),
                            'timestamp': timestamp,
                            'time_str': time_str
                        })
                        
                        return result
            
            # Fallback to active window if no meeting app or meeting app detection disabled
            window_info = self.get_active_window_info()
            
            # Capture the screenshot
            if window_info.get('success', False):
                # Use a different approach depending on window info availability
                if window_info.get('bounds'):
                    # Capture specific window if we have bounds
                    result = self._capture_specific_window(window_info, filepath)
                else:
                    # Fall back to capturing the frontmost application
                    result = self._capture_frontmost_app(filepath)
                
                if result.get('success', False):
                    # Increment counter for next screenshot
                    self.screenshot_count += 1
                    
                    # Add window info to result
                    result.update({
                        'app_name': window_info.get('app_name', ''),
                        'window_name': window_info.get('window_name', ''),
                        'timestamp': timestamp,
                        'time_str': time_str
                    })
                
                return result
            else:
                return window_info
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Failed to capture screenshot: {str(e)}"
            }
    
    def _capture_specific_window(self, window_info: Dict[str, Any], filepath: Path) -> Dict[str, Any]:
        """Capture a specific window based on window info."""
        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Use the full path to screencapture
            screencapture_path = "/usr/sbin/screencapture"
            
            # Make sure file exists and is executable
            if not os.path.isfile(screencapture_path) or not os.access(screencapture_path, os.X_OK):
                logger.warning(f"screencapture utility not found or not executable at {screencapture_path}")
                return self._capture_screen_fallback(filepath)
            
            # Use -w to capture the frontmost window
            try:
                subprocess.run([screencapture_path, '-w', str(filepath)], 
                              check=True, capture_output=True, timeout=5)
                
                if filepath.exists() and filepath.stat().st_size > 0:
                    return {
                        'success': True,
                        'message': 'Screenshot captured',
                        'filepath': str(filepath),
                        'format': self.format
                    }
                else:
                    logger.warning("screencapture command executed but no file was created")
                    return self._capture_screen_fallback(filepath)
                    
            except subprocess.SubprocessError as e:
                logger.warning(f"screencapture command failed: {e}")
                return self._capture_screen_fallback(filepath)
                
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return {
                'success': False,
                'message': f"Failed to capture screenshot: {str(e)}"
            }
    
    def _capture_frontmost_app(self, filepath: Path) -> Dict[str, Any]:
        """Capture the frontmost application's window."""
        try:
            # Use screencapture utility to capture the frontmost window
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Use the FULL PATH to the macOS screencapture utility
            screencapture_path = "/usr/sbin/screencapture"
            
            # Check if the utility exists
            if not Path(screencapture_path).exists():
                # Try alternate locations
                alternate_paths = [
                    "/usr/bin/screencapture",
                    "/bin/screencapture"
                ]
                for path in alternate_paths:
                    if Path(path).exists():
                        screencapture_path = path
                        break
                else:
                    return {
                        'success': False,
                        'message': "Could not find screencapture utility on this system"
                    }
            
            # Run with full path
            subprocess.run([screencapture_path, '-w', '-o', '-x', temp_path], 
                          check=True, capture_output=True)
            
            # Check if the file was created and has content
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                # Move or convert the file as needed
                if self.format == 'png':
                    os.rename(temp_path, filepath)
                else:
                    # Convert using Pillow if not PNG
                    from PIL import Image
                    img = Image.open(temp_path)
                    img.save(filepath, quality=self.quality)
                    os.remove(temp_path)
                
                return {
                    'success': True,
                    'message': 'Screenshot captured',
                    'filepath': str(filepath),
                    'format': self.format
                }
            else:
                # If the temp file is empty, try the fallback method
                os.remove(temp_path)
                return self._capture_screen_fallback(filepath)
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Failed to capture frontmost app: {str(e)}"
            }
    
    def _capture_screen_fallback(self, filepath: Path) -> Dict[str, Any]:
        """Fallback method to capture the entire screen."""
        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Get the main screen
            rect = CGRectNull  # This will capture the entire screen
            
            # Import the required Quartz functions
            from Quartz import CGImageGetWidth, CGImageGetHeight
            
            # Capture the screen
            screenshot = CGWindowListCreateImage(
                rect,
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
                kCGWindowImageDefault
            )
            
            if screenshot is None:
                logger.warning("CGWindowListCreateImage returned None, trying direct PIL capture")
                return self._pil_screenshot_fallback(filepath)
            
            # Use Quartz functions to get width and height
            width = CGImageGetWidth(screenshot)
            height = CGImageGetHeight(screenshot)
            
            # Convert to NSImage
            ns_image = NSImage.alloc().initWithCGImage_size_(screenshot, (width, height))
            
            if not ns_image:
                logger.warning("Failed to create NSImage, trying direct PIL capture")
                return self._pil_screenshot_fallback(filepath)
            
            # Check if representations exist
            if not ns_image.representations() or len(ns_image.representations()) == 0:
                logger.warning("NSImage has no representations, trying direct PIL capture")
                return self._pil_screenshot_fallback(filepath)
            
            # Create NSArray with image representation
            rep_array = NSArray.arrayWithObject_(ns_image.representations()[0])
            
            if not rep_array:
                logger.warning("Failed to create NSArray, trying direct PIL capture")
                return self._pil_screenshot_fallback(filepath)
            
            # Get PNG representation
            ns_data = NSBitmapImageRep.representationOfImageRepsInArray_usingType_properties_(
                rep_array,
                NSPNGFileType,
                {}
            )
            
            if not ns_data:
                logger.warning("Failed to create PNG representation, trying direct PIL capture")
                return self._pil_screenshot_fallback(filepath)
            
            # Write to file
            success = ns_data.writeToFile_atomically_(str(filepath), False)
            
            if not success:
                logger.warning("writeToFile_atomically_ returned False, trying direct PIL capture")
                return self._pil_screenshot_fallback(filepath)
            
            return {
                'success': True,
                'message': 'Screenshot captured (fallback method)',
                'filepath': str(filepath),
                'format': self.format
            }
            
        except Exception as e:
            import traceback
            logger.error(f"Screenshot fallback error: {e}\n{traceback.format_exc()}")
            # Try one more fallback method
            return self._pil_screenshot_fallback(filepath)
        
    def _pil_screenshot_fallback(self, filepath: Path) -> Dict[str, Any]:
        """Ultimate fallback using PIL to capture the screen."""
        try:
            # Try using PIL/Pillow for screenshot
            import PIL.ImageGrab
            
            # Capture the whole screen
            img = PIL.ImageGrab.grab()
            
            # Save the image
            img.save(str(filepath))
            
            return {
                'success': True,
                'message': 'Screenshot captured (PIL fallback)',
                'filepath': str(filepath),
                'format': self.format
            }
        except Exception as e:
            import traceback
            logger.error(f"PIL screenshot fallback error: {e}\n{traceback.format_exc()}")
            return {
                'success': False,
                'message': f"Failed to capture screen with all methods: {str(e)}"
            }

if __name__ == "__main__":
    # Simple test code
    screenshot = ScreenshotCapture()
    
    # Create a test meeting directory
    test_dir = Path(tempfile.mkdtemp())
    screenshots_dir = test_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True, parents=True)
    
    screenshot.set_meeting_path(str(test_dir))
    
    # Check for meeting apps first
    meeting_apps = screenshot.detect_meeting_apps()
    if meeting_apps:
        print(f"Found meeting apps: {', '.join([app.get('meeting_app_name', '') for app in meeting_apps])}")
    
    print("Taking screenshot...")
    result = screenshot.capture_active_window()
    
    if result.get('success', False):
        print(f"Screenshot saved to: {result.get('filepath')}")
        print(f"Application: {result.get('app_name')}")
        if 'meeting_app' in result:
            print(f"Meeting app detected: {result.get('meeting_app')}")
        print(f"Window: {result.get('window_name')}")
    else:
        print(f"Failed: {result.get('message')}")
    
    print(f"Test files in: {test_dir}")