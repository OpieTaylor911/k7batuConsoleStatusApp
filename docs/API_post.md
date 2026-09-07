small bidirectional control panel instead of only a status monitor.

I’d change the architecture from:

uConsole
   |
   | GET /api/sidekick
   v
Sidekick display

to:

                    STATUS
              GET /api/sidekick
             every 2-3 seconds
                     |
                     v
┌──────────────┐   Wi-Fi   ┌──────────────────────┐
│  ESP32-S3    │◄─────────►│      uConsole        │
│   SIDEKICK   │            │                      │
│              │            │ status_api.py        │
│ Capacitive   │            │ AIO controller       │
│ touchscreen  │            │ Radio services       │
└──────────────┘            └──────────────────────┘
       |
       | TOUCH
       v
   SDR / LoRa / USB
   GPS / BT / etc.
       |
       | POST
       v
/api/sidekick/control
I would add a control endpoint

Keep your existing read-only endpoint:

GET /api/sidekick

and add:

POST /api/sidekick/control

For example, tapping the SDR tile could send:

{
  "device": "SDR",
  "action": "on"
}

Turning it off:

{
  "device": "SDR",
  "action": "off"
}

The uConsole should reply with something like:

{
  "ok": true,
  "device": "SDR",
  "state": "on"
}

Then the ESP32 waits for the normal status poll to confirm:

SDR=G;

That last part is important: the touchscreen should request the action, but the uConsole remains authoritative about the actual state.

Touch behavior

With 480×320 we have enough room to make the tiles actual controls.

I would make:

┌─────────────────────────────────────────────────────────────┐
│ K7BAT SIDEKICK                              82%   47C  LIVE │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ● SDR       ● GPS       ● NET       ● AIO       ● BAT    │
│                                                             │
│   ● SDR+      ● ADSB      ● GPSD      ● VNC       ● RVR    │
│                                                             │
│   ● READ      ● TAR       ● BT        ● TEMP      ● PWR    │
│                                                             │
│   ● LORA      ● USB       ● ETH       ● INET      82%      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                SYSTEM NORMAL                         ⚙      │
└─────────────────────────────────────────────────────────────┘

For controllable hardware, tapping a tile would bring up something like:

┌─────────────────────────────────────┐
│              SDR RADIO              │
│                                     │
│            Current: ON              │
│                                     │
│      [ TURN OFF ]    [ CANCEL ]     │
│                                     │
└─────────────────────────────────────┘

I would not toggle power immediately on the first tap. A confirmation dialog is worth it for radios and power rails because an accidental touch could shut down hardware.

Which tiles should actually be controllable

I would distinguish status-only from control-capable tiles.

Tile	Touch action
SDR	AIO SDR rail ON/OFF
LORA	LoRa rail ON/OFF
USB	USB/AC1200 rail ON/OFF
BT	Bluetooth service ON/OFF
GPSD	Start/stop gpsd
ADSB	Start/stop readsb
VNC	Start/stop VNC
SDR+	Launch/stop SDR++
TAR	start/stop tar1090/readsb stack
GPS	status/detail only
NET	status/detail only
BAT	battery details
TEMP	temperature details
PWR	power details, probably not shutdown on single tap
ETH	status only
INET	status only

For AIO power rails in particular this fits your existing Sidekick definitions very well:

SDR
LORA
USB

because those are already tied to hardware rail state.

API control format

I would actually make the endpoint a little more general than only device/action.

Use:

{
  "target": "SDR",
  "command": "power",
  "value": "on"
}

Examples:

{
  "target": "LORA",
  "command": "power",
  "value": "off"
}
{
  "target": "GPSD",
  "command": "service",
  "value": "start"
}
{
  "target": "VNC",
  "command": "service",
  "value": "restart"
}

That lets the same API evolve beyond simple ON/OFF.

Response

I would have the uConsole return:

{
  "ok": true,
  "target": "SDR",
  "command": "power",
  "requested": "on",
  "message": "SDR power enabled"
}

On failure:

{
  "ok": false,
  "target": "SDR",
  "error": "AIO controller unavailable"
}

The ESP32 can briefly show:

SDR
TURNING ON...

and then the next normal /api/sidekick poll determines whether the LED becomes green.

The ESP32 side

The touch handler could become conceptually:

void handleTilePress(int index)
{
    String key = indicators[index].key;

    if (key == "SDR")
    {
        showPowerDialog(
            "SDR",
            indicators[index].state == STATE_GREEN
        );
    }

    else if (key == "LORA")
    {
        showPowerDialog(
            "LORA",
            indicators[index].state == STATE_GREEN
        );
    }

    else if (key == "USB")
    {
        showPowerDialog(
            "USB",
            indicators[index].state == STATE_GREEN
        );
    }
}

Then:

bool sendControl(
    const String &target,
    const String &command,
    const String &value
)
{
    if (WiFi.status() != WL_CONNECTED)
        return false;

    String url =
        "http://" +
        serverAddress +
        "/api/sidekick/control";

    HTTPClient http;

    http.begin(url);

    http.addHeader(
        "Content-Type",
        "application/json"
    );

    String body =
        "{\"target\":\"" +
        target +
        "\",\"command\":\"" +
        command +
        "\",\"value\":\"" +
        value +
        "\"}";

    int code =
        http.POST(body);

    bool ok =
        code >= 200 &&
        code < 300;

    http.end();

    return ok;
}
I would also add authentication

Since Sidekick would now be able to change hardware state, I would add a small shared token.

During provisioning:

TOKEN=<random-sidekick-token>

stored in Preferences.

Then ESP32 sends:

Authorization: Bearer <token>

The control API verifies it before accepting anything.

So:

http.addHeader(
    "Authorization",
    "Bearer " + apiToken
);

Your status GET can remain unauthenticated if you want, but I would protect the control endpoint.

Even better: long press for control

With capacitive touch, I like this interaction:

Tap

Show details

Hold for ~800 ms

Open ON/OFF control

That makes accidental switching much less likely.

For example:

Tap SDR
    ↓
SDR
State: ON
AIO Rail: ON
Service: readsb running

Hold SDR
    ↓
┌────────────────────────────┐
│ Turn SDR power OFF?        │
│                            │
│   CANCEL       TURN OFF    │
└────────────────────────────┘

That would make the 3.5" Sidekick feel much more like an actual commercial hardware controller rather than just an ESP32 dashboard.

And because your existing API model already separates things such as SDR, LORA, USB, GPSD, ADSB, BT, etc., this is a very natural extension of the current Sidekick architecture.