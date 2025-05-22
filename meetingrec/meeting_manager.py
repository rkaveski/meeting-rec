import os
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("meetingrec.meeting_manager")

class MeetingManager:
    """Manages meeting folders and related operations."""
    
    def __init__(self, output_dir: Optional[str] = None):
        """Initialize the meeting manager.
        
        Args:
            output_dir: Path to meetings directory. If None, this must be set later.
        """
        self.output_dir = Path(output_dir) if output_dir else None
    
    def set_output_dir(self, output_dir: str) -> None:
        """Set the meetings output directory.
        
        Args:
            output_dir: Path to the meetings directory
        """
        self.output_dir = Path(output_dir)
    
    def get_meetings(self, max_meetings: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get a list of all meetings.
        
        Args:
            max_meetings: Maximum number of meetings to return (newest first)
            
        Returns:
            List of meeting info dictionaries
        """
        if not self.output_dir or not self.output_dir.exists():
            logger.warning(f"Output directory does not exist: {self.output_dir}")
            return []
        
        meetings = []
        
        # Look for meeting directories
        for item in self.output_dir.iterdir():
            if not item.is_dir():
                continue
                
            # Check if this looks like a meeting directory
            has_audio = any(item.glob("meeting_audio.*"))
            has_screenshots = item.joinpath("screenshots").exists()
            has_info = item.joinpath("meeting_info.txt").exists()
            
            # Skip if it doesn't look like a meeting folder
            if not (has_audio or has_screenshots or has_info):
                continue
                
            # Extract meeting information
            meeting_info = {
                "path": str(item),
                "name": item.name,
                "date": None,
                "has_report": item.joinpath("meeting_report.md").exists(),
                "has_audio": has_audio,
                "has_screenshots": has_screenshots,
                "screenshot_count": len(list(item.joinpath("screenshots").glob("*"))) if has_screenshots else 0
            }
            
            # Try to extract date from folder name
            try:
                # Assuming format like "2023-01-01-14-30-meeting"
                date_part = item.name.split("-meeting")[0]
                meeting_date = datetime.strptime(date_part, "%Y-%m-%d-%H-%M")
                meeting_info["date"] = meeting_date.isoformat()
                
                # Add formatted date for display
                meeting_info["date_formatted"] = meeting_date.strftime("%Y-%m-%d %H:%M")
            except (ValueError, IndexError):
                # Use folder modification time as fallback
                meeting_info["date"] = datetime.fromtimestamp(
                    item.stat().st_mtime).isoformat()
                meeting_info["date_formatted"] = datetime.fromtimestamp(
                    item.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            
            # Extract duration from meeting_info.txt if available
            if has_info:
                try:
                    with open(item / "meeting_info.txt", "r") as f:
                        info_text = f.read()
                        
                    # Look for duration line
                    for line in info_text.split("\n"):
                        if "Duration:" in line:
                            try:
                                duration_str = line.split("Duration:")[1].strip()
                                duration_val = float(duration_str.split(" ")[0])
                                meeting_info["duration"] = duration_val
                                
                                # Format duration for display
                                mins = int(duration_val // 60)
                                secs = int(duration_val % 60)
                                meeting_info["duration_formatted"] = f"{mins}m {secs}s"
                            except (IndexError, ValueError):
                                pass
                except Exception as e:
                    logger.warning(f"Error reading meeting info for {item.name}: {e}")
            
            meetings.append(meeting_info)
        
        # Sort by date, newest first
        meetings.sort(key=lambda m: m.get("date", ""), reverse=True)
        
        # Limit results if requested
        if max_meetings and max_meetings > 0:
            return meetings[:max_meetings]
            
        return meetings
    
    def open_meeting_folder(self, meeting_path: str) -> bool:
        """Open a meeting folder in Finder.
        
        Args:
            meeting_path: Path to the meeting folder
            
        Returns:
            True if successful, False otherwise
        """
        try:
            meeting_path = Path(meeting_path)
            if not meeting_path.exists():
                logger.error(f"Meeting path does not exist: {meeting_path}")
                return False
                
            # Open the folder in Finder
            subprocess.run(["open", str(meeting_path)])
            return True
        except Exception as e:
            logger.error(f"Error opening meeting folder: {e}")
            return False
    
    def open_meetings_directory(self) -> bool:
        """Open the main meetings directory in Finder.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.output_dir or not self.output_dir.exists():
                logger.error(f"Output directory does not exist: {self.output_dir}")
                return False
                
            # Open the directory in Finder
            subprocess.run(["open", str(self.output_dir)])
            return True
        except Exception as e:
            logger.error(f"Error opening meetings directory: {e}")
            return False
    
    def get_meeting_info(self, meeting_path: str) -> Dict[str, Any]:
        """Get detailed information about a specific meeting.
        
        Args:
            meeting_path: Path to the meeting folder
            
        Returns:
            Dictionary with meeting details
        """
        try:
            meeting_path = Path(meeting_path)
            if not meeting_path.exists():
                return {"success": False, "message": "Meeting not found"}
                
            # Basic info
            info = {
                "success": True,
                "path": str(meeting_path),
                "name": meeting_path.name,
                "date": datetime.fromtimestamp(meeting_path.stat().st_mtime).isoformat(),
                "has_report": meeting_path.joinpath("meeting_report.md").exists(),
                "has_audio": any(meeting_path.glob("meeting_audio.*")),
                "has_screenshots": meeting_path.joinpath("screenshots").exists(),
            }
            
            # Count screenshots if they exist
            if info["has_screenshots"]:
                info["screenshot_count"] = len(list(meeting_path.joinpath("screenshots").glob("*")))
            
            # Read meeting_info.txt if it exists
            info_file = meeting_path / "meeting_info.txt"
            if info_file.exists():
                try:
                    with open(info_file, "r") as f:
                        info["info_text"] = f.read()
                except Exception as e:
                    logger.warning(f"Error reading meeting info: {e}")
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting meeting info: {e}")
            return {"success": False, "message": str(e)}