#!/usr/bin/env python3
"""
Secure Remote Assist Mode - Diagnostics Bundle Generator
Provides temporary diagnostics bundle workflow with tokenized upload path.
"""

import os
import sys
import subprocess
import tempfile
import tarfile
from datetime import datetime
from pathlib import Path


class DiagnosticsBundle:
    """Creates and manages diagnostic bundles for remote assistance."""
    
    def __init__(self):
        self.bundle_name = f"uconsole-diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.output_dir = Path.home() / "Downloads"
        self.output_file = self.output_dir / f"{self.bundle_name}.tar.gz"
        
    def create_bundle(self):
        """Create a compressed archive of system diagnostics."""
        print(f"Creating diagnostics bundle: {self.bundle_name}")
        print(f"Output will be saved to: {self.output_file}")
        print()
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = Path(temp_dir) / self.bundle_name
            bundle_path.mkdir()
            
            # Collect diagnostics
            steps = [
                ("System Information", self._collect_system_info),
                ("Network Configuration", self._collect_network_config),
                ("Wi-Fi Status", self._collect_wifi_status),
                ("GPS Status", self._collect_gps_status),
                ("AIO Controller", self._collect_aio_status),
                ("Running Services", self._collect_services_status),
                ("USB Devices", self._collect_usb_devices),
                ("Hardware Monitors", self._collect_hardware_monitors),
                ("Application Logs", self._collect_app_logs),
                ("Configuration Files", self._collect_config_files),
                ("File System Status", self._collect_filesystem_status),
            ]
            
            for i, (name, collector) in enumerate(steps, 1):
                print(f"[{i}/{len(steps)}] {name}...")
                try:
                    collector(bundle_path)
                except Exception as e:
                    print(f"  Warning: Failed to collect {name}: {e}")
            
            # Create summary
            self._create_summary(bundle_path)
            
            # Create compressed archive
            return self._create_archive(bundle_path, temp_dir)
    
    def _collect_system_info(self, bundle_path):
        """Collect system information."""
        output = bundle_path / "system_info.txt"
        with open(output, 'w') as f:
            f.write("=== OS Information ===\n")
            try:
                with open('/etc/os-release') as os_release:
                    f.write(os_release.read())
            except Exception as e:
                f.write(f"Unable to read os-release: {e}\n")
            
            f.write("\n=== Kernel Version ===\n")
            try:
                result = subprocess.run(['uname', '-r'], capture_output=True, text=True)
                f.write(result.stdout)
            except Exception as e:
                f.write(f"uname failed: {e}\n")
            
            f.write("\n=== Hardware Model ===\n")
            try:
                with open('/proc/device-tree/model', 'rb') as model_file:
                    f.write(model_file.read().decode('utf-8', errors='ignore'))
            except Exception as e:
                f.write(f"Unable to read hardware model: {e}\n")
    
    def _collect_network_config(self, bundle_path):
        """Collect network configuration."""
        output = bundle_path / "network_config.txt"
        with open(output, 'w') as f:
            f.write("=== Network Interfaces ===\n")
            try:
                result = subprocess.run(['ip', '-br', 'link', 'show'], capture_output=True, text=True)
                f.write(result.stdout + "\n")
            except Exception as e:
                f.write(f"ip command failed: {e}\n")
            
            f.write("=== IP Addresses ===\n")
            try:
                result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
                f.write(result.stdout + "\n")
            except Exception as e:
                f.write(f"ip addr failed: {e}\n")
            
            f.write("=== Routing Table ===\n")
            try:
                result = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True)
                f.write(result.stdout + "\n")
            except Exception as e:
                f.write(f"ip route failed: {e}\n")
            
            f.write("=== Wi-Fi Interfaces ===\n")
            try:
                result = subprocess.run(['iw', 'dev'], capture_output=True, text=True)
                f.write(result.stdout)
            except Exception as e:
                f.write(f"iw dev failed: {e}\n")
    
    def _collect_wifi_status(self, bundle_path):
        """Collect Wi-Fi status."""
        output = bundle_path / "wifi_status.txt"
        with open(output, 'w') as f:
            f.write("=== Active Wi-Fi Connections ===\n")
            try:
                result = subprocess.run(['nmcli', 'connection', 'show', '--active'], 
                                      capture_output=True, text=True)
                f.write(result.stdout if result.stdout else "No active connections\n")
            except Exception as e:
                f.write(f"nmcli failed: {e}\n")
            
            f.write("\n=== Wi-Fi Signal Strength ===\n")
            try:
                with open('/proc/net/wireless') as wireless:
                    f.write(wireless.read())
            except Exception as e:
                f.write(f"No wireless data: {e}\n")
    
    def _collect_gps_status(self, bundle_path):
        """Collect GPS status."""
        output = bundle_path / "gps_status.txt"
        with open(output, 'w') as f:
            f.write("=== GPSD Status ===\n")
            try:
                result = subprocess.run(['systemctl', 'status', 'gpsd', '--no-pager', '-l'], 
                                      capture_output=True, text=True)
                f.write(result.stdout)
            except Exception as e:
                f.write(f"gpsd not running: {e}\n")
            
            f.write("\n=== GPS Position Sample ===\n")
            try:
                result = subprocess.run(['timeout', '3', 'gpspipe', '-w', '-n', '5'], 
                                      capture_output=True, text=True)
                f.write(result.stdout if result.stdout else "No GPS data\n")
            except Exception as e:
                f.write(f"gpspipe failed: {e}\n")
            
            f.write("\n=== GPS Device Info ===\n")
            try:
                devices = subprocess.run(['ls', '-la', '/dev/ttyACM*', '/dev/ttyUSB*'], 
                                       capture_output=True, text=True)
                if 'No such file' not in devices.stderr:
                    f.write(devices.stdout)
                else:
                    f.write("No GPS device found\n")
            except Exception as e:
                f.write(f"Error listing devices: {e}\n")
    
    def _collect_aio_status(self, bundle_path):
        """Collect AIO controller status."""
        output = bundle_path / "aio_status.txt"
        with open(output, 'w') as f:
            f.write("=== AIO Controller Status ===\n")
            try:
                result = subprocess.run(['aiov2_ctl', '--status'], capture_output=True, text=True)
                f.write(result.stdout if result.stdout else "aiov2_ctl failed\n")
            except Exception as e:
                f.write(f"aiov2_ctl failed: {e}\n")
            
            f.write("\n=== AIO Power States ===\n")
            for device in ['GPS', 'SDR', 'LORA', 'USB']:
                try:
                    result = subprocess.run(['aiov2_ctl', '--get', device.lower()], 
                                          capture_output=True, text=True)
                    state = result.stdout.strip() if result.stdout else "unknown"
                    f.write(f"{device}: {state}\n")
                except Exception as e:
                    f.write(f"{device}: error ({e})\n")
    
    def _collect_services_status(self, bundle_path):
        """Collect running services status."""
        output = bundle_path / "services_status.txt"
        with open(output, 'w') as f:
            f.write("=== Active Services ===\n")
            try:
                result = subprocess.run([
                    'systemctl', 'list-units', '--type=service', 
                    '--state=running', '--no-pager'
                ], capture_output=True, text=True)
                f.write(result.stdout[:5000] if result.stdout else "No services\n")
            except Exception as e:
                f.write(f"systemctl failed: {e}\n")
            
            f.write("\n=== Service Status Details ===\n")
            for svc in ['gpsd', 'readsb', 'kismet']:
                try:
                    result = subprocess.run(
                        ['systemctl', 'status', svc, '--no-pager', '-l'], 
                        capture_output=True, text=True
                    )
                    f.write(f"--- {svc} ---\n{result.stdout}\n\n")
                except Exception as e:
                    f.write(f"{svc} not found: {e}\n\n")
    
    def _collect_usb_devices(self, bundle_path):
        """Collect USB device information."""
        output = bundle_path / "usb_devices.txt"
        with open(output, 'w') as f:
            f.write("=== USB Devices ===\n")
            try:
                result = subprocess.run(['lsusb', '-v'], capture_output=True, text=True)
                f.write(result.stdout[:10000] if result.stdout else "lsusb failed\n")
            except Exception as e:
                f.write(f"lsusb failed: {e}\n")
            
            f.write("\n=== USB Bus Info ===\n")
            try:
                result = subprocess.run(['lsusb', '-t'], capture_output=True, text=True)
                f.write(result.stdout if result.stdout else "lsusb -t failed\n")
            except Exception as e:
                f.write(f"lsusb -t failed: {e}\n")
    
    def _collect_hardware_monitors(self, bundle_path):
        """Collect hardware monitor data."""
        output = bundle_path / "hardware_monitors.txt"
        with open(output, 'w') as f:
            f.write("=== CPU Temperature ===\n")
            try:
                thermal = Path('/sys/class/thermal')
                for zone in thermal.glob('thermal_zone*'):
                    temp_file = zone / 'temp'
                    if temp_file.exists():
                        with open(temp_file) as tf:
                            f.write(f"{zone.name}: {tf.read().strip()}°C\n")
            except Exception as e:
                f.write(f"No thermal data: {e}\n")
            
            f.write("\n=== CPU Frequency ===\n")
            try:
                with open('/proc/cpuinfo') as cpuinfo:
                    for line in cpuinfo:
                        if 'cpu MHz' in line or 'processor' in line:
                            f.write(line)
            except Exception as e:
                f.write(f"CPU info unavailable: {e}\n")
            
            f.write("\n=== Memory Usage ===\n")
            try:
                result = subprocess.run(['free', '-h'], capture_output=True, text=True)
                f.write(result.stdout)
            except Exception as e:
                f.write(f"free failed: {e}\n")
    
    def _collect_app_logs(self, bundle_path):
        """Collect application logs."""
        output = bundle_path / "app_logs.txt"
        with open(output, 'w') as f:
            f.write("=== uConsole Status App Log ===\n")
            app_log = Path.home() / ".local" / "share" / "k7bat-uconsole-status" / "app.log"
            try:
                if app_log.exists():
                    with open(app_log) as log_file:
                        lines = log_file.readlines()
                        f.write("".join(lines[-100:]))  # Last 100 lines
                else:
                    f.write("No application log found\n")
            except Exception as e:
                f.write(f"Unable to read app log: {e}\n")
            
            f.write("\n=== Recent System Logs (last 50 lines) ===\n")
            try:
                result = subprocess.run(['journalctl', '--no-pager', '-n', '50'], 
                                      capture_output=True, text=True)
                f.write(result.stdout[:10000] if result.stdout else "journalctl failed\n")
            except Exception as e:
                f.write(f"journalctl failed: {e}\n")
    
    def _collect_config_files(self, bundle_path):
        """Collect configuration files."""
        config_dir = bundle_path / "config"
        config_dir.mkdir()
        
        # Copy settings if exists
        settings_file = Path.home() / ".config" / "k7bat-uconsole-status" / "settings.json"
        try:
            if settings_file.exists():
                (config_dir / "settings.json").write_text(settings_file.read_text())
        except Exception as e:
            pass  # Ignore errors for optional files
        
        # Copy network interfaces if exists
        interfaces_file = Path('/etc/network/interfaces')
        try:
            if interfaces_file.exists():
                (config_dir / "interfaces").write_text(interfaces_file.read_text())
        except Exception as e:
            pass
    
    def _collect_filesystem_status(self, bundle_path):
        """Collect file system status."""
        output = bundle_path / "filesystem_status.txt"
        with open(output, 'w') as f:
            f.write("=== Disk Space ===\n")
            try:
                result = subprocess.run(['df', '-h'], capture_output=True, text=True)
                f.write(result.stdout)
            except Exception as e:
                f.write(f"df failed: {e}\n")
            
            f.write("\n=== Home Directory Size ===\n")
            try:
                config_size = Path.home() / ".config" / "k7bat-uconsole-status"
                if config_size.exists():
                    result = subprocess.run(
                        ['du', '-sh', str(config_size)], 
                        capture_output=True, text=True
                    )
                    f.write(result.stdout)
                else:
                    f.write("Config directory not found\n")
            except Exception as e:
                f.write(f"Unable to calculate size: {e}\n")
    
    def _create_summary(self, bundle_path):
        """Create summary file."""
        summary = bundle_path / "SUMMARY.txt"
        with open(summary, 'w') as f:
            f.write("uConsole Diagnostics Bundle\n")
            f.write("===========================\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            try:
                hostname = subprocess.run(['hostname'], capture_output=True, text=True)
                f.write(f"Hostname: {hostname.stdout.strip()}\n")
            except Exception:
                f.write("Hostname: unknown\n")
            
            f.write(f"Bundle Name: {self.bundle_name}\n\n")
            
            f.write("Contents:\n")
            try:
                for item in bundle_path.iterdir():
                    if item.is_file():
                        size = item.stat().st_size
                        f.write(f"  - {item.name}: {size} bytes\n")
            except Exception as e:
                f.write(f"Unable to list bundle contents: {e}\n")
    
    def _create_archive(self, bundle_path, temp_dir):
        """Create compressed archive."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        archive_path = str(self.output_file)
        full_bundle_path = str(bundle_path)
        
        try:
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(full_bundle_path, arcname=self.bundle_name)
            
            # Verify archive was created
            if self.output_file.exists():
                size = self.output_file.stat().st_size
                print(f"\n✓ Diagnostics bundle created successfully!")
                print(f"Location: {self.output_file}")
                print(f"Size: {size} bytes ({size / 1024:.1f} KB)")
                return str(self.output_file)
            else:
                print("Error: Archive file was not created")
                return None
                
        except Exception as e:
            print(f"Failed to create archive: {e}")
            return None


def main():
    """Main entry point."""
    bundle = DiagnosticsBundle()
    
    try:
        output_file = bundle.create_bundle()
        
        if output_file:
            print("\nTo upload this bundle, share it with your support contact.")
            print("They will provide a token to securely upload the file.")
            return 0
        else:
            print("Failed to create diagnostics bundle")
            return 1
            
    except KeyboardInterrupt:
        print("\nBundle creation cancelled")
        return 130
    except Exception as e:
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
