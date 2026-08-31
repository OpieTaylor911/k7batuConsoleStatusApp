Your uConsole provisioning flow can now be very simple. Open the ESP32 serial port at 115200 and send:

SETWIFI=K7BAT-SIDEKICK|YourPasswordHere

followed by a newline.

The Sidekick should respond:

WIFI=SAVING
SSID=K7BAT-SIDEKICK
WIFI=CONNECTING
WIFI=CONNECTED
IP=10.77.0.2

If the password or AP is wrong:

WIFI=SAVING
SSID=K7BAT-SIDEKICK
WIFI=CONNECTING
WIFI=FAILED

Your uConsole app can later ask:

GETIP

and receive:

IP=10.77.0.2

or query everything:

GETWIFI

which returns something like:

WIFI=CONNECTED
SSID=K7BAT-SIDEKICK
IP=10.77.0.2

You can also wipe the stored credentials with:

CLEARWIFI