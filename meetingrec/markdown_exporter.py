import logging
import re
import json
import io
import base64
import time

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from meetingrec.config_manager import ConfigManager

logger = logging.getLogger("meetingrec.markdown_exporter")

class MarkdownExporter:
    """Exports meeting data to markdown format."""
    
    def __init__(self, config_manager=None, max_image_width=None, jpeg_quality=None, transcript_wait_seconds=None):
        """Initialize the markdown exporter.
        
        Args:
            config_manager: Optional config manager instance
            max_image_width: Maximum width for embedded images
            jpeg_quality: JPEG quality for embedded images
            transcript_wait_seconds: Maximum seconds to wait for transcript
        """
        self.config_manager = config_manager or ConfigManager()
        
        # Get defaults from config manager if values not provided
        markdown_config = self.config_manager.get_markdown_config()
        self.max_image_width = max_image_width or markdown_config["max_image_width"]
        self.jpeg_quality = jpeg_quality or markdown_config["jpeg_quality"]
        self.transcript_wait_seconds = transcript_wait_seconds or markdown_config["transcript_wait_seconds"]
    
    def get_markdown_config(self) -> Dict[str, Any]:
        """Get markdown export configuration."""
        # Check if the section exists, if not create it with defaults
        if "markdown" not in self.config["meetingrec"]:
            self.config["meetingrec"]["markdown"] = self.DEFAULT_CONFIG["meetingrec"]["markdown"]
        return self.config["meetingrec"]["markdown"]
    
    def generate_report(self, meeting_path: Path) -> Path:
        """
        Generate a comprehensive markdown report for a meeting.
        
        Args:
            meeting_path: Path to the meeting folder
            
        Returns:
            Path to the generated markdown file
        """
        logger.info(f"Generating markdown report for meeting: {meeting_path}")
        
        # Ensure meeting_path is a Path object
        if isinstance(meeting_path, str):
            meeting_path = Path(meeting_path)
        
        # Define the output markdown file path
        markdown_file = meeting_path / f"{meeting_path.name}_report.md"
        
        # Log all files in the meeting directory for debugging
        self._log_directory_contents(meeting_path)
        
        # Get meeting data
        audio_file = self._find_audio_file(meeting_path)
        transcript_file = self._find_transcript_file(meeting_path)
        
        # Wait for transcript file if audio exists but transcript doesn't
        if audio_file and not transcript_file:
            transcript_file = self._wait_for_transcript(meeting_path)
        
        screenshot_files = self._find_screenshot_files(meeting_path)
        
        # Generate markdown content
        content = []
        
        # Add title
        meeting_name = meeting_path.name
        content.append(f"# Meeting: {meeting_name}\n")
        
        # Add date and time
        meeting_datetime = self._extract_datetime_from_folder_name(meeting_name)
        if meeting_datetime:
            content.append(f"**Date and Time:** {meeting_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n")
        else:
            # Fallback to folder creation time
            try:
                folder_time = datetime.fromtimestamp(meeting_path.stat().st_ctime)
                content.append(f"**Date and Time:** {folder_time.strftime('%Y-%m-%d %H:%M:%S')} (folder creation time)\n")
            except Exception as e:
                logger.error(f"Error getting folder creation time: {e}")
        
        # Add audio file info if available
        if audio_file:
            content.append(f"**Audio File:** {audio_file.name}\n")
        else:
            content.append("**Audio File:** Not found\n")
        
        # Add transcript section if available
        if transcript_file:
            content.append("\n## Transcript\n")
            transcript_text = self._read_transcript(transcript_file)
            content.append(transcript_text)
            content.append("\n")
        else:
            content.append("\n## Transcript\n")
            content.append("*Transcript not available. The audio file may still be processing.*\n\n")
        
        # Add screenshots section if available
        if screenshot_files:
            content.append("## Screenshots\n")
            for i, screenshot_file in enumerate(screenshot_files, 1):
                try:
                    # Get metadata about the screenshot
                    capture_time = datetime.fromtimestamp(screenshot_file.stat().st_ctime)
                    content.append(f"### Screenshot {i} - {capture_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    
                    # Use relative path for linking
                    rel_path = screenshot_file.relative_to(meeting_path)
                    content.append(f"![Screenshot {i}]({rel_path})\n\n")
                    logger.info(f"Linked screenshot {i}: {screenshot_file.name}")
                    
                except Exception as e:
                    logger.error(f"Error processing screenshot {screenshot_file}: {e}")
                    # Fallback to relative path if processing fails
                    rel_path = screenshot_file.relative_to(meeting_path)
                    content.append(f"![Screenshot {i} (failed to process)]({rel_path})\n\n")
        else:
            content.append("## Screenshots\n")
            content.append("*No screenshots were captured during this meeting.*\n")
        
        # Write content to file
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(content))
        
        # Log the final file size
        file_size = markdown_file.stat().st_size
        logger.info(f"Markdown report generated: {markdown_file} ({self._format_file_size(file_size)})")
        
        return markdown_file
    
    def _process_image_for_embedding(self, image_path: Path) -> Tuple[str, str, int, int]:
        """
        Process an image for embedding in markdown:
        1. Resize if necessary
        2. Convert to JPEG for compression
        3. Base64 encode
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (base64_data, mime_type, original_size, new_size)
        """
        # Get original file size
        original_size = image_path.stat().st_size
        
        # Determine MIME type based on file extension
        mime_type = "data:image/png"
        if image_path.suffix.lower() in ['.jpg', '.jpeg']:
            mime_type = "data:image/jpeg"
        
        # Open the image with PIL
        with Image.open(image_path) as img:
            # Check if resizing is needed
            if img.width > self.max_image_width:
                # Calculate new height to maintain aspect ratio
                ratio = self.max_image_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((self.max_image_width, new_height), Image.LANCZOS)
                logger.info(f"Resized image from {img.width}x{img.height} to {self.max_image_width}x{new_height}")
            
            # Convert to JPEG and compress
            output = io.BytesIO()
            
            # Convert to RGB if it's RGBA (needed for JPEG conversion)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
                
            img.save(output, format='JPEG', quality=self.jpeg_quality, optimize=True)
            processed_image_data = output.getvalue()
            new_size = len(processed_image_data)
            
            # Base64 encode
            encoded_data = base64.b64encode(processed_image_data).decode('utf-8')
            
            # Update MIME type to JPEG since we converted the image
            mime_type = "data:image/jpeg"
            
            return encoded_data, mime_type, original_size, new_size
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def _log_directory_contents(self, directory: Path) -> None:
        """Log all files in a directory for debugging purposes."""
        try:
            files = list(directory.iterdir())
            logger.info(f"Directory {directory} contains {len(files)} files/folders:")
            for file in files:
                if file.is_dir():
                    logger.info(f"  - {file.name}/ (directory)")
                    # Also log contents of screenshots directory
                    if file.name == "screenshots":
                        screenshot_files = list(file.iterdir())
                        logger.info(f"    Screenshots directory contains {len(screenshot_files)} files:")
                        for ss_file in screenshot_files:
                            logger.info(f"      - {ss_file.name} ({self._format_file_size(ss_file.stat().st_size)})")
                else:
                    logger.info(f"  - {file.name} ({self._format_file_size(file.stat().st_size)})")
        except Exception as e:
            logger.error(f"Error listing directory contents: {e}")
    
    def _wait_for_transcript(self, meeting_path: Path, max_wait_seconds=None) -> Optional[Path]:
        """Wait for transcript file to appear, up to max_wait_seconds."""
        if max_wait_seconds is None:
            max_wait_seconds = self.transcript_wait_seconds
            
        logger.info(f"Waiting for transcript file to appear (max {max_wait_seconds} seconds)...")
        
        for _ in range(max_wait_seconds):
            transcript_file = self._find_transcript_file(meeting_path)
            if transcript_file:
                logger.info(f"Found transcript file after waiting: {transcript_file}")
                return transcript_file
            
            # Wait 1 second before checking again
            time.sleep(1)
        
        logger.warning(f"No transcript file found after waiting {max_wait_seconds} seconds")
        return None

    def _find_audio_file(self, meeting_path: Path) -> Optional[Path]:
        """Find the audio file in the meeting folder."""
        # Try different extensions and patterns
        for pattern in ["*.wav", "*.mp3", "*.m4a", "*audio*.*"]:
            audio_files = list(meeting_path.glob(pattern))
            if audio_files:
                logger.info(f"Found audio file: {audio_files[0]}")
                return audio_files[0]
        
        logger.warning(f"No audio file found in {meeting_path}")
        return None

    def _find_transcript_file(self, meeting_path: Path) -> Optional[Path]:
        """Find the transcript file in the meeting folder."""
        # Try different patterns for transcript files
        for pattern in ["*transcript*.txt", "*transcript*.json", "*.transcript", "*_transcript*.*"]:
            transcript_files = list(meeting_path.glob(pattern))
            if transcript_files:
                logger.info(f"Found transcript file: {transcript_files[0]}")
                return transcript_files[0]
        
        logger.warning(f"No transcript file found in {meeting_path}")
        return None

    def _find_screenshot_files(self, meeting_path: Path) -> List[Path]:
        """Find all screenshot files in the meeting folder."""
        # Check the screenshots subfolder
        screenshots_dir = meeting_path / "screenshots"
        
        if not screenshots_dir.exists() or not screenshots_dir.is_dir():
            logger.warning(f"Screenshots directory not found: {screenshots_dir}")
            return []
        
        # Get all image files from the screenshots directory
        screenshot_files = []
        for ext in [".png", ".jpg", ".jpeg"]:
            screenshot_files.extend(screenshots_dir.glob(f"*{ext}"))
        
        # Sort by creation time
        screenshot_files.sort(key=lambda x: x.stat().st_ctime)
        
        logger.info(f"Found {len(screenshot_files)} screenshot files")
        return screenshot_files

    def _read_transcript(self, transcript_file: Path) -> str:
        """Read and format the transcript from file."""
        try:
            with open(transcript_file, 'r') as f:
                # Check if it's a JSON file
                if transcript_file.suffix.lower() == '.json':
                    try:
                        data = json.load(f)
                        # Check if it's in the format from OpenAI's Whisper API
                        if isinstance(data, dict) and 'text' in data:
                            return data['text']
                        # Otherwise, just return the formatted JSON
                        return f"\n{json.dumps(data, indent=2)}\n"
                    except json.JSONDecodeError:
                        # If it's not valid JSON, treat it as plain text
                        f.seek(0)  # Reset file pointer to beginning
                        return f.read()
                else:
                    # Plain text file
                    return f.read()
        except Exception as e:
            logger.error(f"Error reading transcript file: {e}")
            return "*Transcript could not be loaded due to an error.*"

    def _extract_datetime_from_folder_name(self, folder_name: str) -> Optional[datetime]:
        """Extract datetime from folder name if possible."""
        try:
            # Our known pattern is: YYYY-MM-DD-HH-MM-meeting
            # Example: 2025-05-21-21-11-meeting
            pattern = r'(\d{4}-\d{2}-\d{2}-\d{2}-\d{2})'
            match = re.search(pattern, folder_name)
            
            if match:
                dt_str = match.group(1)
                return datetime.strptime(dt_str, '%Y-%m-%d-%H-%M')
            
            logger.warning(f"Could not extract datetime from folder name: {folder_name}")
            return None
        except Exception as e:
            logger.error(f"Error extracting datetime from folder name: {e}")
            return None
        
    def _add_meeting_info(self, content: List[str], meeting_path: Path) -> None:
        """Add meeting information to the report."""
        info_path = meeting_path / "meeting_info.txt"
        if info_path.exists():
            content.append("## Meeting Information\n")
            try:
                with open(info_path, "r") as f:
                    meeting_info = f.read()
                content.append(f"\n{meeting_info}\n\n")
            except Exception as e:
                logger.error(f"Error reading meeting info file: {e}")
                content.append(f"*Error reading meeting information: {str(e)}*\n\n")
    
    def _add_audio_info(self, content: List[str], meeting_path: Path) -> None:
        """Add audio recording information to the report."""
        audio_files = list(meeting_path.glob("meeting_audio.*"))
        if audio_files:
            content.append("## Audio Recording\n")
            audio_file = audio_files[0]
            content.append(f"- Recording file: `{audio_file.name}`\n")
            
            # Add audio duration if available in meeting_info.txt
            info_path = meeting_path / "meeting_info.txt"
            if info_path.exists():
                try:
                    with open(info_path, "r") as f:
                        info_text = f.read()
                        
                    # Look for duration line
                    for line in info_text.split("\n"):
                        if "Duration:" in line:
                            content.append(f"- {line.strip()}\n")
                            break
                except Exception as e:
                    logger.debug(f"Error extracting duration from meeting info: {e}")
            
            content.append("\n")
    
    def _add_transcription(self, content: List[str], meeting_path: Path) -> None:
        """Add transcription to the report if available."""
        transcript_files = list(meeting_path.glob("transcript_*.json"))
        if transcript_files:
            content.append("## Transcription\n")
            
            # Use the most recent transcript file
            transcript_file = max(transcript_files, key=lambda p: p.stat().st_mtime)
            try:
                with open(transcript_file, "r") as f:
                    transcript_data = json.load(f)
                    
                # Handle different transcript formats
                if "text" in transcript_data:
                    # Simple format
                    content.append(transcript_data["text"])
                elif "segments" in transcript_data:
                    # Segmented format with timestamps
                    for segment in transcript_data["segments"]:
                        start_time = segment.get("start", 0)
                        minutes = int(start_time) // 60
                        seconds = int(start_time) % 60
                        timestamp = f"[{minutes:02d}:{seconds:02d}]"
                        
                        content.append(f"{timestamp} {segment.get('text', '')}\n")
                
                content.append("\n")
            except Exception as e:
                logger.error(f"Error processing transcript: {e}")
                content.append(f"*Error loading transcript: {str(e)}*\n\n")
    
    def _add_insights(self, content: List[str], meeting_path: Path) -> None:
        """Add meeting insights to the report if available."""
        insights_path = meeting_path / "meeting_insights.json"
        if insights_path.exists():
            content.append("## Meeting Insights\n")
            try:
                with open(insights_path, "r") as f:
                    insights_data = json.load(f)
                
                if "summary" in insights_data and insights_data["summary"]:
                    content.append("### Summary\n")
                    content.append(f"{insights_data['summary']}\n\n")
                
                if "key_points" in insights_data and insights_data["key_points"]:
                    content.append("### Key Points\n")
                    for point in insights_data["key_points"]:
                        content.append(f"- {point}\n")
                    content.append("\n")
                
                if "action_items" in insights_data and insights_data["action_items"]:
                    content.append("### Action Items\n")
                    for item in insights_data["action_items"]:
                        content.append(f"- [ ] {item}\n")
                    content.append("\n")
            except Exception as e:
                logger.error(f"Error processing meeting insights: {e}")
                content.append(f"*Error loading insights: {str(e)}*\n\n")
    
    def _add_screenshots(self, content: List[str], meeting_path: Path) -> None:
        """Add screenshots to the report with BASE64 encoding."""
        screenshots_dir = meeting_path / "screenshots"
        if screenshots_dir.exists():
            screenshot_files = list(screenshots_dir.glob("*"))
            if screenshot_files:
                content.append("## Screenshots\n")
                
                # Sort screenshots by name (which should include timestamps)
                screenshot_files.sort()
                
                for i, screenshot in enumerate(screenshot_files, 1):
                    # Extract timestamp from filename if available
                    timestamp = ""
                    try:
                        name_parts = screenshot.stem.split("_")
                        if len(name_parts) >= 3:
                            timestamp = name_parts[2].replace("-", ":")
                            timestamp = f"[{timestamp}] "
                    except Exception:
                        pass
                    
                    # Add screenshot title
                    content.append(f"### {timestamp}Screenshot {i}\n")
                    
                    try:
                        # Determine image format
                        img_format = screenshot.suffix.lower().lstrip('.')
                        if img_format == 'jpg':
                            img_format = 'jpeg'  # BASE64 uses 'jpeg' not 'jpg'
                        
                        # Open and resize image (optional - reduces file size)
                        with Image.open(screenshot) as img:
                            # Resize large images to reduce file size
                            max_width = 1200  # Max width for large screens
                            if img.width > max_width:
                                ratio = max_width / img.width
                                new_height = int(img.height * ratio)
                                img = img.resize((max_width, new_height), Image.LANCZOS)
                            
                            # Save to bytes buffer
                            buffer = io.BytesIO()
                            img.save(buffer, format=img_format)
                            img_str = base64.b64encode(buffer.getvalue()).decode('ascii')
                        
                        # Add BASE64 encoded image
                        content.append(f"![Screenshot {i}](data:image/{img_format};base64,{img_str})\n\n")
                        
                    except Exception as e:
                        logger.error(f"Error embedding screenshot {screenshot}: {e}")
                        content.append(f"*Error embedding screenshot: {str(e)}*\n\n")
                        # Fallback to relative path
                        rel_path = f"screenshots/{screenshot.name}"
                        content.append(f"![Screenshot {i} (not embedded)]({rel_path})\n\n")
    
    def _add_footer(self, content: List[str]) -> None:
        """Add footer to the report."""
        content.append("\n---\n")
        content.append(f"*Generated by MeetingRec on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
