#!/usr/bin/env python3
"""
MeetingRec - AI-powered meeting recorder and transcription tool

This is the main entry point for the application.
"""
import sys
import os
import traceback
import logging

# Add the current directory to the path so we can import meetingrec
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up basic console logging before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("meetingrec.startup")
logger.info("Starting MeetingRec...")

try:
    from meetingrec.menu_bar_app import MeetingRecApp
    from meetingrec.error_manager import error_manager
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    print("Make sure all dependencies are installed.")
    sys.exit(1)

if __name__ == "__main__":
    try:
        logger.info("Initializing application...")
        app = MeetingRecApp()
        app.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        traceback.print_exc()
        
        try:
            # Try to capture through error manager
            error_info = error_manager.capture_exception("Application startup")
            logger.error(f"Error details: {error_info.get('message', 'Unknown error')}")
        except Exception:
            # Last resort error handling
            logger.error("Could not use error manager to handle exception")
            
        sys.exit(1)