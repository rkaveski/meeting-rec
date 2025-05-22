import json
import re

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from meetingrec.config_manager import ConfigManager


class TranscriptAligner:
    """Aligns screenshots with transcript segments based on timestamps."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the transcript aligner with configuration.
        
        Args:
            config_manager: Configuration manager instance. If None, a new one is created.
        """
        self.config_manager = config_manager or ConfigManager()
        self.output_dir = Path(self.config_manager.get_output_dir())
    
    def align_meeting_content(self, meeting_path: str) -> Dict[str, Any]:
        """Align screenshots with transcript segments for a meeting.
        
        Args:
            meeting_path: Path to the meeting directory containing transcript and screenshots
            
        Returns:
            Dict containing alignment result and content information
        """
        meeting_dir = Path(meeting_path)
        
        if not meeting_dir.exists():
            return {
                "success": False,
                "message": f"Meeting directory not found: {meeting_dir}"
            }
        
        # Find transcript JSON file
        transcript_files = list(meeting_dir.glob("transcript_*.json"))
        if not transcript_files:
            return {
                "success": False,
                "message": "No transcript file found in meeting directory"
            }
        
        # Use the most recent transcript file if multiple exist
        transcript_file = sorted(transcript_files)[-1]
        
        # Find screenshots
        screenshots_dir = meeting_dir / "screenshots"
        if not screenshots_dir.exists():
            return {
                "success": False,
                "message": "Screenshots directory not found"
            }
        
        screenshot_files = sorted(screenshots_dir.glob("screenshot_*.*"))
        if not screenshot_files:
            return {
                "success": False,
                "message": "No screenshots found in meeting directory"
            }
        
        try:
            # Load transcript data
            with open(transcript_file, "r") as f:
                transcript_data = json.load(f)
            
            # Prepare screenshots metadata
            screenshots_metadata = self._extract_screenshots_metadata(screenshot_files)
            
            # Get transcript segments
            segments = transcript_data.get("segments", [])
            if not segments:
                return {
                    "success": False,
                    "message": "No transcript segments found in transcript file"
                }
            
            # Get meeting recording start time
            meeting_info_file = meeting_dir / "meeting_info.txt"
            recording_start_time = self._extract_recording_start_time(meeting_info_file)
            
            # Align screenshots with transcript segments
            aligned_content = self._align_screenshots_with_segments(
                segments, screenshots_metadata, recording_start_time
            )
            
            # Save aligned content
            aligned_file = meeting_dir / "aligned_content.json"
            with open(aligned_file, "w") as f:
                json.dump(aligned_content, f, indent=2)
            
            return {
                "success": True,
                "message": "Meeting content aligned successfully",
                "meeting_path": str(meeting_dir),
                "aligned_file": str(aligned_file),
                "screenshots_count": len(screenshots_metadata),
                "segments_count": len(segments),
                "content": aligned_content
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to align meeting content: {str(e)}"
            }
    
    def _extract_screenshots_metadata(self, screenshot_files: List[Path]) -> List[Dict[str, Any]]:
        """Extract metadata from screenshot filenames.
        
        Args:
            screenshot_files: List of screenshot file paths
            
        Returns:
            List of dictionaries containing screenshot metadata
        """
        screenshots_metadata = []
        
        # Expected filename format: screenshot_00001_HH-MM-SS.png
        screenshot_pattern = re.compile(r"screenshot_(\d+)_(\d{2})-(\d{2})-(\d{2})\..*")
        
        for screenshot_file in screenshot_files:
            filename = screenshot_file.name
            match = screenshot_pattern.match(filename)
            
            if match:
                index = int(match.group(1))
                hour = int(match.group(2))
                minute = int(match.group(3))
                second = int(match.group(4))
                
                # Calculate timestamp in seconds from start of day
                timestamp_seconds = hour * 3600 + minute * 60 + second
                
                screenshots_metadata.append({
                    "file": str(screenshot_file),
                    "filename": filename,
                    "index": index,
                    "timestamp": timestamp_seconds,
                    "time_str": f"{hour:02d}:{minute:02d}:{second:02d}"
                })
        
        # Sort by timestamp
        screenshots_metadata.sort(key=lambda x: x["timestamp"])
        
        return screenshots_metadata
    
    def _extract_recording_start_time(self, meeting_info_file: Path) -> Optional[float]:
        """Extract recording start time from meeting info file.
        
        Args:
            meeting_info_file: Path to meeting info file
            
        Returns:
            Recording start time as seconds from start of day, or None if not found
        """
        if not meeting_info_file.exists():
            return None
        
        try:
            with open(meeting_info_file, "r") as f:
                info_text = f.read()
            
            # Look for start time in ISO format
            matches = re.search(r"Recording started at: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", info_text)
            if matches:
                start_time_str = matches.group(1)
                start_time = datetime.fromisoformat(start_time_str)
                
                # Convert to seconds from start of day
                seconds_from_day_start = start_time.hour * 3600 + start_time.minute * 60 + start_time.second
                return seconds_from_day_start
                
        except Exception:
            pass
            
        return None
    
    def _align_screenshots_with_segments(
        self, 
        segments: List[Dict[str, Any]], 
        screenshots: List[Dict[str, Any]],
        recording_start_time: Optional[float]
    ) -> Dict[str, Any]:
        """Align screenshots with transcript segments based on timestamps.
        
        Args:
            segments: List of transcript segments
            screenshots: List of screenshot metadata
            recording_start_time: Recording start time in seconds from day start
            
        Returns:
            Dictionary containing aligned content
        """
        aligned_segments = []
        
        # Process transcript segments
        for segment in segments:
            segment_start = segment.get("start", 0)  # Seconds from start of recording
            segment_end = segment.get("end", 0)
            segment_text = segment.get("text", "").strip()
            
            # Skip empty segments
            if not segment_text:
                continue
            
            # Find screenshots that belong to this segment
            segment_screenshots = []
            
            for screenshot in screenshots:
                screenshot_time = screenshot["timestamp"]
                
                # Adjust screenshot time if we have recording start time
                if recording_start_time is not None:
                    # Calculate seconds from recording start
                    if screenshot_time >= recording_start_time:
                        screenshot_relative_time = screenshot_time - recording_start_time
                    else:
                        # Handle case where screenshot might be after midnight
                        screenshot_relative_time = screenshot_time + (24 * 3600) - recording_start_time
                else:
                    # If we don't have recording start time, use screenshot time directly
                    # This is less accurate but still allows for ordering
                    screenshot_relative_time = screenshot_time
                
                # Check if screenshot falls within this segment's time range
                # Add a small buffer (3 seconds) to catch screenshots taken just before a segment
                if segment_start - 3 <= screenshot_relative_time <= segment_end + 3:
                    segment_screenshots.append({
                        "file": screenshot["file"],
                        "relative_time": screenshot_relative_time,
                        "time_str": screenshot["time_str"]
                    })
            
            # Create aligned segment
            aligned_segment = {
                "start": segment_start,
                "end": segment_end,
                "text": segment_text,
                "screenshots": segment_screenshots
            }
            
            aligned_segments.append(aligned_segment)
        
        # Create aligned content structure
        aligned_content = {
            "segments": aligned_segments,
            "total_screenshots": len(screenshots),
            "total_segments": len(aligned_segments),
            "screenshots_used": sum(len(s["screenshots"]) for s in aligned_segments)
        }
        
        return aligned_content
    
    def generate_markdown_preview(self, aligned_content: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Generate a Markdown preview of the aligned content.
        
        Args:
            aligned_content: Aligned content dictionary
            output_path: Optional path to save the Markdown file
            
        Returns:
            Markdown content as string
        """
        segments = aligned_content.get("segments", [])
        
        markdown_lines = [
            "# Meeting Transcript with Screenshots",
            "",
            f"Total Segments: {aligned_content.get('total_segments', 0)}",
            f"Total Screenshots: {aligned_content.get('total_screenshots', 0)}",
            f"Screenshots Used: {aligned_content.get('screenshots_used', 0)}",
            "",
            "---",
            ""
        ]
        
        for segment in segments:
            # Format timestamp
            start_time = segment.get("start", 0)
            minutes = int(start_time) // 60
            seconds = int(start_time) % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            
            # Add segment text
            markdown_lines.append(f"### {timestamp} {segment.get('text', '')}")
            markdown_lines.append("")
            
            # Add screenshots if any
            screenshots = segment.get("screenshots", [])
            for i, screenshot in enumerate(screenshots):
                file_path = screenshot.get("file", "")
                rel_path = Path(file_path).name
                markdown_lines.append(f"![Screenshot {i+1}]({rel_path})")
                markdown_lines.append("")
            
            markdown_lines.append("---")
            markdown_lines.append("")
        
        markdown_content = "\n".join(markdown_lines)
        
        # Save to file if output path provided
        if output_path:
            with open(output_path, "w") as f:
                f.write(markdown_content)
                
        return markdown_content


if __name__ == "__main__":
    # Simple test code
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python transcript_aligner.py <meeting_path>")
        sys.exit(1)
    
    meeting_path = sys.argv[1]
    
    aligner = TranscriptAligner()
    result = aligner.align_meeting_content(meeting_path)
    
    if result.get("success"):
        print(f"Alignment successful: {result.get('message')}")
        print(f"Screenshots: {result.get('screenshots_count')}")
        print(f"Segments: {result.get('segments_count')}")
        
        # Generate markdown preview
        aligned_content = result.get("content")
        markdown_path = Path(meeting_path) / "transcript_with_screenshots.md"
        aligner.generate_markdown_preview(aligned_content, str(markdown_path))
        print(f"Markdown preview saved to: {markdown_path}")
    else:
        print(f"Alignment failed: {result.get('message')}")