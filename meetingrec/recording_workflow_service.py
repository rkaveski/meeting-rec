import logging
import threading

from pathlib import Path
from typing import Optional, Dict, Any, Callable

from meetingrec.system_audio_recorder import SystemAudioRecorder
from meetingrec.transcription_service import TranscriptionService
from meetingrec.markdown_exporter import MarkdownExporter
from meetingrec.screenshot_capture import ScreenshotCapture
from meetingrec.config_manager import ConfigManager
from meetingrec.error_manager import safe_execute

logger = logging.getLogger("meetingrec.recording_workflow")

class RecordingWorkflowService:
    """Orchestrates the complete recording workflow - Single Responsibility for workflow management"""
    
    def __init__(
        self, 
        config_manager: ConfigManager,
        notification_callback: Optional[Callable[[str, str, str], None]] = None
    ):
        """
        Initialize the recording workflow service
        
        Args:
            config_manager: Configuration manager instance
            notification_callback: Function to call for notifications (title, subtitle, message)
        """
        self.config_manager = config_manager
        self.notification_callback = notification_callback or self._default_notification
        
        # Initialize core services
        self.audio_recorder = SystemAudioRecorder(config_manager)
        self.transcription_service = TranscriptionService(config_manager)
        self.markdown_exporter = MarkdownExporter(config_manager=config_manager)
        self.screenshot_capture = ScreenshotCapture(config_manager)
        
        # Current recording state
        self.current_meeting_path: Optional[str] = None
        self.is_processing = False
        
    def _default_notification(self, title: str, subtitle: str, message: str):
        """Default notification handler - just log"""
        logger.info(f"Notification: {title} - {subtitle}: {message}")
    
    def _notify(self, title: str, subtitle: str, message: str = ""):
        """Send notification via callback"""
        try:
            self.notification_callback(title, subtitle, message)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    @safe_execute
    def start_recording(self) -> Dict[str, Any]:
        """Start the recording workflow"""
        if self.audio_recorder.is_currently_recording():
            return {"success": False, "message": "Recording already in progress"}
        
        # Start audio recording
        result = self.audio_recorder.start_recording()
        
        if result.get("success", False):
            self.current_meeting_path = result["meeting_path"]
            
            # Configure screenshot capture for this meeting
            self.screenshot_capture.set_meeting_path(self.current_meeting_path)
            
            self._notify("MeetingRec", "Recording Started", "System audio recording started")
            
            logger.info(f"Recording workflow started: {self.current_meeting_path}")
            
            return {
                "success": True,
                "meeting_path": self.current_meeting_path,
                "message": "Recording started successfully"
            }
        else:
            logger.error(f"Failed to start recording: {result.get('message')}")
            return result
    
    @safe_execute
    def stop_recording(self) -> Dict[str, Any]:
        """Stop recording and start post-processing workflow"""
        if not self.audio_recorder.is_currently_recording():
            return {"success": False, "message": "No recording in progress"}
        
        # Stop audio recording
        result = self.audio_recorder.stop_recording()
        
        if result.get("success", False):
            meeting_path = result.get("meeting_path")
            audio_path = result.get("audio_path")
            duration = result.get("duration", 0)
            
            self._notify(
                "MeetingRec", 
                "Recording Stopped", 
                f"Saved {duration:.1f}s recording"
            )
            
            # Start post-processing in background
            self._start_post_processing(meeting_path, audio_path)
            
            # Clear current meeting path
            self.current_meeting_path = None
            
            return {
                "success": True,
                "meeting_path": meeting_path,
                "audio_path": audio_path,
                "duration": duration,
                "message": "Recording stopped successfully"
            }
        else:
            logger.error(f"Failed to stop recording: {result.get('message')}")
            return result
    
    def _start_post_processing(self, meeting_path: str, audio_path: str):
        """Start post-processing workflow in background thread"""
        if not meeting_path or not audio_path:
            logger.error("Cannot start post-processing: missing paths")
            return
        
        def post_process():
            try:
                self.is_processing = True
                self._process_completed_recording(meeting_path, audio_path)
            finally:
                self.is_processing = False
        
        threading.Thread(target=post_process, daemon=True).start()
    
    def _process_completed_recording(self, meeting_path: str, audio_path: str):
        """Process completed recording: transcription + markdown generation"""
        meeting_path_obj = Path(meeting_path)
        audio_path_obj = Path(audio_path)
        
        try:
            # Start transcription if API key is configured
            api_key = self.config_manager.get_openai_api_key()
            if api_key:
                logger.info("Starting transcription process...")
                self._notify(
                    "MeetingRec",
                    "Processing Audio",
                    "Transcribing audio... This may take a few minutes."
                )
                
                transcription_result = self.transcription_service.transcribe_audio(
                    audio_path_obj,
                    meeting_path_obj
                )
                
                if transcription_result.get("success", False):
                    logger.info("Transcription completed successfully")
                    self._notify(
                        "MeetingRec",
                        "Transcription Complete",
                        "Audio transcription finished"
                    )
                else:
                    logger.warning(f"Transcription failed: {transcription_result.get('message')}")
                    self._notify(
                        "MeetingRec",
                        "Transcription Failed", 
                        transcription_result.get('message', 'Unknown error')
                    )
            else:
                logger.info("No OpenAI API key configured, skipping transcription")
            
            # Generate markdown report
            logger.info("Generating markdown report...")
            self._notify(
                "MeetingRec",
                "Generating Report",
                "Creating meeting summary..."
            )
            
            report_path = self.markdown_exporter.generate_report(meeting_path_obj)
            
            self._notify(
                "MeetingRec",
                "Report Ready",
                f"Meeting report created: {report_path.name}"
            )
            
            logger.info(f"Post-processing completed for meeting: {meeting_path_obj.name}")
            
        except Exception as e:
            logger.error(f"Error in post-processing: {e}")
            self._notify(
                "MeetingRec",
                "Processing Error",
                f"Error generating report: {str(e)}"
            )
    
    @safe_execute
    def capture_screenshot(self) -> Dict[str, Any]:
        """Capture screenshot for current meeting"""
        if not self.current_meeting_path:
            return {
                "success": False,
                "message": "No active meeting - start recording first"
            }
        
        # Ensure screenshot capture has the meeting path set
        if not self.screenshot_capture.current_meeting_path:
            self.screenshot_capture.set_meeting_path(self.current_meeting_path)
        
        result = self.screenshot_capture.capture_active_window()
        
        if result.get("success", False):
            self._notify(
                "MeetingRec", 
                "Screenshot Captured", 
                f"From: {result.get('app_name', 'Unknown app')}"
            )
        else:
            self._notify(
                "MeetingRec",
                "Screenshot Failed",
                result.get('message', 'Failed to capture screenshot')
            )
        
        return result
    
    def is_currently_recording(self) -> bool:
        """Check if recording is in progress"""
        return self.audio_recorder.is_currently_recording()
    
    def is_currently_processing(self) -> bool:
        """Check if post-processing is in progress"""
        return self.is_processing
    
    def get_current_meeting_path(self) -> Optional[str]:
        """Get current meeting path"""
        return self.current_meeting_path
    
    def cleanup_on_exit(self) -> bool:
        """Cleanup when application exits"""
        logger.info("RecordingWorkflowService cleanup started")
        
        try:
            # Stop recording if in progress
            if self.audio_recorder.is_currently_recording():
                logger.info("Stopping active recording during cleanup")
                self.audio_recorder.cleanup_on_exit()
            
            logger.info("RecordingWorkflowService cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"Error during RecordingWorkflowService cleanup: {e}")
            return False
    
    def check_system_status(self) -> Dict[str, Any]:
        """Check system status for all components"""
        audio_status = self.audio_recorder.check_system_status()
        
        # Add additional status checks
        status = {
            "audio_recording": audio_status,
            "openai_configured": bool(self.config_manager.get_openai_api_key()),
            "output_directory": self.config_manager.get_output_dir(),
            "overall_ready": not audio_status["issues"]
        }
        
        return status