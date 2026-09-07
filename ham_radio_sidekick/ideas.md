I want to create a ham amateure radio stack of software for my uconsole

Absolutely. Given your CM5 uConsole running Debian Trixie, I’d turn it into a K7BAT Field Radio Console with a curated set of applications rather than installing every ham package available. Debian already has strong ARM64 support for most of the stack, including SDR++, WSJT-X, FLDIGI, FLRig, Gpredict, QSSTV, FreeDV, QLog, Dire Wolf, Hamlib, and related tools.

I’d organize the software like this:

Section	Software	Purpose
Radio Control	Hamlib / rigctld	Common CAT-control backend
	FLRig	GUI radio control
	wfview	Excellent for modern Icom radios
SDR	SDR++	Primary SDR receiver/interface
	GQRX	Lightweight alternative
	SDRangel	Advanced SDR / signal work
Digital HF	WSJT-X	FT8, FT4, WSPR, JT modes
	JS8Call	JS8 keyboard messaging
	FLDIGI	PSK31, Olivia, RTTY, MFSK, etc.
	FLMsg / FLAmp	Forms and emergency data transfer
Packet / APRS	Dire Wolf	Software TNC, AX.25, APRS
	Xastir	APRS mapping/tracking
	AX.25 Linux tools	Native packet networking
Satellite	Gpredict	Satellite passes + rotor/radio control
	SatDump	NOAA/Meteor/weather satellite reception
	QSSTV	SSTV / satellite image decoding
Voice	FreeDV	Digital HF voice
	QTel	EchoLink client
Logging	QLog	Modern Linux ham logbook
	TrustedQSL	LoTW signing/upload
	XDX	DX Cluster client
Propagation	VOACAP / pythonprop	HF propagation
	WWL	Maidenhead locator calculations
GPS	gpsd + gpspipe	GPS infrastructure
	your existing GPS tooling	Location integration
Utilities	CHIRP	Program handheld/mobile radios
	QDMR	DMR codeplug programming
	rtl_433	ISM-band signal decoding
Aircraft / RF Intel	readsb + tar1090	ADS-B
	rtl_ais	Marine AIS

A lot of this is already packaged for ARM64. Debian currently lists ARM64 builds for FLDIGI, FLRig, FreeDV, Gpredict, GQRX, QSSTV, QDMR and others. Trixie backports also provides current ARM64 packages for SDR++, Dire Wolf, QLog, WSJT-X and Hamlib.

The architecture I would use

Instead of letting every application talk directly to radios and GPS hardware, give the uConsole a common service layer:

                 K7BAT uConsole Radio Console
 ┌──────────────────────────────────────────────────────┐
 │                  K7BAT GTK Dashboard                 │
 │                                                      │
 │ RADIO │ DIGITAL │ APRS │ SAT │ SDR │ LOG │ UTILITIES│
 └──────────────────────────┬───────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              │     Radio Service Layer    │
              │                            │
              │  rigctld       gpsd        │
              │  Dire Wolf     PipeWire    │
              │  rtl_tcp       serial      │
              └───────┬────────────┬───────┘
                      │            │
       ┌──────────────┼────────────┼──────────────┐
       │              │            │              │
     RADIO           SDR          GPS          AUDIO
       │              │            │              │
 Yaesu/Icom      RTL-SDR/Airspy   AIO GPS     USB Codec
 Kenwood/etc       HackRF/etc.                 Radio

The important piece is Hamlib/rigctld.

For example:

                 ┌────────────┐
                 │   Radio    │
                 └─────┬──────┘
                       │ CAT
                 ┌─────▼──────┐
                 │  rigctld   │
                 │ TCP :4532  │
                 └─────┬──────┘
                       │
       ┌───────────────┼────────────────┐
       │               │                │
   WSJT-X           FLDIGI          Gpredict
       │               │                │
       └───────────────┼────────────────┘
                       │
                    QLog

That avoids the classic situation where WSJT-X has /dev/ttyUSB0 locked and then FLRig or Gpredict can't access it.

Your main uConsole screen

I'd build your existing GTK status console into something like:

┌─────────────────────────────────────────────────────┐
│ K7BAT RADIO CONSOLE                    GPS ●  NET ● │
├─────────────────────────────────────────────────────┤
│                                                     │
│  RADIO        SDR          DIGITAL       APRS       │
│  ┌───────┐   ┌───────┐    ┌───────┐    ┌───────┐  │
│  │146.52 │   │SDR++  │    │WSJT-X │    │ MAP   │  │
│  │ FM    │   │ ● RUN │    │ ● OFF │    │ ● RUN │  │
│  └───────┘   └───────┘    └───────┘    └───────┘  │
│                                                     │
│  SATELLITE    PACKET       LOGBOOK       TOOLS     │
│  ┌───────┐   ┌───────┐    ┌───────┐    ┌───────┐  │
│  │NOAA19 │   │DIREWLF│    │ QLOG  │    │ CHIRP │  │
│  │ 12:34 │   │ ● RUN │    │ 1,284 │    │       │  │
│  └───────┘   └───────┘    └───────┘    └───────┘  │
│                                                     │
├─────────────────────────────────────────────────────┤
│ RADIO: IC-705 │ GPS: 8 SAT │ GRID: CN85 │ BAT 82% │
└─────────────────────────────────────────────────────┘

And then make each category a page.

RADIO would show connected transceiver, frequency, mode, S-meter, SWR if available, CAT status and PTT status.

DIGITAL would launch WSJT-X, JS8Call, FLDIGI, FreeDV and QSSTV.

APRS / PACKET would give you Dire Wolf status, decoded packet count, your GPS coordinates/grid, Xastir, AX.25 interfaces and eventually Winlink.

SATELLITE would show the next five passes directly on your dashboard instead of requiring Gpredict to be open all the time.

For example:

NEXT SATELLITES

NOAA-19       12:46     MAX 67°
ISS           13:18     MAX 41°
METEOR M2-4   14:03     MAX 73°
SO-50         14:37     MAX 29°
NOAA-18       15:12     MAX 54°

That would be extremely useful on the uConsole.

APRS deserves special treatment

I would make Dire Wolf a system service rather than an application you manually launch.

It can become the uConsole's packet infrastructure:

Radio / SDR
     │
     ▼
┌──────────┐
│Dire Wolf │
└────┬─────┘
     │
 ┌───┼───────────────┐
 │   │               │
 ▼   ▼               ▼
APRS AX.25          KISS
 │                   │
 ▼                   ▼
Xastir           Other apps

Debian Trixie backports currently offers Dire Wolf 1.8.1, described as a soundcard TNC for APRS.

That gives you the beginnings of an actual portable packet station rather than just an APRS viewer.

SDR

Since you already have SDR++ working on the uConsole, I would make that the default.

Your SDR page could detect attached hardware:

SDR DEVICES

● RTL-SDR Blog V4
  SN: 00000001
  SDR++                         [ OPEN ]

● HackRF One
  SN: 87A...
  SDR++                         [ OPEN ]

○ Airspy
  Not connected

And under that:

DECODERS

ADS-B
AIS
APRS
POCSAG
NOAA
Meteor
433 MHz
FM
DMR

You already have part of that infrastructure with readsb/tar1090.

Satellite station

I'd go beyond Gpredict.

Install:

Gpredict → SatDump → QSSTV → SDR++

SatDump is especially interesting for the uConsole because it turns the system into a genuinely useful portable satellite receiver. Debian's current testing repository includes SatDump packages alongside the standard ham-radio applications.

Eventually your dashboard could automatically say:

SATELLITE ALERT

METEOR M2-4
Pass begins: 14:03
Max elevation: 73°

Suggested:
137.900 MHz
QPSK

[ OPEN SDR ] [ OPEN SATDUMP ]
Logging

I'd use QLog as your primary local log.

It is available for Debian, including current Trixie backports.

But I'd make the GTK dashboard communicate with it or its database so your home page could show:

TODAY

QSOs       12
DXCC        6
GRID        8
FT8         9
SSB         3

LAST CONTACT
K7ABC
14.230 MHz
CN84

Then integrate:

QLog
  │
  ├── LoTW
  ├── QRZ
  ├── eQSL
  └── ADIF export

TrustedQSL is also available in Trixie backports.

I would also add a dedicated Field section

This is where the uConsole could become more interesting than a typical ham laptop.

FIELD

● GPS FIX
CN85xx
45.52 / -122.67

● APRS
K7BAT-7

● BATTERY
82% / 4h 12m

● INTERNET
WiFi

● RADIO
IC-705 Connected

● LOCAL REPEATER
146.840 -
Tone 100.0

● PROPAGATION
20m GOOD
40m FAIR
10m POOR

Potential later integrations could include repeater databases, Maidenhead locator calculations, offline maps, emergency message forms, Winlink, weather information, solar propagation information, compass/bearing and antenna calculations.

Installation groups

Rather than one enormous installer, I'd make our uConsole setup support profiles:

K7BAT HAM STACK

[1] Core Radio
    Hamlib
    FLRig
    QLog
    GPSD

[2] Digital Modes
    WSJT-X
    JS8Call
    FLDIGI
    FLMsg
    FreeDV

[3] APRS / Packet
    Dire Wolf
    Xastir
    AX.25

[4] Satellite
    Gpredict
    SatDump
    QSSTV

[5] SDR
    SDR++
    GQRX
    SDRangel
    rtl-sdr tools

[6] Radio Programming
    CHIRP
    QDMR

[7] RF Monitoring
    readsb
    tar1090
    rtl_433
    rtl_ais

[8] Install EVERYTHING

The result would effectively be a custom ham-radio operating environment for the uConsole.

And I think there is a bigger opportunity here: instead of merely creating an install script, we could extend the GTK application we've already been developing into K7BAT Radio Console, where it detects hardware and presents all of these programs through one commercial-looking interface. Your Sidekick ESP display could then show radio frequency/mode, GPS, APRS, SDR, digital-mode activity, battery and satellite alerts beside the uConsole.

A logical next step is for me to build the complete Debian Trixie installation script + application menu structure + systemd services for this stack, using the software above and preserving the SDR/GPS/status pieces you already have.

With profiles we could change the profile with the sidekick or on the uconsole its self right?

Yes — and I think profiles should become a core concept shared by the uConsole and Sidekick, rather than just installation groups.

The uConsole would be the authority that actually applies a profile. The Sidekick would be a remote control/status panel that tells the uConsole to switch profiles. That way you never have the ESP32 directly trying to manage Linux services.

For example, you could define profiles like:
Profile	What happens
FIELD	GPS, Dire Wolf/APRS, logging, radio CAT, Sidekick enabled
HF DIGITAL	rigctld + WSJT-X + logging + GPS
APRS	Dire Wolf + GPS + APRS map/logging
SATELLITE	Gpredict + SDR++ + SatDump + GPS
SDR	SDR++ + SDR hardware services
ADS-B	readsb + tar1090 + SDR
EMCOMM	Dire Wolf + FLDIGI + FLMsg + GPS + logging
LOW POWER	GPS + CAT + logging; stop SDR and unnecessary services
DESKTOP	Normal uConsole environment

Then the architecture becomes:

                         K7BAT RADIO CONSOLE
                                │
                       ┌────────▼─────────┐
                       │ Profile Manager  │
                       │                 │
                       │ FIELD           │
                       │ HF DIGITAL      │
                       │ APRS            │
                       │ SATELLITE       │
                       │ SDR             │
                       │ EMCOMM          │
                       └────────┬────────┘
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
             systemd         Apps          Hardware
                 │              │              │
            Dire Wolf       WSJT-X          SDR
            rigctld         FLDIGI           GPS
            gpsd            Gpredict         Radio
            readsb          SatDump          Audio
                                ▲
                                │
                    ┌───────────┴───────────┐
                    │    Status/Profile API │
                    └───────────┬───────────┘
                                │
                              Wi-Fi
                                │
                       ┌────────▼────────┐
                       │    SIDEKICK     │
                       │                │
                       │  PROFILE       │
                       │  HF DIGITAL    │
                       │                │
                       │   ◀       ▶    │
                       │                │
                       │   [ ACTIVATE ] │
                       └────────────────┘

On the uConsole

I'd put a persistent PROFILE selector in the GTK dashboard. Selecting SATELLITE, for example, could automatically stop conflicting SDR processes, start GPS/CAT services, configure the SDR device, and present Gpredict/SatDump launch controls.

The important distinction is that a profile doesn't necessarily have to launch every GUI application immediately. We can define actions such as:

service: start
service: stop
application: launch
application: make-available
hardware: reserve
configuration: apply

So HF DIGITAL might say:

PROFILE: HF DIGITAL

START
  gpsd
  rigctld
  pipewire

STOP
  readsb
  rtl_tcp
  direwolf

RESERVE
  /dev/ttyUSB0 -> RADIO
  USB Audio    -> RADIO
  SDR          -> AVAILABLE

LAUNCH
  QLog
  WSJT-X

SIDEKICK DISPLAY
  Frequency
  Mode
  Callsign
  Grid
  TX/RX
  GPS
  Battery

And Sidekick becomes much more useful

Instead of Sidekick being primarily a status board, I'd give it a Profile screen.

Something like:

┌───────────────────────────────┐
│ K7BAT             ● CONNECTED │
├───────────────────────────────┤
│                               │
│        ACTIVE PROFILE         │
│                               │
│        HF DIGITAL             │
│                               │
│     ◀               ▶         │
│                               │
│       [ CHANGE ]              │
├───────────────────────────────┤
│ RADIO ●  GPS ●  NET ●  BAT 84│
└───────────────────────────────┘

Swipe/right or buttons:

HF DIGITAL
     ↓
APRS
     ↓
SATELLITE
     ↓
SDR
     ↓
ADS-B
     ↓
EMCOMM
     ↓
LOW POWER

Selecting one sends something conceptually as simple as:

POST /api/profile
{
  "profile": "satellite"
}

The uConsole responds:

{
  "profile": "satellite",
  "status": "activating"
}

Then:

SIDEKICK

SATELLITE
ACTIVATING...

GPS       ✓
SDR       ✓
CAT       ✓
GPREDICT  ✓
SATDUMP   ✓

READY

That also fits very naturally into the status API you already have running between the uConsole and Sidekick.
Profiles could also change the Sidekick UI

This is the part I'd especially build.

HF DIGITAL

14.074.000
USB-D

FT8
RX ●

K7BAT
CN85

APRS

APRS
144.390

K7BAT-7

GPS ●
PKTS  127
LAST  K7XYZ

SATELLITE

METEOR M2-4

AOS  14:03
  -00:12:41

137.900 MHz

AZ  218°
EL   12°

SDR

SDR++

162.550 MHz
NFM

RTL-SDR V4

GAIN  28.0
RSSI  -71

So you're effectively turning the Sidekick into a context-sensitive control head for the uConsole.

I'd also have a long press of a Sidekick button bring up Quick Profiles, making it possible to switch from FIELD → APRS → SATELLITE without touching the uConsole.

And because the actual profile engine lives on Linux, the GTK application, Sidekick, CLI, scripts, and eventually even physical GPIO buttons can all use the exact same profile manager.

That architecture is considerably cleaner than having each component independently start and stop programs.