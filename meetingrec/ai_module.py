import json
import time
import re
import openai

from pathlib import Path
from typing import Dict, Any, Optional

from meetingrec.config_manager import ConfigManager


class AIModule:
    """Uses OpenAI GPT models to analyze meeting transcripts and generate insights."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the AI module with configuration.
        
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
        
        # AI settings
        self.model = self.ai_config.get("gpt_model", "gpt-4o")
        self.temperature = float(self.ai_config.get("temperature", 0.2))
        self.max_tokens = self.ai_config.get("max_tokens", 4000)
    
    def process_meeting(self, meeting_path: str) -> Dict[str, Any]:
        """Process a meeting to generate summary, action items, and key points.
        
        Args:
            meeting_path: Path to the meeting directory
            
        Returns:
            Dict containing processing results
        """
        meeting_dir = Path(meeting_path)
        
        if not meeting_dir.exists():
            return {
                "success": False,
                "message": f"Meeting directory not found: {meeting_dir}"
            }
        
        # Check if API key is set
        if not self.api_key:
            return {
                "success": False,
                "message": "OpenAI API key not set. Please update your configuration."
            }
        
        try:
            # Load aligned content if available
            aligned_file = meeting_dir / "aligned_content.json"
            if aligned_file.exists():
                with open(aligned_file, "r") as f:
                    aligned_content = json.load(f)
                content_source = "aligned"
            else:
                # Fall back to transcript file if aligned content not available
                transcript_files = list(meeting_dir.glob("transcript_*.json"))
                if not transcript_files:
                    return {
                        "success": False,
                        "message": "No transcript or aligned content found"
                    }
                
                # Use the most recent transcript file
                transcript_file = sorted(transcript_files)[-1]
                with open(transcript_file, "r") as f:
                    transcript_data = json.load(f)
                
                # Extract text from transcript
                if "text" in transcript_data:
                    full_text = transcript_data["text"]
                    segments = transcript_data.get("segments", [])
                else:
                    segments = transcript_data.get("segments", [])
                    full_text = " ".join([s.get("text", "") for s in segments])
                
                # Create simplified content with just text
                aligned_content = {
                    "segments": [{
                        "text": s.get("text", ""),
                        "start": s.get("start", 0),
                        "end": s.get("end", 0),
                        "screenshots": []
                    } for s in segments if s.get("text")]
                }
                content_source = "transcript"
            
            # Extract meeting content
            meeting_text = self._extract_meeting_text(aligned_content)
            
            # Generate insights
            insights = {}
            
            # Generate meeting summary
            summary_result = self.generate_summary(meeting_text)
            if summary_result.get("success"):
                insights["summary"] = summary_result.get("summary")
            
            # Extract action items
            action_items_result = self.extract_action_items(meeting_text)
            if action_items_result.get("success"):
                insights["action_items"] = action_items_result.get("action_items")
            
            # Identify key points
            key_points_result = self.identify_key_points(meeting_text)
            if key_points_result.get("success"):
                insights["key_points"] = key_points_result.get("key_points")
            
            # Save insights
            insights_file = meeting_dir / "meeting_insights.json"
            with open(insights_file, "w") as f:
                json.dump(insights, f, indent=2)
            
            # Generate markdown report
            markdown_report = self._generate_markdown_report(aligned_content, insights)
            report_file = meeting_dir / "meeting_report.md"
            with open(report_file, "w") as f:
                f.write(markdown_report)
            
            return {
                "success": True,
                "message": "Meeting processed successfully",
                "meeting_path": str(meeting_dir),
                "insights_file": str(insights_file),
                "report_file": str(report_file),
                "content_source": content_source,
                "insights": insights
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to process meeting: {str(e)}"
            }
    
    def _extract_meeting_text(self, aligned_content: Dict[str, Any]) -> str:
        """Extract text content from aligned meeting data.
        
        Args:
            aligned_content: Aligned content dictionary
            
        Returns:
            Meeting text as string
        """
        segments = aligned_content.get("segments", [])
        lines = []
        
        for segment in segments:
            # Format timestamp
            start_time = segment.get("start", 0)
            minutes = int(start_time) // 60
            seconds = int(start_time) % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            
            # Add segment text with timestamp
            lines.append(f"{timestamp} {segment.get('text', '')}")
        
        return "\n".join(lines)
    
    def generate_summary(self, meeting_text: str) -> Dict[str, Any]:
        """Generate a summary of the meeting.
        
        Args:
            meeting_text: Text content of the meeting
            
        Returns:
            Dict containing summary result
        """
        try:
            prompt = f"""
            You are a professional meeting summarizer. Your task is to create a clear, concise summary 
            of the following meeting transcript. Focus on the main discussion points and outcomes.
            
            Here is the meeting transcript:
            
            {meeting_text}
            
            Please provide a summary that captures the key points of the discussion.
            Your summary should be approximately 3-5 paragraphs.
            """
            
            response = self._call_openai_api(prompt)
            
            if response.get("success"):
                return {
                    "success": True,
                    "summary": response.get("content"),
                    "tokens_used": response.get("tokens_used")
                }
            else:
                return response
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to generate summary: {str(e)}"
            }
    
    def extract_action_items(self, meeting_text: str) -> Dict[str, Any]:
        """Extract action items from the meeting.
        
        Args:
            meeting_text: Text content of the meeting
            
        Returns:
            Dict containing action items result
        """
        try:
            prompt = f"""
            You are a professional meeting assistant. Your task is to extract all action items, 
            tasks, and commitments made during this meeting.
            
            For each action item, identify:
            1. The task to be done
            2. Who is responsible (if mentioned)
            3. Any deadline (if mentioned)
            
            Here is the meeting transcript:
            
            {meeting_text}
            
            Please list all action items in a numbered list format. If no action items are mentioned,
            state "No action items were identified in this meeting."
            """
            
            response = self._call_openai_api(prompt)
            
            if response.get("success"):
                # Process response to extract action items as a list
                action_items_text = response.get("content")
                action_items = []
                
                # Process response into a structured format if action items were found
                if "No action items" not in action_items_text:
                    # Simple regex-based extraction - this could be improved
                    items = re.findall(r'\d+\.\s+(.*?)(?=\d+\.|$)', action_items_text, re.DOTALL)
                    for item in items:
                        action_items.append(item.strip())
                
                return {
                    "success": True,
                    "action_items": action_items,
                    "action_items_text": action_items_text,
                    "tokens_used": response.get("tokens_used")
                }
            else:
                return response
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to extract action items: {str(e)}"
            }
    
    def identify_key_points(self, meeting_text: str) -> Dict[str, Any]:
        """Identify key points from the meeting.
        
        Args:
            meeting_text: Text content of the meeting
            
        Returns:
            Dict containing key points result
        """
        try:
            prompt = f"""
            You are a professional meeting analyst. Your task is to identify the 5-7 most important 
            key points or insights from this meeting.
            
            Focus on identifying:
            - Important decisions made
            - Critical information shared
            - Significant concerns raised
            - Notable ideas discussed
            
            Here is the meeting transcript:
            
            {meeting_text}
            
            Please list each key point as a brief, clear statement.
            """
            
            response = self._call_openai_api(prompt)
            
            if response.get("success"):
                # Process response to extract key points as a list
                key_points_text = response.get("content")
                key_points = []
                
                # Simple extraction - could be improved for more complex responses
                lines = key_points_text.split('\n')
                for line in lines:
                    line = line.strip()
                    # Look for lines that start with a number, bullet, or dash
                    if re.match(r'^(\d+\.|\*|\-)\s+', line):
                        # Remove the prefix and add to key points
                        point = re.sub(r'^(\d+\.|\*|\-)\s+', '', line)
                        if point:
                            key_points.append(point)
                
                return {
                    "success": True,
                    "key_points": key_points,
                    "key_points_text": key_points_text,
                    "tokens_used": response.get("tokens_used")
                }
            else:
                return response
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to identify key points: {str(e)}"
            }
    
    def _call_openai_api(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API with error handling and retries.
        
        Args:
            prompt: The prompt to send to the API
            
        Returns:
            Dict containing API response
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = openai.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional meeting assistant that helps analyze meeting transcripts."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                # Extract content from response
                content = response.choices[0].message.content.strip()
                tokens_used = response.usage.total_tokens
                
                return {
                    "success": True,
                    "content": content,
                    "tokens_used": tokens_used
                }
                
            except openai.RateLimitError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    return {
                        "success": False,
                        "message": "OpenAI API rate limit exceeded. Please try again later."
                    }
                    
            except openai.APIError as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return {
                        "success": False,
                        "message": f"OpenAI API error: {str(e)}"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error calling OpenAI API: {str(e)}"
                }
    
    def _generate_markdown_report(self, aligned_content: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Generate a markdown report from aligned content and insights.
        
        Args:
            aligned_content: Aligned content dictionary
            insights: Insights dictionary
            
        Returns:
            Markdown report as string
        """
        # Get data
        segments = aligned_content.get("segments", [])
        summary = insights.get("summary", "")
        action_items = insights.get("action_items", [])
        key_points = insights.get("key_points", [])
        
        # Create report
        report_lines = [
            "# Meeting Report",
            "",
            "## Summary",
            "",
            summary,
            "",
            "## Key Points",
            ""
        ]
        
        # Add key points
        for i, point in enumerate(key_points):
            report_lines.append(f"{i+1}. {point}")
        
        report_lines.extend([
            "",
            "## Action Items",
            ""
        ])
        
        # Add action items
        if action_items:
            for i, item in enumerate(action_items):
                report_lines.append(f"{i+1}. {item}")
        else:
            report_lines.append("No action items were identified in this meeting.")
        
        report_lines.extend([
            "",
            "## Transcript with Screenshots",
            ""
        ])
        
        # Add transcript with screenshots
        for segment in segments:
            # Format timestamp
            start_time = segment.get("start", 0)
            minutes = int(start_time) // 60
            seconds = int(start_time) % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            
            # Add segment text
            report_lines.append(f"### {timestamp} {segment.get('text', '')}")
            report_lines.append("")
            
            # Add screenshots if any
            screenshots = segment.get("screenshots", [])
            for i, screenshot in enumerate(screenshots):
                file_path = screenshot.get("file", "")
                # Use relative path for markdown
                rel_path = f"screenshots/{Path(file_path).name}"
                report_lines.append(f"![Screenshot {i+1}]({rel_path})")
                report_lines.append("")
            
            if screenshots:
                report_lines.append("---")
                report_lines.append("")
        
        return "\n".join(report_lines)


if __name__ == "__main__":
    # Simple test code
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ai_module.py <meeting_path>")
        sys.exit(1)
    
    meeting_path = sys.argv[1]
    
    ai = AIModule()
    result = ai.process_meeting(meeting_path)
    
    if result.get("success"):
        print(f"Meeting processed successfully")
        print(f"Report saved to: {result.get('report_file')}")
        print(f"Insights saved to: {result.get('insights_file')}")
    else:
        print(f"Processing failed: {result.get('message')}")