#!/bin/bash
# Fix install.sh to handle duplicate source/destination

awk '
/if \[ -f "\$SCRIPT_DIR\/status_api.py" \]; then/ {
    print "if [ -f \"$SCRIPT_DIR/status_api.py\" ] && [ \"$SCRIPT_DIR\" != \"$PREFIX\" ]; then"
    getline; print $0
    next
}
/if \[ -f "\$SCRIPT_DIR\/sidekick_apikey.py" \]; then/ {
    print "if [ -f \"$SCRIPT_DIR/sidekick_apikey.py\" ] && [ \"$SCRIPT_DIR\" != \"$PREFIX\" ]; then"
    getline; print $0
    next
}
{print}
' /home/bcaddy/uconsole-k7bat/install.sh > /tmp/install_fixed.sh

mv /tmp/install_fixed.sh /home/bcaddy/uconsole-k7bat/install.sh
chmod +x /home/bcaddy/uconsole-k7bat/install.sh
