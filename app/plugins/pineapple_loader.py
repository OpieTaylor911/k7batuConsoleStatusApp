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
from pathlib import Path
from typing import Dict, List, Optional, Any


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


class PineappleModuleLoader:
    """Load and execute Hak5 Pineapple modules."""
    
    def __init__(self, modules_dir: Optional[Path] = None):
        """
        Initialize the module loader.
        
        Args:
            modules_dir: Directory containing pineapple modules (default: ~/.config/k7bat-uconsole-status/pineapple_modules)
        """
        self.modules_dir = modules_dir or Path.home() / ".config" / "k7bat-uconsole-status" / "pineapple_modules"
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        
        self.loaded_modules: Dict[str, PineappleModule] = {}
        self.logger = logging.getLogger(__name__)
        
    def discover_modules(self) -> List[Dict[str, Any]]:
        """Discover all available modules in the modules directory."""
        modules = []
        
        if not self.modules_dir.exists():
            return modules
            
        for module_path in self.modules_dir.iterdir():
            if module_path.is_dir():
                metadata = self._load_module_metadata(module_path)
                if metadata:
                    modules.append(metadata)
                    
        return modules
    
    def _load_module_metadata(self, module_dir: Path) -> Optional[Dict[str, Any]]:
        """Load module metadata from module.json."""
        metadata_file = module_dir / "module.json"
        
        if not metadata_file.exists():
            self.logger.warning(f"No module.json found in {module_dir}")
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
                
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error loading metadata from {module_dir}: {e}")
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


