#!/usr/bin/env python3
"""
Shared Sidekick API key helpers.

status_api.py (the HTTP server) and the Sidekick Setup GUI plugin
(app/plugins/sidekick_setup_ui.py) both import this so they always agree on
where the key lives and what format it's in.
"""

import os
import secrets

API_KEY_PREFIX = "k7_sk_"
API_KEY_FILENAME = ".apikey"


def generate_api_key():
    """Generate a new 256-bit Sidekick API key: 'k7_sk_' + a random URL-safe token."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def load_or_create_api_key(directory):
    """Return the persistent API key stored in <directory>/.apikey, creating it if missing."""
    path = os.path.join(directory, API_KEY_FILENAME)
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                key = f.read().strip()
            if key.startswith(API_KEY_PREFIX):
                return key
        key = generate_api_key()
        with open(path, "w") as f:
            f.write(key)
        os.chmod(path, 0o600)
        return key
    except OSError as e:
        print(f"Warning: could not load/create Sidekick API key at {path}: {e}")
        return generate_api_key()
