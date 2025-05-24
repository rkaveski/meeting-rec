import os
import yaml
import hashlib
import subprocess

from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages application configuration through YAML files."""

    DEFAULT_CONFIG = {
        "meetingrec": {
            "output_dir": str(Path.home() / "MeetingRec" / "meetings"),
            "audio": {
                "format": "mp3",
                "sample_rate": 44100,
                "channel": "mono",
                "bitrate": "96k",
                "quality": "medium"
            },
            "screenshot": {
                "format": "jpg",
                "quality": 85
            },
            "markdown": {
                "max_image_width": 1200,
                "jpeg_quality": 85,
                "transcript_wait_seconds": 1800,
            },
            "meeting_app_detection": {
                "enabled": True
            },
            "ai": {
                "openai_api_key": "",
                "model": "gpt-4o",
                "temperature": 0.2,
                "max_tokens": 2048,
                "whisper_model": "whisper-1"
            }
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize ConfigManager with an optional path to the config file.

        Args:
            config_path: Path to the configuration file. If None, uses the default
                         location in the user's home directory.
        """
        if config_path is None:
            self.config_dir = Path.home() / ".meetingrec"
            self.config_path = self.config_dir / "config.yaml"
        else:
            self.config_path = Path(config_path)
            self.config_dir = self.config_path.parent

        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from the YAML file, with fallback to defaults."""
        if not self.config_path.exists():
            self._create_default_config()

        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)

            if not config:
                return self.DEFAULT_CONFIG

            return self._merge_with_defaults(config)
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG

    def _create_default_config(self) -> None:
        """Create a default configuration file with documentation."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, 'w') as f:
            f.write("# MeetingRec Configuration File\n")
            f.write(
                "# This file controls all aspects of the MeetingRec application\n\n")

            f.write("meetingrec:\n")
            f.write("  # Directory where meeting recordings are saved\n")
            f.write(
                f"  output_dir: {self.DEFAULT_CONFIG['meetingrec']['output_dir']}\n\n")

            f.write("  # System audio recording settings (using FFmpeg)\n")
            f.write("  audio:\n")
            f.write("    # Output audio format (mp3, wav, m4a)\n")
            f.write(
                f"    format: {self.DEFAULT_CONFIG['meetingrec']['audio']['format']}\n")
            f.write("    # Audio sample rate (Hz)\n")
            f.write(
                f"    sample_rate: {self.DEFAULT_CONFIG['meetingrec']['audio']['sample_rate']}\n")
            f.write("    # Audio channels (mono, stereo)\n")
            f.write(
                f"    channel: {self.DEFAULT_CONFIG['meetingrec']['audio']['channel']}\n")
            f.write(
                "    # Audio bitrate for compressed formats (e.g., 128k, 192k, 256k)\n")
            f.write(
                f"    bitrate: {self.DEFAULT_CONFIG['meetingrec']['audio']['bitrate']}\n")
            f.write("    # Audio quality (high, medium, low)\n")
            f.write(
                f"    quality: {self.DEFAULT_CONFIG['meetingrec']['audio']['quality']}\n\n")

            f.write("  # Screenshot settings\n")
            f.write("  screenshot:\n")
            f.write("    # Output image format (jpg)\n")
            f.write(
                f"    format: {self.DEFAULT_CONFIG['meetingrec']['screenshot']['format']}\n")
            f.write("    # Image quality (for jpg)\n")
            f.write(
                f"    quality: {self.DEFAULT_CONFIG['meetingrec']['screenshot']['quality']}\n\n")

            f.write("  # Markdown export settings\n")
            f.write("  markdown:\n")
            f.write("    # Maximum width for embedded images (in pixels)\n")
            f.write(
                f"    max_image_width: {self.DEFAULT_CONFIG['meetingrec']['markdown']['max_image_width']}\n")
            f.write("    # JPEG quality for embedded images (0-100)\n")
            f.write(
                f"    jpeg_quality: {self.DEFAULT_CONFIG['meetingrec']['markdown']['jpeg_quality']}\n")
            f.write("    # Maximum seconds to wait for transcript generation\n")
            f.write(
                f"    transcript_wait_seconds: {self.DEFAULT_CONFIG['meetingrec']['markdown']['transcript_wait_seconds']}\n\n")

            f.write("  # Meeting app detection settings\n")
            f.write("  meeting_app_detection:\n")
            f.write("    # Enable automatic detection of meeting applications\n")
            f.write(
                f"    enabled: {self.DEFAULT_CONFIG['meetingrec']['meeting_app_detection']['enabled']}\n\n")

            f.write("  # AI settings (for transcription and insights)\n")
            f.write("  ai:\n")
            f.write(
                "    # Your OpenAI API key - required for transcription and AI features\n")
            f.write(
                "    # Get your API key from: https://platform.openai.com/api-keys\n")
            f.write(
                f"    openai_api_key: {self.DEFAULT_CONFIG['meetingrec']['ai']['openai_api_key']}\n")
            f.write("    # Whisper model for transcription\n")
            f.write(
                f"    whisper_model: {self.DEFAULT_CONFIG['meetingrec']['ai']['whisper_model']}\n")
            f.write("    # GPT model for summaries and insights\n")
            f.write(
                f"    model: {self.DEFAULT_CONFIG['meetingrec']['ai']['model']}\n")
            f.write(
                "    # AI temperature parameter (0.0-1.0, lower = more focused)\n")
            f.write(
                f"    temperature: {self.DEFAULT_CONFIG['meetingrec']['ai']['temperature']}\n")
            f.write("    # Maximum tokens for AI responses\n")
            f.write(
                f"    max_tokens: {self.DEFAULT_CONFIG['meetingrec']['ai']['max_tokens']}\n\n")

            f.write("# Note: FFmpeg is required for system audio recording.\n")
            f.write("# Install with: brew install ffmpeg\n")

        print(f"Created default configuration at {self.config_path}")

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge the loaded configuration with defaults to ensure all fields exist."""
        result = self.DEFAULT_CONFIG.copy()

        def deep_update(source, updates):
            for key, value in updates.items():
                if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                    source[key] = deep_update(source[key], value)
                else:
                    source[key] = value
            return source

        return deep_update(result, config)

    def save_config(self) -> None:
        """Save the current configuration to the YAML file."""
        with open(self.config_path, 'w') as file:
            yaml.dump(self.config, file, default_flow_style=False)

    def get_config(self) -> Dict[str, Any]:
        """Get the complete configuration dictionary."""
        return self.config

    def get_openai_api_key(self) -> str:
        """Get the OpenAI API key."""
        try:
            return self.config["meetingrec"]["ai"].get("openai_api_key", "")
        except (KeyError, TypeError):
            # If the path doesn't exist, return empty string
            return ""

    def set_openai_api_key(self, api_key: str) -> None:
        """Set the OpenAI API key."""
        # Ensure ai section exists
        if "ai" not in self.config["meetingrec"]:
            self.config["meetingrec"]["ai"] = {}

        # Set key in the primary location
        self.config["meetingrec"]["ai"]["openai_api_key"] = api_key

    def get_output_dir(self) -> str:
        """Get the output directory for meeting data."""
        return self.config["meetingrec"]["output_dir"]

    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio recording configuration."""
        return self.config["meetingrec"]["audio"]

    def get_screenshot_config(self) -> Dict[str, Any]:
        """Get screenshot capture configuration."""
        return self.config["meetingrec"]["screenshot"]

    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI model configuration."""
        return self.config["meetingrec"]["ai"]

    def get_markdown_config(self) -> Dict[str, Any]:
        """Get markdown export configuration."""
        # Check if the section exists, if not create it with defaults
        if "markdown" not in self.config["meetingrec"]:
            self.config["meetingrec"]["markdown"] = {
                "max_image_width": 1200,
                "jpeg_quality": 85,
                "transcript_wait_seconds": 1800
            }
        return self.config["meetingrec"]["markdown"]

    def open_config_in_editor(self) -> None:
        """Open the configuration file in the default text editor."""
        if not self.config_path.exists():
            self._create_default_config()
            
        # Try VS Code first if available, then fall back to default app
        try:
            # Try to open with VS Code directly
            result = subprocess.run(['code', str(self.config_path)], 
                                  capture_output=True, timeout=2)
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
            
        # Fallback to default application for .yaml files
        os.system(f"open '{self.config_path}'")

    def reload_config(self) -> None:
        """Reload the configuration from disk."""
        self.config = self._load_config()

    def get_config_hash(self) -> str:
        """Get a hash of the current configuration file content.

        Returns:
            SHA-256 hash of the config file content
        """
        try:
            if not self.config_path.exists():
                return ""

            with open(self.config_path, 'rb') as file:
                file_content = file.read()
                return hashlib.sha256(file_content).hexdigest()
        except Exception as e:
            print(f"Error hashing config: {e}")
            return ""


if __name__ == "__main__":
    # Example usage
    config_manager = ConfigManager()
    print(f"Output directory: {config_manager.get_output_dir()}")
    print(
        f"OpenAI API key: {config_manager.get_openai_api_key() or 'Not set'}")
    print(f"Audio config: {config_manager.get_audio_config()}")
    print(f"Markdown config: {config_manager.get_markdown_config()}")
