# K7BAT Sidekick Preset / Macro System

## VS Code Implementation Plan for the Two 3.5-Inch Displays

**Targets** 1. **Hosyond 3.5-inch CYD** --- ESP32-WROOM-32, ST7796U,
480x320 landscape, XPT2046 resistive touch, `BOARD=cyd`. 2. **ESP32-S3
3.5-inch ST77922** --- ESP32-S3, ST77922, 480x320 landscape, capacitive
touch using the known-good vendor `ST77922_TOUCH` driver.

## Goal

Turn Sidekick from a status/control display into a configurable uConsole
preset launcher. A user can long-press the dashboard, select a locally
cached preset such as **GPS DRIVE**, **ADS-B MONITOR**, **SDR RADIO**,
**FIELD MODE**, or **LOW POWER**, and the Sidekick sends the preset ID
to the uConsole over the authenticated Sidekick API.

The ESP32 must **not** execute the Linux workflow itself. It sends only
a preset ID. The uConsole owns sequencing, services, applications, AIO
power rails, verification, error handling, and logging.

## UX

Keep the existing dashboard and normal tile taps. Add a non-blocking
long press of about 1000--1200 ms:

``` text
Touch down
    |
    +-- release before threshold --> existing normal tap
    |
    +-- hold >= threshold --------> open Preset Launcher
```

Both 3.5-inch displays can use the same 480x320 layout:

``` text
+------------------------------------------------+
| K7BAT SIDEKICK                     PRESETS     |
+------------------------------------------------+
|                                                |
|   [ GPS DRIVE ]        [ ADS-B MONITOR ]      |
|                                                |
|   [ SDR RADIO ]        [ FIELD MODE ]         |
|                                                |
|   [ LOW POWER ]        [ ALL SYSTEMS ]        |
|                                                |
+------------------------------------------------+
|                    BACK                        |
+------------------------------------------------+
```

Use `millis()`, never `delay(1200)`, for long-press detection.

## Screen State Model

Replace scattered modal booleans over time with:

``` cpp
enum ScreenMode
{
    SCREEN_DASHBOARD,
    SCREEN_CONTROL_DIALOG,
    SCREEN_PRESETS,
    SCREEN_PRESET_RUNNING,
    SCREEN_PRESET_RESULT
};

ScreenMode screenMode = SCREEN_DASHBOARD;
```

Route touch by screen mode.

## Long-Press State

Suggested common state:

``` cpp
bool fingerDown = false;
bool longPressTriggered = false;
unsigned long fingerDownAt = 0;
int16_t fingerDownX = 0;
int16_t fingerDownY = 0;

#define LONG_PRESS_MS 1100
#define LONG_PRESS_MOVE_TOLERANCE 15
```

Concept:

``` cpp
if (touchDown && !fingerDown)
{
    fingerDown = true;
    longPressTriggered = false;
    fingerDownAt = millis();
    fingerDownX = x;
    fingerDownY = y;
}

if (touchDown && fingerDown && !longPressTriggered &&
    millis() - fingerDownAt >= LONG_PRESS_MS)
{
    longPressTriggered = true;
    openPresetLauncher();
}

if (!touchDown && fingerDown)
{
    if (!longPressTriggered)
        handleNormalTap(fingerDownX, fingerDownY);

    fingerDown = false;
}
```

Cancel the pending long press if movement exceeds the tolerance.

## API

Keep:

``` text
GET  /api/sidekick
POST /api/sidekick/control
```

Add:

``` text
GET  /api/sidekick/presets
POST /api/sidekick/preset
GET  /api/sidekick/capabilities
```

### GET `/api/sidekick/presets`

Return UI metadata only:

``` json
{
  "version": 7,
  "presets": [
    {"id":"gps_drive","name":"GPS DRIVE","icon":"gps","color":"green"},
    {"id":"adsb_monitor","name":"ADS-B MONITOR","icon":"aircraft","color":"blue"},
    {"id":"sdr_radio","name":"SDR RADIO","icon":"radio","color":"blue"},
    {"id":"field_mode","name":"FIELD MODE","icon":"field","color":"yellow"}
  ]
}
```

Do not send shell commands or implementation details to the ESP32.

### POST `/api/sidekick/preset`

Request:

``` http
POST /api/sidekick/preset
Authorization: Bearer <sidekick-token>
Content-Type: application/json
```

``` json
{"preset":"gps_drive"}
```

Response:

``` json
{"ok":true,"preset":"gps_drive","status":"started"}
```

### GET `/api/sidekick/capabilities`

Example:

``` json
{
  "controls":["SDR","GPS","LORA","USB"],
  "services":["gpsd","readsb","vnc","bluetooth"],
  "presets":true
}
```

## uConsole Preset Definitions

Keep authoritative definitions on the uConsole, preferably data-driven:

``` text
app/
  plugins/
    sidekick/
      presets/
        gps_drive.yaml
        adsb_monitor.yaml
        sdr_radio.yaml
        field_mode.yaml
        low_power.yaml
```

Example `gps_drive.yaml`:

``` yaml
id: gps_drive
name: GPS DRIVE
description: Start GPS hardware and the navigation environment.

actions:
  - type: power
    target: GPS
    value: on

  - type: service
    target: gpsd
    value: start

  - type: wait_for
    target: GPSD
    state: G
    timeout_seconds: 10

  - type: application
    target: gps-map
    value: start
```

Example `adsb_monitor.yaml`:

``` yaml
id: adsb_monitor
name: ADS-B MONITOR

actions:
  - type: power
    target: SDR
    value: on

  - type: service
    target: readsb
    value: start

  - type: wait_for
    target: READ
    state: G
    timeout_seconds: 10

  - type: application
    target: adsb-map
    value: start
```

Example `field_mode.yaml`:

``` yaml
id: field_mode
name: FIELD MODE

actions:
  - type: power
    target: GPS
    value: on

  - type: power
    target: LORA
    value: on

  - type: service
    target: gpsd
    value: start

  - type: service
    target: bluetooth
    value: start

  - type: service
    target: vnc
    value: stop
```

## Preset Executor

Do not execute presets directly inside the HTTP route. Add a preset
manager/executor:

``` text
status_api.py
    |
    +--> preset_manager.py
             |
             +--> load preset
             +--> validate preset
             +--> authorize actions
             +--> execute sequence
             +--> verify state
             +--> record result
```

Initial allowlisted action types:

``` text
power
service
application
wait_for
delay
```

Possible future action types:

``` text
sdr
volume
display
navigation
bluetooth
wifi
lora
script
```

Never accept arbitrary shell command text from a Sidekick. If `script`
is later supported, the device sends an allowlisted server-side script
ID.

## Local Preset Storage

Use **LittleFS** on both boards for the cached catalog.

Suggested files:

``` text
/presets.json
/preset-version.txt
```

Continue using `Preferences` / NVS for:

``` text
ssid
pass
server
token
```

Never store the Bearer token in `/presets.json`.

Example cache:

``` json
{
  "version":7,
  "presets":[
    {"id":"gps_drive","name":"GPS DRIVE","icon":"gps","color":"green"},
    {"id":"adsb_monitor","name":"ADS-B MONITOR","icon":"aircraft","color":"blue"}
  ]
}
```

Boot/sync flow:

``` text
Boot
 |
 +--> mount LittleFS
 +--> load cached presets
 +--> show dashboard
 +--> connect Wi-Fi
 +--> GET /api/sidekick/presets
 +--> compare version
       |
       +-- same --> keep cache
       +-- newer --> replace cache
```

Cached presets may still be displayed while disconnected, but execution
requires the uConsole API.

## Common Firmware Interface

Create reusable logic instead of duplicating preset code in both
sketches:

``` cpp
struct SidekickPreset
{
    String id;
    String name;
    String icon;
    String color;
};

bool loadPresetCache();
bool savePresetCache();
bool syncPresets();
bool sendPreset(const String &presetId);

void openPresetLauncher();
void closePresetLauncher();
void drawPresetLauncher();
void handlePresetTouch(int16_t x, int16_t y);
```

Longer term:

``` text
sidekick_common/
  SidekickPresetStore.h
  SidekickPresetStore.cpp
  SidekickApi.h
  SidekickApi.cpp
```

Board-specific firmware should own only display/touch initialization,
coordinate handling, rendering details, and hardware recovery.

## Preset Execution UI

When selected:

``` text
+------------------------------------------------+
| GPS DRIVE                                      |
+------------------------------------------------+
|                                                |
|             Starting preset...                 |
|                                                |
|                 PLEASE WAIT                    |
|                                                |
+------------------------------------------------+
```

Success:

``` text
+------------------------------------------------+
| GPS DRIVE                                      |
+------------------------------------------------+
|                    OK                          |
| GPS and navigation environment started.        |
|                 [ BACK ]                       |
+------------------------------------------------+
```

Failure:

``` text
+------------------------------------------------+
| GPS DRIVE                                      |
+------------------------------------------------+
|                  FAILED                        |
| gpsd did not become active.                    |
|              [ RETRY ] [ BACK ]                |
+------------------------------------------------+
```

After completion, refresh `GET /api/sidekick` so displayed state remains
authoritative.

## Hosyond ST7796U / XPT2046 Integration

Preserve the known-good current implementation:

``` text
ESP32-WROOM-32
ST7796U
480x320 landscape
XPT2046 resistive touch
BOARD=cyd
```

Preserve: - LovyanGFX ST7796 configuration. - XPT2046 calibration. -
`CALTOUCH`. - `GETTOUCH`. - calibration persistence. - conservative
touch SPI settings. - non-flashing API refresh behavior.

Resistive long-press handling needs extra release debounce and movement
tolerance because the stylus can produce noisy samples. Recommended
threshold: 1100--1300 ms.

## ST77922 ESP32-S3 3.5-Inch Integration

Preserve the known-good vendor stack:

``` cpp
#include "ST77922.h"
#include "ST77922_Touch.h"

ST77922 lcd;
ST77922_TOUCH touch;
```

Keep the known-good display/touch rotation and any existing
touch-health/recovery logic. Capacitive touch is well suited to a \~1000
ms long press.

Do not replace this working vendor touch layer while adding presets.

## Security Requirements

1.  Continue USB provisioning with `TOKEN=<api-key>`.
2.  Store the token in Preferences namespace `sidekick`, key `token`.
3.  Never store the token in the preset catalog.
4.  Never return or log the token in normal diagnostics.
5.  Sidekick sends preset IDs, not commands.
6.  uConsole validates the preset exists.
7.  Preset action types and targets are allowlisted.
8.  Reject arbitrary shell commands from the device.
9.  Log preset execution server-side.
10. Record success/failure for each action.
11. `POST /api/sidekick/preset` uses the same Bearer-token validation
    model as `/api/sidekick/control`.

## Suggested Server Result Model

For each run, track:

``` json
{
  "preset":"gps_drive",
  "status":"success",
  "started_at":"...",
  "finished_at":"...",
  "actions":[
    {"type":"power","target":"GPS","status":"success"},
    {"type":"service","target":"gpsd","status":"success"},
    {"type":"wait_for","target":"GPSD","status":"success"},
    {"type":"application","target":"gps-map","status":"success"}
  ]
}
```

This can later support history/auditing in the uConsole Status App.

## Future SDR Example

``` yaml
id: sdr_airband
name: SDR AIRBAND

actions:
  - type: power
    target: SDR
    value: on

  - type: application
    target: sdrpp
    value: start

  - type: sdr
    frequency: 118300000
    mode: AM
    bandwidth: 12000

  - type: volume
    value: 65
```

The Sidekick still sends only:

``` json
{"preset":"sdr_airband"}
```

## Implementation Order for VS Code

### Phase 1 --- uConsole backend

-   [ ] Create preset definition directory.
-   [ ] Create `preset_manager.py`.
-   [ ] Define allowed action types and targets.
-   [ ] Implement YAML preset loading and validation.
-   [ ] Implement `GET /api/sidekick/presets`.
-   [ ] Implement authenticated `POST /api/sidekick/preset`.
-   [ ] Implement `GET /api/sidekick/capabilities`.
-   [ ] Add execution logging.
-   [ ] Add clear error responses.

### Phase 2 --- Common ESP32 preset support

-   [ ] Enable LittleFS.
-   [ ] Define `SidekickPreset`.
-   [ ] Load `/presets.json` at boot.
-   [ ] Implement catalog download.
-   [ ] Compare catalog versions.
-   [ ] Save updated catalog atomically.
-   [ ] Implement authenticated `sendPreset()`.
-   [ ] Add `GETPRESETS` Serial diagnostic.
-   [ ] Add `SYNCPRESETS` Serial diagnostic.

### Phase 3 --- Hosyond 3.5-inch UI

-   [ ] Add non-blocking long-press detection to XPT2046 handler.
-   [ ] Preserve normal tile taps.
-   [ ] Add preset launcher.
-   [ ] Add preset-running screen.
-   [ ] Add success/failure screen.
-   [ ] Verify touch calibration remains stable.
-   [ ] Verify API polling does not cause display flashing.

### Phase 4 --- ST77922 3.5-inch UI

-   [ ] Add long-press state around existing vendor capacitive touch
    handling.
-   [ ] Do not replace `ST77922_TOUCH`.
-   [ ] Add the same preset launcher layout.
-   [ ] Add running/result screens.
-   [ ] Preserve touch recovery.
-   [ ] Verify API polling remains responsive.

### Phase 5 --- Testing

-   [ ] Wi-Fi absent.
-   [ ] API absent.
-   [ ] Token absent.
-   [ ] Invalid token.
-   [ ] Empty preset catalog.
-   [ ] Corrupt local cache.
-   [ ] Preset removed from server.
-   [ ] Preset action failure.
-   [ ] Long press does not trigger normal tap.
-   [ ] Normal tap still opens individual control.
-   [ ] Reboot preserves cache.
-   [ ] Updated catalog synchronizes.
-   [ ] Both 3.5-inch boards display identical preset names/actions.
-   [ ] uConsole remains authoritative after execution.

## Recommended First Presets

Start with a small useful catalog:

``` text
GPS DRIVE
ADS-B MONITOR
SDR RADIO
FIELD MODE
LOW POWER
```

Do not begin with arbitrary user-defined shell macros. Establish the
typed/allowlisted preset executor first.

## Target Architecture

``` text
                   K7BAT SIDEKICK
                +-------------------+
                | Dashboard         |
                |                   |
                | tap  = control    |
                | hold = presets    |
                +---------+---------+
                          |
                          v
                +-------------------+
                | Local Preset Cache|
                | LittleFS          |
                +---------+---------+
                          |
                          | Bearer API
                          v
             +---------------------------+
             | uConsole Sidekick API     |
             |                           |
             | /sidekick                 |
             | /control                  |
             | /presets                  |
             | /preset                   |
             | /capabilities             |
             +-------------+-------------+
                           |
                    +------+------+
                    | Preset      |
                    | Executor    |
                    +------+------+
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
          AIO Rails      systemd       Apps
        SDR/GPS/LoRa   gpsd/readsb   Map/SDR++
```

## Definition of Done

The feature is complete when either 3.5-inch Sidekick can:

1.  Boot and load its cached preset catalog.
2.  Continue showing the normal Sidekick dashboard.
3.  Distinguish a normal tap from a long press.
4.  Open the Preset Launcher after a long press.
5.  Display presets supplied by the uConsole.
6.  Send only the selected preset ID using Bearer authentication.
7.  Display running/success/failure feedback.
8.  Refresh normal Sidekick status after execution.
9.  Survive reboot with Wi-Fi, server, token, touch configuration, and
    preset cache intact.
10. Run the same preset catalog on both 3.5-inch hardware targets
    without embedding Linux workflow logic in either firmware.
