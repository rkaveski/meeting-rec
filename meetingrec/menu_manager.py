import rumps
import logging
import importlib.util
import sys

from pathlib import Path
from typing import Dict, Callable, Optional

logger = logging.getLogger("meetingrec.menu_manager")

def get_version() -> str:
    """Get the application version from setup.py"""
    try:
        # Find the setup.py file in the parent directory
        setup_path = Path(__file__).resolve().parent.parent / "setup.py"
        
        if not setup_path.exists():
            logger.warning(f"setup.py not found at {setup_path}")
            return "Unknown"
            
        # Load the setup module
        spec = importlib.util.spec_from_file_location("setup", setup_path)
        setup = importlib.util.module_from_spec(spec)
        sys.modules["setup"] = setup
        spec.loader.exec_module(setup)
        
        # Return the VERSION from setup.py
        return f"v{setup.VERSION}"
    except Exception as e:
        logger.error(f"Error getting version: {e}")
        return "Unknown"

class MenuManager:
    """
    Handles the creation and management of the application menu structure.
    Maintains direct references to menu items for reliable access.
    """
    
    def __init__(self, app: rumps.App, callbacks: Dict[str, Callable] = None):
        """
        Initialize the menu manager with a reference to the rumps app.
        
        Args:
            app: The rumps.App instance
            callbacks: Dictionary mapping menu keys to callback functions
        """
        self.app = app
        self.callbacks = callbacks or {}
        
        # Store direct references to important menu items
        self.menu_items: Dict[str, rumps.MenuItem] = {}
        
        # Create the menu structure
        self._create_menu_structure()
        
        logger.info("MenuManager initialized successfully")
    
    def _create_menu_structure(self) -> None:
        """Create the initial menu structure for the application."""
        logger.info("Creating menu structure")
        
        # Create menu items with callbacks directly attached
        start_recording = self._create_menu_item("start_recording", "Start Recording")
        stop_recording = self._create_menu_item("stop_recording", "Stop Recording")
        stop_recording.state = False  # Initially disabled
        capture_screenshot = self._create_menu_item("capture_screenshot", "Capture Screenshot")
        show_meetings = self._create_menu_item("show_meetings", "Show Meetings")
        open_config = self._create_menu_item("open_config", "Open Config")
        
        # Create version item (will show as disabled)
        version_text = "v. Unknown"
        try:
            # Read version directly from the file without importing
            import re
            from pathlib import Path
            
            setup_path = Path(__file__).resolve().parent.parent / "setup.py"
            if setup_path.exists():
                with open(setup_path, 'r') as f:
                    content = f.read()
                    # Look for VERSION = "x.y.z" pattern
                    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        version_text = f"v. {match.group(1)}"
        except Exception as e:
            logger.error(f"Error reading version: {e}")
        
        version_item = rumps.MenuItem(version_text)
        version_item.set_callback(None)  # No callback
        
        # Set the app's menu directly
        self.app.menu = [
            start_recording,
            stop_recording,
            None,  # separator
            capture_screenshot,
            None,  # separator
            show_meetings,
            open_config,
            None,  # separator
            version_item
        ]
        
        # Store reference to version item
        self.menu_items["version"] = version_item
        
        logger.info(f"Menu structure created with {len(self.menu_items)} items")
    
    def _create_menu_item(self, key: str, title: str) -> rumps.MenuItem:
        """
        Create a menu item, store a reference, and attach a callback if available.
        
        Args:
            key: The key to identify this menu item
            title: The display title for the menu item
            
        Returns:
            The created menu item
        """
        # Get the callback for this key if it exists
        callback = self.callbacks.get(key)
        
        # Create the menu item with or without a callback
        menu_item = rumps.MenuItem(title, callback=callback)
        
        # Store a reference
        self.menu_items[key] = menu_item
        
        return menu_item
    
    def get_menu_item(self, key: str) -> Optional[rumps.MenuItem]:
        """Get a menu item by its key."""
        return self.menu_items.get(key)
    
    def set_menu_state(self, key: str, enabled: bool) -> None:
        """Set the state of a menu item."""
        menu_item = self.menu_items.get(key)
        if menu_item:
            menu_item.state = enabled
        else:
            logger.error(f"Menu item not found: {key}")