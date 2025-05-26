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
            },
            "app": {
                "first_run": True,
                "ffmpeg_notification_shown": False
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
        
        # Add comments to the YAML for better user experience
        config_with_comments = f"""# MeetingRec Configuration File
# This file controls all aspects of the MeetingRec application

{yaml.dump(self.DEFAULT_CONFIG, default_flow_style=False, indent=2, sort_keys=False)}

# Note: FFmpeg is required for system audio recording.
# Install with: brew install ffmpeg
# Get your OpenAI API key from: https://platform.openai.com/api-keys
"""
        
        with open(self.config_path, 'w') as f:
            f.write(config_with_comments)
        
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

    def is_first_run(self) -> bool:
        """Check if this is the first run of the application"""
        try:
            return self.config["meetingrec"]["app"].get("first_run", True)
        except (KeyError, TypeError):
            return True

    def set_first_run_complete(self) -> None:
        """Mark first run as complete"""
        if "app" not in self.config["meetingrec"]:
            self.config["meetingrec"]["app"] = {}
        self.config["meetingrec"]["app"]["first_run"] = False
        self.save_config()

    def is_ffmpeg_notification_shown(self) -> bool:
        """Check if FFmpeg notification has been shown"""
        try:
            return self.config["meetingrec"]["app"].get("ffmpeg_notification_shown", False)
        except (KeyError, TypeError):
            return False

    def set_ffmpeg_notification_shown(self) -> None:
        """Mark FFmpeg notification as shown"""
        if "app" not in self.config["meetingrec"]:
            self.config["meetingrec"]["app"] = {}
        self.config["meetingrec"]["app"]["ffmpeg_notification_shown"] = True
        self.save_config()


if __name__ == "__main__":
    # Example usage
    config_manager = ConfigManager()
    print(f"Output directory: {config_manager.get_output_dir()}")
    print(
        f"OpenAI API key: {config_manager.get_openai_api_key() or 'Not set'}")
    print(f"Audio config: {config_manager.get_audio_config()}")
    print(f"Markdown config: {config_manager.get_markdown_config()}")
