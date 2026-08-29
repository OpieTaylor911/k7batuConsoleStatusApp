#!/usr/bin/env python3
"""
Wi-Fi Assessment Module Loader Plugin

This plugin enables loading and executing Wi-Fi assessment tools
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
        DEBUG_LOG = Path("/home/bcaddy/uconsole-k7bat/wifi_assessment_debug.log")
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        pass  # Don't let logging fail the app


class WifiAssessmentModule:
    """Wi-Fi assessment module for executing actions."""
    
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


class WifiAssessmentLoader:
    """Load and execute Wi-Fi assessment tools."""
    
    def __init__(self, modules_dir: Optional[Path] = None):
        """
        Initialize the loader.
        
        Args:
            modules_dir: Optional custom modules directory
        """
        self.modules_dir = modules_dir or Path("/opt/wifi-hack-linux")
        # Check if we should use sudo (default: True)
        self.use_sudo = os.environ.get("WIFI_ASSESSMENT_NO_SUDO", "").lower() not in ("1", "true", "yes")
        debug_log(f"[DEBUG] WifiAssessmentLoader initialized with modules_dir={self.modules_dir}, use_sudo={self.use_sudo}")
        
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available Wi-Fi assessment tools."""
        tools = [
            {"id": "wifi_scan", "name": "Wi-Fi Network Scan", "description": "Scan for nearby networks"},
            {"id": "monitor_mode", "name": "Monitor Mode Toggle", "description": "Enable/disable monitor mode"},
            {"id": "deauth_test", "name": "Deauthentication Test", "description": "Test deauth frames (lab only)"},
            {"id": "handshake_capture", "name": "Handshake Capture", "description": "Capture 4-way handshake"},
            {"id": "crack_test", "name": "Password Crack Test", "description": "Test cracking with wordlist"}
        ]
        debug_log(f"[DEBUG] Found {len(tools)} available tools")
        return tools
        
    def execute_tool(self, tool_id: str, interface: str = "wlan0", **kwargs) -> tuple:
        """
        Execute a Wi-Fi assessment tool.
        
        Args:
            tool_id: ID of the tool to execute
            interface: Network interface to use
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        try:
            debug_log(f"[DEBUG] Executing tool {tool_id} on interface {interface}")
            
            if tool_id == "wifi_scan":
                cmd = ["sudo", "iwlist", interface, "scan"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                return (result.returncode == 0, result.stdout + result.stderr)
                
            elif tool_id == "monitor_mode":
                enable = kwargs.get("enable", True)
                if enable:
                    cmd = ["sudo", "airmon-ng", "start", interface]
                else:
                    cmd = ["sudo", "airmon-ng", "stop", f"{interface}mon"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                return (result.returncode == 0, result.stdout + result.stderr)
                
            elif tool_id == "deauth_test":
                target_bssid = kwargs.get("target_bssid", "ff:ff:ff:ff:ff:ff")
                target_client = kwargs.get("target_client", "00:00:00:00:00:00")
                count = kwargs.get("count", 10)
                cmd = ["sudo", "aireplay-ng", "--deauth", str(count), "-a", target_bssid, "-c", target_client, f"{interface}mon"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                return (result.returncode == 0, result.stdout + result.stderr)
                
            elif tool_id == "handshake_capture":
                bssid = kwargs.get("bssid", "")
                filter_expr = ""
                cmd = ["sudo", "airodump-ng", filter_expr, "-c", "6", "--write-interval", "1", "-w", "/tmp/handshake", f"{interface}mon"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                return (result.returncode == 0, result.stdout + result.stderr)
                
            elif tool_id == "crack_test":
                pcap_file = kwargs.get("pcap_file", "/tmp/handshake-01.cap")
                wordlist = kwargs.get("wordlist", "/usr/share/wordlists/rockyou.txt")
                cmd = ["sudo", "aircrack-ng", pcap_file, "-w", wordlist]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                return (result.returncode == 0, result.stdout + result.stderr)
                
            else:
                return (False, f"Unknown tool ID: {tool_id}")
                
        except subprocess.TimeoutExpired:
            debug_log(f"[ERROR] Tool execution timed out: {tool_id}")
            return (False, "Command timed out")
        except Exception as e:
            debug_log(f"[ERROR] Executing tool {tool_id}: {str(e)}")
            return (False, f"Error: {str(e)}")
