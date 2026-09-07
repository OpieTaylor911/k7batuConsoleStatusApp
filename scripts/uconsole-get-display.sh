#!/bin/bash
# Helper script to get bcaddy's display variable

# Check if XDG_RUNTIME_DIR exists for bcaddy (uid 1000)
if [ -d "/run/user/1000" ]; then
    echo ":0"
else
    # Fallback - try to read from bcaddy's environment file
    if [ -f "/home/bcaddy/.display" ]; then
        cat /home/bcaddy/.display
    else
        echo ":0"
    fi
fi
