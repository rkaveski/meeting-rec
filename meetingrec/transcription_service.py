import os
import json
import logging
import time

from pathlib import Path
from typing import Dict, Any, Optional

from openai import OpenAI
from meetingrec.config_manager import ConfigManager
from meetingrec.error_manager import error_manager

# Get logger
logger = logging.getLogger("meetingrec.transcription")

class TranscriptionService:
    """Handles audio transcription using OpenAI's Whisper API."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the transcription service with configuration.
        
        Args:
            config_manager: Configuration manager instance. If None, a new one is created.
        """
        self.config_manager = config_manager or ConfigManager()
        self.ai_config = self.config_manager.get_ai_config()
        
        # Get API key
        api_key = self.config_manager.get_openai_api_key()
        if not api_key:
            logger.warning("OpenAI API key not set. Transcription will not be available.")
        
        # Initialize OpenAI client
        self.client = None
        if api_key:
            self.client = OpenAI(api_key=api_key)
    
    def transcribe_audio(self, audio_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Transcribe audio file using OpenAI's Whisper API.
        
        Args:
            audio_path: Path to the audio file
            output_dir: Directory to save the transcript
            
        Returns:
            Dict containing transcription information
        """
        if not self.client:
            return {
                "success": False,
                "message": "OpenAI API key not configured. Please set your API key in the config."
            }
        
        if not audio_path.exists():
            return {
                "success": False,
                "message": f"Audio file not found: {audio_path}"
            }
        
        logger.info(f"Starting transcription of {audio_path}")
        start_time = time.time()
        
        try:
            # Format timestamp for filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"transcript_{timestamp}.json"
            
            # Check if file is larger than 25MB (Whisper API limit)
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            if file_size_mb > 25:
                logger.warning(f"Audio file size ({file_size_mb:.1f}MB) exceeds the 25MB limit for Whisper API")
                return {
                    "success": False,
                    "message": f"Audio file too large ({file_size_mb:.1f}MB). Maximum size is 25MB."
                }
            
            # Get whisper model from config
            model = self.ai_config.get("whisper_model", "whisper-1")
            
            # Open audio file and transcribe
            with open(audio_path, "rb") as audio_file:
                logger.info(f"Sending audio to OpenAI Whisper API (model: {model})...")
                
                response = self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    response_format="verbose_json",
                    temperature=0.2,
                    language="en"
                )
                
            # Convert to dictionary for JSON serialization if necessary
            try:
                # If response is already a dict, use it directly
                transcript_data = response if isinstance(response, dict) else response.model_dump()
            except AttributeError:
                # If response is a different type, convert to dict
                transcript_data = {"text": str(response)}
            
            # Save transcript to file
            with open(output_path, "w") as f:
                json.dump(transcript_data, f, indent=2)
            
            duration = time.time() - start_time
            logger.info(f"Transcription completed in {duration:.1f}s. Saved to {output_path}")
            
            return {
                "success": True,
                "message": "Transcription completed successfully",
                "transcript_path": str(output_path),
                "duration": duration,
                "text": transcript_data.get("text", ""),
                "segments": transcript_data.get("segments", [])
            }
            
        except Exception as e:
            error_info = error_manager.capture_exception("Transcription")
            logger.error(f"Error during transcription: {e}")
            
            return {
                "success": False,
                "message": f"Transcription failed: {str(e)}",
                "error_info": error_info
            }
