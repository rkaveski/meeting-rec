import os
import rumps
import subprocess
import sys
import logging
import threading
import queue
from functools import wraps

from meetingrec.recording_workflow_service import RecordingWorkflowService
from meetingrec.config_manager import ConfigManager
from meetingrec.error_manager import error_manager, safe_execute, safe_notification
from meetingrec.menu_manager import MenuManager
from meetingrec.system_audio_recorder import FFmpegDependencyManager

logger = logging.getLogger("meetingrec.menu_bar")

# Thread-safe UI operations queue
ui_operation_queue = queue.Queue()


def safe_main_thread(func):
    """Decorator to ensure function runs on main thread with fallback for older rumps versions"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if hasattr(rumps, 'main_thread'):
            # Use rumps.main_thread if available
            @rumps.main_thread
            def run_on_main():
                return func(*args, **kwargs)
            return run_on_main()
        else:
            # Fallback: Check if we're already on main thread
            if threading.current_thread() is threading.main_thread():
                return func(*args, **kwargs)
            else:
                # Queue the operation and use a different approach
                result = [None]
                exception = [None]

                def run_and_store():
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        exception[0] = e

                # For UI operations, we'll need to handle this differently
                # Log a warning and try to run anyway
                logger.warning(f"Running {func.__name__} from non-main thread")
                run_and_store()

                if exception[0]:
                    raise exception[0]
                return result[0]
    return wrapper


class MeetingRecApp(rumps.App):
    """Main menu bar application - focused only on UI and menu management"""

    def __init__(self):
        # Initialize the rumps.App
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, 'resources', 'icon.png')

        super(MeetingRecApp, self).__init__(
            name="MeetingRec",
            title="",
            icon=icon_path,
            template=True,
            quit_button="Quit"
        )

        # Initialize configuration
        self.config_manager = ConfigManager()

        # Initialize recording workflow service with notification callback
        self.recording_service = None
        try:
            self.recording_service = RecordingWorkflowService(
                self.config_manager,
                notification_callback=safe_notification
            )
            logger.info("Recording service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize recording service: {e}")
            # Don't crash the app - run in degraded mode
            self._show_initialization_error(str(e))
            # Continue initialization to allow config access

        # Create menu callbacks
        callbacks = {
            "start_recording": self.start_recording,
            "stop_recording": self.stop_recording,
            "capture_screenshot": self.capture_screenshot,
            "show_meetings": self.show_meetings,
            "open_config": self.open_config,
            "check_system": self.check_system
        }

        # Initialize menu manager
        self.menu_manager = MenuManager(self, callbacks)

        # Run startup procedures
        self._run_startup_checks()

        logger.info("MeetingRecApp initialization complete")

    def _show_initialization_error(self, error_message: str):
        """Show initialization error to user"""
        if "FFmpeg" in error_message:
            self._show_ffmpeg_installation_dialog()
        else:
            safe_notification(
                "MeetingRec",
                "Initialization Error",
                f"Failed to start: {error_message}"
            )

    def _show_ffmpeg_installation_dialog(self):
        """Show FFmpeg installation instructions with improved error handling"""
        try:
            instructions = FFmpegDependencyManager.get_installation_instructions()

            safe_notification(
                "MeetingRec",
                "FFmpeg Required",
                "FFmpeg is required for system audio recording."
            )

            logger.error(f"FFmpeg installation required:\n{instructions}")

            # Use safe_main_thread wrapper with error handling
            @safe_main_thread
            def show_alert_on_main_thread():
                try:
                    rumps.alert(
                        title="FFmpeg Required",
                        message=instructions,
                        ok="OK"
                    )
                except Exception as e:
                    logger.error(f"Error showing alert dialog: {e}")
                    # Fallback: print to console for debugging
                    print(f"FFmpeg Required:\n{instructions}")

            # Call the main thread function
            show_alert_on_main_thread()
        except Exception as e:
            logger.error(f"Error in FFmpeg dialog: {e}")
            # Minimal fallback notification
            safe_notification(
                "MeetingRec",
                "Setup Required",
                "Please install FFmpeg for audio recording."
            )

    def _run_startup_checks(self):
        """Run startup checks and show guidance if needed"""
        if not self.recording_service:
            logger.warning(
                "Recording service not available - running in degraded mode")
            self._show_degraded_mode_guidance()
            return

        try:
            # Check system status
            status = self.recording_service.check_system_status()

            if not status["overall_ready"]:
                audio_issues = status["audio_recording"]["issues"]
                if audio_issues:
                    logger.warning(f"Audio system issues: {audio_issues}")

            # Check API key configuration
            if not status["openai_configured"]:
                self._show_first_run_guidance()
        except Exception as e:
            logger.error(f"Error during startup checks: {e}")
            # Continue anyway - don't let startup checks crash the app

    def _show_first_run_guidance(self):
        """Show first-run guidance for API key setup"""
        safe_notification(
            "MeetingRec",
            "Welcome to MeetingRec",
            "Please configure your OpenAI API key for transcription."
        )

        def delayed_open_config():
            import time
            time.sleep(1.5)
            self.open_config(None)

        threading.Thread(target=delayed_open_config, daemon=True).start()

    def _show_degraded_mode_guidance(self):
        """Show guidance when running in degraded mode"""
        safe_notification(
            "MeetingRec",
            "Limited Mode",
            "Some features unavailable. Check configuration."
        )

    @safe_execute
    def start_recording(self, _):
        """Start recording workflow"""
        if not self.recording_service:
            safe_notification("MeetingRec", "Service Unavailable",
                              "Recording service not available")
            return

        result = self.recording_service.start_recording()

        if result.get("success", False):
            # Update menu state
            self.menu_manager.set_menu_state("start_recording", False)
            self.menu_manager.set_menu_state("stop_recording", True)
        # Error notification already handled by the service

    @safe_execute
    def stop_recording(self, _):
        """Stop recording workflow"""
        if not self.recording_service:
            safe_notification("MeetingRec", "Service Unavailable",
                              "Recording service not available")
            return

        result = self.recording_service.stop_recording()

        if result.get("success", False):
            # Update menu state
            self.menu_manager.set_menu_state("start_recording", True)
            self.menu_manager.set_menu_state("stop_recording", False)
        # Error notification already handled by the service

    @safe_execute
    def capture_screenshot(self, _):
        """Capture screenshot for current meeting"""
        if not self.recording_service:
            safe_notification("MeetingRec", "Service Unavailable",
                              "Recording service not available")
            return

        # Service handles the screenshot capture and notifications
        self.recording_service.capture_screenshot()

    @safe_execute
    def open_config(self, _):
        """Open configuration file in text editor"""
        try:
            self.config_manager.open_config_in_editor()
            safe_notification(
                "MeetingRec",
                "Config Opened",
                "Configuration file opened in text editor. Restart after changes."
            )
        except Exception as e:
            logger.error(f"Failed to open config file: {e}")
            safe_notification(
                "MeetingRec",
                "Config Error",
                f"Could not open config file: {e}"
            )

    @safe_execute
    def check_system(self, _):
        """Check and display system status"""
        if not self.recording_service:
            safe_notification("MeetingRec", "Service Unavailable",
                              "Recording service not available")
            return

        status = self.recording_service.check_system_status()

        if status["overall_ready"]:
            ffmpeg_version = status["audio_recording"].get(
                "ffmpeg_version", "OK")
            safe_notification(
                "MeetingRec",
                "System Check",
                f"All systems ready. FFmpeg: {ffmpeg_version}"
            )
        else:
            issues = status["audio_recording"]["issues"]
            issues_text = "; ".join(issues) if issues else "Unknown issues"
            safe_notification(
                "MeetingRec",
                "System Issues",
                f"Issues found: {issues_text}"
            )

    @safe_execute
    def show_meetings(self, _):
        """Open meetings folder in Finder"""
        meetings_dir = self.config_manager.get_output_dir()
        subprocess.run(["open", meetings_dir])

        safe_notification(
            "MeetingRec",
            "Meetings Folder",
            "Opened in Finder"
        )

    def quit_application(self):
        """Handle application quit - delegate cleanup to service"""
        logger.info("Application quitting...")

        if self.recording_service:
            self.recording_service.cleanup_on_exit()

        logger.info("Application quit complete")
        return True


if __name__ == "__main__":
    try:
        MeetingRecApp().run()
    except Exception as e:
        error_info = error_manager.capture_exception("Application startup")

        # Use safe main thread for alert
        @safe_main_thread
        def show_error_alert():
            try:
                rumps.alert(
                    title="Fatal Error",
                    message=f"MeetingRec failed to start:\n\n{error_info.get('message', 'Unknown error')}",
                    ok="Quit"
                )
            except Exception as alert_error:
                logger.error(f"Failed to show error alert: {alert_error}")
                print(
                    f"FATAL ERROR: {error_info.get('message', 'Unknown error')}")

        show_error_alert()
        sys.exit(1)
