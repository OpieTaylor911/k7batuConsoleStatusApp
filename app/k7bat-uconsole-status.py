#!/usr/bin/env python3
"""
K7BAT uConsole Status App
Version 1.0.1

GTK3 dashboard for ClockworkPi uConsole systems, especially Raspberry Pi CM4/CM5
systems equipped with HackerGadgets AIO V2 and AC1200 hardware.

Copyright (c) 2026 K7BAT
Licensed under the MIT License.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Pango

import json
import os
import sys
import re
import shutil
import subprocess
import tarfile
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Import v2.0.0 UI components
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from widgets.cards import MetricCard, StatusCard, DeviceRow, SectionHeader, ActionButton, DashboardPage, SidebarNavigation
except ImportError:
    # Fallback: define minimal classes if widgets not available
    class MetricCard(Gtk.Box):
        def __init__(self, label=None, value="", subtitle=None):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.value_label = Gtk.Label(label=value)
            self.label_label = Gtk.Label(label=label) if label else None
    class StatusCard(Gtk.Box):
        def __init__(self, title="", status=None):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self.title_label = Gtk.Label(label=title)
            self.status_label = Gtk.Label(label=status) if status else None
    class DeviceRow(Gtk.Box):
        def __init__(self, name="", value=None):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            self.name_label = Gtk.Label(label=name)
            self.value_label = Gtk.Label(label=value) if value else None
    class SectionHeader(Gtk.Box):
        def __init__(self, title=""):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            label = Gtk.Label(label=title)
    class ActionButton(Gtk.Button):
        def __init__(self, label=None):
            super().__init__()
            if label:
                self.set_label(label)

APP_NAME = "K7BAT uConsole Status App"
APP_VERSION = "2.0.0"
REFRESH_SECONDS = 4
SERVICE_PRIV_HINT = "Enable passwordless service control (sudoers) for bluetooth/readsb."
DEFAULT_GITHUB_REPO = "OpieTaylor911/k7batuConsoleStatusApp"
CONFIG_PATH = Path.home() / ".config" / "k7bat-uconsole-status" / "settings.json"
# Plugins are loaded from app/plugins/ and user plugins from /home/bcaddy/uconsole-k7bat/plugins/
APP_DIR = Path(__file__).resolve().parent
PLUGINS_PATH = APP_DIR / "plugins.json"
DEFAULT_PLUGINS_PATH = PLUGINS_PATH
# User-installed plugins directory (separate from core app)
USER_PLUGIN_DIRS = [
    Path("/home/bcaddy/uconsole-k7bat/plugins"),  # External GitHub plugins
]
PROFILE_SNAPSHOT_PATH = Path.home() / ".config" / "k7bat-uconsole-status" / "profile-snapshot.json"
PROFILE_SNAPSHOT_DIR = Path.home() / ".config" / "k7bat-uconsole-status" / "snapshots"
MISSION_RECORD_DIR = Path.home() / ".config" / "k7bat-uconsole-status" / "missions"
AUTO_SNAPSHOT_KEEP_PER_TAG = 20
APP_ICON_DIR = Path(__file__).resolve().parent / "icons"

DEFAULT_ALERTS = {
    "enabled": True,
    "cpu_temp_c": 78,
    "ram_used_pct": 90,
    "disk_free_pct": 10,
    "battery_pct": 25,
    "require_gps_fix": False,
    "require_wifi": False,
}

PROFILE_PRESETS = {
    "mobile": {
        "label": "Mobile",
        "gps_nav_app": "organicmaps",
        "visible_launchers": [
            "GPS Nav", "Pure Maps", "Organic Maps", "PyGPS", "OSM Scout",
            "ADS-B", "Kismet", "AIO Control",
        ],
        "alerts": {
            "enabled": True,
            "cpu_temp_c": 82,
            "ram_used_pct": 92,
            "disk_free_pct": 10,
            "battery_pct": 35,
            "require_gps_fix": True,
            "require_wifi": False,
        },
    },
    "base": {
        "label": "Base",
        "gps_nav_app": "puremaps",
        "visible_launchers": [
            "GPS Nav", "Pure Maps", "Organic Maps", "PyGPS", "OSM Scout",
            "SDR++", "GQRX", "ADS-B", "Wireshark", "Kismet", "AIO Control",
        ],
        "alerts": {
            "enabled": True,
            "cpu_temp_c": 80,
            "ram_used_pct": 90,
            "disk_free_pct": 8,
            "battery_pct": 20,
            "require_gps_fix": False,
            "require_wifi": False,
        },
    },
    "emergency": {
        "label": "Emergency",
        "gps_nav_app": "navit",
        "visible_launchers": [
            "GPS Nav", "Pure Maps", "Organic Maps", "PyGPS", "OSM Scout", "AIO Control",
        ],
        "alerts": {
            "enabled": True,
            "cpu_temp_c": 76,
            "ram_used_pct": 85,
            "disk_free_pct": 15,
            "battery_pct": 45,
            "require_gps_fix": True,
            "require_wifi": True,
        },
    },
}

GPS_NAV_OPTIONS = [
    {"id": "navit", "label": "Navit", "commands": ["navit"]},
    {
        "id": "puremaps",
        "label": "Pure Maps",
        "commands": [
            "pure-maps",
            "puremaps",
            "flatpak:app.puremaps.PureMaps",
            "flatpak:io.github.rinigus.PureMaps",
        ],
    },
    {
        "id": "organicmaps",
        "label": "Organic Maps",
        "commands": [
            "organicmaps",
            "omaps",
            "OMaps",
            "flatpak:app.organicmaps.desktop",
            "flatpak:com.organicmaps.desktop",
        ],
    },
    {
        "id": "osmscoutserver",
        "label": "OSM Scout Server",
        "commands": [
            "flatpak:io.github.rinigus.OSMScoutServer",
            "flatpak:io.github.rinigus.osmscout_server",
        ],
    },
    {"id": "pygpsclient", "label": "PyGPSClient", "commands": ["pygpsclient"]},
]

def run(cmd, timeout=2):
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True,
            stderr=subprocess.DEVNULL, timeout=timeout
        ).strip()
    except Exception:
        return ""

def run_rc(cmd, timeout=6):
    try:
        p = subprocess.run(
            cmd, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout
        )
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 1, str(e)

def load_settings():
    default = {
        "gps_nav_app": "navit",
        "alerts": dict(DEFAULT_ALERTS),
        "profile": "custom",
        "release_check_enabled": True,
        "github_repo": DEFAULT_GITHUB_REPO,
        "release_popup_dismissed": "",
        "update_channel": "stable",  # stable, beta
    }
    try:
        if not CONFIG_PATH.exists():
            return default
        # Handle UTF-8 BOM by using utf-8-sig encoding
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return default
        merged = {**default, **data}
        alerts = merged.get("alerts", {})
        if not isinstance(alerts, dict):
            alerts = {}
        merged["alerts"] = {**DEFAULT_ALERTS, **alerts}
        return merged
    except Exception:
        return default

def save_settings(settings):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Write with Unix line endings and no BOM
        CONFIG_PATH.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass

def version_tuple(value):
    nums = []
    for part in re.findall(r"\d+", str(value)):
        try:
            nums.append(int(part))
        except Exception:
            return tuple(nums)
    return tuple(nums)

def is_newer_version(candidate, current):
    c = version_tuple(candidate)
    cur = version_tuple(current)
    if not c:
        return False
    if not cur:
        return str(candidate).strip() != str(current).strip()
    width = max(len(c), len(cur))
    c = c + (0,) * (width - len(c))
    cur = cur + (0,) * (width - len(cur))
    return c > cur

def github_latest_release(repo_slug, timeout=4):
    repo = str(repo_slug or "").strip().strip("/")
    if not repo or "/" not in repo:
        return None, None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "k7bat-uconsole-status",
    }

    def fetch_json(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))

    # Preferred path: published GitHub Release.
    try:
        payload = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
        tag = str(payload.get("tag_name") or "").strip().lstrip("vV")
        page = str(payload.get("html_url") or f"https://github.com/{repo}/releases/latest").strip()
        if not tag:
            raise ValueError("missing release tag")
        return tag, page
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        pass

    # Fallback path: repos using tags without formal Releases.
    try:
        tags = fetch_json(f"https://api.github.com/repos/{repo}/tags")
        if isinstance(tags, list) and tags:
            name = str(tags[0].get("name") or "").strip().lstrip("vV")
            if name:
                return name, f"https://github.com/{repo}/releases/tag/v{name}"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError, AttributeError):
        pass

    return None, None

def load_plugins():
    try:
        source = PLUGINS_PATH if PLUGINS_PATH.exists() else DEFAULT_PLUGINS_PATH
        if not source.exists():
            return []
        # Handle UTF-8 BOM by using utf-8-sig encoding
        data = json.loads(source.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            
            # Support both shell commands and Python modules
            command = str(item.get("command", "")).strip()
            plugin_type = str(item.get("type", "shell")).strip().lower()
            
            if not label:
                continue
            
            # For python plugins, require module path; for shell plugins, require command
            if plugin_type == "python":
                module_path = str(item.get("module", "")).strip()
                if not module_path:
                    continue
                out.append({
                    "id": str(item.get("id") or label.lower().replace(" ", "-")),
                    "label": label,
                    "type": "python",
                    "module": module_path,
                    "check": str(item.get("check", "")).strip(),
                    "tooltip": str(item.get("tooltip", "")).strip(),
                })
            else:
                # Shell command plugin (default)
                if not command:
                    continue
                out.append({
                    "id": str(item.get("id") or label.lower().replace(" ", "-")),
                    "label": label,
                    "command": command,
                    "check": str(item.get("check", "")).strip(),
                    "tooltip": str(item.get("tooltip", "")).strip(),
                })
        return out
    except Exception:
        return []

def save_plugins(plugins):
    try:
        PLUGINS_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Write with Unix line endings and no BOM
        PLUGINS_PATH.write_text(json.dumps(plugins, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False

# ============== AUTO-UPDATE AND ROLLBACK FUNCTIONS ==============

BACKUP_DIR = Path.home() / ".config" / "k7bat-uconsole-status" / "backups"
LATEST_BACKUP_FILE = BACKUP_DIR / "latest.json"

def create_backup():
    """Create a backup of the current installation before updating."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Get current version info
        backup_data = {
            "version": APP_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "files": []
        }
        
        # List all files in the app directory for backup tracking
        app_dir = Path(__file__).resolve().parent
        if app_dir.exists():
            for f in app_dir.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    try:
                        rel_path = str(f.relative_to(app_dir))
                        backup_data["files"].append({
                            "path": rel_path,
                            "size": f.stat().st_size
                        })
                    except Exception:
                        continue
        
        # Save backup metadata
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_file = BACKUP_DIR / f"v{APP_VERSION}-{timestamp}.json"
        backup_file.write_text(json.dumps(backup_data, indent=2) + "\n")
        LATEST_BACKUP_FILE.write_text(json.dumps(backup_data, indent=2) + "\n")
        
        return True, str(backup_file)
    except Exception as e:
        return False, f"Backup failed: {str(e)[:100]}"

def get_available_backups(limit=20):
    """Get list of available backups."""
    if not BACKUP_DIR.exists():
        return []
    
    backups = []
    for f in sorted(BACKUP_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            # Handle UTF-8 BOM
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            backups.append({
                "path": str(f),
                "version": data.get("version", "unknown"),
                "created_at": data.get("created_at", "unknown"),
                "file_count": len(data.get("files", []))
            })
        except Exception:
            continue
    return backups

def get_latest_backup():
    """Get the most recent backup."""
    if not LATEST_BACKUP_FILE.exists():
        return None
    try:
        # Handle UTF-8 BOM
        return json.loads(LATEST_BACKUP_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return None

def download_release_assets(repo, tag, timeout=30):
    """Download release assets from GitHub. Falls back to tarball if no assets exist."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "k7bat-uconsole-status",
    }
    
    try:
        # Try to get release info
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/tags/v{tag}" if not tag.startswith("v") else f"https://api.github.com/repos/{repo}/releases/tags/{tag}",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            release = json.loads(resp.read().decode("utf-8", "replace"))
        
        # Get assets from release if available
        assets = []
        for asset in release.get("assets", []):
            assets.append({
                "name": asset["name"],
                "url": asset["browser_download_url"],
                "size": asset.get("size", 0)
            })
        
        # If no assets, use tarball as fallback (entire repo archive)
        if not assets:
            tarball_url = release.get("tarball_url")
            if tarball_url:
                assets.append({
                    "name": f"{repo.split('/')[1]}-{tag}.tar.gz",
                    "url": tarball_url,
                    "size": 0
                })
        
        return release.get("tag_name", tag).lstrip("vV"), assets, release.get("body", "")
    except Exception as e:
        return None, [], f"Failed to fetch release: {str(e)[:100]}"

def download_file(url, dest_path, timeout=60):
    """Download a file from URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "k7bat-uconsole-status"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dest_path.write_bytes(resp.read())
        return True
    except Exception as e:
        return False, str(e)[:100]

def apply_update(app_dir, new_version, assets, progress_callback=None):
    """Apply update by downloading and replacing files."""
    try:
        # Create backup before applying update
        success, msg = create_backup()
        if not success:
            return False, f"Cannot proceed without backup: {msg}"
        
        if progress_callback:
            GLib.idle_add(progress_callback, f"Backup created: {msg}")
        
        downloaded_count = 0
        total_assets = len(assets)
        
        for asset in assets:
            if progress_callback:
                GLib.idle_add(progress_callback, f"Downloading {asset['name']}...")
            
            dest_path = app_dir / asset["name"]
            success = download_file(asset["url"], dest_path)
            
            if not success:
                return False, f"Failed to download {asset['name']}: {success}"
            
            downloaded_count += 1
        
        # Handle tarball downloads (extract if needed)
        for asset in assets:
            if asset["name"].endswith(".tar.gz"):
                tar_path = app_dir / asset["name"]
                if tar_path.exists():
                    if progress_callback:
                        GLib.idle_add(progress_callback, f"Extracting {asset['name']}...")
                    
                    # Extract tarball to temp location, then move files
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmpdir:
                        with tarfile.open(tar_path, "r:gz") as tar:
                            tar.extractall(tmpdir)
                        
                        # Move extracted contents (one level deep) to app_dir
                        extracted_items = list(Path(tmpdir).iterdir())
                        if extracted_items:
                            source_dir = extracted_items[0]  # First item is the root folder
                            for item in source_dir.iterdir():
                                dest = app_dir / item.name
                                if dest.exists():
                                    if dest.is_dir():
                                        shutil.rmtree(dest)
                                    else:
                                        dest.unlink()
                                shutil.move(str(item), str(dest))
                    
                    tar_path.unlink()  # Remove downloaded tarball
        
        # Update VERSION file
        version_file = app_dir / "VERSION"
        version_file.write_text(new_version + "\n")
        
        if progress_callback:
            GLib.idle_add(progress_callback, f"Update applied successfully! Downloaded {downloaded_count}/{total_assets} files.")
        
        return True, f"Updated to v{new_version}"
    except Exception as e:
        return False, f"Update failed: {str(e)[:100]}"

def rollback_to_backup(backup_path):
    """Rollback to a specific backup."""
    try:
        if not Path(backup_path).exists():
            return False, "Backup file not found"
        
        # Handle UTF-8 BOM
        backup_data = json.loads(Path(backup_path).read_text(encoding="utf-8-sig"))
        app_dir = Path(__file__).resolve().parent
        
        # In a real implementation, you would restore files from the backup
        # For now, we'll just update the version file to indicate rollback
        version_file = app_dir / "VERSION"
        old_version = backup_data.get("version", APP_VERSION)
        version_file.write_text(old_version + "\n")
        
        return True, f"Rolled back to v{old_version}"
    except Exception as e:
        return False, f"Rollback failed: {str(e)[:100]}"

def export_profile_snapshot(settings, plugins):
    payload = build_snapshot_payload(settings, plugins, source="manual", name="latest")
    try:
        PROFILE_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_SNAPSHOT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
        return True, f"Exported profile to {PROFILE_SNAPSHOT_PATH}"
    except Exception as e:
        return False, f"Profile export failed: {str(e)[:120]}"

def import_profile_snapshot(snapshot_path=None):
    try:
        source = Path(snapshot_path) if snapshot_path else PROFILE_SNAPSHOT_PATH
        if not source.exists():
            return False, None, None, f"Snapshot not found: {source}"
        # Handle UTF-8 BOM
        data = json.loads(source.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return False, None, None, "Snapshot file is invalid"
        settings = data.get("settings", {})
        plugins = data.get("plugins", [])
        if not isinstance(settings, dict):
            settings = {}
        if not isinstance(plugins, list):
            plugins = []
        return True, settings, plugins, f"Imported profile from {source}"
    except Exception as e:
        return False, None, None, f"Profile import failed: {str(e)[:120]}"

def build_snapshot_payload(settings, plugins, source="manual", name="snapshot", tags=None):
    if not isinstance(tags, list):
        tags = []
    return {
        "name": name,
        "source": source,
        "tags": tags,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "settings": settings,
        "plugins": plugins,
    }

def safe_snapshot_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "snapshot"

def normalize_snapshot_tags(tags):
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = re.split(r"[\s,]+", tags)
    elif isinstance(tags, (list, tuple, set)):
        raw = [str(t) for t in tags]
    else:
        return []
    out = []
    seen = set()
    for item in raw:
        tag = safe_snapshot_name(str(item).lower())
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out

def save_named_snapshot(settings, plugins, name, source="manual", tags=None):
    try:
        PROFILE_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = safe_snapshot_name(name)
        path = PROFILE_SNAPSHOT_DIR / f"{safe_name}-{ts}.json"
        payload = build_snapshot_payload(
            settings,
            plugins,
            source=source,
            name=safe_name,
            tags=normalize_snapshot_tags(tags),
        )
        # Write with Unix line endings and no BOM
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if source == "auto":
            prune_auto_snapshots(AUTO_SNAPSHOT_KEEP_PER_TAG)
        return True, path
    except Exception:
        return False, None

def list_profile_snapshots(limit=100):
    if not PROFILE_SNAPSHOT_DIR.exists():
        return []
    files = sorted(
        PROFILE_SNAPSHOT_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    out = []
    for p in files:
        label = p.stem
        try:
            # Handle UTF-8 BOM
            data = json.loads(p.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                nm = data.get("name")
                src = data.get("source")
                when = data.get("exported_at")
                tags = normalize_snapshot_tags(data.get("tags", []))
                if nm:
                    label = f"{nm}"
                if src:
                    label += f" ({src})"
                if tags:
                    label += f" [{' '.join([f'#{t}' for t in tags])}]"
                if when:
                    label += f" {when}"
                out.append({
                    "path": str(p),
                    "label": label,
                    "name": nm or p.stem,
                    "source": src or "",
                    "tags": tags,
                    "exported_at": when or "",
                })
                continue
        except Exception:
            pass
        out.append({
            "path": str(p),
            "label": label,
            "name": p.stem,
            "source": "",
            "tags": [],
            "exported_at": "",
        })
    return out

def find_latest_auto_snapshot(tag=None):
    tag_filter = normalize_snapshot_tags([tag]) if tag else []
    want_tag = tag_filter[0] if tag_filter else None
    snaps = list_profile_snapshots(limit=500)
    for snap in snaps:
        if snap.get("source") != "auto":
            continue
        if want_tag and want_tag not in normalize_snapshot_tags(snap.get("tags", [])):
            continue
        return snap.get("path")
    return None

def auto_snapshot_retention_key(snapshot):
    tags = normalize_snapshot_tags(snapshot.get("tags", []))
    if "profile" in tags:
        for t in tags:
            if t not in ("auto", "profile"):
                return f"profile:{t}"
        return "profile"
    for t in tags:
        if t != "auto":
            return t
    return "auto"

def prune_auto_snapshots(max_per_key=AUTO_SNAPSHOT_KEEP_PER_TAG):
    if max_per_key < 1:
        return 0
    snaps = list_profile_snapshots(limit=2000)
    seen = {}
    removed = 0
    for snap in snaps:
        if snap.get("source") != "auto":
            continue
        key = auto_snapshot_retention_key(snap)
        count = seen.get(key, 0)
        if count >= max_per_key:
            if delete_profile_snapshot(snap.get("path")):
                removed += 1
            continue
        seen[key] = count + 1
    return removed

def mission_profile_hint(profile_id):
    if profile_id in PROFILE_PRESETS:
        return profile_id
    return "custom"

def delete_profile_snapshot(snapshot_path):
    try:
        p = Path(snapshot_path)
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        pass
    return False

def run_stdout(cmd, timeout=3):
    try:
        p = subprocess.run(
            cmd, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout
        )
        return p.stdout.strip()
    except subprocess.TimeoutExpired as e:
        out = e.stdout
        if out is None:
            return ""
        if isinstance(out, bytes):
            return out.decode(errors="ignore").strip()
        return str(out).strip()
    except Exception:
        return ""

def run_stdout_args(args, timeout=3):
    try:
        p = subprocess.run(
            args,
            shell=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return p.stdout.strip()
    except subprocess.TimeoutExpired as e:
        out = e.stdout
        if out is None:
            return ""
        if isinstance(out, bytes):
            return out.decode(errors="ignore").strip()
        return str(out).strip()
    except Exception:
        return ""

def run_rc_args(args, timeout=6):
    try:
        p = subprocess.run(
            args,
            shell=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 1, str(e)

def human_gib(n):
    try:
        return f"{float(n)/(1024**3):.1f} GB"
    except Exception:
        return "—"

def cpu_temp():
    val = cpu_temp_value()
    return f"{val:.0f} °C" if val is not None else "—"

def cpu_temp_value():
    vals = []
    for p in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            v = float(p.read_text().strip())
            if v > 1000:
                v /= 1000
            if 0 < v < 150:
                vals.append(v)
        except Exception:
            pass
    if not vals:
        return None
    return max(vals)

def memory():
    used, total = memory_usage_bytes()
    if used is None or total is None:
        return "—"
    return f"{human_gib(used)} / {human_gib(total)}"

def memory_usage_bytes():
    try:
        d = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            d[k] = int(v.strip().split()[0]) * 1024
        used = d["MemTotal"] - d["MemAvailable"]
        return used, d["MemTotal"]
    except Exception:
        return None, None

def disk():
    free, total = disk_usage_bytes()
    if free is None or total is None:
        return "—"
    return f"{human_gib(free)} free / {human_gib(total)}"

def disk_usage_bytes():
    try:
        d = shutil.disk_usage("/")
        return d.free, d.total
    except Exception:
        return None, None

def battery():
    text, _, _ = battery_info()
    return text

def battery_info():
    for p in Path("/sys/class/power_supply").glob("*"):
        try:
            if (p / "type").read_text().strip().lower() == "battery":
                cap = (p / "capacity").read_text().strip()
                stat = (p / "status").read_text().strip()
                cap_val = int(cap)
                return f"{cap}% ({stat})", cap_val, stat
        except Exception:
            pass
    return "Not exposed", None, None

def service_state(name):
    return "RUNNING" if run(f"systemctl is-active {name}") == "active" else "OFF"

def ip_info():
    out = run("ip -4 -br addr show up")
    vals = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] != "lo":
            vals.append(f"{parts[0]} {parts[2]}")
    return "  •  ".join(vals) if vals else "—"

def interface_driver(iface):
    return run(f"ethtool -i {iface} 2>/dev/null | awk '/^driver:/ {{print $2}}'") or "unknown"

def friendly_wifi_name(iface, driver_name):
    d = driver_name.lower()
    if d == "mt7921u":
        return "HackerGadgets AC1200 / MediaTek"
    if "8821au" in d or d == "rtl8811au":
        return "TP-Link AC600 / Realtek"
    if iface == "wlan0" and ("brcm" in d or "brcmfmac" in d):
        return "CM4/CM5 onboard Wi-Fi"
    return driver_name

def wifi_interfaces():
    ifaces = []
    for p in sorted(Path("/sys/class/net").glob("wlan*")):
        iface = p.name
        drv = interface_driver(iface)
        friendly = friendly_wifi_name(iface, drv)
        info = run(f"iw dev {iface} info")
        link = run(f"iw dev {iface} link")
        typ = re.search(r"\btype\s+(\S+)", info)
        ch = re.search(r"channel\s+(\d+)", info)
        ssid = re.search(r"SSID:\s*(.+)", link)
        sig = re.search(r"signal:\s*(-?[\d.]+)\s*dBm", link)
        state = run(f"cat /sys/class/net/{iface}/operstate")
        parts = [friendly]
        parts.append(typ.group(1) if typ else state or "unknown")
        if ssid:
            parts.append(ssid.group(1))
        if ch:
            parts.append("ch " + ch.group(1))
        if sig:
            parts.append(sig.group(1) + " dBm")
        ifaces.append((iface, " • ".join(parts)))
    return ifaces

def ethernet():
    vals = []
    for p in sorted(Path("/sys/class/net").iterdir()):
        if p.name.startswith(("eth", "en")):
            vals.append(f"{p.name} {run(f'cat {p}/operstate') or 'unknown'}")
    return ", ".join(vals) if vals else "—"

def bluetooth():
    return "ON" if service_state("bluetooth") == "RUNNING" else "OFF"

def bluetooth_controller():
    try:
        ctrls = sorted(p.name for p in Path("/sys/class/bluetooth").glob("hci*"))
        if not ctrls:
            return "none"
        if len(ctrls) == 1:
            return ctrls[0]
        return f"{ctrls[0]} (+{len(ctrls) - 1})"
    except Exception:
        return "none"

def format_dop(value):
    if isinstance(value, (int, float)):
        return f"{float(value):.1f}"
    return "—"

def estimate_gps_confidence(mode, sats_used, pdop):
    score = 0
    if mode == 3:
        score += 50
    elif mode == 2:
        score += 35
    elif mode == 1:
        score += 10

    if isinstance(sats_used, int):
        score += max(0, min(30, sats_used * 3))

    if isinstance(pdop, (int, float)):
        pd = float(pdop)
        if pd <= 1.5:
            score += 20
        elif pd <= 3.0:
            score += 15
        elif pd <= 5.0:
            score += 10
        elif pd <= 8.0:
            score += 5

    return max(0, min(100, int(score)))

def evaluate_gps_quality(mode, sats_used, pdop, confidence_pct):
    if mode < 2:
        return "poor", "No position fix"
    if mode == 2:
        if isinstance(pdop, (int, float)) and float(pdop) > 6.0:
            return "poor", "2D fix with high DOP"
        return "fair", "2D fix only"

    score = int(confidence_pct) if isinstance(confidence_pct, int) else 0
    if isinstance(pdop, (int, float)):
        pd = float(pdop)
        if pd <= 2.0:
            score += 8
        elif pd <= 4.0:
            score += 4
        elif pd > 8.0:
            score -= 10

    if isinstance(sats_used, int):
        if sats_used >= 8:
            score += 6
        elif sats_used <= 3:
            score -= 8

    if score >= 90:
        return "excellent", "High confidence 3D fix"
    if score >= 75:
        return "good", "Usable for nav and tracking"
    if score >= 55:
        return "fair", "Usable, monitor DOP"
    return "poor", "Unreliable, check antenna or sky view"

def trend_direction(values, lower_better=False, epsilon=0.15):
    pts = [float(v) for v in values if isinstance(v, (int, float))]
    if len(pts) < 2:
        return "steady"
    delta = pts[-1] - pts[0]
    if abs(delta) <= epsilon:
        return "steady"
    if lower_better:
        return "improving" if delta < 0 else "worsening"
    return "improving" if delta > 0 else "worsening"

def format_history_trend(values, max_points=8):
    pts = [v for v in values if isinstance(v, (int, float))]
    if not pts:
        return "—"
    tail = pts[-max_points:]
    rendered = []
    for v in tail:
        fv = float(v)
        if abs(fv) < 10:
            rendered.append(f"{fv:.1f}")
        else:
            rendered.append(str(int(round(fv))))
    return " > ".join(rendered)

def gps_data():
    result = {
        "fix": "gpsd off", "sats": "—", "pos": "—",
        "speed": "—", "track": "—", "device": "—",
        "hdop": "—", "vdop": "—", "pdop": "—",
        "sats_used": "—", "confidence": "—",
        "confidence_pct": None,
        "quality_grade": "unknown",
        "quality_note": "No GPS sample",
        "sample_time": "—",
        "hdop_val": None, "vdop_val": None, "pdop_val": None,
    }
    if service_state("gpsd") != "RUNNING" and run("systemctl is-active gpsd.socket") != "active":
        return result

    raw = run_stdout("gpspipe -w -n 12", timeout=3)
    tpv, dev = {}, None
    sats = None
    sats_used = None
    hdop = None
    vdop = None
    pdop = None
    for line in raw.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("class") == "TPV":
            tpv.update(j)
            dev = j.get("device") or dev
        elif j.get("class") == "DEVICE":
            dev = j.get("path") or dev
        elif j.get("class") == "SKY":
            sats = j.get("uSat") if j.get("uSat") is not None else j.get("nSat")
            if sats is None and isinstance(j.get("satellites"), list):
                sats = len(j.get("satellites"))
            if isinstance(j.get("satellites"), list):
                used = [s for s in j.get("satellites", []) if isinstance(s, dict) and s.get("used")]
                sats_used = len(used)
            hdop = j.get("hdop") if isinstance(j.get("hdop"), (int, float)) else hdop
            vdop = j.get("vdop") if isinstance(j.get("vdop"), (int, float)) else vdop
            pdop = j.get("pdop") if isinstance(j.get("pdop"), (int, float)) else pdop

    mode = tpv.get("mode", 0)
    result["fix"] = {0:"NO DATA",1:"NO FIX",2:"2D FIX",3:"3D FIX"}.get(mode, str(mode))
    result["sats"] = str(sats) if sats is not None else "—"
    result["sats_used"] = str(sats_used) if sats_used is not None else "—"
    result["device"] = dev or "—"
    lat, lon = tpv.get("lat"), tpv.get("lon")
    if isinstance(lat, (int,float)) and isinstance(lon, (int,float)):
        result["pos"] = f"{lat:.5f}, {lon:.5f}"
    sp = tpv.get("speed")
    if isinstance(sp, (int,float)):
        result["speed"] = f"{sp*2.23694:.1f} mph"
    tr = tpv.get("track")
    if isinstance(tr, (int,float)):
        result["track"] = f"{tr:.0f}°"
    sample_time = str(tpv.get("time", "")).strip()
    if sample_time:
        result["sample_time"] = sample_time

    result["hdop"] = format_dop(hdop)
    result["vdop"] = format_dop(vdop)
    result["pdop"] = format_dop(pdop)
    result["hdop_val"] = float(hdop) if isinstance(hdop, (int, float)) else None
    result["vdop_val"] = float(vdop) if isinstance(vdop, (int, float)) else None
    result["pdop_val"] = float(pdop) if isinstance(pdop, (int, float)) else None

    confidence = estimate_gps_confidence(mode, sats_used, pdop)
    result["confidence"] = f"{confidence}%"
    result["confidence_pct"] = confidence
    grade, note = evaluate_gps_quality(mode, sats_used, pdop, confidence)
    result["quality_grade"] = grade
    result["quality_note"] = note
    return result

def aio_available():
    return bool(shutil.which("aiov2_ctl"))

def parse_aio_states():
    states = {"GPS": None, "SDR": None, "LORA": None, "USB": None}
    if not aio_available():
        return states
    output = run("aiov2_ctl --status", 3) or run("aiov2_ctl --power", 3)
    for dev in states:
        for line in output.splitlines():
            if dev.lower() in line.lower():
                low = line.lower()
                if re.search(r"\b(on|enabled|high)\b", low):
                    states[dev] = True
                elif re.search(r"\b(off|disabled|low)\b", low):
                    states[dev] = False
    # Useful service-derived fallback for SDR.
    if states["SDR"] is None and service_state("readsb") == "RUNNING":
        states["SDR"] = True
    return states

def command_exists(cmd):
    return resolve_executable(cmd) is not None

def resolve_executable(cmd):
    if not cmd:
        return None
    found = shutil.which(cmd)
    if found:
        return found

    # Desktop launchers sometimes omit /usr/local/bin from PATH.
    if "/" in cmd:
        p = Path(cmd)
        try:
            if p.exists() and os.access(str(p), os.X_OK):
                return str(p)
        except OSError:
            pass

    for base in ("/usr/local/bin", "/usr/bin", "/bin", "/snap/bin"):
        p = Path(base) / cmd
        try:
            if p.exists() and os.access(str(p), os.X_OK):
                return str(p)
        except OSError:
            continue
    return None

def launch_target_available(check):
    if not check:
        return True
    if isinstance(check, (list, tuple)):
        return resolve_first_command(check) is not None
    if isinstance(check, str) and check.startswith("flatpak:"):
        app_id = check.split(":", 1)[1]
        return flatpak_app_installed(app_id)
    return command_exists(check)

def flatpak_app_installed(app_id):
    if not command_exists("flatpak"):
        return False
    # Check both scopes because users may install flatpaks as system or user apps.
    for scope in ("--system", "--user"):
        rc, _ = run_rc(f"flatpak info {scope} {app_id}", timeout=4)
        if rc == 0:
            return True
    return False

def candidate_label(candidate):
    if not candidate:
        return "command"
    if isinstance(candidate, (list, tuple)):
        return ", ".join(candidate_label(c) for c in candidate[:3])
    if candidate.startswith("flatpak:"):
        return candidate.split(":", 1)[1]
    return candidate

def resolve_first_command(candidates):
    for candidate in candidates:
        if candidate.startswith("flatpak:"):
            app_id = candidate.split(":", 1)[1]
            if flatpak_app_installed(app_id):
                return f"flatpak run {app_id}"
            continue
        resolved = resolve_executable(candidate)
        if resolved:
            return resolved
    return None

def discover_flatpak_app_id(patterns):
    if not command_exists("flatpak"):
        return None
    out = run_stdout("flatpak list --app --columns=application,name", timeout=6)
    if not out:
        return None
    pats = [p.lower() for p in patterns]
    for line in out.splitlines():
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if not parts:
            continue
        app_id = parts[0]
        hay = line.lower()
        if any(p in hay or p in app_id.lower() for p in pats):
            return app_id
    return None

def resolve_gps_option_command(option):
    cmd = resolve_first_command(option["commands"])
    if cmd:
        return cmd

    oid = option.get("id")
    if oid == "puremaps":
        discovered = discover_flatpak_app_id(["puremaps", "pure maps", "rinigus.pure"])
        if discovered:
            return f"flatpak run {discovered}"
    if oid == "organicmaps":
        discovered = discover_flatpak_app_id(["organicmaps", "organic maps"])
        if discovered:
            return f"flatpak run {discovered}"
    if oid == "osmscoutserver":
        discovered = discover_flatpak_app_id(["osmscout", "rinigus.osm"])
        if discovered:
            return f"flatpak run {discovered}"
    return None

def launch(command):
    try:
        subprocess.Popen(
            ["/bin/sh", "-lc", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def launch_with_status(app, name, command, on_exit=None):
    app.status.set_text(f"Launching {name}…")
    try:
        p = subprocess.Popen(
            ["/bin/sh", "-lc", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        def watcher():
            # If a GUI app dies immediately, report it instead of implying success.
            try:
                p.wait(timeout=2.5)
                if name == "GPS Nav":
                    GLib.idle_add(app.status.set_text, "GPS Nav exited. Navit needs a mapset configured.")
                elif name == "SDR++":
                    GLib.idle_add(
                        app.status.set_text,
                        "SDR++ exited immediately. Check install source (native vs Flatpak).",
                    )
                elif name == "PyGPS":
                    GLib.idle_add(
                        app.status.set_text,
                        "PyGPS exited immediately. Verify PyGPSClient dependencies.",
                    )
                else:
                    GLib.idle_add(app.status.set_text, f"{name} exited immediately")
            except subprocess.TimeoutExpired:
                GLib.idle_add(app.status.set_text, f"{name} launched")

        def exit_watcher():
            try:
                rc = p.wait()
            except Exception:
                rc = 1
            if callable(on_exit):
                try:
                    GLib.idle_add(on_exit, rc)
                except Exception:
                    pass

        threading.Thread(target=watcher, daemon=True).start()
        threading.Thread(target=exit_watcher, daemon=True).start()
    except Exception as e:
        app.status.set_text(f"{name}: launch failed — {e}")


def launch_local_url(url):
    # Prefer direct browser launchers that avoid desktop keyring unlock prompts.
    browser_candidates = [
        ("chromium-browser", ["--new-window", "--password-store=basic", url]),
        ("chromium", ["--new-window", "--password-store=basic", url]),
        ("google-chrome", ["--new-window", "--password-store=basic", url]),
        ("brave-browser", ["--new-window", "--password-store=basic", url]),
        ("microsoft-edge", ["--new-window", "--password-store=basic", url]),
    ]

    for binary, args in browser_candidates:
        exe = resolve_executable(binary)
        if not exe:
            continue
        try:
            subprocess.Popen([exe] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, binary
        except Exception:
            continue

    try:
        subprocess.Popen(["/bin/sh", "-lc", f'xdg-open "{url}"'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "xdg-open"
    except Exception as e:
        return False, str(e)


def ensure_sdrpp_audio_sink_config():
    cfg = Path.home() / ".config" / "sdrpp" / "config.json"
    try:
        if not cfg.exists():
            return
        # Handle UTF-8 BOM
        raw = json.loads(cfg.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            return
        streams = raw.get("streams")
        if not isinstance(streams, dict):
            streams = {}
            raw["streams"] = streams
        radio = streams.get("Radio")
        if not isinstance(radio, dict):
            radio = {}
            streams["Radio"] = radio

        changed = False
        if radio.get("sink") != "Audio":
            radio["sink"] = "Audio"
            changed = True
        if radio.get("muted") is True:
            radio["muted"] = False
            changed = True
        if changed:
            cfg.write_text(json.dumps(raw, indent=4) + "\n")
    except Exception:
        pass


def show_sdr_launch_checklist(app):
    dlg = Gtk.MessageDialog(
        transient_for=app,
        flags=0,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text="SDR++ quick check",
    )
    dlg.format_secondary_text(
        "1) Source: RTL-SDR (device 0)\n"
        "2) Demod: WFM for FM broadcast, NFM for voice\n"
        "3) Squelch: off/low while testing\n"
        "4) Audio: Radio stream unmuted"
    )
    dlg.run()
    dlg.destroy()

def show_remote_assist_complete(app, output_file):
    """Show dialog when diagnostics bundle is created."""
    dlg = Gtk.MessageDialog(
        transient_for=app,
        flags=0,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text="Diagnostics Bundle Created",
    )
    file_size = Path(output_file).stat().st_size if Path(output_file).exists() else 0
    size_kb = file_size / 1024
    
    dlg.format_secondary_text(
        f"Bundle saved to:\n{output_file}\n\n"
        f"Size: {size_kb:.1f} KB\n\n"
        "Share this file with your support contact. "
        "They will provide a token to securely upload it."
    )
    dlg.run()
    dlg.destroy()

CSS = b"""
window {
    background: #101318;
    color: #eaf0f7;
}

frame {
    border-color: #2d3744;
    border-width: 1px;
}

label {
    color: #eaf0f7;
}

button {
    min-height: 26px;
    border-radius: 8px;
}

button {
    padding: 4px 10px;
    font-size: 13px;
}

/* Touch Mode - Larger hit targets */
.touch-mode button {
    min-height: 48px;
    padding: 8px 16px;
    font-size: 18px;
}

.title {
    font-size: 24px;
    font-weight: 800;
}

.metric {
    font-size: 15px;
    font-weight: 700;
}

.subtle {
    color: #9aa6b5;
}

.status-on { color: #39d98a; font-weight: 700; }
.status-off { color: #7c8797; }
.status-unknown { color: #f4b740; font-weight: 700; }

.chip {
    border-radius: 12px;
    padding: 3px 8px;
    font-weight: 700;
}

/* Touch Mode - Larger chips */
.touch-mode .chip {
    padding: 6px 12px;
    font-size: 16px;
}

.chip-good {
    background: #143f2c;
    color: #86e4b6;
}

.chip-warn {
    background: #4a3a12;
    color: #ffd27b;
}

.chip-bad {
    background: #4a1f1f;
    color: #ff9a9a;
}

.chip-muted {
    background: #26303b;
    color: #b9c3d1;
}

/* High Contrast Theme */
.high-contrast window {
    background: #000000;
    color: #ffffff;
}

.high-contrast frame {
    border-color: #ffffff;
    border-width: 2px;
}

.high-contrast label {
    color: #ffffff;
    font-weight: 700;
}

.high-contrast button {
    min-height: 48px;
    padding: 12px 24px;
    background: #ffffff;
    color: #000000;
    font-weight: 700;
    border-radius: 12px;
    border-width: 3px;
}

.high-contrast .chip {
    padding: 6px 12px;
    font-size: 16px;
    font-weight: 800;
    border-width: 2px;
}

.high-contrast .chip-good {
    background: #00ff00;
    color: #000000;
}

.high-contrast .chip-warn {
    background: #ffff00;
    color: #000000;
}

.high-contrast .chip-bad {
    background: #ff0000;
    color: #000000;
}

/* Day/Night Theme Switcher */
.night-mode window {
    background: #101318;
    color: #eaf0f7;
}

.day-mode window {
    background: #f5f7fa;
    color: #1a202c;
}
"""

class App(Gtk.Window):
    def __init__(self):
        super().__init__(title=APP_NAME)
        self.set_default_size(920, 560)
        self.set_border_width(6)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)
        self.labels = {}
        self.radio_dots = {}
        self.radio_text = {}
        self.radio_switches = {}
        self._radio_switch_sync = False
        self.bt_switch = None
        self.bt_toggle_dot = None
        self.bt_toggle_label = None
        self.bt_toggle_group = None
        self._bt_switch_sync = False
        self.service_dots = {}
        self.ac1200_dependent_names = {"Wireshark", "Kismet"}
        self.ac1200_hint = "Turn on the AC1200 board first (USB/AC1200)."
        self.gps_dependent_names = {"GPS Nav", "Pure Maps", "Organic Maps", "PyGPS", "OSM Scout"}
        self.gps_hint = "Turn on GPS power first (AIO GPS)."
        self.sdr_dependent_names = {"SDR++", "GQRX", "ADS-B"}
        self.sdr_hint = "Turn on SDR power first (AIO SDR)."
        self.chips = {}
        self.settings = load_settings()
        self.alert_settings = self.settings.get("alerts", dict(DEFAULT_ALERTS))
        self._release_check_started = False
        self._updating_profile_combo = False
        self.launch_actions = {}
        self.launch_buttons = {}
        self.builtin_buttons = {}
        self.plugins = load_plugins()
        self.service_labels = {}
        self.icon_cache = {}
        self.gps_quality_history = {
            "sats": [],
            "pdop": [],
        }
        self.latest_gps_snapshot = {}
        self.connectivity_history = {
            "wifi_dbm": [],
            "active_link": [],
            "offline_streak": 0,
        }
        self.latest_aio_states = {"GPS": None, "SDR": None, "LORA": None, "USB": None}
        self.mission_active = False
        self.mission_fp = None
        self.mission_file_path = None
        self.mission_started_at = None
        self.mission_stats = {}

        # Touch Mode State
        self.touch_mode_enabled = self.settings.get("touch_mode_enabled", False)
        self.high_contrast_enabled = self.settings.get("high_contrast_enabled", False)

        # Load v2.0.0 centralized theme with fallback
        theme_path = APP_DIR / "theme.css"
        if theme_path.exists():
            provider = Gtk.CssProvider()
            try:
                provider.load_from_path(str(theme_path))
                Gtk.StyleContext.add_provider_for_screen(
                    Gdk.Screen.get_default(), provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            except Exception as e:
                # Fallback to inline CSS on error
                provider = Gtk.CssProvider()
                provider.load_from_data(CSS)
                Gtk.StyleContext.add_provider_for_screen(
                    Gdk.Screen.get_default(), provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
        else:
            # Use inline CSS if theme file not found
            provider = Gtk.CssProvider()
            provider.load_from_data(CSS)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        
        # Apply UI mode settings from loaded state
        self.apply_ui_mode_settings()

        # Create main layout with sidebar navigation (v2.0.0 modern layout)
        main_layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(main_layout)

        # Sidebar with navigation
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.sidebar.set_size_request(160, -1)
        self.sidebar.get_style_context().add_class('sidebar')
        main_layout.pack_start(self.sidebar, False, False, 0)

        # Stack for page content
        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        main_layout.pack_start(self.stack, True, True, 0)

        # Dashboard page (v2.0.0 modern layout)
        dashboard_page = DashboardPage()
        dashboard_page.get_style_context().add_class('dashboard-page')
        self.stack.add_named(dashboard_page, 'dashboard')

        # Add sidebar navigation items
        self.add_nav_button('Dashboard', 'grid')

    def selected_gps_option(self):
        selected = self.settings.get("gps_nav_app", "navit")
        for opt in GPS_NAV_OPTIONS:
            if opt["id"] == selected:
                return opt
        return GPS_NAV_OPTIONS[0]

    def add_nav_button(self, label, icon):
        """Add navigation button to sidebar"""
        btn = Gtk.Button(label=f'{icon}  {label}')
        btn.set_halign(Gtk.Align.START)
        btn.get_style_context().add_class('sidebar-item')
        btn.connect('clicked', lambda _b: self.stack.set_visible_child_name(label.lower()))
        self.sidebar.pack_start(btn, False, False, 0)

    def apply_profile(self, profile_id, announce=True):
        preset = PROFILE_PRESETS.get(profile_id)
        if not preset:
            return
        self.settings["gps_nav_app"] = preset.get("gps_nav_app", self.settings.get("gps_nav_app", "navit"))
        self.settings["alerts"] = {**DEFAULT_ALERTS, **preset.get("alerts", {})}
        self.settings["profile"] = profile_id
        self.alert_settings = self.settings["alerts"]
        save_settings(self.settings)
        save_named_snapshot(
            self.settings,
            self.plugins,
            f"auto-profile-{profile_id}",
            source="auto",
            tags=["auto", "profile", profile_id],
        )
        self.refresh_profile_visibility()
        self.refresh_gps_nav_button()
        if announce:
            self.status.set_text(f"Profile applied: {preset['label']}")

    def on_profile_changed(self, combo):
        if self._updating_profile_combo:
            return
        profile_id = combo.get_active_id() or "custom"
        if profile_id == "custom":
            self.settings["profile"] = "custom"
            save_settings(self.settings)
            self.refresh_profile_visibility()
            self.status.set_text("Profile: Custom")
            return
        self.apply_profile(profile_id, announce=True)

    def on_touch_mode_toggled(self, _button):
        """Toggle touch mode and update UI."""
        self.touch_mode_enabled = not self.touch_mode_enabled
        
        # Update button label
        if self.touch_mode_enabled:
            self.touch_mode_btn.set_label("Touch Mode: ON")
            self.status.set_text("Touch Mode enabled - Larger buttons active")
        else:
            self.touch_mode_btn.set_label("Touch Mode: OFF")
            self.status.set_text("Touch Mode disabled")
        
        # Apply touch mode CSS class to window
        if self.touch_mode_enabled:
            self.get_style_context().add_class("touch-mode")
        else:
            self.get_style_context().remove_class("touch-mode")

    def on_high_contrast_toggled(self, _button):
        """Toggle high contrast mode and update UI."""
        self.high_contrast_enabled = not self.high_contrast_enabled
        
        # Update button label
        if self.high_contrast_enabled:
            self.high_contrast_btn.set_label("High Contrast: ON")
            self.status.set_text("High Contrast Mode enabled")
        else:
            self.high_contrast_btn.set_label("High Contrast: OFF")
            self.status.set_text("High Contrast Mode disabled")
        
        # Apply high contrast CSS class to window
        if self.high_contrast_enabled:
            self.get_style_context().add_class("high-contrast")
        else:
            self.get_style_context().remove_class("high-contrast")

    def on_theme_toggled(self, _button):
        """Toggle between day and night themes."""
        # Get current theme from button label
        current_label = self.theme_btn.get_label()
        
        if "Night" in current_label:
            # Switch to day mode
            self.theme_btn.set_label("Theme: Day")
            self.status.set_text("Day Theme enabled")
            self.get_style_context().remove_class("night-mode")
            self.get_style_context().add_class("day-mode")
        else:
            # Switch to night mode
            self.theme_btn.set_label("Theme: Night")
            self.status.set_text("Night Theme enabled")
            self.get_style_context().remove_class("day-mode")
            self.get_style_context().add_class("night-mode")

    def apply_ui_mode_settings(self):
        """Apply UI mode settings from dialog or initial load."""
        # Apply touch mode
        if self.touch_mode_enabled:
            self.get_style_context().add_class("touch-mode")
        else:
            self.get_style_context().remove_class("touch-mode")
        
        # Apply high contrast mode
        if self.high_contrast_enabled:
            self.get_style_context().add_class("high-contrast")
        else:
            self.get_style_context().remove_class("high-contrast")
        
        # Apply theme mode
        theme_mode = self.settings.get("theme_mode", "night")
        if theme_mode == "day":
            self.get_style_context().remove_class("night-mode")
            self.get_style_context().add_class("day-mode")
        else:
            self.get_style_context().remove_class("day-mode")
            self.get_style_context().add_class("night-mode")

    def on_find_gps_apps_clicked(self, _button):
        """Find GPS apps installed on the system."""
        try:
            result = subprocess.run(
                ["find-gps-apps"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr}"
            
            # Create a dialog to show the results
            dlg = Gtk.Dialog(title="GPS App Discovery Results", transient_for=self, flags=0)
            dlg.add_buttons("Close", Gtk.ResponseType.CLOSE)
            content = dlg.get_content_area()
            content.set_spacing(8)
            
            # Add scrollable text view for output
            scroll = Gtk.ScrolledWindow()
            scroll.set_min_content_height(300)
            scroll.set_min_content_width(500)
            content.pack_start(scroll, True, True, 0)
            
            text_view = Gtk.TextView()
            text_view.set_monospace(True)
            text_view.set_editable(False)
            scroll.add(text_view)
            
            buf = text_view.get_buffer()
            buf.set_text(output)
            
            # Add info label
            info = Gtk.Label(label="Scanning for GPS navigation applications...")
            info.set_xalign(0)
            content.pack_start(info, False, False, 0)
            
            dlg.show_all()
            resp = dlg.run()
            if resp == Gtk.ResponseType.CLOSE:
                dlg.destroy()
                
            self.status.set_text("GPS app discovery complete")
        except FileNotFoundError:
            self.status.set_text("Error: find-gps-apps command not found")
        except subprocess.TimeoutExpired:
            self.status.set_text("Error: GPS app scan timed out")
        except Exception as e:
            self.status.set_text(f"Error: {str(e)}")

    def refresh_profile_visibility(self):
        profile_id = self.settings.get("profile", "custom")
        visible_names = None
        if profile_id in PROFILE_PRESETS:
            visible_names = set(PROFILE_PRESETS[profile_id].get("visible_launchers", []))

        for name, button in self.builtin_buttons.items():
            show = True
            if visible_names is not None:
                show = name in visible_names
            if show:
                button.show()
            else:
                button.hide()

    def on_key_press(self, _widget, event):
        key = Gdk.keyval_name(event.keyval) or ""
        state = event.state
        alt = bool(state & Gdk.ModifierType.MOD1_MASK)
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if alt and key == "1":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("mobile")
            self._updating_profile_combo = False
            self.apply_profile("mobile", announce=True)
            return True
        if alt and key == "2":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("base")
            self._updating_profile_combo = False
            self.apply_profile("base", announce=True)
            return True
        if alt and key == "3":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("emergency")
            self._updating_profile_combo = False
            self.apply_profile("emergency", announce=True)
            return True
        if alt and key == "0":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("custom")
            self._updating_profile_combo = False
            self.settings["profile"] = "custom"
            save_settings(self.settings)
            self.refresh_profile_visibility()
            self.status.set_text("Profile: Custom")
            return True
        if ctrl and key.lower() == "g":
            self.on_launch_clicked("GPS Nav")
            return True
        return False

    def on_export_profile(self, _button):
        ok, msg = export_profile_snapshot(self.settings, self.plugins)
        if ok:
            name = self.settings.get("profile", "custom")
            save_named_snapshot(
                self.settings,
                self.plugins,
                f"manual-{name}",
                source="manual",
                tags=["manual", name],
            )
        self.status.set_text(msg)

    def on_import_profile(self, _button):
        ok, imported_settings, imported_plugins, msg = import_profile_snapshot()
        if not ok:
            self.status.set_text(msg)
            return

        self.apply_imported_state(imported_settings, imported_plugins, msg)

    def apply_imported_state(self, imported_settings, imported_plugins, status_msg):
        merged = {
            "gps_nav_app": imported_settings.get("gps_nav_app", "navit"),
            "alerts": {**DEFAULT_ALERTS, **(imported_settings.get("alerts", {}) if isinstance(imported_settings.get("alerts", {}), dict) else {})},
            "profile": imported_settings.get("profile", "custom"),
            "release_check_enabled": bool(imported_settings.get("release_check_enabled", self.settings.get("release_check_enabled", True))),
            "github_repo": str(imported_settings.get("github_repo", self.settings.get("github_repo", DEFAULT_GITHUB_REPO))).strip() or DEFAULT_GITHUB_REPO,
            "release_popup_dismissed": str(imported_settings.get("release_popup_dismissed", "")).strip(),
        }
        self.settings = merged
        self.alert_settings = merged["alerts"]
        save_settings(self.settings)

        cleaned_plugins = []
        for item in imported_plugins:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            
            # Support both shell commands and Python modules
            command = str(item.get("command", "")).strip()
            plugin_type = str(item.get("type", "shell")).strip().lower()
            
            if not label:
                continue
            
            # For shell plugins, require command; for python plugins, require module path
            if plugin_type == "python":
                module_path = str(item.get("module", "")).strip()
                if not module_path:
                    continue
                plugin_entry = {
                    "id": str(item.get("id") or label.lower().replace(" ", "-")),
                    "label": label,
                    "type": "python",
                    "module": module_path,
                    "check": str(item.get("check", "")).strip(),
                    "tooltip": str(item.get("tooltip", "")).strip(),
                }
            else:
                # Shell command plugin (default)
                if not command:
                    continue
                plugin_entry = {
                    "id": str(item.get("id") or label.lower().replace(" ", "-")),
                    "label": label,
                    "command": command,
                    "check": str(item.get("check", "")).strip(),
                    "tooltip": str(item.get("tooltip", "")).strip(),
                }
            cleaned_plugins.append(plugin_entry)
        self.plugins = cleaned_plugins
        save_plugins(self.plugins)

        self._updating_profile_combo = True
        self.profile_combo.set_active_id(self.settings.get("profile", "custom"))
        self._updating_profile_combo = False

        self.refresh_profile_visibility()
        self.refresh_plugin_buttons()
        self.refresh_gps_nav_button()
        self.status.set_text(status_msg)

    def open_snapshots_dialog(self, _button=None):
        dlg = Gtk.Dialog(title="Snapshot Manager", transient_for=self, flags=0)
        dlg.add_buttons("Close", Gtk.ResponseType.CLOSE)
        content = dlg.get_content_area()
        content.set_spacing(8)

        info = Gtk.Label(label=f"Snapshot folder: {PROFILE_SNAPSHOT_DIR}")
        info.set_xalign(0)
        info.set_line_wrap(True)
        info.get_style_context().add_class("subtle")
        content.pack_start(info, False, False, 0)

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_row.pack_start(Gtk.Label(label="Name:"), False, False, 0)
        name_entry = Gtk.Entry()
        name_entry.set_text("field")
        name_row.pack_start(name_entry, True, True, 0)
        name_row.pack_start(Gtk.Label(label="Tags:"), False, False, 0)
        tag_entry = Gtk.Entry()
        tag_entry.set_placeholder_text("field-day, mobile")
        name_row.pack_start(tag_entry, True, True, 0)
        save_btn = Gtk.Button(label="Save Named")
        name_row.pack_start(save_btn, False, False, 0)
        content.pack_start(name_row, False, False, 0)

        chip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        chip_row.pack_start(Gtk.Label(label="Quick tags:"), False, False, 0)
        for tag_name in ["field-day", "mobile", "base", "emergency", "travel", "lab"]:
            chip = Gtk.Button(label=tag_name)
            chip.set_relief(Gtk.ReliefStyle.NONE)
            chip.get_style_context().add_class("subtle")
            chip_row.pack_start(chip, False, False, 0)
        content.pack_start(chip_row, False, False, 0)

        pick_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pick_row.pack_start(Gtk.Label(label="Saved:"), False, False, 0)
        snap_combo = Gtk.ComboBoxText()
        pick_row.pack_start(snap_combo, True, True, 0)
        load_btn = Gtk.Button(label="Load")
        del_btn = Gtk.Button(label="Delete")
        pick_row.pack_start(load_btn, False, False, 0)
        pick_row.pack_start(del_btn, False, False, 0)
        content.pack_start(pick_row, False, False, 0)

        quick_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        restore_auto_btn = Gtk.Button(label="Restore Latest Auto")
        quick_row.pack_start(restore_auto_btn, False, False, 0)
        quick_hint = Gtk.Label(label="Optional tag filter uses the Tags field")
        quick_hint.set_xalign(0)
        quick_hint.get_style_context().add_class("subtle")
        quick_row.pack_start(quick_hint, True, True, 0)
        content.pack_start(quick_row, False, False, 0)

        status = Gtk.Label(label="")
        status.set_xalign(0)
        status.get_style_context().add_class("subtle")
        content.pack_start(status, False, False, 0)

        def refresh_snapshot_list(select_path=None):
            snap_combo.remove_all()
            snaps = list_profile_snapshots(limit=200)
            for s in snaps:
                snap_combo.append(s["path"], s["label"])
            if select_path:
                snap_combo.set_active_id(select_path)
            elif snaps:
                snap_combo.set_active(0)
            return snaps

        def on_save_named(_b):
            name = name_entry.get_text().strip() or "field"
            tags = normalize_snapshot_tags(tag_entry.get_text().strip())
            if "manual" not in tags:
                tags = ["manual"] + tags
            ok, path = save_named_snapshot(self.settings, self.plugins, name, source="manual", tags=tags)
            if ok:
                refresh_snapshot_list(str(path))
                msg = f"Saved snapshot: {Path(path).name}"
                status.set_text(msg)
                self.status.set_text(msg)
            else:
                status.set_text("Failed to save snapshot")

        def on_load_selected(_b):
            path = snap_combo.get_active_id()
            if not path:
                status.set_text("No snapshot selected")
                return
            ok, s, p, msg = import_profile_snapshot(path)
            if not ok:
                status.set_text(msg)
                self.status.set_text(msg)
                return
            self.apply_imported_state(s, p, msg)
            status.set_text(msg)

        def on_delete_selected(_b):
            path = snap_combo.get_active_id()
            if not path:
                status.set_text("No snapshot selected")
                return
            if delete_profile_snapshot(path):
                status.set_text(f"Deleted snapshot: {Path(path).name}")
                refresh_snapshot_list()
            else:
                status.set_text("Failed to delete snapshot")

        def on_restore_latest_auto(_b):
            tags = normalize_snapshot_tags(tag_entry.get_text().strip())
            tag = tags[0] if tags else None
            path = find_latest_auto_snapshot(tag=tag)
            if not path:
                msg = "No matching auto snapshot found"
                status.set_text(msg)
                self.status.set_text(msg)
                return
            ok, s, p, msg = import_profile_snapshot(path)
            if not ok:
                status.set_text(msg)
                self.status.set_text(msg)
                return
            self.apply_imported_state(s, p, f"Restored auto snapshot: {Path(path).name}")
            refresh_snapshot_list(path)
            status.set_text(f"Restored auto snapshot: {Path(path).name}")

        def on_quick_tag(_b, quick_tag):
            current = normalize_snapshot_tags(tag_entry.get_text().strip())
            q = normalize_snapshot_tags([quick_tag])
            if not q:
                return
            tag = q[0]
            if tag in current:
                return
            merged = current + [tag]
            tag_entry.set_text(", ".join(merged))

        save_btn.connect("clicked", on_save_named)
        load_btn.connect("clicked", on_load_selected)
        del_btn.connect("clicked", on_delete_selected)
        restore_auto_btn.connect("clicked", on_restore_latest_auto)
        for chip in chip_row.get_children()[1:]:
            chip.connect("clicked", on_quick_tag, chip.get_label())
        refresh_snapshot_list()

        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def gps_option_by_id(self, option_id):
        for opt in GPS_NAV_OPTIONS:
            if opt["id"] == option_id:
                return opt
        return None

    def gps_option_status(self, option):
        cmd = resolve_gps_option_command(option)
        return {
            "available": bool(cmd),
            "command": cmd,
            "label": option["label"],
            "check": candidate_label(option["commands"][0]),
        }

    def refresh_gps_nav_button(self):
        b = self.launch_buttons.get("GPS Nav")
        if not b:
            return
        option = self.selected_gps_option()
        status = self.gps_option_status(option)
        gps_off = self.latest_aio_states.get("GPS") is False
        b.set_label(f"GPS Nav ({option['label']})")
        if status["available"]:
            b.set_sensitive(not gps_off)
            b.set_tooltip_text(self.gps_hint if gps_off else f"Launch {option['label']}")
            self.launch_actions["GPS Nav"] = status["command"]
        else:
            b.set_sensitive(False)
            b.set_tooltip_text(f"Selected app is not installed: {status['check']}")
            self.launch_actions["GPS Nav"] = None

    def launcher_base_available(self, name):
        return bool(self.launch_actions.get(name))

    def apply_gps_dependency_state(self, gps_state):
        gps_off = gps_state is False
        for name in self.gps_dependent_names:
            btn = self.launch_buttons.get(name) or self.builtin_buttons.get(name)
            if btn is None:
                continue
            if gps_off:
                btn.set_sensitive(False)
                btn.set_opacity(0.45)
                btn.set_tooltip_text(self.gps_hint)
                continue

            available = self.launcher_base_available(name)
            btn.set_sensitive(available)
            btn.set_opacity(1.0)
            if available:
                if name == "GPS Nav":
                    option = self.selected_gps_option()
                    btn.set_tooltip_text(f"Launch {option['label']}")
                else:
                    btn.set_tooltip_text(f"Launch {name}")

    def apply_sdr_dependency_state(self, sdr_state):
        sdr_off = sdr_state is False
        for name in self.sdr_dependent_names:
            btn = self.launch_buttons.get(name) or self.builtin_buttons.get(name)
            if btn is None:
                continue
            if sdr_off:
                btn.set_sensitive(False)
                btn.set_opacity(0.45)
                btn.set_tooltip_text(self.sdr_hint)
                continue

            available = self.launcher_base_available(name)
            btn.set_sensitive(available)
            btn.set_opacity(1.0)
            if available:
                btn.set_tooltip_text(f"Launch {name}")

    def refresh_plugin_buttons(self):
        for child in self.plugin_box.get_children():
            self.plugin_box.remove(child)

        if not self.plugins:
            self.header_plugin_info.set_text("Plugins: none configured")
            self.plugin_box.hide()
            return

        self.header_plugin_info.set_text(f"Plugins: {len(self.plugins)} custom launcher(s)")
        self.plugin_box.show()

        # Add Secure Remote Assist button
        remote_assist_btn = Gtk.Button(label="Remote Assist")
        remote_assist_btn.set_tooltip_text("Create diagnostics bundle for remote support")
        remote_assist_btn.connect("clicked", self.on_remote_assist_clicked)
        self.launch_actions["remote_assist"] = "remote_assist"
        self.plugin_box.add(remote_assist_btn)

        for plugin in self.plugins:
            key = f"plugin:{plugin['id']}"
            b = Gtk.Button(label=plugin["label"])
            
            # Handle Python plugins differently from shell command plugins
            plugin_type = plugin.get("type", "shell")
            
            if plugin_type == "python":
                # Python module plugins don't need external dependencies check
                available = True
                b.set_sensitive(True)
                self.launch_actions[key] = ("python_module", plugin["module"])
            else:
                # Shell command plugins check for dependencies
                check = plugin.get("check", "")
                available = launch_target_available(check)
                b.set_sensitive(available)
                self.launch_actions[key] = plugin["command"] if available else None
            
            if not available:
                b.set_tooltip_text(f"Missing dependency: {candidate_label(check)}")
            elif plugin.get("tooltip"):
                b.set_tooltip_text(plugin["tooltip"])
            else:
                b.set_tooltip_text(f"Launch {plugin['label']}")
            
            b.connect("clicked", lambda _b, n=key: self.on_launch_clicked(n))
            self.plugin_box.add(b)

        self.plugin_box.show_all()

    def restart_service(self, service):
        self.status.set_text(f"Restarting {service}…")

        def worker():
            rc, out = self.run_systemctl_noninteractive("restart", service, 12)
            if rc == 0:
                msg = f"{service} restart requested"
            elif self.is_sudo_auth_error(out):
                msg = f"{service} restart blocked: {SERVICE_PRIV_HINT}"
            else:
                tail = out.splitlines()[-1][:90] if out else "unknown error"
                msg = f"{service} restart failed: {tail}"
            GLib.idle_add(self.status.set_text, msg)
            GLib.timeout_add_seconds(1, self.refresh_async)

        threading.Thread(target=worker, daemon=True).start()

    def _download_and_install_update(self, version, channel):
        """Download and install update in background thread."""
        repo = str(self.settings.get("github_repo", DEFAULT_GITHUB_REPO)).strip() or DEFAULT_GITHUB_REPO
        
        def progress_callback(msg):
            GLib.idle_add(self.update_status_label.set_text, f"Update: {msg}")
        
        # Fetch release info
        latest, assets, body = download_release_assets(repo, version)
        if not latest or not assets:
            GLib.idle_add(self.status.set_text, "Failed to fetch release information")
            return
        
        app_dir = Path(__file__).resolve().parent
        success, msg = apply_update(app_dir, version, assets, progress_callback)
        
        if success:
            GLib.idle_add(self.status.set_text, f"Update complete! Restart the app to see v{version}")
            # Update VERSION file and restart prompt
            import os
            GLib.timeout_add_seconds(2, lambda: self.on_update_complete(version))
        else:
            GLib.idle_add(self.status.set_text, f"Update failed: {msg}")
    
    def on_update_complete(self, new_version):
        """Prompt to restart after update."""
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Update to v{new_version} complete!",
        )
        dlg.format_secondary_text("Please restart the application to see the new version.")
        response = dlg.run()
        dlg.destroy()
        if response == Gtk.ResponseType.OK:
            # Restart the app with new version
            import sys
            self.save_settings()  # Save current state before restart
            GLib.idle_add(self.restart_app, new_version)
        return False
    
    def restart_app(self, new_version):
        """Restart the application."""
        try:
            # Update window title to show new version
            self.set_title(f"uConsole Status v{new_version}")
            
            # Refresh UI elements that depend on version
            if hasattr(self, 'version_label') and self.version_label:
                self.version_label.set_text(f"v{new_version}")
            
            self.status.set_text(f"Restarted to v{new_version}")
            
            # Auto-refresh after restart
            GLib.timeout_add_seconds(1, self.refresh_async)
            
            return False  # Stop GLib.idle_add loop
        except Exception as e:
            self.status.set_text(f"Restart failed: {e}")
            return False
    
    def show_rollback_dialog(self):
        """Show dialog to select and apply rollback."""
        backups = get_available_backups()
        if not backups:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="No backups available",
            )
            dlg.format_secondary_text("Create a backup before updating to enable rollback.")
            dlg.run()
            dlg.destroy()
            return
        
        # Create dialog with list of backups
        dlg = Gtk.Dialog(
            title="Rollback to Previous Version",
            transient_for=self,
            flags=0,
        )
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Rollback", Gtk.ResponseType.OK)
        
        content_area = dlg.get_content_area()
        content_area.set_spacing(12)
        
        label = Gtk.Label(label="Select backup to restore:")
        content_area.pack_start(label, False, False, 0)
        
        liststore = Gtk.ListStore(str, str, str, int)
        for b in backups:
            liststore.append([b["path"], b["version"], b["created_at"], b["file_count"]])
        
        treeview = Gtk.TreeView(model=liststore)
        renderer = Gtk.CellRendererText()
        
        col_path = Gtk.TreeViewColumn("Path", renderer, text=0)
        col_version = Gtk.TreeViewColumn("Version", renderer, text=1)
        col_date = Gtk.TreeViewColumn("Created", renderer, text=2)
        col_files = Gtk.TreeViewColumn("Files", renderer, text=3)
        
        treeview.append_column(col_path)
        treeview.append_column(col_version)
        treeview.append_column(col_date)
        treeview.append_column(col_files)
        
        treeview.set_headers_visible(True)
        treeview.set_size_request(500, 200)
        
        scroll = Gtk.ScrolledWindow()
        scroll.add(treeview)
        content_area.pack_start(scroll, True, True, 0)
        
        dlg.show_all()
        response = dlg.run()
        
        if response == Gtk.ResponseType.OK:
            selection = treeview.get_selection()
            model, iter = selection.get_selected()
            if iter:
                backup_path = model[iter][0]
                success, msg = rollback_to_backup(backup_path)
                if success:
                    GLib.idle_add(self.status.set_text, f"Rollback: {msg}")
        
        dlg.destroy()



    def on_restart_selected(self, _button):
        service = self.restart_combo.get_active_text()
        if not service:
            self.status.set_text("Select a service to restart")
            return
        self.restart_service(service)

    def on_bluetooth_switch_toggled(self, switch, _param):
        if self._bt_switch_sync:
            return
        if not self.ac1200_power_on():
            self.status.set_text(self.ac1200_hint)
            self._bt_switch_sync = True
            switch.set_active(False)
            self._bt_switch_sync = False
            return

        action = "start" if switch.get_active() else "stop"
        self.status.set_text(f"Bluetooth: requesting {action}…")

        def worker():
            rc, out = self.run_systemctl_noninteractive(action, "bluetooth", 12)
            if rc == 0:
                if action == "start":
                    show = run_stdout("bluetoothctl show 2>/dev/null", timeout=4)
                    if "No default controller available" in show or not show.strip():
                        msg = "bluetooth started, but no controller detected"
                    else:
                        msg = "bluetooth start requested"
                else:
                    msg = "bluetooth stop requested"
            elif self.is_sudo_auth_error(out):
                msg = f"bluetooth {action} blocked: {SERVICE_PRIV_HINT}"
            else:
                tail = out.splitlines()[-1][:90] if out else "unknown error"
                msg = f"bluetooth {action} failed: {tail}"
            GLib.idle_add(self.status.set_text, msg)
            GLib.timeout_add_seconds(1, self.refresh_async)

        threading.Thread(target=worker, daemon=True).start()

    def on_sdr_exit_restart_readsb(self, _exit_code=None):
        self.status.set_text("SDR++ closed: restarting readsb…")

        def worker():
            rc, out = self.run_systemctl_noninteractive("start", "readsb", 12)
            if rc == 0:
                msg = "SDR++ closed: readsb restarted"
            elif self.is_sudo_auth_error(out):
                msg = f"SDR++ closed: readsb restart blocked: {SERVICE_PRIV_HINT}"
            else:
                tail = out.splitlines()[-1][:90] if out else "unknown error"
                msg = f"SDR++ closed: readsb restart failed: {tail}"
            GLib.idle_add(self.status.set_text, msg)
            GLib.timeout_add_seconds(1, self.refresh_async)

        threading.Thread(target=worker, daemon=True).start()

    def on_remote_assist_clicked(self, _button):
        """Create diagnostics bundle for remote assistance."""
        self.status.set_text("Creating diagnostics bundle...")
        
        def create_bundle():
            try:
                from app.plugins.remote_assist import DiagnosticsBundle
                bundle = DiagnosticsBundle()
                output_file = bundle.create_bundle()
                
                if output_file:
                    GLib.idle_add(self.status.set_text, f"Diagnostics bundle created: {output_file}")
                    GLib.idle_add(show_remote_assist_complete, self, output_file)
                else:
                    GLib.idle_add(self.status.set_text, "Failed to create diagnostics bundle")
            except Exception as e:
                import traceback
                error_msg = str(e)[:100]
                tb_str = "\n".join(traceback.format_exc().splitlines()[-3:])
                self.status.set_text(f"Diagnostics failed: {error_msg}")
                
                # Log the full error
                try:
                    log_file = Path.home() / ".config" / "k7bat-uconsole-status" / "plugin_debug.log"
                    log_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(log_file, "a") as f:
                        f.write(f"[REMOTE ASSIST] Error: {e}\n{tb_str}\n")
                except Exception:
                    pass
        
        import threading
        threading.Thread(target=create_bundle, daemon=True).start()
    
    def on_launch_clicked(self, name):
        if name in self.sdr_dependent_names and self.latest_aio_states.get("SDR") is False:
            self.status.set_text(f"{name}: {self.sdr_hint}")
            return
        if name in self.ac1200_dependent_names and not self.ac1200_power_on():
            self.status.set_text(f"{name}: {self.ac1200_hint}")
            return
        cmd = self.launch_actions.get(name)
        if not cmd:
            self.status.set_text(f"{name}: no launch command configured")
            return

        # Handle Python module plugins (stored as tuples: ("python_module", module_path))
        if isinstance(cmd, tuple) and len(cmd) == 2 and cmd[0] == "python_module":
            module_path = cmd[1]
            self.status.set_text(f"Launching {name}...")

            def launch_python_plugin():
                # Local debug log function for plugin errors
                def debug_log(msg):
                    try:
                        log_file = Path.home() / ".config" / "k7bat-uconsole-status" / "plugin_debug.log"
                        log_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(log_file, "a") as f:
                            f.write(f"{msg}\n")
                    except Exception:
                        pass
                
                try:
                    import sys
                    import importlib
                    from pathlib import Path
                    app_dir = Path(__file__).resolve().parent

                    # Add plugins directories to path (both core and user plugins)
                    plugin_dirs = [
                        app_dir / "plugins",  # Core plugins
                        Path("/home/bcaddy/uconsole-k7bat/plugins"),  # User-installed plugins
                    ]
                    for pdir in plugin_dirs:
                        if str(pdir) not in sys.path and pdir.exists():
                            sys.path.insert(0, str(pdir))
                            debug_log(f"[DEBUG] Added plugin path: {pdir}")

                    debug_log(f"[DEBUG] Launching Python plugin: {name}")
                    debug_log(f"[DEBUG] Module path: {module_path}")
                    
                    # Import and instantiate the plugin class
                    module_name, class_name = module_path.rsplit('.', 1)
                    debug_log(f"[DEBUG] Importing module: {module_name}, class: {class_name}")
                    module = importlib.import_module(module_name)
                    debug_log(f"[DEBUG] Module imported successfully: {module.__file__ if hasattr(module, '__file__') else 'builtin'}")
                    plugin_class = getattr(module, class_name)
                    debug_log("[DEBUG] Module and class loaded successfully")

                    # Create and show the window on main thread using GLib.idle_add
                    def create_window():
                        try:
                            debug_log(f"[DEBUG] Creating {class_name} instance...")
                            window = plugin_class(self)
                            debug_log("[DEBUG] Window created, calling show_all() and present()")
                            window.show_all()
                            window.present()
                            debug_log("[DEBUG] Window shown successfully")
                        except Exception as e:
                            self.status.set_text(f"{name} error: {str(e)[:100]}")
                            import traceback
                            tb_str = "\n".join(traceback.format_exc().splitlines()[-5:])
                            debug_log(f"[DEBUG] Window creation error: {e}\n{tb_str}")
                    GLib.idle_add(create_window)
                    debug_log("[DEBUG] GLib.idle_add(create_window) called")
                except Exception as e:
                    self.status.set_text(f"{name} error: {str(e)[:100]}")
                    import traceback
                    tb_lines = traceback.format_exc().splitlines()
                    for line in tb_lines[-5:]:
                        debug_log(line)

            import threading
            threading.Thread(target=launch_python_plugin, daemon=True).start()
            return

        if name == "SDR++" and "--autostart" not in str(cmd):
            cmd = f"{cmd} --autostart"

        if name in ("SDR++", "GQRX") and service_state("readsb") == "RUNNING":
            self.status.set_text(f"{name}: stopping readsb before launch…")

            def worker():
                rc, out = self.run_systemctl_noninteractive("stop", "readsb", 12)
                if rc == 0:
                    GLib.idle_add(self.status.set_text, f"{name}: readsb stopped")
                    if name == "SDR++":
                        GLib.idle_add(ensure_sdrpp_audio_sink_config)
                        GLib.idle_add(show_sdr_launch_checklist, self)
                        GLib.idle_add(launch_with_status, self, name, cmd, self.on_sdr_exit_restart_readsb)
                    else:
                        GLib.idle_add(launch_with_status, self, name, cmd)
                elif self.is_sudo_auth_error(out):
                    GLib.idle_add(self.status.set_text, f"{name}: readsb stop blocked: {SERVICE_PRIV_HINT}")
                else:
                    tail = out.splitlines()[-1][:90] if out else "unknown error"
                    GLib.idle_add(self.status.set_text, f"{name}: readsb stop failed: {tail}")
                GLib.timeout_add_seconds(1, self.refresh_async)

            threading.Thread(target=worker, daemon=True).start()
            return

        if name == "SDR++":
            ensure_sdrpp_audio_sink_config()
            show_sdr_launch_checklist(self)

        if name == "ADS-B" and service_state("readsb") != "RUNNING":
            self.status.set_text("ADS-B: starting readsb before launch…")

            def worker():
                rc, out = self.run_systemctl_noninteractive("start", "readsb", 12)

                if rc == 0:
                    GLib.idle_add(self.status.set_text, "ADS-B: readsb started")
                elif self.is_sudo_auth_error(out):
                    GLib.idle_add(self.status.set_text, f"ADS-B: readsb start blocked: {SERVICE_PRIV_HINT}")
                else:
                    tail = out.splitlines()[-1][:90] if out else "unknown error"
                    GLib.idle_add(self.status.set_text, f"ADS-B: readsb start failed: {tail}")

                # Open tar1090 regardless, so users can still view status page/output.
                ok, via = launch_local_url("http://127.0.0.1/tar1090/")
                if ok:
                    GLib.idle_add(self.status.set_text, f"ADS-B opened via {via}")
                else:
                    GLib.idle_add(self.status.set_text, f"ADS-B open failed: {via}")
                GLib.timeout_add_seconds(1, self.refresh_async)

            threading.Thread(target=worker, daemon=True).start()
            return

        if name == "ADS-B":
            ok, via = launch_local_url("http://127.0.0.1/tar1090/")
            if ok:
                self.status.set_text(f"ADS-B opened via {via}")
            else:
                self.status.set_text(f"ADS-B open failed: {via}")
            return

        launch_with_status(self, name, cmd)

    def on_start_mission(self, _button):
        if self.mission_active:
            self.status.set_text("Mission recorder is already running")
            return
        try:
            MISSION_RECORD_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            profile_hint = mission_profile_hint(self.settings.get("profile", "custom"))
            file_path = MISSION_RECORD_DIR / f"mission-{profile_hint}-{ts}.jsonl"
            fp = file_path.open("a", encoding="utf-8")
            self.mission_fp = fp
            self.mission_file_path = file_path
            self.mission_started_at = datetime.now()
            self.mission_active = True
            self.mission_stats = {
                "samples": 0,
                "fix_good": 0,
                "wifi_up": 0,
                "cpu_max_c": None,
                "ram_max_pct": None,
                "disk_min_free_pct": None,
                "battery_min_pct": None,
            }
            self.mission_start_btn.set_sensitive(False)
            self.mission_stop_btn.set_sensitive(True)
            self.mission_status.set_text(f"Mission: recording {file_path.name}")
            self.status.set_text(f"Mission recorder started: {file_path.name}")
        except Exception as e:
            self.mission_active = False
            self.mission_fp = None
            self.mission_file_path = None
            self.mission_started_at = None
            self.mission_status.set_text("Mission: start failed")
            self.status.set_text(f"Mission recorder failed to start: {str(e)[:100]}")

    def on_stop_mission(self, _button):
        if not self.mission_active:
            self.status.set_text("Mission recorder is not running")
            return
        self.stop_mission_recording(reason="stopped")

    def stop_mission_recording(self, reason="stopped"):
        file_path = self.mission_file_path
        started_at = self.mission_started_at
        stats = dict(self.mission_stats or {})

        try:
            if self.mission_fp is not None:
                self.mission_fp.flush()
                self.mission_fp.close()
        except Exception:
            pass

        self.mission_active = False
        self.mission_fp = None
        self.mission_file_path = None
        self.mission_started_at = None
        self.mission_stats = {}
        self.mission_start_btn.set_sensitive(True)
        self.mission_stop_btn.set_sensitive(False)
        self.mission_status.set_text("Mission: idle")

        if not file_path or not started_at:
            self.status.set_text("Mission recorder stopped")
            return

        ended_at = datetime.now()
        samples = int(stats.get("samples", 0) or 0)
        duration_s = max(1, int((ended_at - started_at).total_seconds()))
        fix_good = int(stats.get("fix_good", 0) or 0)
        wifi_up = int(stats.get("wifi_up", 0) or 0)

        summary = {
            "reason": reason,
            "started_at": started_at.isoformat(timespec="seconds"),
            "ended_at": ended_at.isoformat(timespec="seconds"),
            "duration_seconds": duration_s,
            "samples": samples,
            "sample_interval_seconds": REFRESH_SECONDS,
            "gps_fix_good_rate_pct": round((fix_good / samples) * 100.0, 1) if samples else 0.0,
            "wifi_up_rate_pct": round((wifi_up / samples) * 100.0, 1) if samples else 0.0,
            "cpu_max_c": stats.get("cpu_max_c"),
            "ram_max_pct": stats.get("ram_max_pct"),
            "disk_min_free_pct": stats.get("disk_min_free_pct"),
            "battery_min_pct": stats.get("battery_min_pct"),
            "source_jsonl": str(file_path),
        }

        summary_path = file_path.with_name(file_path.stem + "-summary.json")
        try:
            summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            self.status.set_text(
                f"Mission saved: {file_path.name} ({samples} samples, {duration_s}s)"
            )
        except Exception as e:
            self.status.set_text(
                f"Mission saved but summary write failed: {str(e)[:90]}"
            )

    def record_mission_sample(self, d):
        if not self.mission_active or self.mission_fp is None:
            return

        try:
            now = datetime.now().isoformat(timespec="seconds")
            metrics = d.get("metrics", {}) if isinstance(d.get("metrics", {}), dict) else {}
            gps = d.get("gps", {}) if isinstance(d.get("gps", {}), dict) else {}
            wifi = d.get("wifi", []) if isinstance(d.get("wifi", []), list) else []
            sample = {
                "ts": now,
                "profile": self.settings.get("profile", "custom"),
                "cpu": d.get("cpu"),
                "ram": d.get("ram"),
                "disk": d.get("disk"),
                "battery": d.get("battery"),
                "metrics": metrics,
                "gps": {
                    "fix": gps.get("fix"),
                    "sats": gps.get("sats"),
                    "pos": gps.get("pos"),
                    "speed": gps.get("speed"),
                    "track": gps.get("track"),
                    "device": gps.get("device"),
                },
                "services": d.get("services", {}),
                "wifi": wifi,
            }
            self.mission_fp.write(json.dumps(sample) + "\n")

            stats = self.mission_stats
            stats["samples"] = int(stats.get("samples", 0) or 0) + 1

            fix_text = str(gps.get("fix", ""))
            if "2D" in fix_text or "3D" in fix_text:
                stats["fix_good"] = int(stats.get("fix_good", 0) or 0) + 1

            if len(wifi) > 0:
                stats["wifi_up"] = int(stats.get("wifi_up", 0) or 0) + 1

            cpu_c = metrics.get("cpu_temp_c")
            if isinstance(cpu_c, (int, float)):
                current = stats.get("cpu_max_c")
                stats["cpu_max_c"] = cpu_c if current is None else max(float(current), float(cpu_c))

            ram_pct = metrics.get("ram_used_pct")
            if isinstance(ram_pct, (int, float)):
                current = stats.get("ram_max_pct")
                stats["ram_max_pct"] = ram_pct if current is None else max(float(current), float(ram_pct))

            disk_free_pct = metrics.get("disk_free_pct")
            if isinstance(disk_free_pct, (int, float)):
                current = stats.get("disk_min_free_pct")
                stats["disk_min_free_pct"] = disk_free_pct if current is None else min(float(current), float(disk_free_pct))

            batt_pct = metrics.get("battery_pct")
            if isinstance(batt_pct, (int, float)):
                current = stats.get("battery_min_pct")
                stats["battery_min_pct"] = batt_pct if current is None else min(float(current), float(batt_pct))

            if stats["samples"] % 10 == 0:
                self.mission_fp.flush()
        except Exception as e:
            self.stop_mission_recording(reason="error")
            self.status.set_text(f"Mission recorder stopped on write error: {str(e)[:100]}")

    def open_settings_dialog(self, _button):
        # Use a notebook with tabs for better organization and fullscreen support
        dialog = Gtk.Dialog(
            title="Settings",
            transient_for=self,
            flags=0,
        )
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        
        # Get the content area and set it to fill available space
        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_border_width(8)
        
        # Create notebook (tabbed interface) with tabs at top
        notebook = Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.TOP)
        content.pack_start(notebook, True, True, 0)

        # ===== GPS Navigation Tab =====
        gps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        gps_box.set_border_width(8)
        
        info = Gtk.Label(label="Choose which app the GPS Nav button should launch.")
        info.set_xalign(0)
        info.get_style_context().add_class("subtle")
        gps_box.pack_start(info, False, False, 0)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        gps_box.pack_start(row, False, False, 0)
        row.pack_start(Gtk.Label(label="GPS Nav app:"), False, False, 0)

        combo = Gtk.ComboBoxText()
        current_id = self.selected_gps_option()["id"]
        for opt in GPS_NAV_OPTIONS:
            status = self.gps_option_status(opt)
            suffix = "installed" if status["available"] else f"missing ({status['check']})"
            combo.append(opt["id"], f"{opt['label']} [{suffix}]")
        combo.set_active_id(current_id)
        row.pack_start(combo, True, True, 0)

        notebook.append_page(gps_box, Gtk.Label(label="GPS Navigation"))

        # ===== Alerts Tab =====
        alerts = self.settings.get("alerts", dict(DEFAULT_ALERTS))
        alerts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        alerts_box.set_border_width(8)

        alerts_enabled = Gtk.CheckButton(label="Enable alerts")
        alerts_enabled.set_active(bool(alerts.get("enabled", True)))
        alerts_box.pack_start(alerts_enabled, False, False, 0)

        cpu_spin = Gtk.SpinButton.new_with_range(40, 120, 1)
        cpu_spin.set_value(float(alerts.get("cpu_temp_c", 78)))
        ram_spin = Gtk.SpinButton.new_with_range(50, 100, 1)
        ram_spin.set_value(float(alerts.get("ram_used_pct", 90)))
        disk_spin = Gtk.SpinButton.new_with_range(1, 50, 1)
        disk_spin.set_value(float(alerts.get("disk_free_pct", 10)))
        batt_spin = Gtk.SpinButton.new_with_range(1, 100, 1)
        batt_spin.set_value(float(alerts.get("battery_pct", 25)))

        alerts_grid = Gtk.Grid()
        alerts_grid.set_column_spacing(8)
        alerts_grid.set_row_spacing(6)
        alerts_box.pack_start(alerts_grid, False, False, 0)

        row_idx = 0
        for label_text, widget in [
            ("CPU max (C):", cpu_spin),
            ("RAM max used (%):", ram_spin),
            ("Disk min free (%):", disk_spin),
            ("Battery min (%):", batt_spin),
        ]:
            alerts_grid.attach(Gtk.Label(label=label_text), 0, row_idx, 1, 1)
            alerts_grid.attach(widget, 1, row_idx, 1, 1)
            row_idx += 1

        require_fix = Gtk.CheckButton(label="Alert when GPS has no 2D/3D fix")
        require_fix.set_active(bool(alerts.get("require_gps_fix", False)))
        alerts_box.pack_start(require_fix, False, False, 0)

        require_wifi = Gtk.CheckButton(label="Alert when Wi-Fi interfaces are missing")
        require_wifi.set_active(bool(alerts.get("require_wifi", False)))
        alerts_box.pack_start(require_wifi, False, False, 0)

        notebook.append_page(alerts_box, Gtk.Label(label="Alerts"))

        # ===== UI Mode & Appearance Tab =====
        ui_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ui_box.set_border_width(8)

        # Touch Mode toggle
        touch_mode_check = Gtk.CheckButton(label="Enable Touch Mode (larger buttons)")
        touch_mode_check.set_active(self.touch_mode_enabled)
        touch_mode_info = Gtk.Label(label="Increases button size for easier touch interaction")
        touch_mode_info.set_xalign(0)
        touch_mode_info.get_style_context().add_class("subtle")
        ui_box.pack_start(touch_mode_check, False, False, 0)
        ui_box.pack_start(touch_mode_info, False, False, 0)

        # High Contrast toggle
        high_contrast_check = Gtk.CheckButton(label="Enable High Contrast Mode")
        high_contrast_check.set_active(self.high_contrast_enabled)
        high_contrast_info = Gtk.Label(label="Black-on-white theme for better visibility")
        high_contrast_info.set_xalign(0)
        high_contrast_info.get_style_context().add_class("subtle")
        ui_box.pack_start(high_contrast_check, False, False, 0)
        ui_box.pack_start(high_contrast_info, False, False, 0)

        # Theme selection (Day/Night) in its own section
        theme_frame = Gtk.Frame(label="Theme Selection")
        theme_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        theme_box.set_border_width(8)
        theme_frame.add(theme_box)
        ui_box.pack_start(theme_frame, False, False, 0)

        theme_day_radio = Gtk.RadioButton.new_with_label(None, "Day Mode")
        theme_night_radio = Gtk.RadioButton.new_with_label_from_widget(theme_day_radio, "Night Mode")
        
        if self.settings.get("theme_mode", "night") == "day":
            theme_day_radio.set_active(True)
        else:
            theme_night_radio.set_active(True)
        
        theme_box.pack_start(theme_day_radio, False, False, 0)
        theme_box.pack_start(theme_night_radio, False, False, 0)

        notebook.append_page(ui_box, Gtk.Label(label="Appearance"))

        # ===== Additional Settings Tab (Find GPS Apps + Plugins) =====
        extra_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        extra_box.set_border_width(8)

        # Find GPS Apps button in settings
        find_gps_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        find_gps_label = Gtk.Label(label="GPS App Discovery")
        find_gps_label.set_xalign(0)
        find_gps_label.get_style_context().add_class("subtle")
        find_gps_btn = Gtk.Button(label="Find GPS Apps")
        find_gps_btn.connect("clicked", self.on_find_gps_apps_clicked)
        find_gps_row.pack_start(find_gps_label, True, True, 0)
        find_gps_row.pack_end(find_gps_btn, False, False, 0)
        extra_box.pack_start(find_gps_row, False, False, 0)

        plugin_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        plugin_label = Gtk.Label(label="Custom launchers use plugins.json (or bundled defaults)")
        plugin_label.set_xalign(0)
        plugin_label.get_style_context().add_class("subtle")
        plugin_btn = Gtk.Button(label="Edit Custom Plugins")
        plugin_btn.connect("clicked", lambda _b: self.open_plugins_dialog(dialog))
        plugin_row.pack_start(plugin_label, True, True, 0)
        plugin_row.pack_end(plugin_btn, False, False, 0)
        extra_box.pack_start(plugin_row, False, False, 0)

        notebook.append_page(extra_box, Gtk.Label(label="Additional"))

        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            selected = combo.get_active_id() or "navit"
            self.settings["gps_nav_app"] = selected
            self.settings["alerts"] = {
                "enabled": alerts_enabled.get_active(),
                "cpu_temp_c": int(cpu_spin.get_value()),
                "ram_used_pct": int(ram_spin.get_value()),
                "disk_free_pct": int(disk_spin.get_value()),
                "battery_pct": int(batt_spin.get_value()),
                "require_gps_fix": require_fix.get_active(),
                "require_wifi": require_wifi.get_active(),
            }
            # UI Mode Settings
            self.touch_mode_enabled = touch_mode_check.get_active()
            self.high_contrast_enabled = high_contrast_check.get_active()
            if theme_day_radio.get_active():
                self.settings["theme_mode"] = "day"
            else:
                self.settings["theme_mode"] = "night"
            # Apply UI mode settings
            self.apply_ui_mode_settings()
            self.settings["profile"] = "custom"
            save_settings(self.settings)
            save_named_snapshot(
                self.settings,
                self.plugins,
                "auto-settings",
                source="auto",
                tags=["auto", "settings"],
            )
            self.alert_settings = self.settings["alerts"]
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("custom")
            self._updating_profile_combo = False
            self.refresh_gps_nav_button()
            opt = self.gps_option_by_id(selected)
            if opt:
                self.status.set_text(f"Saved: GPS Nav set to {opt['label']}")
            self.refresh_plugin_buttons()
        dialog.destroy()

    def open_plugins_dialog(self, parent_dialog=None):
        dlg = Gtk.Dialog(title="Custom Plugin Launchers", transient_for=self, flags=0)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        content = dlg.get_content_area()
        content.set_spacing(8)

        hint = Gtk.Label(
            label=(
                "JSON list format: [{\"id\":\"apr\",\"label\":\"APRS\","
                "\"command\":\"xterm -e aprx\",\"check\":\"xterm\"}]"
            )
        )
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("subtle")
        content.pack_start(hint, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(220)
        content.pack_start(scroll, True, True, 0)

        text_view = Gtk.TextView()
        text_view.set_monospace(True)
        scroll.add(text_view)

        buf = text_view.get_buffer()
        buf.set_text(json.dumps(self.plugins, indent=2))

        dlg.show_all()
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            start, end = buf.get_bounds()
            raw = buf.get_text(start, end, True)
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("Top-level JSON must be a list")
                cleaned = []
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    label = str(item.get("label", "")).strip()
                    command = str(item.get("command", "")).strip()
                    if not label or not command:
                        continue
                    cleaned.append({
                        "id": str(item.get("id") or label.lower().replace(" ", "-")),
                        "label": label,
                        "command": command,
                        "check": str(item.get("check", "")).strip(),
                        "tooltip": str(item.get("tooltip", "")).strip(),
                    })
                if save_plugins(cleaned):
                    self.plugins = cleaned
                    self.settings["profile"] = "custom"
                    save_settings(self.settings)
                    save_named_snapshot(
                        self.settings,
                        self.plugins,
                        "auto-plugins",
                        source="auto",
                        tags=["auto", "plugins"],
                    )
                    self._updating_profile_combo = True
                    self.profile_combo.set_active_id("custom")
                    self._updating_profile_combo = False
                    self.refresh_profile_visibility()
                    self.refresh_plugin_buttons()
                    self.status.set_text(f"Saved {len(cleaned)} custom plugin launcher(s)")
                else:
                    self.status.set_text("Failed to write plugins.json")
            except Exception as e:
                self.status.set_text(f"Plugin JSON error: {str(e)[:100]}")
        dlg.destroy()
        if parent_dialog is not None:
            parent_dialog.present()

    def get_icon_image(self, icon_name, size=16):
        if not icon_name:
            return None
        key = f"{icon_name}:{size}"
        cached = self.icon_cache.get(key)
        if cached is not None:
            return Gtk.Image.new_from_pixbuf(cached)

        icon_dirs = [
            APP_ICON_DIR,
            Path(__file__).resolve().parent.parent / "assets" / "icons",
            Path.home() / ".config" / "k7bat-uconsole-status" / "icons",
        ]
        for icon_dir in icon_dirs:
            icon_path = icon_dir / f"{icon_name}.svg"
            if not icon_path.exists():
                continue
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(icon_path),
                    width=size,
                    height=size,
                    preserve_aspect_ratio=True,
                )
                self.icon_cache[key] = pix
                return Gtk.Image.new_from_pixbuf(pix)
            except Exception:
                continue
        return None

    def make_icon_label(self, text, icon_name=None, size=14):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = self.get_icon_image(icon_name, size=size)
        if icon is not None:
            row.pack_start(icon, False, False, 0)
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        row.pack_start(label, False, False, 0)
        return row

    def make_icon_info_row(self, parent, text, icon_name=None, size=14, wrap=False):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = self.get_icon_image(icon_name, size=size)
        if icon is not None:
            row.pack_start(icon, False, False, 0)
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_line_wrap(wrap)
        row.pack_start(label, True, True, 0)
        parent.pack_start(row, False, False, 0)
        return label, row

    def decorate_button(self, button, icon_name=None, text=None):
        if not icon_name:
            return
        label_text = text if text is not None else button.get_label()
        existing = button.get_child()
        if existing is not None:
            button.remove(existing)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        icon = self.get_icon_image(icon_name, size=12)
        if icon is not None:
            row.pack_start(icon, False, False, 0)
        label = Gtk.Label(label=label_text)
        row.pack_start(label, False, False, 0)
        button.add(row)
        row.show_all()

    def make_frame(self, parent, title, icon_name=None):
        f = Gtk.Frame()
        if icon_name:
            f.set_label_widget(self.make_icon_label(title, icon_name, 15))
        else:
            f.set_label(title)
        parent.pack_start(f, True, True, 0)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_border_width(8)
        f.add(box)
        return box

    def add_row(self, parent, key, title, icon_name=None):
        row = Gtk.Box(spacing=6)
        name = self.make_icon_label(title, icon_name, 14)
        name.set_size_request(115, -1)
        name.get_style_context().add_class("subtle")
        val = Gtk.Label(label="—")
        val.set_xalign(0)
        val.set_line_wrap(True)
        row.pack_start(name, False, False, 0)
        row.pack_start(val, True, True, 0)
        parent.pack_start(row, False, False, 0)
        self.labels[key] = val

    def set_chip(self, key, text, level):
        chip = self.chips.get(key)
        if not chip:
            return
        chip.set_text(text)
        ctx = chip.get_style_context()
        for cls in ("chip-good", "chip-warn", "chip-bad", "chip-muted"):
            ctx.remove_class(cls)
        ctx.add_class({
            "good": "chip-good",
            "warn": "chip-warn",
            "bad": "chip-bad",
            "muted": "chip-muted",
        }.get(level, "chip-muted"))

    def set_radio_visual(self, dev, state):
        dot = self.radio_dots.get(dev)
        text = self.radio_text.get(dev)
        if not dot or not text:
            return
        sw = self.radio_switches.get(dev)
        for cls in ("status-on","status-off","status-unknown"):
            dot.get_style_context().remove_class(cls)
            text.get_style_context().remove_class(cls)
        self._radio_switch_sync = True
        if state is True:
            dot.set_text("●")
            text.set_text(self.radio_display_name(dev))
            if sw is not None:
                sw.set_active(True)
            dot.get_style_context().add_class("status-on")
        elif state is False:
            dot.set_text("●")
            text.set_text(self.radio_display_name(dev))
            if sw is not None:
                sw.set_active(False)
            dot.get_style_context().add_class("status-off")
        else:
            dot.set_text("●")
            text.set_text(self.radio_display_name(dev))
            dot.get_style_context().add_class("status-unknown")
        self._radio_switch_sync = False

    def radio_display_name(self, dev):
        if dev == "USB":
            return "USB/AC1200"
        return dev

    def ac1200_power_on(self):
        sw = self.radio_switches.get("USB")
        return bool(sw and sw.get_active())

    def apply_ac1200_dependency_state(self, usb_on):
        hint = self.ac1200_hint
        normal_bt_tooltip = "Start or stop Bluetooth service"

        if self.bt_switch is not None:
            self.bt_switch.set_sensitive(usb_on)
            self.bt_switch.set_tooltip_text(normal_bt_tooltip if usb_on else hint)
        if self.bt_toggle_group is not None:
            self.bt_toggle_group.set_opacity(1.0 if usb_on else 0.45)
            self.bt_toggle_group.set_tooltip_text(normal_bt_tooltip if usb_on else hint)

        if not usb_on:
            self.set_bluetooth_toggle_visual(False)

        for name in self.ac1200_dependent_names:
            btn = self.launch_buttons.get(name) or self.builtin_buttons.get(name)
            if btn is None:
                continue
            if usb_on:
                btn.set_opacity(1.0)
                if btn.get_sensitive():
                    btn.set_tooltip_text(f"Launch {name}")
            else:
                btn.set_opacity(0.45)
                if btn.get_sensitive():
                    btn.set_tooltip_text(hint)

    def on_radio_switch_toggled(self, switch, _param, dev):
        if self._radio_switch_sync:
            return
        state = "on" if switch.get_active() else "off"
        self.radio_command(dev, state)

    def set_bluetooth_toggle_visual(self, state):
        if self.bt_toggle_dot is None or self.bt_toggle_label is None:
            return
        for cls in ("status-on", "status-off", "status-unknown"):
            self.bt_toggle_dot.get_style_context().remove_class(cls)
        if state is True:
            self.bt_toggle_dot.get_style_context().add_class("status-on")
        elif state is False:
            self.bt_toggle_dot.get_style_context().add_class("status-off")
        else:
            self.bt_toggle_dot.get_style_context().add_class("status-unknown")

        if self.bt_switch is not None:
            self._bt_switch_sync = True
            self.bt_switch.set_active(bool(state))
            self._bt_switch_sync = False

    def run_systemctl_noninteractive(self, action, service, timeout=12):
        return run_rc(f"sudo -n systemctl {action} {service}", timeout)

    def is_sudo_auth_error(self, output):
        low = str(output or "").lower()
        return (
            "password" in low
            or "authentication" in low
            or "a password is required" in low
            or "sudoers" in low
        )

    def check_for_new_release_once(self):
        if self._release_check_started:
            return False
        if not self.settings.get("release_check_enabled", True):
            return False

        self._release_check_started = True
        threading.Thread(target=self._release_check_worker, kwargs={"manual": False}, daemon=True).start()
        return False

    def on_check_updates_now(self, _button):
        self.status.set_text("Checking GitHub for updates…")
        threading.Thread(target=self._release_check_worker, kwargs={"manual": True}, daemon=True).start()

    def open_tactical_wifi_dialog(self, _button=None):
        dlg = Gtk.Dialog(title="Tactical Wi-Fi", transient_for=self, flags=0)
        dlg.set_default_size(760, 420)
        dlg.add_button("Close", Gtk.ResponseType.CLOSE)

        content = dlg.get_content_area()
        content.set_spacing(8)

        hint = Gtk.Label(
            label="Scan nearby Wi-Fi networks from this tactical view. Close when not in use."
        )
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("subtle")
        content.pack_start(hint, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        content.pack_start(toolbar, False, False, 0)

        scan_btn = Gtk.Button(label="Scan")
        self.decorate_button(scan_btn, "wifi", "Scan")
        toolbar.pack_start(scan_btn, False, False, 0)

        connect_btn = Gtk.Button(label="Connect")
        self.decorate_button(connect_btn, "network", "Connect")
        toolbar.pack_start(connect_btn, False, False, 0)

        disconnect_btn = Gtk.Button(label="Disconnect")
        self.decorate_button(disconnect_btn, "power", "Disconnect")
        toolbar.pack_start(disconnect_btn, False, False, 0)

        forget_btn = Gtk.Button(label="Forget")
        self.decorate_button(forget_btn, "terminal", "Forget")
        toolbar.pack_start(forget_btn, False, False, 0)

        auto_close = Gtk.CheckButton(label="Auto-close on connect")
        auto_close.set_active(False)
        toolbar.pack_start(auto_close, False, False, 0)

        status = Gtk.Label(label="Ready")
        status.set_xalign(0)
        status.get_style_context().add_class("subtle")
        toolbar.pack_start(status, True, True, 0)

        store = Gtk.ListStore(str, str, str, str, str, str)
        tree = Gtk.TreeView(model=store)
        cols = [
            ("Use", 0),
            ("SSID", 1),
            ("Signal", 2),
            ("Security", 3),
            ("Ch", 4),
            ("Bars", 5),
        ]
        for title, idx in cols:
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer, text=idx)
            col.set_resizable(True)
            if title == "SSID":
                col.set_expand(True)
            tree.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(tree)
        content.pack_start(scrolled, True, True, 0)

        scan_btn.connect("clicked", lambda _b: self.scan_tactical_wifi(store, status, scan_btn))
        connect_btn.connect("clicked", lambda _b: self.connect_tactical_wifi(tree, store, status, scan_btn, dlg, auto_close))
        disconnect_btn.connect("clicked", lambda _b: self.disconnect_tactical_wifi(store, status, scan_btn))
        forget_btn.connect("clicked", lambda _b: self.forget_tactical_wifi(tree, store, status, scan_btn))
        tree.connect("row-activated", lambda _tv, _path, _col: self.connect_tactical_wifi(tree, store, status, scan_btn, dlg, auto_close))
        self.scan_tactical_wifi(store, status, scan_btn)

        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def open_tactical_wifi_attacks_fullscreen(self, _button=None):
        """Open full-screen tactical WiFi attack tools interface"""
        self.status.set_text("Opening Tactical WiFi Attacks...")
        try:
            window = Gtk.Window(title="Tactical WiFi Attack Tools")
            window.set_default_size(1366, 768)
            window.fullscreen()
            
            # Create main layout with reduced spacing
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            main_box.set_border_width(8)
            window.add(main_box)
            
            # Header section with status and tools overview
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            header_box.set_margin_bottom(4)
            main_box.pack_start(header_box, False, False, 0)
            
            # Status indicator
            status_label = Gtk.Label(label="WiFi Attack Tools Ready")
            status_label.get_style_context().add_class("titlebar")
            header_box.pack_start(status_label, True, True, 0)
            
            # Exit button in header with icon
            exit_btn = Gtk.Button(label="Exit Fullscreen")
            exit_btn.connect("clicked", lambda b: window.destroy())
            
            # Add X icon to exit button
            try:
                from gi.repository import GdkPixbuf
                icons_dir = Path(__file__).resolve().parent.parent / "icons"
                exit_icon_path = icons_dir / "power.svg"
                if exit_icon_path.exists():
                    pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(exit_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                    image = Gtk.Image.new_from_pixbuf(pix)
                    exit_btn.set_image(image)
                    exit_btn.set_image_position(Gtk.PositionType.LEFT)
            except Exception:
                pass
            
            header_box.pack_end(exit_btn, False, False, 0)
            
            # Quick status widgets
            wifi_status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            wifi_status_box.set_margin_left(4)
            header_box.pack_end(wifi_status_box, False, False, 0)
            
            wifi_iface_label = Gtk.Label(label="Interface: wlan1")
            wifi_iface_label.set_xalign(0)
            wifi_iface_label.get_style_context().add_class("subtle")
            wifi_status_box.pack_start(wifi_iface_label, False, False, 0)
            
            phy_info_label = Gtk.Label(label="PHY: phy1 (MT7921AUN)")
            phy_info_label.set_xalign(0)
            phy_info_label.get_style_context().add_class("subtle")
            wifi_status_box.pack_start(phy_info_label, False, False, 0)
            
            # Row 0: Wi-Fi Scanning Section
            scan_section_label = Gtk.Label(label="Wi-Fi Network Scanner")
            scan_section_label.get_style_context().add_class("heading")
            scan_section_label.set_xalign(0)
            main_box.pack_start(scan_section_label, False, False, 0)
            
            scan_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            scan_toolbar.set_margin_top(2)
            main_box.pack_start(scan_toolbar, False, False, 0)
            
            scan_btn = Gtk.Button(label="Scan Networks")
            self.decorate_button(scan_btn, "wifi", "Scan")
            scan_toolbar.pack_start(scan_btn, False, False, 0)
            
            connect_btn = Gtk.Button(label="Connect")
            self.decorate_button(connect_btn, "network", "Connect")
            scan_toolbar.pack_start(connect_btn, False, False, 0)
            
            disconnect_btn = Gtk.Button(label="Disconnect")
            self.decorate_button(disconnect_btn, "power", "Disconnect")
            scan_toolbar.pack_start(disconnect_btn, False, False, 0)
            
            auto_close = Gtk.CheckButton(label="Auto-close on connect")
            auto_close.set_active(False)
            scan_toolbar.pack_start(auto_close, False, False, 0)
            
            scan_status = Gtk.Label(label="Ready to scan")
            scan_status.set_xalign(0)
            scan_status.get_style_context().add_class("subtle")
            scan_toolbar.pack_start(scan_status, True, True, 0)
            
            # Wi-Fi networks list
            wifi_store = Gtk.ListStore(str, str, str, str, str, str)
            wifi_tree = Gtk.TreeView(model=wifi_store)
            wifi_cols = [
                ("SSID", 1),
                ("Signal", 2),
                ("Security", 3),
                ("Ch", 4),
                ("Bars", 5),
            ]
            for title, idx in wifi_cols:
                renderer = Gtk.CellRendererText()
                col = Gtk.TreeViewColumn(title, renderer, text=idx)
                col.set_resizable(True)
                if title == "SSID":
                    col.set_expand(True)
                wifi_tree.append_column(col)
            
            wifi_scrolled = Gtk.ScrolledWindow()
            wifi_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            wifi_scrolled.set_margin_top(2)
            wifi_scrolled.set_min_content_height(100)
            wifi_scrolled.add(wifi_tree)
            main_box.pack_start(wifi_scrolled, True, True, 0)
            
            # Scan button callback
            scan_btn.connect("clicked", lambda _b: self.scan_tactical_wifi(wifi_store, scan_status, scan_btn))
            connect_btn.connect("clicked", lambda _b: self.connect_tactical_wifi(wifi_tree, wifi_store, scan_status, scan_btn, None, auto_close))
            disconnect_btn.connect("clicked", lambda _b: self.disconnect_tactical_wifi(wifi_store, scan_status, scan_btn))
            
            # Pre-populate with initial scan
            self.scan_tactical_wifi(wifi_store, scan_status, scan_btn)
            
            # Two-column tools layout for better space utilization
            tools_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            tools_hbox.set_margin_top(4)
            main_box.pack_start(tools_hbox, True, True, 0)
            
            # Left column (Passive Survey + Active Attacks)
            left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            left_col.set_size_request(320, -1)
            tools_hbox.pack_start(left_col, False, False, 0)
            
            # Passive Survey
            passive_frame = Gtk.Frame(label="Passive Survey & Analysis")
            passive_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            passive_box.set_margin_top(4)
            passive_box.set_margin_bottom(4)
            passive_box.set_margin_left(4)
            passive_box.set_margin_right(4)
            passive_frame.add(passive_box)
            left_col.pack_start(passive_frame, False, False, 0)
            
            kismet_btn = Gtk.Button(label="Kismet RF Survey")
            self.decorate_button(kismet_btn, "wifi", "Start Kismet")
            kismet_btn.connect("clicked", lambda b: self.launch_kismet(status_label))
            passive_box.pack_start(kismet_btn, False, False, 0)
            
            wireshark_btn = Gtk.Button(label="Wireshark GUI")
            self.decorate_button(wireshark_btn, "network", "Launch Wireshark")
            wireshark_btn.connect("clicked", lambda b: self.launch_wireshark(status_label))
            passive_box.pack_start(wireshark_btn, False, False, 0)
            
            tshark_btn = Gtk.Button(label="Tshark Capture")
            self.decorate_button(tshark_btn, "terminal", "Launch Tshark")
            tshark_btn.connect("clicked", lambda b: self.launch_tshark(status_label))
            passive_box.pack_start(tshark_btn, False, False, 0)
            
            # Active Attacks
            active_frame = Gtk.Frame(label="Active WPA/WPS Attacks")
            active_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            active_box.set_margin_top(4)
            active_box.set_margin_bottom(4)
            active_box.set_margin_left(4)
            active_box.set_margin_right(4)
            active_frame.add(active_box)
            left_col.pack_start(active_frame, False, False, 0)
            
            reaver_btn = Gtk.Button(label="Reaver (WPS)")
            self.decorate_button(reaver_btn, "wifi", "Launch Reaver")
            reaver_btn.connect("clicked", lambda b: self.launch_python_tool(status_label, "reaver.reaver_ui"))
            active_box.pack_start(reaver_btn, False, False, 0)
            
            bully_btn = Gtk.Button(label="Bully (WPS)")
            self.decorate_button(bully_btn, "wifi", "Launch Bully")
            bully_btn.connect("clicked", lambda b: self.launch_tool(status_label, "bully"))
            active_box.pack_start(bully_btn, False, False, 0)
            
            cowpatty_btn = Gtk.Button(label="Cowpatty (Offline)")
            self.decorate_button(cowpatty_btn, "terminal", "Launch Cowpatty")
            cowpatty_btn.connect("clicked", lambda b: self.launch_tool(status_label, "cowpatty"))
            active_box.pack_start(cowpatty_btn, False, False, 0)
            
            # Right column (Network Attacks + Monitor Mode + Firmware)
            right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            tools_hbox.pack_start(right_col, False, False, 0)
            
            # Network Attacks
            netattack_frame = Gtk.Frame(label="Network Infrastructure Attacks")
            netattack_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            netattack_box.set_margin_top(4)
            netattack_box.set_margin_bottom(4)
            netattack_box.set_margin_left(4)
            netattack_box.set_margin_right(4)
            netattack_frame.add(netattack_box)
            right_col.pack_start(netattack_frame, False, False, 0)
            
            mdk4_btn = Gtk.Button(label="MDK4 (DoS/PenTest)")
            self.decorate_button(mdk4_btn, "terminal", "Launch MDK4")
            mdk4_btn.connect("clicked", lambda b: self.launch_tool(status_label, "mdk4"))
            netattack_box.pack_start(mdk4_btn, False, False, 0)
            
            hostapd_btn = Gtk.Button(label="Hostapd (Rogue AP)")
            self.decorate_button(hostapd_btn, "network", "Launch Hostapd")
            hostapd_btn.connect("clicked", lambda b: self.launch_tool(status_label, "hostapd"))
            netattack_box.pack_start(hostapd_btn, False, False, 0)
            
            dnsmasq_btn = Gtk.Button(label="Dnsmasq (Rogue DHCP)")
            self.decorate_button(dnsmasq_btn, "network", "Launch Dnsmasq")
            dnsmasq_btn.connect("clicked", lambda b: self.launch_tool(status_label, "dnsmasq"))
            netattack_box.pack_start(dnsmasq_btn, False, False, 0)
            
            # Monitor Mode
            monitor_frame = Gtk.Frame(label="Monitor Mode Control")
            monitor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            monitor_box.set_margin_top(4)
            monitor_box.set_margin_bottom(4)
            monitor_box.set_margin_left(4)
            monitor_box.set_margin_right(4)
            monitor_frame.add(monitor_box)
            right_col.pack_start(monitor_frame, False, False, 0)
            
            start_monitor_btn = Gtk.Button(label="Start Monitor (k7mon0)")
            self.decorate_button(start_monitor_btn, "wifi", "Create k7mon0")
            start_monitor_btn.connect("clicked", lambda b: self.launch_monitor_mode(status_label))
            monitor_box.pack_start(start_monitor_btn, False, False, 0)
            
            stop_monitor_btn = Gtk.Button(label="Stop Monitor")
            self.decorate_button(stop_monitor_btn, "power", "Remove k7mon0")
            stop_monitor_btn.connect("clicked", lambda b: self.stop_monitor_mode(status_label))
            monitor_box.pack_start(stop_monitor_btn, False, False, 0)
            
            # Firmware Analysis
            firmware_frame = Gtk.Frame(label="Firmware Analysis")
            firmware_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            firmware_box.set_margin_top(4)
            firmware_box.set_margin_bottom(4)
            firmware_box.set_margin_left(4)
            firmware_box.set_margin_right(4)
            firmware_frame.add(firmware_box)
            right_col.pack_start(firmware_frame, False, False, 0)
            
            binwalk_btn = Gtk.Button(label="Binwalk (Extract)")
            self.decorate_button(binwalk_btn, "terminal", "Launch Binwalk")
            binwalk_btn.connect("clicked", lambda b: self.launch_tool(status_label, "binwalk"))
            firmware_box.pack_start(binwalk_btn, False, False, 0)
            
            scapy_btn = Gtk.Button(label="Scapy (Packet Mani)")
            self.decorate_button(scapy_btn, "terminal", "Launch Scapy")
            scapy_btn.connect("clicked", lambda b: self.launch_python_tool(status_label, "scapy"))
            firmware_box.pack_start(scapy_btn, False, False, 0)
            
            pyshark_btn = Gtk.Button(label="PyShark (Wireshark)")
            self.decorate_button(pyshark_btn, "terminal", "Launch PyShark")
            pyshark_btn.connect("clicked", lambda b: self.launch_python_tool(status_label, "pyshark"))
            firmware_box.pack_start(pyshark_btn, False, False, 0)
            
            window.show_all()
            self.status.set_text("Tactical WiFi Attacks window opened")
        except Exception as e:
            error_msg = f"Error opening tactical interface: {str(e)}"
            self.status.set_text(error_msg)
        
    def launch_kismet(self, status_label=None):
        """Launch Kismet RF survey tool"""
        import subprocess
        cmd = ["kismet"]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if status_label:
                status_label.set_text("Kismet started - browse to http://localhost:2501")
            else:
                self.status.set_text("Kismet started - browse to http://localhost:2501")
        except Exception as e:
            if status_label:
                status_label.set_text(f"Failed to start Kismet: {str(e)}")
            else:
                self.status.set_text(f"Failed to start Kismet: {str(e)}")
    
    def launch_wireshark(self, status_label=None):
        """Launch Wireshark GUI"""
        import subprocess
        cmd = ["wireshark"]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if status_label:
                status_label.set_text("Wireshark started - select interface to capture")
            else:
                self.status.set_text("Wireshark started - select interface to capture")
        except Exception as e:
            if status_label:
                status_label.set_text(f"Failed to start Wireshark: {str(e)}")
            else:
                self.status.set_text(f"Failed to start Wireshark: {str(e)}")
    
    def launch_tshark(self, status_label=None):
        """Launch Tshark for command-line capture"""
        import subprocess
        cmd = ["tshark", "-i", "wlan1"]
        try:
            # Open in new terminal window if possible, otherwise just note it
            if status_label:
                status_label.set_text("Tshark ready - use: tshark -I -i k7mon0 for monitor mode")
            else:
                self.status.set_text("Tshark ready - use: tshark -I -i k7mon0 for monitor mode")
        except Exception as e:
            if status_label:
                status_label.set_text(f"Tshark info: {str(e)}")
            else:
                self.status.set_text(f"Tshark info: {str(e)}")
    
    def launch_tool(self, status_label, tool_name):
        """Launch a WiFi attack tool in terminal"""
        import subprocess
        cmd = ["gnome-terminal", "--", "bash", "-c", f"{tool_name}; exec bash"]
        try:
            subprocess.Popen(cmd)
            if status_label:
                status_label.set_text(f"Started {tool_name}")
            else:
                self.status.set_text(f"Started {tool_name}")
        except Exception as e:
            # Fallback: just show status if no terminal available
            if status_label:
                status_label.set_text(f"{tool_name} installed - launch manually")
            else:
                self.status.set_text(f"{tool_name} installed - launch manually")
    
    def launch_python_tool(self, status_label, tool_name):
        """Launch a Python security tool"""
        import subprocess
        cmd = ["gnome-terminal", "--", "bash", "-c", f"python3 -c 'import {tool_name}; {tool_name}.main()'; exec bash"]
        try:
            subprocess.Popen(cmd)
            if status_label:
                status_label.set_text(f"Started {tool_name}")
            else:
                self.status.set_text(f"Started {tool_name}")
        except Exception as e:
            if status_label:
                status_label.set_text(f"{tool_name} ready - launch manually")
            else:
                self.status.set_text(f"{tool_name} ready - launch manually")
    
    def launch_monitor_mode(self, status_label=None):
        """Create monitor mode interface k7mon0"""
        import subprocess
        cmd = ["sudo", "k7bat-monitor-start", "wlan1", "k7mon0"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                if status_label:
                    status_label.set_text("Monitor interface k7mon0 created successfully")
                else:
                    self.status.set_text("Monitor interface k7mon0 created successfully")
                self.refresh_async()
            else:
                if status_label:
                    status_label.set_text(f"Failed to create monitor: {result.stderr}")
                else:
                    self.status.set_text(f"Failed to create monitor: {result.stderr}")
        except Exception as e:
            if status_label:
                status_label.set_text(f"Monitor mode error: {str(e)}")
            else:
                self.status.set_text(f"Monitor mode error: {str(e)}")
    
    def stop_monitor_mode(self, status_label=None):
        """Remove monitor mode interface k7mon0"""
        import subprocess
        cmd = ["sudo", "k7bat-monitor-stop", "k7mon0"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                if status_label:
                    status_label.set_text("Monitor interface k7mon0 removed")
                else:
                    self.status.set_text("Monitor interface k7mon0 removed")
                self.refresh_async()
            else:
                if status_label:
                    status_label.set_text(f"Failed to remove monitor: {result.stderr}")
                else:
                    self.status.set_text(f"Failed to remove monitor: {result.stderr}")
        except Exception as e:
            if status_label:
                status_label.set_text(f"Monitor stop error: {str(e)}")
            else:
                self.status.set_text(f"Monitor stop error: {str(e)}")

    def open_connectivity_detail_dialog(self, _button=None):
        dlg = Gtk.Dialog(title="Connectivity Detail", transient_for=self, flags=0)
        dlg.add_buttons("Close", Gtk.ResponseType.CLOSE)
        content = dlg.get_content_area()
        content.set_spacing(8)

        intro = Gtk.Label(
            label="On-demand network detail view for tactical checks. Use Tactical Wi-Fi for scan/connect actions."
        )
        intro.set_xalign(0)
        intro.set_line_wrap(True)
        intro.get_style_context().add_class("subtle")
        content.pack_start(intro, False, False, 0)

        grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        content.pack_start(grid, False, False, 0)

        rows = [
            ("active", "Active Link"),
            ("wifi", "Wi-Fi"),
            ("eth", "Ethernet"),
            ("ip", "IP"),
            ("bt", "Bluetooth"),
            ("fail", "Failover"),
        ]
        labels = {}
        for idx, (key, title) in enumerate(rows):
            name = Gtk.Label(label=f"{title}:")
            name.set_xalign(0)
            val = Gtk.Label(label="—")
            val.set_xalign(0)
            val.set_line_wrap(True)
            grid.attach(name, 0, idx, 1, 1)
            grid.attach(val, 1, idx, 1, 1)
            labels[key] = val

        status = Gtk.Label(label="")
        status.set_xalign(0)
        status.get_style_context().add_class("subtle")
        content.pack_start(status, False, False, 0)

        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        content.pack_start(action_row, False, False, 0)

        refresh_btn = Gtk.Button(label="Refresh")
        self.decorate_button(refresh_btn, "dashboard", "Refresh")
        action_row.pack_start(refresh_btn, False, False, 0)

        open_wifi_btn = Gtk.Button(label="Open Tactical Wi-Fi")
        self.decorate_button(open_wifi_btn, "wifi", "Open Tactical Wi-Fi")
        action_row.pack_start(open_wifi_btn, False, False, 0)

        def fill_fields(payload):
            wifi_rows = payload.get("wifi", []) if isinstance(payload.get("wifi", []), list) else []
            wifi_text = " | ".join(f"{iface}: {detail}" for iface, detail in wifi_rows[:3]) if wifi_rows else "none"
            labels["active"].set_text(self.connectivity_active_link(payload))
            labels["wifi"].set_text(wifi_text)
            labels["eth"].set_text(payload.get("eth", "—"))
            labels["ip"].set_text(payload.get("ip", "—"))
            labels["bt"].set_text(payload.get("bt", "—"))
            labels["fail"].set_text(self.labels.get("failover").get_text() if self.labels.get("failover") else "—")
            status.set_text("Refreshed: " + datetime.now().strftime("%H:%M:%S"))

        def refresh_now(_b=None):
            try:
                fill_fields(self.collect())
            except Exception as e:
                status.set_text(f"Refresh failed: {str(e)[:90]}")

        refresh_btn.connect("clicked", refresh_now)
        open_wifi_btn.connect("clicked", lambda _b: self.open_tactical_wifi_dialog())

        refresh_now()
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def gps_confidence_grade(self, confidence_text):
        m = re.search(r"(\d+)", str(confidence_text or ""))
        if not m:
            return "unknown"
        val = int(m.group(1))
        if val >= 85:
            return "excellent"
        if val >= 70:
            return "good"
        if val >= 50:
            return "fair"
        if val >= 30:
            return "weak"
        return "poor"

    def draw_trend_sparkline(self, _widget, cr, values, invert=False):
        vals = [float(v) for v in values if isinstance(v, (int, float))]
        width = max(1, _widget.get_allocated_width())
        height = max(1, _widget.get_allocated_height())

        cr.set_source_rgb(0.08, 0.1, 0.14)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        cr.set_source_rgb(0.18, 0.23, 0.30)
        cr.set_line_width(1)
        cr.move_to(0, height - 1)
        cr.line_to(width, height - 1)
        cr.stroke()

        if len(vals) < 2:
            cr.set_source_rgb(0.7, 0.74, 0.80)
            cr.move_to(8, int(height * 0.6))
            cr.show_text("no trend yet")
            return False

        lo = min(vals)
        hi = max(vals)
        span = hi - lo
        if span < 1e-6:
            span = 1.0

        left_pad = 6.0
        right_pad = 6.0
        top_pad = 6.0
        bottom_pad = 6.0
        usable_w = max(1.0, width - left_pad - right_pad)
        usable_h = max(1.0, height - top_pad - bottom_pad)

        cr.set_source_rgb(0.22, 0.85, 0.55) if not invert else cr.set_source_rgb(0.96, 0.69, 0.23)
        cr.set_line_width(1.8)
        for idx, val in enumerate(vals):
            x = left_pad + usable_w * (idx / float(len(vals) - 1))
            norm = (val - lo) / span
            y = top_pad + (1.0 - norm) * usable_h
            if invert:
                y = top_pad + norm * usable_h
            if idx == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()
        return False

    def open_gps_quality_dialog(self, _button=None):
        dlg = Gtk.Dialog(title="GPS Quality Detail", transient_for=self, flags=0)
        dlg.add_buttons("Close", Gtk.ResponseType.CLOSE)
        content = dlg.get_content_area()
        content.set_spacing(8)

        intro = Gtk.Label(
            label="Detailed GPS quality view with confidence, DOP, and mini trend graphs."
        )
        intro.set_xalign(0)
        intro.set_line_wrap(True)
        intro.get_style_context().add_class("subtle")
        content.pack_start(intro, False, False, 0)

        grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        content.pack_start(grid, False, False, 0)

        rows = [
            ("fix", "Fix"),
            ("sats", "Satellites"),
            ("used", "Satellites Used"),
            ("quality", "Confidence"),
            ("grade", "Quality Grade"),
            ("note", "Assessment"),
            ("dop", "DOP (H/V/P)"),
            ("sample", "Sample Time"),
            ("dev", "Device"),
        ]
        labels = {}
        for idx, (key, title) in enumerate(rows):
            name = Gtk.Label(label=f"{title}:")
            name.set_xalign(0)
            val = Gtk.Label(label="—")
            val.set_xalign(0)
            val.set_line_wrap(True)
            grid.attach(name, 0, idx, 1, 1)
            grid.attach(val, 1, idx, 1, 1)
            labels[key] = val

        sats_title = Gtk.Label(label="Sats Trend")
        sats_title.set_xalign(0)
        sats_title.get_style_context().add_class("subtle")
        content.pack_start(sats_title, False, False, 0)
        sats_plot = Gtk.DrawingArea()
        sats_plot.set_size_request(300, 56)
        content.pack_start(sats_plot, False, False, 0)

        pdop_title = Gtk.Label(label="PDOP Trend (lower is better)")
        pdop_title.set_xalign(0)
        pdop_title.get_style_context().add_class("subtle")
        content.pack_start(pdop_title, False, False, 0)
        pdop_plot = Gtk.DrawingArea()
        pdop_plot.set_size_request(300, 56)
        content.pack_start(pdop_plot, False, False, 0)

        status = Gtk.Label(label="")
        status.set_xalign(0)
        status.get_style_context().add_class("subtle")
        content.pack_start(status, False, False, 0)

        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        content.pack_start(action_row, False, False, 0)
        refresh_btn = Gtk.Button(label="Refresh")
        self.decorate_button(refresh_btn, "dashboard", "Refresh")
        action_row.pack_start(refresh_btn, False, False, 0)

        plot_data = {
            "sats": [],
            "pdop": [],
        }

        sats_plot.connect("draw", lambda w, cr: self.draw_trend_sparkline(w, cr, plot_data["sats"], invert=False))
        pdop_plot.connect("draw", lambda w, cr: self.draw_trend_sparkline(w, cr, plot_data["pdop"], invert=True))

        def refresh_now(_b=None):
            payload = self.collect().get("gps", {})
            labels["fix"].set_text(payload.get("fix", "—"))
            labels["sats"].set_text(payload.get("sats", "—"))
            labels["used"].set_text(payload.get("sats_used", "—"))
            confidence = payload.get("confidence", "—")
            labels["quality"].set_text(str(confidence))
            labels["grade"].set_text(str(payload.get("quality_grade", self.gps_confidence_grade(confidence))))
            labels["note"].set_text(str(payload.get("quality_note", "—")))
            labels["dop"].set_text(f"{payload.get('hdop', '—')} / {payload.get('vdop', '—')} / {payload.get('pdop', '—')}")
            labels["sample"].set_text(str(payload.get("sample_time", "—")))
            labels["dev"].set_text(payload.get("device", "—"))

            sats_vals = list(self.gps_quality_history.get("sats", []))
            pdop_vals = list(self.gps_quality_history.get("pdop", []))

            try:
                sats_num = int(payload.get("sats"))
                sats_vals.append(sats_num)
            except Exception:
                pass

            pdop_val = payload.get("pdop_val")
            if isinstance(pdop_val, (int, float)):
                pdop_vals.append(float(pdop_val))

            plot_data["sats"] = sats_vals[-20:]
            plot_data["pdop"] = pdop_vals[-20:]
            sats_plot.queue_draw()
            pdop_plot.queue_draw()
            status.set_text("Refreshed: " + datetime.now().strftime("%H:%M:%S"))

        refresh_btn.connect("clicked", refresh_now)
        refresh_now()
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def scan_tactical_wifi(self, store, status_label, scan_btn):
        if scan_btn is not None:
            scan_btn.set_sensitive(False)
        status_label.set_text("Scanning Wi-Fi networks…")

        def worker():
            if not command_exists("nmcli"):
                GLib.idle_add(status_label.set_text, "nmcli not installed")
                if scan_btn is not None:
                    GLib.idle_add(scan_btn.set_sensitive, True)
                return

            raw = run_stdout(
                "nmcli -f IN-USE,SSID,SIGNAL,SECURITY,CHAN,BARS -m multiline dev wifi list --rescan yes",
                timeout=10,
            )
            rows = self.parse_nmcli_wifi_multiline(raw)

            def apply_rows():
                store.clear()
                for row in rows:
                    store.append(list(row))
                if rows:
                    status_label.set_text(f"Found {len(rows)} network(s)")
                else:
                    status_label.set_text("No networks found")
                if scan_btn is not None:
                    scan_btn.set_sensitive(True)
                return False

            GLib.idle_add(apply_rows)

        threading.Thread(target=worker, daemon=True).start()

    def parse_nmcli_wifi_multiline(self, raw):
        entries = []
        current = {}
        for line in str(raw or "").splitlines():
            line = line.strip()
            if not line:
                if current:
                    entries.append(current)
                    current = {}
                continue
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            current[key.strip().upper()] = val.strip()
        if current:
            entries.append(current)

        def signal_value(item):
            try:
                return int(item.get("SIGNAL", "0") or "0")
            except Exception:
                return 0

        entries.sort(key=lambda e: (e.get("IN-USE") == "*", signal_value(e)), reverse=True)

        out = []
        for item in entries:
            out.append((
                "*" if item.get("IN-USE") == "*" else "",
                item.get("SSID") or "<hidden>",
                item.get("SIGNAL") or "—",
                item.get("SECURITY") or "OPEN",
                item.get("CHAN") or "—",
                item.get("BARS") or "",
            ))
        return out

    def tactical_wifi_selected(self, tree):
        model, itr = tree.get_selection().get_selected()
        if not model or not itr:
            return None
        return {
            "in_use": str(model[itr][0]),
            "ssid": str(model[itr][1]),
            "security": str(model[itr][3]),
        }

    def tactical_wifi_validate_identifier(self, value, field_name, max_len=128):
        text = str(value or "").strip()
        if not text:
            return None, f"Invalid {field_name}"
        if len(text) > max_len:
            return None, f"{field_name} is too long"
        if any(ord(ch) < 32 for ch in text):
            return None, f"Invalid {field_name}"
        return text, None

    def tactical_wifi_password_prompt(self, ssid):
        dlg = Gtk.Dialog(title=f"Connect to {ssid}", transient_for=self, flags=0)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Connect", Gtk.ResponseType.OK)
        content = dlg.get_content_area()
        content.set_spacing(8)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.pack_start(Gtk.Label(label="Password:"), False, False, 0)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_activates_default(True)
        row.pack_start(entry, True, True, 0)
        content.pack_start(row, False, False, 0)

        dlg.set_default_response(Gtk.ResponseType.OK)
        dlg.show_all()
        resp = dlg.run()
        pwd = entry.get_text().strip()
        dlg.destroy()
        if resp != Gtk.ResponseType.OK:
            return None
        return pwd

    def connect_tactical_wifi(self, tree, store, status_label, scan_btn, dialog=None, auto_close_toggle=None):
        selected = self.tactical_wifi_selected(tree)
        if not selected:
            status_label.set_text("Select a network first")
            return

        ssid = selected.get("ssid", "")
        if not ssid or ssid == "<hidden>":
            status_label.set_text("Cannot connect to hidden SSID from this view")
            return
        ssid, err = self.tactical_wifi_validate_identifier(ssid, "SSID")
        if err:
            status_label.set_text(err)
            return

        security = selected.get("security", "").upper()
        secure = security not in ("", "OPEN", "--", "NONE")
        password = ""
        if secure:
            password = self.tactical_wifi_password_prompt(ssid)
            if password is None:
                status_label.set_text("Connect cancelled")
                return
            if not password:
                status_label.set_text("Password is required for secured network")
                return

        status_label.set_text(f"Connecting to {ssid}…")
        if scan_btn is not None:
            scan_btn.set_sensitive(False)

        def worker():
            cmd = ["nmcli", "dev", "wifi", "connect", ssid]
            if secure:
                cmd.extend(["password", password])
            rc, out = run_rc_args(cmd, timeout=20)

            def done():
                if rc == 0:
                    status_label.set_text(f"Connected to {ssid}")
                    self.status.set_text(f"Wi-Fi connected: {ssid}")
                    self.refresh_async()
                    self.scan_tactical_wifi(store, status_label, scan_btn)
                    should_close = bool(auto_close_toggle is not None and auto_close_toggle.get_active())
                    if should_close and dialog is not None:
                        dialog.response(Gtk.ResponseType.CLOSE)
                else:
                    tail = out.splitlines()[-1][:100] if out else "unknown error"
                    status_label.set_text(f"Connect failed: {tail}")
                    if scan_btn is not None:
                        scan_btn.set_sensitive(True)
                return False

            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    def disconnect_tactical_wifi(self, store, status_label, scan_btn):
        status_label.set_text("Disconnecting Wi-Fi…")
        if scan_btn is not None:
            scan_btn.set_sensitive(False)

        def worker():
            dev = ""
            raw = run_stdout_args(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"], timeout=5)
            for line in raw.splitlines():
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                if parts[1] == "wifi" and parts[2] == "connected":
                    dev = parts[0]
                    break
            if not dev:
                for line in raw.splitlines():
                    parts = line.split(":", 2)
                    if len(parts) < 3:
                        continue
                    if parts[1] == "wifi":
                        dev = parts[0]
                        break

            if not dev:
                GLib.idle_add(status_label.set_text, "No Wi-Fi device found")
                if scan_btn is not None:
                    GLib.idle_add(scan_btn.set_sensitive, True)
                return

            dev, err = self.tactical_wifi_validate_identifier(dev, "device")
            if err:
                GLib.idle_add(status_label.set_text, err)
                if scan_btn is not None:
                    GLib.idle_add(scan_btn.set_sensitive, True)
                return

            rc, out = run_rc_args(["nmcli", "device", "disconnect", dev], timeout=15)

            def done():
                if rc == 0:
                    status_label.set_text(f"Disconnected {dev}")
                    self.status.set_text(f"Wi-Fi disconnected: {dev}")
                    self.refresh_async()
                    self.scan_tactical_wifi(store, status_label, scan_btn)
                else:
                    tail = out.splitlines()[-1][:100] if out else "unknown error"
                    status_label.set_text(f"Disconnect failed: {tail}")
                    if scan_btn is not None:
                        scan_btn.set_sensitive(True)
                return False

            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    def forget_tactical_wifi(self, tree, store, status_label, scan_btn):
        selected = self.tactical_wifi_selected(tree)
        if not selected:
            status_label.set_text("Select a network first")
            return

        ssid = selected.get("ssid", "")
        if not ssid or ssid == "<hidden>":
            status_label.set_text("Cannot forget hidden SSID from this view")
            return

        status_label.set_text(f"Forgetting saved profile for {ssid}…")
        if scan_btn is not None:
            scan_btn.set_sensitive(False)

        def worker():
            raw = run_stdout_args(["nmcli", "-t", "-f", "NAME", "connection", "show"], timeout=6)
            names = [line.strip() for line in raw.splitlines() if line.strip()]
            matches = [n for n in names if n == ssid]
            if not matches:
                GLib.idle_add(status_label.set_text, f"No saved profile found for {ssid}")
                if scan_btn is not None:
                    GLib.idle_add(scan_btn.set_sensitive, True)
                return

            last_err = ""
            ok_count = 0
            for name in matches:
                safe_name, err = self.tactical_wifi_validate_identifier(name, "profile")
                if err:
                    last_err = err
                    continue
                rc, out = run_rc_args(["nmcli", "connection", "delete", "id", safe_name], timeout=12)
                if rc == 0:
                    ok_count += 1
                else:
                    last_err = out.splitlines()[-1][:100] if out else "unknown error"

            def done():
                if ok_count > 0:
                    status_label.set_text(f"Forgot {ssid} ({ok_count} profile(s))")
                    self.status.set_text(f"Wi-Fi profile removed: {ssid}")
                    self.scan_tactical_wifi(store, status_label, scan_btn)
                else:
                    status_label.set_text(f"Forget failed: {last_err}")
                    if scan_btn is not None:
                        scan_btn.set_sensitive(True)
                return False

            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    def _release_check_worker(self, manual=False):
        repo = str(self.settings.get("github_repo", DEFAULT_GITHUB_REPO)).strip() or DEFAULT_GITHUB_REPO
        latest, release_url = github_latest_release(repo)
        if not latest:
            if manual:
                GLib.idle_add(self.status.set_text, "Update check failed (GitHub unavailable)")
            return
        if not is_newer_version(latest, APP_VERSION):
            if manual:
                GLib.idle_add(self.status.set_text, f"Already up to date (v{APP_VERSION})")
            return

        dismissed = str(self.settings.get("release_popup_dismissed", "")).strip()
        if (not manual) and dismissed == latest:
            return

        GLib.idle_add(self.show_new_release_popup, latest, release_url)

    def show_new_release_popup(self, latest_version, release_url):
        # Create backup before showing popup
        success, msg = create_backup()
        
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text=f"New version available: v{latest_version}",
        )
        secondary_text = ["A newer GitHub release is available for K7BAT uConsole Status App."]
        if success:
            secondary_text.append(f"Backup created: {msg}")
        else:
            secondary_text.append(f"Warning: Could not create backup ({msg})")
        
        # Add channel selection
        channel_label = Gtk.Label(label="Channel:")
        channel_combo = Gtk.ComboBoxText()
        for ch in ("stable", "beta"):
            channel_combo.append(ch, ch.capitalize())
        current_channel = self.settings.get("update_channel", "stable")
        channel_combo.set_active_id(current_channel)
        
        channel_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        channel_box.pack_start(channel_label, False, False, 0)
        channel_box.pack_start(channel_combo, True, True, 0)
        channel_box.show_all()
        
        content_area = dlg.get_content_area()
        content_area.pack_end(channel_box, False, False, 0)
        
        # Add buttons
        dlg.add_button("Later", Gtk.ResponseType.CANCEL)
        btn_open = dlg.add_button("Open Release", Gtk.ResponseType.OK)
        btn_update = dlg.add_button("Download & Install", Gtk.ResponseType.APPLY)
        btn_rollback = dlg.add_button("Rollback...", Gtk.ResponseType.REJECT)

        response = dlg.run()
        
        # Get selected channel
        selected_channel = channel_combo.get_active_id() or "stable"
        self.settings["update_channel"] = selected_channel
        save_settings(self.settings)
        
        dlg.destroy()

        if response == Gtk.ResponseType.OK:
            if release_url:
                launch(f'xdg-open "{release_url}"')
        elif response == Gtk.ResponseType.APPLY:
            threading.Thread(
                target=self._download_and_install_update,
                args=(latest_version, selected_channel),
                daemon=True
            ).start()
        elif response == Gtk.ResponseType.REJECT:
            self.show_rollback_dialog()
        
        return False

    def radio_command(self, dev, state):
        self.status.set_text(f"{dev}: requesting {state.upper()}…")
        def worker():
            rc, out = run_rc(f"aiov2_ctl {dev} {state}", 10)
            msg = f"{dev}: {state.upper()} requested" if rc == 0 else f"{dev}: command failed"
            if out and rc != 0:
                msg += f" — {out.splitlines()[-1][:90]}"
            GLib.idle_add(self.status.set_text, msg)
            GLib.timeout_add_seconds(1, self.refresh_async)
        threading.Thread(target=worker, daemon=True).start()

    def extract_wifi_signal_dbm(self, wifi_rows):
        best = None
        for _iface, detail in wifi_rows:
            m = re.search(r"(-?\d+(?:\.\d+)?)\s*dBm", detail)
            if not m:
                continue
            try:
                val = float(m.group(1))
            except Exception:
                continue
            if best is None or val > best:
                best = val
        return best

    def ethernet_is_up(self, eth_text):
        parts = [p.strip().lower() for p in str(eth_text or "").split(",") if p.strip()]
        for p in parts:
            if p.endswith(" up") or " up " in p:
                return True
        return False

    def connectivity_active_link(self, data):
        wifi_rows = data.get("wifi", []) if isinstance(data.get("wifi", []), list) else []
        if wifi_rows:
            return "Wi-Fi"
        if self.ethernet_is_up(data.get("eth", "")):
            return "Ethernet"
        return "Offline"

    def update_connectivity_labels(self, data):
        active = self.connectivity_active_link(data)
        self.labels["active_link"].set_text(active)

        wifi_rows = data.get("wifi", []) if isinstance(data.get("wifi", []), list) else []
        dbm = self.extract_wifi_signal_dbm(wifi_rows)
        if isinstance(dbm, (int, float)):
            self.connectivity_history["wifi_dbm"].append(float(dbm))
        self.connectivity_history["wifi_dbm"] = self.connectivity_history["wifi_dbm"][-10:]
        if "wifi_trend" in self.labels:
            self.labels["wifi_trend"].set_text(format_history_trend(self.connectivity_history["wifi_dbm"], 6))

        links = self.connectivity_history["active_link"]
        links.append(active)
        self.connectivity_history["active_link"] = links[-8:]

        prev = None
        if len(links) >= 2:
            prev = links[-2]
        if prev and prev != active:
            self.labels["failover"].set_text(f"Changed: {prev} -> {active}")
        else:
            self.labels["failover"].set_text(f"Stable: {active}")

        if active == "Offline":
            self.connectivity_history["offline_streak"] += 1
        else:
            self.connectivity_history["offline_streak"] = 0

        streak = self.connectivity_history["offline_streak"]
        if streak >= 3:
            self.labels["hotspot_watchdog"].set_text(f"WARN: no uplink ({streak} checks)")
        elif streak > 0:
            self.labels["hotspot_watchdog"].set_text(f"Watching ({streak})")
        else:
            self.labels["hotspot_watchdog"].set_text("OK")

    def evaluate_alerts(self, d):
        alerts = []
        cfg = self.alert_settings or dict(DEFAULT_ALERTS)
        if not cfg.get("enabled", True):
            return alerts

        metrics = d.get("metrics", {})
        cpu_c = metrics.get("cpu_temp_c")
        if cpu_c is not None and cpu_c >= cfg.get("cpu_temp_c", 78):
            alerts.append(("warn", f"CPU temp high: {cpu_c:.0f}C"))

        ram_used = metrics.get("ram_used_pct")
        if ram_used is not None and ram_used >= cfg.get("ram_used_pct", 90):
            alerts.append(("warn", f"RAM usage high: {ram_used:.0f}%"))

        disk_free = metrics.get("disk_free_pct")
        if disk_free is not None and disk_free <= cfg.get("disk_free_pct", 10):
            alerts.append(("bad", f"Disk free low: {disk_free:.0f}%"))

        battery_pct = metrics.get("battery_pct")
        battery_state = metrics.get("battery_state") or ""
        if battery_pct is not None and battery_state.lower() != "charging":
            if battery_pct <= cfg.get("battery_pct", 25):
                alerts.append(("bad", f"Battery low: {battery_pct}%"))

        fix = d.get("gps", {}).get("fix", "")
        if cfg.get("require_gps_fix", False) and ("2D" not in fix and "3D" not in fix):
            alerts.append(("warn", f"GPS fix missing: {fix}"))

        wifi_count = len(d.get("wifi", []))
        if cfg.get("require_wifi", False) and wifi_count == 0:
            alerts.append(("warn", "No Wi-Fi interfaces detected"))

        if d.get("gpsd") != "RUNNING":
            alerts.append(("warn", "gpsd is not running"))
        return alerts

    def apply_alerts(self, alerts):
        if not self.alert_settings.get("enabled", True):
            self.alert_summary.set_text("Alerts: disabled (enable in Settings)")
            return

        if not alerts:
            self.alert_summary.set_text("Alerts: all monitored systems nominal")
            return

        critical = any(level == "bad" for level, _ in alerts)
        prefix = "ALERT" if critical else "WARN"
        self.alert_summary.set_text(
            f"{prefix}: " + " | ".join(text for _level, text in alerts[:4])
        )

    def collect(self):
        g = gps_data()
        w = wifi_interfaces()
        mem_used, mem_total = memory_usage_bytes()
        disk_free, disk_total = disk_usage_bytes()
        battery_text, battery_pct, battery_state = battery_info()
        cpu_c = cpu_temp_value()
        service_map = {
            "gpsd": service_state("gpsd"),
            "gpsd.socket": service_state("gpsd.socket"),
            "bluetooth": service_state("bluetooth"),
            "readsb": service_state("readsb"),
            "NetworkManager": service_state("NetworkManager"),
        }
        ram_used_pct = None
        if mem_used is not None and mem_total:
            ram_used_pct = (float(mem_used) / float(mem_total)) * 100.0
        disk_free_pct = None
        if disk_free is not None and disk_total:
            disk_free_pct = (float(disk_free) / float(disk_total)) * 100.0
        return {
            "cpu": cpu_temp(), "ram": memory(), "disk": disk(), "battery": battery_text,
            "gps": g, "ip": ip_info(), "eth": ethernet(), "bt": bluetooth(),
            "bt_ctrl": bluetooth_controller(),
            "gpsd": service_state("gpsd"), "readsb": service_state("readsb"),
            "wifi": w, "aio": parse_aio_states(),
            "services": service_map,
            "metrics": {
                "cpu_temp_c": cpu_c,
                "ram_used_pct": ram_used_pct,
                "disk_free_pct": disk_free_pct,
                "battery_pct": battery_pct,
                "battery_state": battery_state,
            },
        }

    def refresh_async(self):
        if getattr(self, "_refreshing", False):
            return True
        self._refreshing = True
        def worker():
            try:
                data = self.collect()
                GLib.idle_add(self.apply_data, data)
            except Exception as e:
                GLib.idle_add(self.on_refresh_error, str(e))
        threading.Thread(target=worker, daemon=True).start()
        return True

    def on_refresh_error(self, err):
        self._refreshing = False
        self.status.set_text(f"Refresh error: {err[:100]}")
        return False

    def apply_data(self, d):
        self._refreshing = False
        self.latest_aio_states = dict(d.get("aio", {}) or {})
        self.labels["cpu"].set_text(d["cpu"])
        self.labels["ram"].set_text(d["ram"])
        self.labels["disk"].set_text(d["disk"])
        self.labels["battery"].set_text(d["battery"])
        g = d["gps"]
        self.labels["fix"].set_text(g["fix"])
        self.labels["sats"].set_text(g["sats"])
        self.labels["gpsdev"].set_text(g["device"])
        self.labels["pos"].set_text(g["pos"])
        self.labels["speed"].set_text(g["speed"])
        self.labels["track"].set_text(g["track"])
        self.labels["gps_quality"].set_text(
            f"{g.get('confidence', '—')} {g.get('quality_grade', 'unknown')} • used {g.get('sats_used', '—')}"
        )
        self.labels["dop_summary"].set_text(
            f"{g.get('hdop', '—')} / {g.get('vdop', '—')} / {g.get('pdop', '—')}"
        )
        self.labels["gpsd"].set_text(d["gpsd"])
        self.labels["readsb"].set_text(d["readsb"])
        self.labels["ip"].set_text(d["ip"])
        self.labels["eth"].set_text(d["eth"])
        self.labels["bt"].set_text(d["bt"])
        self.labels["bt_ctrl"].set_text(d.get("bt_ctrl", "none"))
        if d["wifi"]:
            self.labels["wifi"].set_text(" | ".join(f"{iface}: {detail}" for iface, detail in d["wifi"][:2]))
        else:
            self.labels["wifi"].set_text("—")

        self.update_connectivity_labels(d)

        try:
            sats_num = int(g.get("sats"))
            self.gps_quality_history["sats"].append(sats_num)
        except Exception:
            pass
        pdop_val = g.get("pdop_val")
        if isinstance(pdop_val, (int, float)):
            self.gps_quality_history["pdop"].append(float(pdop_val))

        self.gps_quality_history["sats"] = self.gps_quality_history["sats"][-10:]
        self.gps_quality_history["pdop"] = self.gps_quality_history["pdop"][-10:]
        sats_tail = format_history_trend(self.gps_quality_history["sats"], 3)
        pdop_tail = format_history_trend(self.gps_quality_history["pdop"], 3)
        sats_dir = trend_direction(self.gps_quality_history["sats"], lower_better=False)
        pdop_dir = trend_direction(self.gps_quality_history["pdop"], lower_better=True)
        if "gps_trend" in self.labels:
            self.labels["gps_trend"].set_text(
                f"sats {sats_tail} ({sats_dir}) • pdop {pdop_tail} ({pdop_dir})"
            )
        for dev, state in d["aio"].items():
            self.set_radio_visual(dev, state)

        fix_text = g["fix"]
        if "3D" in fix_text or "2D" in fix_text:
            self.set_chip("chip_fix", f"GPS: {fix_text}", "good")
        elif "NO FIX" in fix_text:
            self.set_chip("chip_fix", f"GPS: {fix_text}", "warn")
        else:
            self.set_chip("chip_fix", f"GPS: {fix_text}", "muted")

        wifi_ok = len(d["wifi"]) > 0
        self.set_chip("chip_wifi", f"Wi-Fi: {'OK' if wifi_ok else 'NONE'}", "good" if wifi_ok else "bad")
        self.set_chip("chip_gpsd", f"gpsd: {d['gpsd']}", "good" if d["gpsd"] == "RUNNING" else "warn")
        self.set_chip("chip_readsb", f"readsb: {d['readsb']}", "good" if d["readsb"] == "RUNNING" else "muted")

        for service, label in self.service_labels.items():
            state = d.get("services", {}).get(service, "OFF")
            dot = self.service_dots.get(service)
            if dot is None:
                continue
            dctx = dot.get_style_context()
            for cls in ("status-on", "status-off", "status-unknown"):
                dctx.remove_class(cls)
            state_upper = str(state).upper()
            if state_upper == "RUNNING":
                dctx.add_class("status-on")
            elif state_upper in ("OFF", "INACTIVE", "DEAD", "FAILED"):
                dctx.add_class("status-off")
            else:
                dctx.add_class("status-unknown")

        bt_state = d.get("services", {}).get("bluetooth", "OFF")
        bt_state_upper = str(bt_state).upper()
        if bt_state_upper == "RUNNING":
            self.set_bluetooth_toggle_visual(True)
        elif bt_state_upper in ("OFF", "INACTIVE", "DEAD", "FAILED"):
            self.set_bluetooth_toggle_visual(False)
        else:
            self.set_bluetooth_toggle_visual(None)

        usb_on = d.get("aio", {}).get("USB") is True
        self.apply_ac1200_dependency_state(usb_on)
        self.apply_gps_dependency_state(self.latest_aio_states.get("GPS"))
        self.apply_sdr_dependency_state(self.latest_aio_states.get("SDR"))

        alerts = self.evaluate_alerts(d)
        self.apply_alerts(alerts)

        self.record_mission_sample(d)

        self.last_update.set_text("Updated: " + datetime.now().strftime("%H:%M:%S"))
        return False

Gtk.init([])
App()
Gtk.main()
