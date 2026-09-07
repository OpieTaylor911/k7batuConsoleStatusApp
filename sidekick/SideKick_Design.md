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
| `SDR` | AIO SDR power rail: green on, off when explicitly off, yellow when its state is unavailable. |
| `GPS` | `G` for a 2D/3D gpsd fix, `Y` for no fix, `X` when gpsd is off. |
| `NET` | `G` when the API detects a connected Wi-Fi interface, otherwise `R`. |
| `AIO` | Aggregate AIO V2 rail state: green when any rail is on, off when all known rails are off, yellow when unavailable. |
| `BAT` | Battery charge: green over 30%, yellow 16-30%, red 0-15%, or `X` if unavailable. |
| `BATPCT` | Numeric battery percentage from 0 to 100; empty when the battery is unavailable. |
| `CHG` | `1` while the battery reports Charging; otherwise `0`. |
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
| `LORA` | AIO LoRa power rail: green on, off when explicitly off, yellow when its state is unavailable. |
| `USB` | AIO USB/AC1200 power rail: green on, off when explicitly off, yellow when its state is unavailable. |
| `ETH` | Ethernet link: green when an `eth*` interface is up; otherwise off. |
| `INTERNET` | Green when Wi-Fi or Ethernet is active, red when neither active. It currently measures an active uplink, not an external ping. |
| `SYS` | Informational system text. Current value: `OK`. |

## Control Endpoint (touch actions)

Read-only status stays on `GET /api/sidekick`. A firmware target with a working
touchscreen may additionally send:

```
POST /api/sidekick/control
Content-Type: application/json

{"target": "SDR", "command": "power", "value": "on"}
```

`target` is a Sidekick indicator key (see the table above), `command` is
`power` or `service`, and `value` is the requested state. The server replies:

```json
{"ok": true, "target": "SDR", "command": "power", "requested": "on", "message": "SDR power requested"}
```

or on failure:

```json
{"ok": false, "target": "SDR", "command": "power", "requested": "on", "error": "aiov2_ctl not available on this system"}
```

The server is authoritative. Firmware must not assume the action succeeded or
flip its own indicator color from this response - wait for the next `GET
/api/sidekick` poll to reflect the real state. A reasonable UX is showing a
transient "TURNING ON..." message on the tile until the next poll confirms it.

| Target | Command | Valid values | Effect |
| --- | --- | --- | --- |
| `SDR`, `LORA`, `USB`, `GPS` | `power` | `on`, `off` | AIO V2 power rail via `aiov2_ctl`. |
| `GPSD` | `service` | `start`, `stop`, `restart` | `gpsd` systemd service. |
| `BT` | `service` | `start`, `stop`, `restart` | `bluetooth` systemd service. |
| `ADSB`, `READ`, `TAR` | `service` | `start`, `stop`, `restart` | `readsb` systemd service (all three tiles share it). |
| `VNC` | `service` | `start`, `stop`, `restart` | VNC systemd service. |
| `SDR+` | `service` | `start`, `stop` | SDR++ systemd service (same as `/api/radio/toggle`). |

`NET`, `BAT`, `BATPCT`, `CHG`, `TEMP`, `PWR`, `ETH`, `INTERNET`, `RVR`, and `SYS`
are status-only and have no control mapping; sending them returns HTTP 400.

Unrecognized `target`/`command` combinations return HTTP 400 with
`{"ok": false, "error": "..."}`. Backend failures (missing `aiov2_ctl`,
`sudo -n systemctl` not permitted, etc.) return HTTP 500 with the same shape.

### Authentication

The uConsole keeps a persistent API key in `.apikey` next to `status_api.py`,
format `k7_sk_<43 random URL-safe characters>` (256 bits of entropy). The key
is created automatically the first time `status_api.py` or the Sidekick Setup
app runs and finds no `.apikey` file (see `sidekick_apikey.py`).

`/api/sidekick/control` always requires a matching header:

```
Authorization: Bearer <api-key>
```

Requests with a missing or wrong token get HTTP 401. `GET /api/sidekick` and
all other existing endpoints are unaffected and remain unauthenticated.

Firmware never generates or edits this key. The Sidekick Setup app sends it
automatically during provisioning (see `TOKEN=` below); firmware only stores
it and replays it as the `Authorization` header on requests to the uConsole.

### Firmware guidance

- Because an accidental tap could cut power to a radio, firmware SHOULD use a
  confirm step (a modal dialog, or tap-to-view + long-press-to-act) before
  sending a `power` or `service` control request rather than toggling on a
  single tap.
- Only send `control` requests for boards with working touch input. If a board
  cannot drive touch, its dashboard remains read-only via `GET /api/sidekick`.

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
| `heltec_e290` | Heltec Vision Master E290 |
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
| `TOKEN=<api-key>` | Store the API key using `Preferences`, reply `TOKEN=OK` (or `TOKEN=INVALID` if empty), and send it as `Authorization: Bearer <api-key>` on every request to the uConsole. |

The Setup app sends `TOKEN=` right after Wi-Fi comes up (same provisioning run
as `SETWIFI=`/`SERVER=`), loading or creating the uConsole's `.apikey` first if
it doesn't have one yet. A device provisioned before this existed simply has no
stored token until the next time it's run through Setup, and its `GET
/api/sidekick` polling keeps working either way since that endpoint doesn't
require the token - only `/api/sidekick/control` does.

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