#!/usr/bin/env python3
"""
Plugin Manager - Load and manage plugins with configuration system.

This module provides utilities for loading plugins, checking their
configuration, and running them with proper dependency management.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple


class PluginManager:
    """Manages plugin loading and execution."""
    
    def __init__(self, plugins_dir: Optional[Path] = None):
        """
        Initialize the plugin manager.
        
        Args:
            plugins_dir: Directory containing plugins. Defaults to 'plugins' subdirectory
                        of the directory containing this file.
        """
        if plugins_dir is None:
            plugins_dir = Path(__file__).resolve().parent
        
        self.plugins_dir = plugins_dir
        self.loaded_plugins: Dict[str, dict] = {}
        self.plugin_configs: Dict[str, dict] = {}
    
    def discover_plugins(self) -> List[Path]:
        """Find all plugin files in the plugins directory."""
        plugins = []
        
        # Look for __init__.py files (package plugins)
        for item in self.plugins_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                plugins.append(item / "__init__.py")
            elif item.suffix == ".py" and item.name != "__init__.py":
                # Single file plugins
                plugins.append(item)
        
        return plugins
    
    def load_plugin(self, plugin_path: Path) -> Optional[dict]:
        """
        Load a plugin from its path.
        
        Args:
            plugin_path: Path to the plugin file or directory
            
        Returns:
            Plugin configuration dictionary or None if loading failed
        """
        try:
            # Determine module name
            if plugin_path.is_dir():
                module_name = plugin_path.name
                init_file = plugin_path / "__init__.py"
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{module_name}", init_file
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugins.{module_name}"] = module
                spec.loader.exec_module(module)
                
                # Check for plugin_config module first
                config_path = plugin_path / "plugin_config.py"
                if config_path.exists():
                    spec = importlib.util.spec_from_file_location(
                        f"plugins.{module_name}.config", config_path
                    )
                    config_module = importlib.util.module_from_spec(spec)
                    sys.modules[f"plugins.{module_name}.config"] = config_module
                    spec.loader.exec_module(config_module)
                    
                    # Get configuration from plugin_config.py
                    config = self._extract_plugin_config(config_module)
                else:
                    # Try to get config from __init__.py
                    config = self._extract_plugin_config(module)
                
            else:
                module_name = plugin_path.stem
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{module_name}", plugin_path
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugins.{module_name}"] = module
                spec.loader.exec_module(module)
                
                config = self._extract_plugin_config(module)
            
            if config:
                self.loaded_plugins[module_name] = {
                    "path": plugin_path,
                    "module": module
                }
                self.plugin_configs[module_name] = config
                
                return config
            
        except Exception as e:
            print(f"Error loading plugin {plugin_path}: {e}", file=sys.stderr)
        
        return None
    
    def _extract_plugin_config(self, module) -> Optional[dict]:
        """
        Extract plugin configuration from a module.
        
        Args:
            module: Loaded Python module
            
        Returns:
            Plugin configuration dictionary
        """
        config = {}
        
        # Try to get PLUGIN_NAME (required)
        if hasattr(module, "PLUGIN_NAME"):
            config["name"] = getattr(module, "PLUGIN_NAME")
        else:
            return None  # No plugin metadata found
        
        # Optional attributes
        config["version"] = getattr(module, "PLUGIN_VERSION", "1.0.0")
        config["requires_sudo"] = getattr(module, "REQUIRES_SUDO", False)
        config["install_packages"] = getattr(module, "INSTALL_PACKAGES", [])
        config["setup_instructions"] = getattr(module, "SETUP_INSTRUCTIONS", "")
        config["permission_commands"] = getattr(module, "PERMISSION_COMMANDS", [])
        
        # Check for utility functions
        if hasattr(module, "get_plugin_info"):
            info_func = getattr(module, "get_plugin_info")
            if callable(info_func):
                info = info_func()
                config.update(info)
        
        return config
    
    def load_all_plugins(self) -> Dict[str, dict]:
        """Load all plugins in the plugins directory."""
        plugins = self.discover_plugins()
        
        for plugin_path in plugins:
            config = self.load_plugin(plugin_path)
            if config:
                print(f"Loaded plugin: {config['name']}")
        
        return self.plugin_configs
    
    def check_dependencies(self, plugin_name: str) -> Tuple[bool, List[str]]:
        """
        Check dependencies for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Tuple of (all_ok: bool, missing_packages: list)
        """
        if plugin_name not in self.plugin_configs:
            return False, []
        
        config = self.plugin_configs[plugin_name]
        packages = config.get("install_packages", [])
        
        import subprocess
        missing = []
        
        for package in packages:
            try:
                result = subprocess.run(
                    ["dpkg-query", "-W", "-f='${Status}'", package],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "install ok installed" not in result.stdout.lower():
                    missing.append(package)
            except Exception:
                pass
        
        return len(missing) == 0, missing
    
    def get_plugin_info(self, plugin_name: str) -> Optional[dict]:
        """Get information about a specific plugin."""
        return self.plugin_configs.get(plugin_name)
    
    def list_plugins(self) -> List[str]:
        """List all loaded plugin names."""
        return list(self.plugin_configs.keys())


# ============================================================================
# Standalone Functions (convenience wrappers)
# ============================================================================

def load_plugin_from_path(plugin_path: Path) -> Optional[dict]:
    """
    Load a single plugin from its path.
    
    Args:
        plugin_path: Path to the plugin file or directory
        
        Returns:
            Plugin configuration dictionary
    """
    manager = PluginManager()
    return manager.load_plugin(plugin_path)


def load_all_plugins() -> Dict[str, dict]:
    """
    Load all plugins in the default plugins directory.
    
    Returns:
        Dictionary of plugin configurations keyed by plugin name
    """
    manager = PluginManager()
    return manager.load_all_plugins()


# ============================================================================
# Main Entry Point (for testing)
# ============================================================================

if __name__ == "__main__":
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    
    print("Loading plugins...")
    
    # Load all plugins
    manager = PluginManager()
    configs = manager.load_all_plugins()
    
    print(f"\nLoaded {len(configs)} plugins:")
    for name, config in configs.items():
        print(f"  - {config.get('name', name)} v{config.get('version', '1.0.0')}")
        
        # Check dependencies
        ok, missing = manager.check_dependencies(name)
        if ok:
            print(f"    ✓ Dependencies satisfied")
        else:
            print(f"    ✗ Missing: {', '.join(missing)}")
        
        if config.get("requires_sudo"):
            print(f"    ⚠ Requires root privileges")
    
    # Test showing setup dialog
    if configs:
        plugin_name = list(configs.keys())[0]
        config = configs[plugin_name]
        
        dialog = Gtk.MessageDialog(
            None,
            0,
            Gtk.MessageType.INFO,
            Gtk.ButtonsType.OK,
            f"Plugin System Ready!\n\n"
            f"Loaded {len(configs)} plugins.\n"
            f"First plugin: {config.get('name', 'Unknown')}\n"
            f"Requires Sudo: {config.get('requires_sudo', False)}"
        )
        dialog.run()
        dialog.destroy()
