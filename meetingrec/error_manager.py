import sys
import logging
import traceback
import rumps

from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path


# Configure logging
LOG_DIR = Path.home() / ".meetingrec" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "meetingrec.log"

# Set up logger with both file and console output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)  # Explicitly add stdout handler
    ]
)

logger = logging.getLogger("meetingrec")

class ErrorCategory(Enum):
    """Categories of errors for better organization and handling."""
    CONFIGURATION = "Configuration Error"
    RECORDING = "Recording Error"
    TRANSCRIPTION = "Transcription Error"
    SCREENSHOT = "Screenshot Error"
    NETWORK = "Network Error"
    API = "API Error"
    PERMISSION = "Permission Error"
    DEPENDENCY = "Dependency Error"
    FILESYSTEM = "File System Error"
    UNKNOWN = "Unknown Error"

class MeetingRecError(Exception):
    """Base exception class for all MeetingRec errors."""
    
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN, 
                 details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.category = category
        self.details = details or {}
        super().__init__(self.message)

class ConfigError(MeetingRecError):
    """Error related to configuration."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.CONFIGURATION, details)

class RecordingError(MeetingRecError):
    """Error related to audio recording."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.RECORDING, details)

class TranscriptionError(MeetingRecError):
    """Error related to transcription."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.TRANSCRIPTION, details)

class ScreenshotError(MeetingRecError):
    """Error related to screenshot capture."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.SCREENSHOT, details)

class NetworkError(MeetingRecError):
    """Error related to network connectivity."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.NETWORK, details)

class APIError(MeetingRecError):
    """Error related to API calls."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.API, details)

class PermissionError(MeetingRecError):
    """Error related to permissions."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.PERMISSION, details)

class DependencyError(MeetingRecError):
    """Error related to missing dependencies."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.DEPENDENCY, details)

class FilesystemError(MeetingRecError):
    """Error related to file system operations."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.FILESYSTEM, details)

class ErrorManager:
    """Centralized error management system for MeetingRec."""
    
    def __init__(self):
        """Initialize the error manager."""
        self.last_error = None
        self.error_count = 0
        self.error_handlers = {}
        
    def register_handler(self, category: ErrorCategory, handler: Callable):
        """Register a handler for a specific error category.
        
        Args:
            category: The category of error to handle
            handler: The function to call when this error occurs
        """
        self.error_handlers[category] = handler
        
    def handle_error(self, error: MeetingRecError, show_notification: bool = True) -> Dict[str, Any]:
        """Handle an error by logging it and optionally showing a notification."""
        self.last_error = error
        self.error_count += 1
        
        # Log the error
        logger.error(f"{error.category.value}: {error.message}")
        if error.details:
            logger.error(f"Details: {error.details}")
        
        if isinstance(error.__cause__, Exception):
            logger.error(f"Caused by: {error.__cause__}")
            logger.debug(traceback.format_exc())
        
        # Call specific handler if registered
        if error.category in self.error_handlers:
            self.error_handlers[error.category](error)
        
        # Show notification
        if show_notification:
            safe_notification(
                "MeetingRec", 
                error.category.value,
                error.message
            )
        
        # Return standardized error response
        return {
            "success": False,
            "error": True,
            "category": error.category.value,
            "message": error.message,
            "details": error.details
        }
    
    def capture_exception(self, context: str = ""):
        """Capture an exception from a try/except block.
        
        This is intended to be called from an except block.
        
        Args:
            context: Additional context for the error
            
        Returns:
            A standardized error response dictionary
        """
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        if exc_type is None:
            return {
                "success": True,
                "message": "No exception to capture"
            }
        
        # Get full traceback
        tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Log the exception
        if context:
            logger.error(f"Exception in {context}: {exc_value}")
        else:
            logger.error(f"Exception: {exc_value}")
        logger.debug(tb_str)
        
        # Determine error category based on exception type
        category = ErrorCategory.UNKNOWN
        if "permission" in str(exc_value).lower():
            category = ErrorCategory.PERMISSION
        elif "network" in str(exc_value).lower() or "connection" in str(exc_value).lower():
            category = ErrorCategory.NETWORK
        elif "file" in str(exc_value).lower() or "directory" in str(exc_value).lower():
            category = ErrorCategory.FILESYSTEM
        elif "api" in str(exc_value).lower():
            category = ErrorCategory.API
        
        # Create appropriate error
        if category == ErrorCategory.PERMISSION:
            error = PermissionError(str(exc_value), {"traceback": tb_str, "context": context})
        elif category == ErrorCategory.NETWORK:
            error = NetworkError(str(exc_value), {"traceback": tb_str, "context": context})
        elif category == ErrorCategory.FILESYSTEM:
            error = FilesystemError(str(exc_value), {"traceback": tb_str, "context": context})
        elif category == ErrorCategory.API:
            error = APIError(str(exc_value), {"traceback": tb_str, "context": context})
        else:
            error = MeetingRecError(str(exc_value), category, {"traceback": tb_str, "context": context})
        
        # Handle the error
        return self.handle_error(error)
    
    def check_dependencies(self) -> List[Dict[str, Any]]:
        """Check for required dependencies and return list of issues.
        
        Returns:
            List of error dictionaries for missing dependencies
        """
        # No current OS dependencies, just python ones
        return []

    def check_permissions(self) -> List[Dict[str, Any]]:
        """Check for required permissions and return list of issues.
        
        Returns:
            List of error dictionaries for missing permissions
        """
        issues = []
        
        # Check for microphone permission
        # Note: The actual permission is requested when the app first uses the mic
        # This just checks if we've been denied before
        try:
            # We'd need to use AVFoundation to check this properly
            # For now, we just log that we can't check permissions
            logger.info("Permission checking not implemented yet")
        except Exception:
            logger.error("Error checking permissions")
        
        return issues

# Global error manager instance
error_manager = ErrorManager()

# Convenience function for error handling in functions
def safe_execute(func):
    """Decorator for safely executing functions with error handling.
    
    This decorator catches exceptions, logs them, and returns a standardized error response.
    
    Args:
        func: The function to wrap with error handling
        
    Returns:
        The wrapped function
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MeetingRecError as e:
            return error_manager.handle_error(e)
        except Exception as e:
            context = f"{func.__module__}.{func.__name__}"
            return error_manager.capture_exception(context)
    return wrapper

def safe_notification(title, subtitle, message):
    """Show a notification with fallback for development mode.
    
    Args:
        title: Notification title
        subtitle: Notification subtitle
        message: Notification message
    """
    # Always log notification to console for development
    console_message = f"\n[NOTIFICATION] {title}: {subtitle}\n{message}\n"
    print(console_message)
    
    try:
        rumps.notification(title, subtitle, message)
    except Exception as e:
        logger.warning(f"Could not show system notification: {e}")
        logger.info(f"Notification was shown in console only: {title} - {subtitle} - {message}")