# K7BAT Sidekick Firmware Integration

This document is the contract for every Sidekick firmware target. A target can
use a different screen, pin map, and ESP32 family, but it must implement this
serial and HTTP behavior to work with the uConsole Status App.

## uConsole Server

The uConsole serves Sidekick status from:

```
http://<uconsole-ip>:8080/api/sidekick
```

The server is implemented by `status_api.py`. In the Status App, start it from
`Settings -> Sidekick API`. It must be running before the Sidekick can show
live state.

The response is plain text, not JSON. It is a semicolon-delimited status
packet. A current example is:

```
SDR=X;GPS=G;NET=R;AIO=X;BAT=G;SDR+=X;ADSB=G;GPSD=G;VNC=X;RVR=X;READ=G;TAR=G;BT=G;TEMP=G;PWR=G;SYS=OK;
```

Poll this endpoint every 2 to 5 seconds while Wi-Fi is connected. Pass the
response body to the display's existing `parseMessage()` function. The
response does not require a trailing newline for HTTP polling.

## Indicator Packet

Every packet token uses `KEY=STATE;`. Ignore unknown keys so the server can add
new indicators without breaking older firmware.

| State | Meaning | Suggested color |
| --- | --- | --- |
| `G` | Healthy / active | Green |
| `Y` | Degraded / waiting / no GPS fix | Yellow |
| `R` | Fault / unavailable network | Red |
| `B` | Informational / alternate state | Blue |
| `X` | Off / unsupported / not installed | Dark gray |

| Key | Current server meaning |
| --- | --- |
| `SDR` | SDR power state. Currently unavailable from the API, so `X`. |
| `GPS` | `G` for a 2D/3D gpsd fix, `Y` for no fix, `X` when gpsd is off. |
| `NET` | `G` when the API detects a connected Wi-Fi interface, otherwise `R`. |
| `AIO` | AIO board aggregate state. Currently `X`. |
| `BAT` | Battery charge: green over 30%, yellow 16-30%, red 0-15%, or `X` if unavailable. |
| `SDR+` | SDR++ application status. Currently `X`. |
| `ADSB` | `G` when `readsb` is active; otherwise `X`. |
| `GPSD` | `G` when gpsd is active; otherwise `X`. |
| `VNC` | `G` when RealVNC service mode or virtual mode is active; otherwise `X`. |
| `RVR` | Reserved indicator. Currently `X`. |
| `READ` | `G` when `readsb` is active; otherwise `X`. |
| `TAR` | `G` when `readsb` is active (tar1090 expected available); otherwise `X`. |
| `BT` | `G` when the Bluetooth service is active; otherwise `X`. |
| `TEMP` | CPU temperature: green below 70 C, yellow 70-79 C, red 80 C or higher, `X` if unavailable. |
| `PWR` | `G` when a system battery is detected; otherwise `X`. |
| `SYS` | Informational system text. Current value: `OK`. |

## Firmware Identity

Each board-specific sketch must define these values:

```cpp
#define SIDEKICK_VERSION "1.0.0"
#define SIDEKICK_BOARD "ideaspark"
```

`SIDEKICK_BOARD` must match a key in `DEVICE_PROFILES` in
`app/plugins/sidekick_setup_ui.py`. The Setup app uses it to auto-select the
right chip family and release board. For current profiles use:

| Firmware board value | Device |
| --- | --- |
| `ideaspark` | IdeaSpark ESP32-WROOM-32/ST7789 |
| `cyd` | CYD ESP32-WROOM-32 |
| `heltec` | Heltec ESP32-S3 |
| `lilygo` | LilyGO ESP32-S3 |

At 115200 baud, implement this command:

```
GETVERSION
```

It must return both lines, in either order:

```
VERSION=1.0.0
BOARD=ideaspark
```

Chip detection alone is not sufficient: different physical boards frequently
share the same ESP32-WROOM-32. The self-reported board identifier is the
authoritative board detection mechanism.

## Serial Provisioning Protocol

The Sidekick Setup app opens the USB serial port at 115200 baud. Implement the
following newline-terminated commands and replies:

| Command | Required behavior |
| --- | --- |
| `SETWIFI=<ssid>|<password>` | Store credentials using `Preferences`, start `WiFi.begin()`, and report progress. |
| `GETWIFI` | Report current connection/configuration state, SSID, and IP when connected. |
| `GETIP` | Reply `IP=<address>` or `IP=NONE`. |
| `CLEARWIFI` | Erase saved credentials, disconnect Wi-Fi, and reply `WIFI=CLEARED`. |
| `GETVERSION` | Reply with both `VERSION=` and `BOARD=` as described above. |
| `SERVER=<uconsole-ip>:8080` | Store the server address in `Preferences`, reply `SERVER=OK`, and use it for HTTP polling. |

Successful Wi-Fi setup should produce these lines:

```
WIFI=SAVING
SSID=K7BAT-SIDEKICK
WIFI=CONNECTING
WIFI=CONNECTED
IP=10.77.0.2
```

Failure should produce:

```
WIFI=SAVING
WIFI=CONNECTING
WIFI=FAILED
```

The current Setup app needs `WIFI=CONNECTED` plus `IP=<address>` to mark the
provisioning operation successful. It sends `SERVER=<address>` after Wi-Fi
setup. Persist that value and restore it after reboot.

## Required Wi-Fi Polling Flow

Use `WiFi.h`, `HTTPClient.h`, and `Preferences.h` in each board sketch. The
essential control flow is:

```cpp
if (WiFi.status() == WL_CONNECTED && serverAddress.length() > 0) {
	HTTPClient http;
	http.begin("http://" + serverAddress + "/api/sidekick");
	http.setTimeout(2000);
	if (http.GET() == HTTP_CODE_OK) {
		parseMessage(http.getString());
	}
	http.end();
}
```

Use a `millis()` interval rather than `delay()` for polling so the display and
serial command processing remain responsive. A failed poll must not erase the
last known indicator states; retain the last display state and retry at the
next interval.

## Release Layout

Firmware downloads resolve this path sequence:

```
releases/index.json
	-> releases/<release path>/release.json
	-> releases/<board path>/manifest.json
	-> merged firmware .bin
```

Each `manifest.json` uses ESP Web Tools format and must contain one merged
image at offset `0`:

```json
{
	"name": "K7BAT Sidekick - Ideaspark ESP32-WROOM-32",
	"version": "1.0.0",
	"new_install_prompt_erase": true,
	"builds": [
		{
			"chipFamily": "ESP32",
			"parts": [
				{
					"path": "sidekick-v1.0.0-ideaspark-wroom.bin",
					"offset": 0
				}
			]
		}
	]
}
```

The Setup app downloads and flashes only this merged file using the offset
declared in `manifest.json`. Produce merged images with `esptool merge_bin`.
Separate bootloader and partition binaries are intentionally not handled by
the Setup app; use Arduino IDE for that manual recovery workflow.