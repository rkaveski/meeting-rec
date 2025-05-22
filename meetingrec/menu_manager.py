import rumps
import logging

from typing import Dict, Callable, Optional

logger = logging.getLogger("meetingrec.menu_manager")

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
        
        # Set the app's menu directly
        self.app.menu = [
            start_recording,
            stop_recording,
            None,  # separator
            capture_screenshot,
            None,  # separator
            show_meetings,
            open_config
        ]
        
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