CM5 Settings for Hackergadget Device:
Lora:
  Module: sx1262
  DIO2_AS_RF_SWITCH: true
  DIO3_TCXO_VOLTAGE: true
  IRQ: 26
  Busy: 24
  Reset: 25
  gpiochip: 15
  spidev: spidev1.0
  
  
  
What do I need to install on my uconsole to have a interface for meshtastic in the gui  

Yes. On your Debian Trixie uConsole, there is already a package that fits what you're asking for extremely well: gtk-meshtastic-client.

It's a native GTK4/libadwaita Meshtastic GUI, packaged directly in Debian Trixie, and supports connecting to a Meshtastic radio over USB serial, Bluetooth, or TCP/IP.

Install it

On the uConsole:

sudo apt update
sudo apt install gtk-meshtastic-client

Then launch it with:

gtk-meshtastic-client

Debian's Trixie package pulls in the Meshtastic Python API and the necessary GTK/libadwaita dependencies automatically.

This is particularly convenient for your uConsole because it's a real Linux desktop application rather than a phone UI stuffed into a browser.

What I'd install alongside it

I'd add the Meshtastic CLI tools as well:

sudo apt install \
    gtk-meshtastic-client \
    python3-meshtastic \
    bluez \
    bluetooth

The underlying Meshtastic Python API supports SerialInterface, TCPInterface, and BLEInterface, so later we can use the same infrastructure from your own K7BAT GTK status application.

That gives us a useful architecture:

              K7BAT uCONSOLE
                    │
          ┌─────────┴──────────┐
          │ Meshtastic Service │
          │ Python API         │
          └─────────┬──────────┘
                    │
       ┌────────────┼─────────────┐
       │            │             │
      USB           BLE          TCP/IP
       │            │             │
       └────────────┼─────────────┘
                    │
             Meshtastic Node
                    │
                  LoRa
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
        Node A    Node B    Node C

The GTK client can then give you the normal graphical Meshtastic experience while we use the Python interface to expose information to your existing dashboard.

It gets better for your K7BAT project

I wouldn't stop at installing the GUI.

I'd add MESHTASTIC as one of the major functions in the radio stack we were discussing:

┌─────────────────────────────────────────────────┐
│ K7BAT RADIO CONSOLE                  GPS ● NET ●│
├─────────────────────────────────────────────────┤
│                                                 │
│ RADIO       SDR        DIGITAL      MESH        │
│                                                 │
│ SAT         APRS       PACKET       LOG         │
│                                                 │
├─────────────────────────────────────────────────┤
│ MESH: 14 NODES │ GPS: CN85 │ BAT: 84%          │
└─────────────────────────────────────────────────┘

Selecting MESH could launch gtk-meshtastic-client.

But the dashboard itself could eventually display:

MESHTASTIC
────────────────────────

Radio        ● CONNECTED
Interface    USB
Channel      LongFast
Nodes        14
Online       8

LAST MESSAGE

K7XYZ
"At trailhead"

RSSI        -87 dBm
SNR          8.5 dB

And a dedicated page could eventually contain:

┌─────────────────────────────────────────────────┐
│ MESHTASTIC                              ● ONLINE │
├─────────────────────────────────────────────────┤
│ NODES                                           │
│                                                 │
│ ● K7BAT-BASE        -72 dBm     0.8 km          │
│ ● K7XYZ             -84 dBm     3.2 km          │
│ ● HILLTOP           -91 dBm     7.6 km          │
│ ○ MOBILE            last 18m                    │
│                                                 │
├─────────────────────────────────────────────────┤
│ MESSAGES                                        │
│                                                 │
│ K7XYZ      Arrived at checkpoint                │
│ HILLTOP    Signal good                          │
│                                                 │
├─────────────────────────────────────────────────┤
│ [ MAP ]      [ MESSAGE ]      [ CONFIG ]        │
└─────────────────────────────────────────────────┘

The Python API already maintains a node database containing things such as node/user and location information, making this kind of integration realistic rather than requiring us to scrape the GTK application.

Th