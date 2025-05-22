import time
import json
import tempfile
import openai

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from pydub import AudioSegment

from meetingrec.config_manager import ConfigManager


class TranscriptionAPI:
    """Handles audio transcription using OpenAI's Whisper API."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the transcription API with configuration.
        
        Args:
            config_manager: Configuration manager instance. If None, a new one is created.
        """
        self.config_manager = config_manager or ConfigManager()
        self.api_key = self.config_manager.get_openai_api_key()
        self.ai_config = self.config_manager.get_ai_config()
        
        # Configure OpenAI client
        if not self.api_key:
            print("Warning: OpenAI API key not set in configuration")
        else:
            openai.api_key = self.api_key
        
        # Transcription settings
        self.model = self.ai_config.get("whisper_model", "whisper-1")
        self.temperature = float(self.ai_config.get("temperature", 0.2))
        self.language = self.ai_config.get("language", "en")
        
        # File type handling
        self.supported_formats = ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]
        self.max_file_size_mb = 25  # OpenAI API limit
    
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe an audio file using OpenAI's Whisper API.
        
        Args:
            audio_path: Path to the audio file
            output_dir: Directory to save the transcription. If None, uses the same
                       directory as the audio file
                       
        Returns:
            Dict containing transcription data and metadata
        """
        audio_path = Path(audio_path)
        
        if output_dir is None:
            output_dir = audio_path.parent
        else:
            output_dir = Path(output_dir)
        
        # Ensure output directory exists
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Check if API key is set
        if not self.api_key:
            return {
                "success": False,
                "message": "OpenAI API key not set. Please update your configuration."
            }
        
        # Check if file exists
        if not audio_path.exists():
            return {
                "success": False,
                "message": f"Audio file not found: {audio_path}"
            }
        
        # Check file format
        if audio_path.suffix.lower()[1:] not in self.supported_formats:
            return {
                "success": False,
                "message": f"Unsupported audio format: {audio_path.suffix}. Supported formats: {', '.join(self.supported_formats)}"
            }
        
        # Check file size and process if needed
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        processed_file = audio_path
        temp_file = None
        
        if file_size_mb > self.max_file_size_mb:
            # Process file to reduce size or split into chunks
            processed_file, temp_file = self._process_large_file(audio_path)
            if not processed_file:
                return {
                    "success": False,
                    "message": f"Failed to process large audio file: {audio_path}"
                }
        
        try:
            # Prepare output files
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_output_path = output_dir / f"transcript_{timestamp}.json"
            text_output_path = output_dir / f"transcript_{timestamp}.txt"
            
            # Start transcription
            print(f"Starting transcription of {audio_path}")
            start_time = time.time()
            
            with open(processed_file, "rb") as audio_file:
                # Call OpenAI API
                transcript_response = openai.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="verbose_json",
                    temperature=self.temperature,
                    language=self.language
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Process response
            if hasattr(transcript_response, 'to_dict'):
                # Handle different response formats based on API version
                transcript_data = transcript_response.to_dict()
            else:
                transcript_data = transcript_response
            
            # Extract text and segments
            full_text = transcript_data.get("text", "")
            segments = transcript_data.get("segments", [])
            
            # Process speaker diarization if available
            processed_transcript = self._process_transcript_with_speakers(full_text, segments)
            
            # Save raw transcript data
            with open(json_output_path, "w") as json_file:
                json.dump(transcript_data, json_file, indent=2)
            
            # Save readable transcript
            with open(text_output_path, "w") as text_file:
                text_file.write(self._format_transcript_for_text(processed_transcript))
            
            # Clean up temporary file if created
            if temp_file and temp_file.exists():
                temp_file.unlink()
            
            # Return success result
            return {
                "success": True,
                "message": f"Transcription completed in {duration:.2f} seconds",
                "audio_path": str(audio_path),
                "json_path": str(json_output_path),
                "text_path": str(text_output_path),
                "duration": duration,
                "transcript": processed_transcript,
                "word_count": len(full_text.split()),
                "segments": len(segments)
            }
            
        except Exception as e:
            # Handle API errors
            error_message = str(e)
            print(f"Transcription error: {error_message}")
            
            # Clean up temporary file if created
            if temp_file and temp_file.exists():
                temp_file.unlink()
                
            return {
                "success": False,
                "message": f"Transcription failed: {error_message}",
                "audio_path": str(audio_path)
            }
    
    def _process_large_file(self, audio_path: Path) -> Tuple[Path, Optional[Path]]:
        """Process large audio files by compressing or splitting them.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Tuple of (processed_file_path, temp_file_path if created or None)
        """
        try:
            # Create a temporary file
            temp_dir = tempfile.gettempdir()
            temp_file = Path(temp_dir) / f"compressed_{audio_path.name}"
            
            # Load audio file
            audio = AudioSegment.from_file(str(audio_path))
            
            # Compress by reducing quality
            compressed_audio = audio.export(
                str(temp_file),
                format="mp3",
                parameters=["-ac", "1", "-ab", "64k"]  # Mono, 64kbps
            )
            
            # Check if compression was successful and file size is now acceptable
            if temp_file.exists() and temp_file.stat().st_size / (1024 * 1024) <= self.max_file_size_mb:
                return temp_file, temp_file
            
            # If compression didn't reduce size enough, we would need to implement splitting logic here
            # For now, we'll return an error condition by returning (None, temp_file)
            return None, temp_file
            
        except Exception as e:
            print(f"Error processing large file: {e}")
            return None, None
    
    def _process_transcript_with_speakers(self, text: str, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process transcript segments without speaker diarization.
        
        Args:
            text: Full transcript text
            segments: List of segment dictionaries from Whisper API
            
        Returns:
            List of processed segments without speaker labels
        """
        processed_segments = []
        
        for i, segment in enumerate(segments):
            # Get basic segment info
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            segment_text = segment.get("text", "").strip()
            
            # Skip empty segments
            if not segment_text:
                continue
            
            # Create processed segment without speaker identification
            processed_segment = {
                "start": start,
                "end": end,
                "text": segment_text,
                "id": len(processed_segments)
            }
            
            processed_segments.append(processed_segment)
        
        return processed_segments
    
    def _format_transcript_for_text(self, processed_transcript: List[Dict[str, Any]]) -> str:
        """Format the processed transcript into readable text.
        
        Args:
            processed_transcript: List of processed transcript segments
            
        Returns:
            Formatted transcript text
        """
        formatted_text = ""
        
        for segment in processed_transcript:
            start_time = segment.get("start", 0)
            text = segment.get("text", "")
            
            # Format timestamp as [MM:SS]
            minutes = int(start_time) // 60
            seconds = int(start_time) % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            
            # Add formatted line (without speaker label)
            formatted_text += f"{timestamp}: {text}\n\n"
        
        return formatted_text
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats."""
        return self.supported_formats


if __name__ == "__main__":
    # Simple test code
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python transcription_api.py <audio_file_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    transcriber = TranscriptionAPI()
    result = transcriber.transcribe_audio(audio_path)
    
    if result.get("success"):
        print(f"Transcription successful: {result.get('message')}")
        print(f"Output files: {result.get('text_path')}, {result.get('json_path')}")
        print(f"Word count: {result.get('word_count')}")
        print(f"Duration: {result.get('duration'):.2f} seconds")
    else:
        print(f"Transcription failed: {result.get('message')}")