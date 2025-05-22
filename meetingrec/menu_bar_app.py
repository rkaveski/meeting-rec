import os
import rumps
import threading
import subprocess
import sys
import logging
from pathlib import Path

from meetingrec.audio_recorder import AudioRecorder
from meetingrec.markdown_exporter import MarkdownExporter
from meetingrec.screenshot_capture import ScreenshotCapture
from meetingrec.config_manager import ConfigManager
from meetingrec.error_manager import error_manager, safe_execute, safe_notification
from meetingrec.menu_manager import MenuManager

# Get logger
logger = logging.getLogger("meetingrec.menu_bar")

class MeetingRecApp(rumps.App):
    def __init__(self):
        # Initialize the rumps.App with minimal config
        script_dir = os.path.dirname(os.path.abspath(__file__))  # Gets the directory of menu_bar_app.py
        icon_path = os.path.join(script_dir, 'resources', 'icon.png')

        super(MeetingRecApp, self).__init__(
            name="MeetingRec",
            title="",  # Keep title empty for icon-only display
            icon=icon_path, 
            template=True,
            quit_button="Quit"
        )
        
        # Initialize core components
        self.config_manager = ConfigManager()
        self.audio_recorder = AudioRecorder(self.config_manager)
        self.screenshot_capture = ScreenshotCapture(self.config_manager)
        
        # Get markdown configuration
        markdown_config = self.config_manager.get_markdown_config()

        # Initialize the MarkdownExporter with configuration
        self.markdown_exporter = MarkdownExporter(
            config_manager=self.config_manager,
            max_image_width=markdown_config.get("max_image_width", 1200),
            jpeg_quality=markdown_config.get("jpeg_quality", 85),
            transcript_wait_seconds=markdown_config.get("transcript_wait_seconds", 180)
        )

        # Track current meeting
        self.current_meeting_path = None
        
        # Create callbacks dictionary
        callbacks = {
            "start_recording": self.start_recording,
            "stop_recording": self.stop_recording,
            "capture_screenshot": self.capture_screenshot,
            "show_meetings": self.show_meetings,
            "open_config": self.open_config,
            "check_system": self.check_system
        }
        
        # Initialize menu manager with callbacks
        self.menu_manager = MenuManager(self, callbacks)
        
        # Run startup checks
        self._run_preflight_checks()
        self._check_first_run()
        
        logger.info("MeetingRecApp initialization complete")
    
    def _run_preflight_checks(self):
        """Run dependency and permission checks on startup."""
        # Since we're using lameenc instead of ffmpeg, we don't need dependency checks
        # Just check for permissions if needed
        permission_issues = error_manager.check_permissions()
        
        if permission_issues:
            safe_notification(
                "MeetingRec", 
                "Permission Check",
                f"Found {len(permission_issues)} permission issue(s). Check app permissions."
            )

    def _check_first_run(self):
        """Check if this is the first run and show setup guidance."""
        # Check if API key is configured
        api_key = self.config_manager.get_openai_api_key()
        if not api_key:
            # Show first-run notification
            safe_notification(
                "MeetingRec",
                "Welcome to MeetingRec",
                "Please configure your OpenAI API key in the config file."
            )
            
            # After a short delay, open the config
            def delayed_open_config():
                import time
                time.sleep(1)
                self.open_config(None)
                
            threading.Thread(target=delayed_open_config, daemon=True).start()

    @safe_execute
    def start_recording(self, _):
        logger.info("Start recording requested")
        if self.audio_recorder.is_currently_recording():
            safe_notification("MeetingRec", "Already Recording", "Recording is already in progress")
            return
            
        # Start recording
        result = self.audio_recorder.start_recording()
        
        if result.get("success", False):
            self.current_meeting_path = result["meeting_path"]
            
            # Set the meeting path in the screenshot capture
            self.screenshot_capture.set_meeting_path(self.current_meeting_path)
            
            # Update menu state
            self.menu_manager.set_menu_state("start_recording", False)
            self.menu_manager.set_menu_state("stop_recording", True)
            
            safe_notification("MeetingRec", "Recording Started", "")
        else:
            # Error is already handled by the safe_execute decorator
            pass

    @safe_execute
    def stop_recording(self, _):
        logger.info("Stop recording requested")
        if not self.audio_recorder.is_currently_recording():
            safe_notification("MeetingRec", "Not Recording", "No recording is in progress")
            return
            
        # Stop recording
        result = self.audio_recorder.stop_recording()
        
        if result.get("success", False):
            # Update menu state
            self.menu_manager.set_menu_state("start_recording", True)
            self.menu_manager.set_menu_state("stop_recording", False)
            
            meeting_path = result.get("meeting_path", "")
            safe_notification("MeetingRec", "Recording Stopped", f"Saved to: {meeting_path}")
            
            # Generate markdown report automatically
            self._generate_markdown_for_meeting_path(meeting_path)
        else:
            # Error is already handled by the safe_execute decorator
            pass

    def _generate_markdown_for_meeting_path(self, meeting_path):
        """Generate markdown for the meeting that just ended."""
        if not meeting_path:
            logger.error("Cannot generate markdown: No meeting path provided")
            return
        
        # Convert string path to Path object if needed
        if isinstance(meeting_path, str):
            meeting_path = Path(meeting_path)
        
        logger.info(f"Automatically generating markdown for meeting: {meeting_path.name}")
        
        # Show notification that we're generating the report
        safe_notification(
            "MeetingRec",
            "Generating Report",
            f"Creating markdown report for: {meeting_path.name}"
        )
        
        try:
            # Generate the markdown report
            report_path = self.markdown_exporter.generate_report(meeting_path)
            
            logger.info(f"Markdown report generated successfully: {report_path}")
            
            safe_notification(
                "MeetingRec",
                "Report Ready",
                f"Report created and saved to: {report_path.name}"
            )
            
            # Optionally open the report
            # subprocess.run(["open", str(report_path)])
        except Exception as e:
            logger.error(f"Error generating markdown for {meeting_path.name}: {e}")
            safe_notification(
                "MeetingRec",
                "Report Generation Failed",
                f"Error: {str(e)}"
            )

    @safe_execute
    def capture_screenshot(self, _):
        logger.info("Screenshot capture requested")
        if not self.current_meeting_path:
            safe_notification(
                "MeetingRec", 
                "No Active Meeting", 
                "Start recording first to capture screenshots"
            )
            return
            
        logger.info(f"Capturing screenshot for meeting: {self.current_meeting_path}")
        
        # Check if the screenshot capture has the meeting path set
        if not self.screenshot_capture.current_meeting_path:
            logger.error("Screenshot capture meeting path not set!")
            # Try to set it again
            self.screenshot_capture.set_meeting_path(self.current_meeting_path)
        
        result = self.screenshot_capture.capture_active_window()
        
        logger.info(f"Screenshot result: {result}")
        
        if result.get("success", False):
            safe_notification(
                "MeetingRec", 
                "Screenshot Captured", 
                f"From: {result.get('app_name', 'Unknown app')}"
            )
        else:
            logger.error(f"Screenshot failed: {result.get('message', 'Unknown error')}")
            safe_notification(
                "MeetingRec",
                "Screenshot Failed",
                result.get('message', 'Failed to capture screenshot')
            )

    @safe_execute
    def open_config(self, _):
        """Open the configuration file in the default editor."""
        # Open the configuration file
        self.config_manager.open_config_in_editor()
        
        # Log the action with detailed information for developers
        logger.info("Configuration file opened - changes require application restart to take effect")
        
        # Use non-blocking notification to inform the user about restart requirement
        safe_notification(
            "MeetingRec", 
            "Config Opened",
            "If you make changes to the configuration, please restart the app for them to take effect."
        )

    @safe_execute
    def check_system(self, _):
        """Check system status and show notification."""
        # We've removed dependency on external tools, so just show success
        rumps.notification(
            "MeetingRec",
            "System Check",
            "All systems ready. No external dependencies required."
        )

    @safe_execute
    def show_meetings(self, _):
        """Open the meetings folder in Finder."""
        meetings_dir = self.config_manager.get_output_dir()
        logger.info(f"Opening meetings directory: {meetings_dir}")
        
        # Open the folder in Finder using the 'open' command
        subprocess.run(["open", meetings_dir])
        
        safe_notification(
            "MeetingRec",
            "Meetings Folder",
            "Opened meetings folder in Finder"
        )

    def quit_application(self):
        """Handle application quit event and perform cleanup before exit."""
        logger.info("Application quitting - performing cleanup...")
        
        # Stop recording if in progress
        if hasattr(self, 'audio_recorder') and self.audio_recorder.is_currently_recording():
            logger.info("Stopping active recording before quit")
            try:
                self.audio_recorder.stop_recording()
            except Exception as e:
                logger.error(f"Error stopping recording during quit: {e}")
        
        logger.info("Application cleanup complete")
        return True

if __name__ == "__main__":
    # Set up exception handling for the main thread
    try:
        MeetingRecApp().run()
    except Exception as e:
        # Get error info
        error_info = error_manager.capture_exception("Application startup")
        
        # Show fatal error dialog
        rumps.alert(
            title="Fatal Error",
            message=f"MeetingRec encountered a fatal error and needs to close:\n\n{error_info.get('message', 'Unknown error')}",
            ok="Quit"
        )
        
        sys.exit(1)