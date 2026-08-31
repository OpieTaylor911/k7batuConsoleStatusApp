#!/usr/bin/env python3

import os
import time
import glob
import shutil
import socket
import subprocess
from pathlib import Path

try:
    import serial
except ImportError:
    raise SystemExit(
        "pyserial is required. Install with: sudo apt install python3-serial"
    )


# ============================================================
# CONFIGURATION
# ============================================================

SERIAL_BAUD = 115200
UPDATE_INTERVAL = 3

# Leave as None to automatically find the ESP32.
SERIAL_DEVICE = None

# USB serial devices to try, in preferred order.
SERIAL_PATTERNS = [
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
]

TEMP_WARNING_C = 70
TEMP_CRITICAL_C = 80

BATTERY_WARNING_PERCENT = 20
BATTERY_CRITICAL_PERCENT = 10


# ============================================================
# STATUS CODES
# ============================================================

GREEN = "G"
YELLOW = "Y"
RED = "R"
BLUE = "B"
OFF = "X"


# ============================================================
# COMMAND HELPERS
# ============================================================

def run_command(command, timeout=2):
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False
        )

        return result.stdout.strip()

    except Exception:
        return ""


def command_exists(command):
    return shutil.which(command) is not None


def process_running(*names):
    """
    Return True if any supplied process name is running.
    """

    for name in names:
        try:
            result = subprocess.run(
                ["pgrep", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )

            if result.returncode == 0:
                return True

        except Exception:
            pass

    return False


def service_status(name):
    """
    Returns:
        G = active
        Y = activating/reloading
        R = failed
        B = installed but inactive
        X = service not found
    """

    if not command_exists("systemctl"):
        return OFF

    load_state = run_command([
        "systemctl",
        "show",
        name,
        "--property=LoadState",
        "--value"
    ])

    if load_state in ("not-found", ""):
        return OFF

    state = run_command([
        "systemctl",
        "is-active",
        name
    ])

    if state == "active":
        return GREEN

    if state in ("activating", "reloading"):
        return YELLOW

    if state == "failed":
        return RED

    return BLUE


# ============================================================
# SERIAL
# ============================================================

def find_serial_device():

    if SERIAL_DEVICE:
        if os.path.exists(SERIAL_DEVICE):
            return SERIAL_DEVICE

    devices = []

    for pattern in SERIAL_PATTERNS:
        devices.extend(glob.glob(pattern))

    if not devices:
        return None

    devices.sort()

    return devices[0]


def open_serial():

    while True:

        device = find_serial_device()

        if not device:
            print("Sidekick: ESP32 serial device not found.")
            time.sleep(3)
            continue

        try:
            print(f"Sidekick: connecting to {device}")

            ser = serial.Serial(
                device,
                SERIAL_BAUD,
                timeout=1,
                write_timeout=1
            )

            # ESP32 often resets when serial is opened.
            time.sleep(2)

            print("Sidekick: connected")

            return ser

        except Exception as exc:
            print(f"Sidekick: unable to open {device}: {exc}")
            time.sleep(3)


# ============================================================
# HARDWARE STATUS
# ============================================================

def sdr_status():

    # Check USB devices first.
    usb = run_command(["lsusb"])

    known_sdr = (
        "RTL2838",
        "RTL2832",
        "Realtek Semiconductor",
    )

    for signature in known_sdr:
        if signature.lower() in usb.lower():
            return GREEN

    # rtl_test may also identify hardware.
    if command_exists("rtl_test"):

        try:
            result = subprocess.run(
                ["rtl_test", "-t"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=3
            )

            text = result.stdout.lower()

            if "found 1 device" in text or "found" in text:
                return GREEN

        except Exception:
            pass

    return OFF


def gps_status():

    # gpspipe gives the best indication if gpsd is configured.
    if command_exists("gpspipe"):

        try:
            result = subprocess.run(
                ["gpspipe", "-w", "-n", "5"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=4,
            )

            data = result.stdout

            # TPV mode 2 or 3 means valid position.
            if '"mode":3' in data or '"mode": 3' in data:
                return GREEN

            if '"mode":2' in data or '"mode": 2' in data:
                return GREEN

            if data:
                return YELLOW

        except Exception:
            pass

    # Hardware present but no confirmed fix.
    candidates = [
        "/dev/ttyAMA0",
        "/dev/ttyAMA10",
        "/dev/serial0",
        "/dev/ttyUSB0",
        "/dev/ttyACM0",
    ]

    for device in candidates:
        if os.path.exists(device):
            return YELLOW

    return OFF


def network_status():

    if not command_exists("ip"):
        return OFF

    route = run_command(["ip", "route", "show", "default"])

    if not route:
        return RED

    # Try internet reachability.
    try:
        socket.create_connection(
            ("1.1.1.1", 53),
            timeout=1
        ).close()

        return GREEN

    except Exception:
        return YELLOW


def aio_status():

    # HackerGadgets AIO utility.
    possible_commands = [
        "aiov2_ctl",
        "aio_ctl",
    ]

    for command in possible_commands:
        if command_exists(command):
            return GREEN

    # Optional indicator file if your dashboard creates one.
    possible_files = [
        "/sys/class/rtc/rtc0",
        "/dev/ttyAMA0",
    ]

    if all(os.path.exists(p) for p in possible_files):
        return BLUE

    return OFF


# ============================================================
# BATTERY / POWER
# ============================================================

def find_battery():

    base = Path("/sys/class/power_supply")

    if not base.exists():
        return None

    for item in base.iterdir():

        type_file = item / "type"

        try:
            if type_file.read_text().strip().lower() == "battery":
                return item
        except Exception:
            continue

    return None


def battery_status():

    battery = find_battery()

    if not battery:
        return OFF

    try:
        capacity = int(
            (battery / "capacity").read_text().strip()
        )

        status = ""

        status_file = battery / "status"

        if status_file.exists():
            status = status_file.read_text().strip().lower()

        if capacity <= BATTERY_CRITICAL_PERCENT:
            return RED

        if capacity <= BATTERY_WARNING_PERCENT:
            return YELLOW

        if status == "charging":
            return BLUE

        return GREEN

    except Exception:
        return OFF


def power_status():

    battery = find_battery()

    if not battery:
        return BLUE

    try:

        status_file = battery / "status"

        if not status_file.exists():
            return BLUE

        status = status_file.read_text().strip().lower()

        if status == "charging":
            return BLUE

        if status == "full":
            return GREEN

        if status == "discharging":
            return GREEN

        return YELLOW

    except Exception:
        return OFF


# ============================================================
# TEMPERATURE
# ============================================================

def cpu_temperature():

    thermal = Path("/sys/class/thermal/thermal_zone0/temp")

    if not thermal.exists():
        return None

    try:
        value = int(thermal.read_text().strip())

        return value / 1000.0

    except Exception:
        return None


def temperature_status():

    temp = cpu_temperature()

    if temp is None:
        return OFF

    if temp >= TEMP_CRITICAL_C:
        return RED

    if temp >= TEMP_WARNING_C:
        return YELLOW

    return GREEN


# ============================================================
# BLUETOOTH
# ============================================================

def bluetooth_status():

    if not command_exists("bluetoothctl"):
        return OFF

    show = run_command(["bluetoothctl", "show"])

    if "Powered: yes" not in show:
        return RED

    info = run_command(["bluetoothctl", "devices", "Connected"])

    if info:
        return GREEN

    return BLUE


# ============================================================
# APPLICATIONS
# ============================================================

def sdrpp_status():

    if process_running(
        "sdrpp",
        "sdr++"
    ):
        return GREEN

    if command_exists("sdrpp"):
        return BLUE

    return OFF


def reaver_status():

    if process_running("reaver"):
        return GREEN

    if command_exists("reaver"):
        return BLUE

    return OFF


def vnc_status():

    processes = [
        "wayvnc",
        "x11vnc",
        "tigervnc",
        "Xtigervnc",
        "vncserver",
    ]

    if process_running(*processes):
        return GREEN

    services = [
        "wayvnc",
        "x11vnc",
        "tigervncserver",
    ]

    for service in services:

        state = service_status(service)

        if state == GREEN:
            return GREEN

    return BLUE


# ============================================================
# ADS-B STACK
# ============================================================

def adsb_status():

    readsb = service_status("readsb")

    if readsb == GREEN:
        return GREEN

    if process_running("readsb"):
        return GREEN

    return readsb


def gpsd_status():

    state = service_status("gpsd")

    if state != OFF:
        return state

    if process_running("gpsd"):
        return GREEN

    return OFF


def readsb_status():

    if process_running("readsb"):
        return GREEN

    return service_status("readsb")


def tar1090_status():

    state = service_status("tar1090")

    if state == GREEN:
        return GREEN

    # tar1090 sometimes isn't a persistent systemd process.
    common_paths = [
        "/usr/local/share/tar1090",
        "/usr/share/tar1090",
        "/var/www/html/tar1090",
    ]

    for path in common_paths:
        if os.path.exists(path):
            return BLUE

    return state


# ============================================================
# SYSTEM HEALTH
# ============================================================

def calculate_system_status(statuses):

    critical_keys = [
        "TEMP",
        "PWR",
        "BAT",
    ]

    for key in critical_keys:

        if statuses.get(key) == RED:
            return "FAULT"

    if RED in statuses.values():
        return "WARNING"

    if YELLOW in statuses.values():
        return "WARNING"

    return "SYSTEM NORMAL"


# ============================================================
# STATUS COLLECTION
# ============================================================

def collect_status():

    status = {}

    # --------------------------------------------------------
    # ROW 1 — HARDWARE
    # --------------------------------------------------------

    status["SDR"] = sdr_status()
    status["GPS"] = gps_status()
    status["NET"] = network_status()
    status["AIO"] = aio_status()
    status["BAT"] = battery_status()

    # --------------------------------------------------------
    # ROW 2 — ACTIVE TOOLS / SERVICES
    # --------------------------------------------------------

    status["SDR+"] = sdrpp_status()
    status["ADSB"] = adsb_status()
    status["GPSD"] = gpsd_status()
    status["VNC"] = vnc_status()
    status["RVR"] = reaver_status()

    # --------------------------------------------------------
    # ROW 3 — INFRASTRUCTURE
    # --------------------------------------------------------

    status["READ"] = readsb_status()
    status["TAR"] = tar1090_status()
    status["BT"] = bluetooth_status()
    status["TEMP"] = temperature_status()
    status["PWR"] = power_status()

    return status


# ============================================================
# SERIAL MESSAGE
# ============================================================

def build_message(status):

    sys_status = calculate_system_status(status)

    fields = []

    order = [
        "SDR",
        "GPS",
        "NET",
        "AIO",
        "BAT",

        "SDR+",
        "ADSB",
        "GPSD",
        "VNC",
        "RVR",

        "READ",
        "TAR",
        "BT",
        "TEMP",
        "PWR",
    ]

    for key in order:
        fields.append(
            f"{key}={status.get(key, OFF)}"
        )

    fields.append(
        f"SYS={sys_status}"
    )

    return ";".join(fields)


# ============================================================
# DEBUG OUTPUT
# ============================================================

def print_status(status):

    temp = cpu_temperature()

    print("")
    print("K7BAT Sidekick")

    print(
        " ".join(
            f"{k}:{v}"
            for k, v in status.items()
        )
    )

    if temp is not None:
        print(f"CPU Temp: {temp:.1f} C")


# ============================================================
# MAIN
# ============================================================

def main():

    print("====================================")
    print(" K7BAT uConsole Sidekick Service")
    print("====================================")

    ser = None

    while True:

        try:

            if ser is None or not ser.is_open:
                ser = open_serial()

            status = collect_status()

            message = build_message(status)

            print_status(status)

            print(
                f"TX: {message}"
            )

            ser.write(
                (message + "\n").encode("utf-8")
            )

            ser.flush()

            time.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:

            print("")
            print("Stopping Sidekick service.")

            if ser:
                ser.close()

            break

        except Exception as exc:

            print(
                f"Sidekick communication error: {exc}"
            )

            try:
                if ser:
                    ser.close()
            except Exception:
                pass

            ser = None

            time.sleep(3)


if __name__ == "__main__":
    main()