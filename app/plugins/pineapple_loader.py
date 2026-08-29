#!/usr/bin/env python3
"""
Hak5 Pineapple Module Loader Plugin

This plugin enables loading and executing Hak5 Pineapple modules directly
from the uConsole Status App.
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any


def debug_log(message: str):
    """Write debug message to log file with timestamp."""
    try:
        timestamp = time.strftime("%H:%M:%S")
        DEBUG_LOG = Path("/home/bcaddy/uconsole-k7bat/pineapple_debug.log")
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        pass  # Don't let logging fail the app


class Request:
    """Simplified Request class for module actions."""
    
    def __init__(self, data: Dict[str, Any] = None):
        self._data = data or {}
        self.user_input = self._data.get('user_input', '')
        self.command = self._data.get('command', '')
        self.input_iface = self._data.get('input_iface', '')
        self.output_iface = self._data.get('output_iface', '')
        self.install = self._data.get('install', False)
        self.output_file = self._data.get('output_file', '')
        
    def __getitem__(self, key):
        return self._data.get(key)


class PineappleModule:
    """Simplified Module class for executing actions."""
    
    def __init__(self, name: str, log_level=logging.INFO):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.handles_action = {}
        
    def handles_action(self, action_name: str):
        """Decorator to register an action handler."""
        def decorator(func):
            self.handles_action[action_name] = func
            return func
        return decorator
        
    def start(self):
        """Start the module (placeholder)."""
        pass

# Add app directory to path for imports
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

# Active modules directory - updated to point to the actual modules location
ACTIVE_MODULES_DIR = Path("/home/bcaddy/uconsole-k7bat/pineapple-modules-full")


class PineappleModuleLoader:
    """Load and execute Hak5 Pineapple modules."""
    
    def __init__(self, modules_dir: Optional[Path] = None):
        """
        Initialize the module loader.
        
        Args:
            modules_dir: Directory containing pineapple modules (default: /home/bcaddy/uconsole-k7bat/pineapple-modules-full)
        """
        self.modules_dir = modules_dir or ACTIVE_MODULES_DIR
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        
        self.loaded_modules: Dict[str, PineappleModule] = {}
        self.logger = logging.getLogger(__name__)
        
    def discover_modules(self) -> List[Dict[str, Any]]:
        """Discover all available modules in the modules directory."""
        debug_log(f"[DEBUG] discover_modules called, modules_dir={self.modules_dir}")
        debug_log(f"[DEBUG] modules_dir exists: {self.modules_dir.exists()}")
        modules = []
        
        if not self.modules_dir.exists():
            debug_log("[DEBUG] modules_dir does not exist, returning empty list")
            return modules
        
        # First, try to load from standard module.json in each subdirectory
        debug_log(f"[DEBUG] Iterating through directory...")
        for module_path in self.modules_dir.iterdir():
            debug_log(f"[DEBUG] Found path: {module_path}")
            if module_path.is_dir():
                # Try standard location first (projects/{name}/src/module.json)
                metadata = self._load_module_metadata(module_path / "projects" / module_path.name / "src")
                
                # If not found, try root of module directory
                if not metadata:
                    metadata = self._load_module_metadata(module_path)
                
                if metadata:
                    debug_log(f"[DEBUG] Loaded metadata for {metadata.get('name', 'unknown')}: {metadata.keys()}")
                    modules.append(metadata)
                    
        debug_log(f"[DEBUG] discover_modules found {len(modules)} modules")
        return modules
    
    def _load_module_metadata(self, module_dir: Path) -> Optional[Dict[str, Any]]:
        """Load module metadata from module.json."""
        debug_log(f"[DEBUG] _load_module_metadata called for {module_dir}")
        metadata_file = module_dir / "module.json"
        
        if not metadata_file.exists():
            self.logger.warning(f"No module.json found in {module_dir}")
            debug_log(f"[DEBUG] No module.json in {module_dir}, returning None")
            return None
            
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                
            # Add additional info
            metadata['path'] = str(module_dir)
            
            # Load Python module if exists
            python_module = module_dir / "module.py"
            if python_module.exists():
                metadata['has_python'] = True
                metadata['python_path'] = str(python_module)
            else:
                metadata['has_python'] = False
                
            debug_log(f"[DEBUG] _load_module_metadata succeeded for {metadata.get('name', 'unknown')}")
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error loading metadata from {module_dir}: {e}")
            debug_log(f"[DEBUG] _load_module_metadata error: {e}")
            return None
    
    def load_module(self, module_name: str) -> Optional[PineappleModule]:
        """
        Load a pineapple module by name.
        
        Args:
            module_name: Name of the module to load
            
        Returns:
            Module instance or None if loading fails
        """
        module_path = self.modules_dir / module_name
        
        if not module_path.exists():
            self.logger.error(f"Module {module_name} not found")
            return None
            
        # Check for Python module
        python_module = module_path / "module.py"
        if not python_module.exists():
            self.logger.error(f"No module.py found in {module_path}")
            return None
        
        try:
            # Import the module
            sys.path.insert(0, str(module_path))
            
            # Read and execute the module
            with open(python_module, 'r') as f:
                module_code = f.read()
                
            # Create a module namespace
            module_globals = {
                '__file__': str(python_module),
                '__name__': f"pineapple.modules.{module_name}",
                'logging': logging,
                'subprocess': subprocess,
                'json': json,
            }
            
            # Execute the module code
            exec(module_code, module_globals)
            
            # Get the module instance
            module_instance = module_globals.get('module')
            
            if module_instance:
                self.loaded_modules[module_name] = module_instance
                return module_instance
                
        except Exception as e:
            self.logger.error(f"Error loading module {module_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
        finally:
            # Clean up path
            if str(module_path) in sys.path:
                sys.path.remove(str(module_path))
                
        return None
    
    def execute_action(self, module_name: str, action: str, 
                      user_input: Optional[str] = None,
                      **kwargs) -> Dict[str, Any]:
        """
        Execute an action on a loaded module.
        
        Args:
            module_name: Name of the module
            action: Action name to execute
            user_input: Optional user input string
            **kwargs: Additional parameters
            
        Returns:
            Result dictionary from the action
        """
        module = self.loaded_modules.get(module_name)
        
        if not module:
            # Try to load it
            module = self.load_module(module_name)
            
        if not module:
            return {'error': f"Module {module_name} not found or failed to load"}
        
        try:
            # Create a request object
            request_data = kwargs.copy()
            if user_input:
                request_data['user_input'] = user_input
                
            request = Request(request_data)
            
            # Call the action handler
            if hasattr(module, 'handles_action') and action in module.handles_action:
                handler = module.handles_action[action]
                result = handler(request)
                
                if isinstance(result, dict):
                    return result
                else:
                    return {'result': str(result)}
                    
        except Exception as e:
            self.logger.error(f"Error executing action {action} on {module_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {'error': str(e)}
            
        return {'error': f"Action {action} not found in module {module_name}"}


# Global loader instance
_loader = None


def get_loader() -> PineappleModuleLoader:
    """Get or create the global loader instance."""
    global _loader
    
    if _loader is None:
        _loader = PineappleModuleLoader()
        
    return _loader


def load_module(module_name: str) -> Optional[PineappleModule]:
    """Load a module by name using the global loader."""
    return get_loader().load_module(module_name)


def execute_action(module_name: str, action: str,
                  user_input: Optional[str] = None,
                  **kwargs) -> Dict[str, Any]:
    """Execute an action using the global loader."""
    return get_loader().execute_action(module_name, action, user_input, **kwargs)


