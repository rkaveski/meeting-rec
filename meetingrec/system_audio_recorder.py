import os
import subprocess
import logging
import time

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from meetingrec.config_manager import ConfigManager
from meetingrec.error_manager import safe_execute, RecordingError

logger = logging.getLogger("meetingrec.system_audio_recorder")


class RecordingState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RecordingSession:
    session_id: str
    start_time: datetime
    output_path: Path
    state: RecordingState
    duration: Optional[float] = None
    file_size: Optional[int] = None


class SystemAudioError(RecordingError):
    """System audio recording specific errors"""
    pass


class FFmpegNotAvailableError(SystemAudioError):
    """FFmpeg is not installed or not accessible"""
    pass


class FFmpegDependencyManager:
    """Handle FFmpeg installation and verification with improved PATH handling"""

    @staticmethod
    def _get_enhanced_env() -> Dict[str, str]:
        """Get enhanced environment with common binary paths"""
        env = os.environ.copy()

        # Common paths where FFmpeg might be installed
        additional_paths = [
            "/usr/local/bin",           # Homebrew default
            "/opt/homebrew/bin",        # Homebrew on Apple Silicon
            "/usr/bin",                 # System binaries
            "/bin",                     # Core binaries
            "/usr/local/sbin",          # Additional system binaries
            "/opt/local/bin",           # MacPorts
        ]

        # Get current PATH and add additional paths
        current_path = env.get("PATH", "")
        path_list = current_path.split(":") if current_path else []

        # Add paths that aren't already included
        for path in additional_paths:
            if path not in path_list:
                path_list.insert(0, path)  # Prepend to give priority

        env["PATH"] = ":".join(path_list)

        logger.debug(f"Enhanced PATH: {env['PATH']}")
        return env

    @staticmethod
    def _find_ffmpeg_executable() -> Optional[str]:
        """Find FFmpeg executable in common locations"""
        # Try with 'which' command first
        try:
            result = subprocess.run(
                ["which", "ffmpeg"],
                capture_output=True,
                timeout=5,
                text=True,
                env=FFmpegDependencyManager._get_enhanced_env()
            )
            if result.returncode == 0 and result.stdout.strip():
                ffmpeg_path = result.stdout.strip()
                logger.info(f"Found FFmpeg via 'which': {ffmpeg_path}")
                return ffmpeg_path
        except Exception as e:
            logger.debug(f"'which ffmpeg' failed: {e}")

        # Try common installation paths directly
        common_paths = [
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",
            "/usr/bin/ffmpeg",
            "/bin/ffmpeg",
            "/opt/local/bin/ffmpeg"
        ]

        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                logger.info(f"Found FFmpeg at: {path}")
                return path

        logger.warning("FFmpeg not found in any common locations")
        return None

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Check if FFmpeg is installed and accessible with improved detection"""
        ffmpeg_path = FFmpegDependencyManager._find_ffmpeg_executable()

        if not ffmpeg_path:
            logger.error("FFmpeg executable not found")
            return False

        # Quick path existence check first
        if not os.path.isfile(ffmpeg_path) or not os.access(ffmpeg_path, os.X_OK):
            logger.error(f"FFmpeg path not executable: {ffmpeg_path}")
            return False

        try:
            # Test FFmpeg with shorter timeout and better error handling
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5,  # Reduced timeout to prevent hanging
                text=True,
                env=FFmpegDependencyManager._get_enhanced_env(),
                stdin=subprocess.DEVNULL  # Prevent hanging on input
            )

            success = result.returncode == 0

            if success:
                logger.info(f"FFmpeg is available at: {ffmpeg_path}")
                # Log first line of version output for debugging
                first_line = result.stdout.split(
                    '\n')[0] if result.stdout else "Unknown version"
                logger.info(f"FFmpeg version: {first_line}")
            else:
                logger.warning(
                    f"FFmpeg test failed. Return code: {result.returncode}")
                if result.stderr:
                    # Limit error log size
                    logger.warning(f"FFmpeg stderr: {result.stderr[:200]}...")

            return success

        except subprocess.TimeoutExpired:
            logger.warning(
                f"FFmpeg version check timed out for: {ffmpeg_path} - may still be functional")
            # Don't fail completely on timeout - FFmpeg might still work for recording
            return True  # Assume it works if executable exists
        except FileNotFoundError:
            logger.error(f"FFmpeg executable not found at: {ffmpeg_path}")
            return False
        except Exception as e:
            logger.warning(
                f"Error testing FFmpeg at {ffmpeg_path}: {e} - assuming functional")
            # Be more permissive with validation errors
            return True

    @staticmethod
    def get_ffmpeg_version() -> Optional[str]:
        """Get FFmpeg version string with improved error handling"""
        ffmpeg_path = FFmpegDependencyManager._find_ffmpeg_executable()
        if not ffmpeg_path:
            return None

        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                timeout=3,  # Even shorter timeout for version check
                text=True,
                env=FFmpegDependencyManager._get_enhanced_env(),
                stdin=subprocess.DEVNULL
            )
            if result.returncode == 0:
                first_line = result.stdout.split('\n')[0]
                return first_line
            return "FFmpeg (version check failed)"
        except subprocess.TimeoutExpired:
            logger.debug("FFmpeg version check timed out")
            return "FFmpeg (version timeout)"
        except Exception as e:
            logger.debug(f"Error getting FFmpeg version: {e}")
            return "FFmpeg (available)"

    @staticmethod
    def check_avfoundation_support() -> bool:
        """Check if FFmpeg supports AVFoundation (macOS audio capture)"""
        ffmpeg_path = FFmpegDependencyManager._find_ffmpeg_executable()
        if not ffmpeg_path:
            return False

        try:
            result = subprocess.run(
                [ffmpeg_path, "-f", "avfoundation",
                    "-list_devices", "true", "-i", ""],
                capture_output=True,
                timeout=15,  # Increased timeout for device listing
                text=True,
                env=FFmpegDependencyManager._get_enhanced_env()
            )
            # FFmpeg returns non-zero when listing devices, but that's expected
            has_avfoundation = "AVFoundation" in result.stderr

            if has_avfoundation:
                logger.info("FFmpeg supports AVFoundation")
            else:
                logger.error("FFmpeg does not support AVFoundation")
                # Log first 500 chars
                logger.debug(f"FFmpeg stderr: {result.stderr[:500]}...")

            return has_avfoundation
        except Exception as e:
            logger.error(f"Error checking AVFoundation support: {e}")
            return False

    @staticmethod
    def get_installation_instructions() -> str:
        """Return installation instructions for FFmpeg"""
        return """FFmpeg is required for system audio recording.

Install via Homebrew:
    brew install ffmpeg

Or download from: https://ffmpeg.org/download.html

After installation, restart MeetingRec.

If FFmpeg is already installed, ensure it's in your PATH:
    echo $PATH
    which ffmpeg"""


class SystemAudioRecorder:
    """Single, reliable system audio recorder using FFmpeg"""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the system audio recorder"""
        self.config_manager = config_manager or ConfigManager()
        self.audio_config = self.config_manager.get_audio_config()
        self.output_dir = Path(self.config_manager.get_output_dir())

        # Recording state
        self.is_recording = False
        self.current_session: Optional[RecordingSession] = None
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.ffmpeg_path: Optional[str] = None

        # Verify FFmpeg availability
        self._verify_dependencies()

        logger.info("SystemAudioRecorder initialized")

    def _verify_dependencies(self) -> None:
        """Verify that FFmpeg is available and supports AVFoundation"""
        if not FFmpegDependencyManager.is_ffmpeg_available():
            raise FFmpegNotAvailableError(
                "FFmpeg is not installed or not accessible")

        # Store the FFmpeg path for later use
        self.ffmpeg_path = FFmpegDependencyManager._find_ffmpeg_executable()

        if not FFmpegDependencyManager.check_avfoundation_support():
            raise FFmpegNotAvailableError(
                "FFmpeg does not support AVFoundation (required for macOS audio capture)")

        version = FFmpegDependencyManager.get_ffmpeg_version()
        logger.info(f"FFmpeg verified and ready: {version}")

    def _get_codec(self) -> str:
        """Get FFmpeg codec based on output format"""
        format_map = {
            "mp3": "libmp3lame",
            "wav": "pcm_s16le",
            "m4a": "aac"
        }
        return format_map.get(self.audio_config.get("format", "mp3"), "libmp3lame")

    def _get_channel_count(self) -> int:
        """Get channel count from config"""
        channel_setting = self.audio_config.get("channel", "stereo")
        return 2 if channel_setting.lower() == "stereo" else 1

    def _get_bitrate(self) -> str:
        """Get audio bitrate from config"""
        return self.audio_config.get("bitrate", "128k")

    def _build_ffmpeg_command(self, output_path: Path) -> List[str]:
        """Build FFmpeg command based on configuration"""
        codec = self._get_codec()

        cmd = [
            self.ffmpeg_path,  # Use the verified FFmpeg path
            "-f", "avfoundation",
            "-i", ":1",  # System audio device
            "-acodec", codec,
            "-ar", str(self.audio_config.get("sample_rate", 44100)),
            "-ac", str(self._get_channel_count()),
        ]

        # Add bitrate for compressed formats
        if codec in ["libmp3lame", "aac"]:
            cmd.extend(["-ab", self._get_bitrate()])

        # Add quality settings
        if codec == "libmp3lame":
            cmd.extend(["-q:a", "2"])  # High quality MP3

        cmd.extend([
            "-y",  # Overwrite output file
            str(output_path)
        ])

        return cmd

    def _create_meeting_directory(self) -> Path:
        """Create a directory for the current meeting's data"""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        meeting_dir = self.output_dir / f"{timestamp}-meeting"

        try:
            meeting_dir.mkdir(parents=True, exist_ok=True)
            (meeting_dir / "screenshots").mkdir(exist_ok=True)
            return meeting_dir
        except Exception as e:
            raise SystemAudioError(
                f"Failed to create meeting directory: {str(e)}",
                {"path": str(meeting_dir)}
            ) from e

    @safe_execute
    def start_recording(self) -> Dict[str, Any]:
        """Start system audio recording using FFmpeg"""
        if self.is_recording:
            return {"success": False, "message": "Recording already in progress"}

        try:
            # Create meeting directory
            meeting_path = self._create_meeting_directory()

            # Create output file path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_format = self.audio_config.get("format", "mp3")
            output_file = meeting_path / f"meeting_audio.{audio_format}"

            # Build FFmpeg command
            cmd = self._build_ffmpeg_command(output_file)
            logger.info(f"Starting FFmpeg with command: {' '.join(cmd)}")

            # Start FFmpeg process with enhanced environment
            self.ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                env=FFmpegDependencyManager._get_enhanced_env()
            )

            # Give FFmpeg a moment to start
            time.sleep(1.0)  # Increased wait time

            # Check if process started successfully
            if self.ffmpeg_process.poll() is not None:
                # Process already terminated
                stdout, stderr = self.ffmpeg_process.communicate()
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"FFmpeg failed to start: {error_msg}")
                raise SystemAudioError(f"FFmpeg failed to start: {error_msg}")

            self.is_recording = True
            self.current_session = RecordingSession(
                session_id=timestamp,
                start_time=datetime.now(),
                output_path=output_file,
                state=RecordingState.RECORDING
            )

            # Save meeting info
            with open(meeting_path / "meeting_info.txt", "w") as f:
                f.write(
                    f"Recording started at: {self.current_session.start_time.isoformat()}\n")
                f.write(f"Audio format: {audio_format}\n")
                f.write(
                    f"Sample rate: {self.audio_config.get('sample_rate', 44100)}\n")
                f.write(f"Channels: {self._get_channel_count()}\n")
                f.write(f"FFmpeg path: {self.ffmpeg_path}\n")

            logger.info(f"Recording started: {output_file}")

            return {
                "success": True,
                "message": "System audio recording started",
                "meeting_path": str(meeting_path),
                "audio_path": str(output_file),
                "timestamp": self.current_session.start_time.isoformat()
            }

        except Exception as e:
            self.is_recording = False
            self.current_session = None
            if self.ffmpeg_process:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process = None
            raise SystemAudioError(
                f"Failed to start recording: {str(e)}") from e

    @safe_execute
    def stop_recording(self) -> Dict[str, Any]:
        """Stop FFmpeg process and return audio file path"""
        if not self.is_recording or not self.ffmpeg_process:
            return {"success": False, "message": "No recording in progress"}

        try:
            logger.info("Stopping FFmpeg recording...")

            # Send quit command to FFmpeg
            self.ffmpeg_process.stdin.write(b'q')
            self.ffmpeg_process.stdin.flush()

            # Wait for process to complete with timeout
            try:
                stdout, stderr = self.ffmpeg_process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "FFmpeg did not respond to quit command, terminating...")
                self.ffmpeg_process.terminate()
                stdout, stderr = self.ffmpeg_process.communicate(timeout=5)

            # Calculate duration
            end_time = datetime.now()
            duration = (
                end_time - self.current_session.start_time).total_seconds()

            # Get file info
            output_path = self.current_session.output_path
            file_size = 0

            if output_path.exists():
                file_size = output_path.stat().st_size
                logger.info(
                    f"Recording saved: {output_path} ({file_size} bytes, {duration:.1f}s)")
            else:
                logger.error("Recording file was not created")
                return {
                    "success": False,
                    "message": "Recording file was not created"
                }

            # Update session info
            self.current_session.duration = duration
            self.current_session.file_size = file_size
            self.current_session.state = RecordingState.IDLE

            # Update meeting info file
            meeting_path = output_path.parent
            with open(meeting_path / "meeting_info.txt", "a") as f:
                f.write(f"Recording stopped at: {end_time.isoformat()}\n")
                f.write(f"Duration: {duration:.2f} seconds\n")
                f.write(f"File size: {file_size} bytes\n")

            # Clean up
            result_path = output_path
            self.is_recording = False
            self.current_session = None
            self.ffmpeg_process = None

            return {
                "success": True,
                "message": "Recording stopped successfully",
                "audio_path": str(result_path),
                "meeting_path": str(meeting_path),
                "duration": duration,
                "file_size": file_size,
                "timestamp_end": end_time.isoformat()
            }

        except Exception as e:
            self.is_recording = False
            self.current_session = None
            if self.ffmpeg_process:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process = None

            raise SystemAudioError(
                f"Failed to stop recording: {str(e)}") from e

    def is_currently_recording(self) -> bool:
        """Check if recording is in progress"""
        return self.is_recording

    def get_current_session(self) -> Optional[RecordingSession]:
        """Get current recording session info"""
        return self.current_session

    def cleanup_on_exit(self) -> bool:
        """Cleanup when app exits - ensure FFmpeg process is terminated"""
        if self.ffmpeg_process and self.is_recording:
            try:
                logger.info("Cleanup: Terminating FFmpeg process...")
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait(timeout=5)
                self.is_recording = False
                self.current_session = None
                return True
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                return False
        return True

    def check_system_status(self) -> Dict[str, Any]:
        """Check system status for audio recording"""
        status = {
            "ffmpeg_available": FFmpegDependencyManager.is_ffmpeg_available(),
            "avfoundation_support": False,
            "ffmpeg_version": None,
            "ffmpeg_path": None,
            "issues": []
        }

        if status["ffmpeg_available"]:
            status["ffmpeg_path"] = FFmpegDependencyManager._find_ffmpeg_executable()
            status["ffmpeg_version"] = FFmpegDependencyManager.get_ffmpeg_version()
            status["avfoundation_support"] = FFmpegDependencyManager.check_avfoundation_support()

            if not status["avfoundation_support"]:
                status["issues"].append("FFmpeg does not support AVFoundation")
        else:
            status["issues"].append(
                "FFmpeg is not installed or not accessible")

        return status


if __name__ == "__main__":
    # Test the recorder
    try:
        recorder = SystemAudioRecorder()
        print("SystemAudioRecorder initialized successfully")

        status = recorder.check_system_status()
        print(f"System status: {status}")

    except Exception as e:
        print(f"Error: {e}")
