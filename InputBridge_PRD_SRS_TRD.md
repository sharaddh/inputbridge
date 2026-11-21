# InputBridge

## Product Requirements Document (PRD), Software Requirements Specification (SRS), and Technical Requirements Document (TRD)

**Document version:** 1.0\
**Date:** 18 November 2026\
**Status:** Proposed --- feasibility-aware engineering specification\
**Working product name:** InputBridge\
**Target platform:** Windows 11 laptop + Android phone (initially Vivo /
Android 15 class device)

------------------------------------------------------------------------

# 1. Executive summary

InputBridge is a Windows utility and Android companion system that lets
a user switch a physical keyboard and wireless mouse between a Windows
laptop and an Android phone using a configurable global keyboard
shortcut.

Example:

1.  The wireless mouse is connected to the laptop through its USB
    receiver (dongle).
2.  The laptop keyboard and mouse normally control Windows.
3.  The user presses a configurable shortcut, such as **Shift + Caps
    Lock**.
4.  InputBridge changes to **Phone mode**.
5.  Keyboard and/or mouse actions are sent to the Android phone through
    a supported transport.
6.  Pressing the shortcut again returns to **Laptop mode**.

The product should support three routing choices:

-   **Both:** keyboard and mouse are routed to the phone.
-   **Keyboard only:** keyboard is routed to the phone; mouse remains on
    Windows.
-   **Mouse only:** mouse is routed to the phone; keyboard remains on
    Windows.

The system should also offer a reliable emergency shortcut to return
control to Windows.

## 1.1 Important feasibility finding

The Windows side can reliably detect keyboard and mouse activity.
However, **detecting an input is not the same as safely redirecting
it**. Windows Raw Input is useful for observing devices, but it does not
suppress the original input. A low-level Windows hook can suppress many
ordinary input events, but it has limitations and is not a universal,
secure input-routing mechanism.

Android also restricts apps from injecting arbitrary keyboard and mouse
events into every app. An ordinary Android app cannot simply behave like
a system-level input driver.

Therefore, InputBridge must be developed in stages and must not promise
unrestricted, system-wide redirection until the selected Android and
Windows implementation has been proven.

**Recommended engineering approach:**

-   **Prototype:** Windows app + Android companion, communicating over
    the phone hotspot/local Wi-Fi. Use Android Debug Bridge (ADB) over
    Wi-Fi for a controlled proof of concept. This validates shortcut
    detection, routing state, network transport, and basic phone
    actions.
-   **MVP:** Windows app + Android companion using an explicit Android
    input strategy. Use an Android Accessibility Service for supported
    pointer gestures and a companion input method (IME) for text entry
    where appropriate. Clearly communicate the limits of each input
    type.
-   **Advanced release:** Investigate a true Bluetooth HID or supported
    virtual-HID architecture. This is the route to more native
    keyboard/mouse behavior, but it requires a separate compatibility
    and driver feasibility spike. Do not assume a standard Windows
    laptop can automatically act as a Bluetooth keyboard/mouse
    peripheral.

The first release should prioritize safe, reversible switching over
pretending that every input can be redirected on every Android screen.

------------------------------------------------------------------------

# 2. Product vision and goals

## 2.1 Vision

Make one physical keyboard and mouse usable across a Windows laptop and
an Android phone, with a fast keyboard shortcut and no need to pick up a
second keyboard or mouse.

## 2.2 Primary goals

1.  Switch between Laptop mode and Phone mode with a configurable
    shortcut.
2.  Support independent keyboard and mouse routing.
3.  Keep the phone connected over a local connection, preferably the
    phone's hotspot or another shared Wi-Fi network.
4.  Show an obvious current mode and connection status.
5.  Provide a fast emergency return-to-laptop action.
6.  Prevent accidental loss of control if the phone disconnects, the app
    crashes, or the network fails.
7.  Keep setup understandable for a non-technical user.
8.  Build the product in testable stages, with clear boundaries around
    Android and Windows limitations.

## 2.3 Non-goals for the first release

-   Replacing Windows input drivers.
-   Guaranteeing input redirection on the Windows secure desktop, login
    screen, UAC prompts, BIOS, or every elevated/anti-cheat application.
-   Supporting iOS in the first release.
-   Supporting multiple phones simultaneously.
-   Supporting gaming-grade, ultra-low-latency mouse movement.
-   Capturing passwords or secretly recording input.
-   Bypassing Android security restrictions or requiring root access.
-   Sending input over the public internet or a cloud server.

------------------------------------------------------------------------

# 3. Target users and use cases

## 3.1 Primary user

A person who works on a Windows 11 laptop and wants to control an
Android phone placed nearby, using the laptop's existing keyboard and
wireless mouse.

## 3.2 Main use cases

  -----------------------------------------------------------------------
  ID                      Use case                Expected result
  ----------------------- ----------------------- -----------------------
  UC-01                   Switch to phone         Configured shortcut
                                                  changes routing to
                                                  Phone mode

  UC-02                   Return to laptop        Shortcut or emergency
                                                  shortcut restores
                                                  Windows routing

  UC-03                   Keyboard-only routing   Keyboard goes to phone;
                                                  mouse remains on
                                                  Windows

  UC-04                   Mouse-only routing      Mouse goes to phone;
                                                  keyboard remains on
                                                  Windows

  UC-05                   Both-device routing     Keyboard and mouse go
                                                  to phone

  UC-06                   Phone disconnects       InputBridge safely
                                                  returns affected
                                                  devices to Windows

  UC-07                   App starts              Default mode is Laptop
                                                  mode

  UC-08                   Change shortcut         User records a new
                                                  shortcut in Settings

  UC-09                   Connection recovery     App reconnects to the
                                                  paired phone without
                                                  sending stale input

  UC-10                   Pause routing           User can immediately
                                                  stop forwarding
  -----------------------------------------------------------------------

## 3.3 Example workflow

``` text
Laptop mode
  Keyboard ───────────────► Windows
  Wireless mouse dongle ──► Windows

          User presses Shift + Caps Lock

Phone mode
  Keyboard ───────────────► InputBridge ──► Android
  Wireless mouse ─────────► InputBridge ──► Android

          User presses shortcut again

Laptop mode
  Keyboard ───────────────► Windows
  Wireless mouse dongle ──► Windows
```

The diagram represents the desired user experience. Actual routing
depends on the input-capture and Android-injection implementation
selected for the device.

------------------------------------------------------------------------

# 4. Product scope and release strategy

## 4.1 Phase 0 --- Technical feasibility spike

**Purpose:** Prove the difficult parts before building a polished UI.

Deliverables:

-   Detect the configured shortcut on Windows.
-   Read mouse and keyboard events for a test application.
-   Establish a local authenticated connection between Windows and
    Android.
-   Send a test message and receive an acknowledgement.
-   Execute a small set of Android test actions using ADB over Wi-Fi.
-   Test whether the chosen Windows interception mechanism can suppress
    ordinary input safely.
-   Record device, Android version, Windows version, and limitations.

**Exit criteria:**

-   Shortcut detection works reliably.
-   The Android phone can be paired and reached over the local network.
-   A test tap and text/key action can be triggered on the phone using
    the prototype mechanism.
-   The team has documented which Windows inputs can and cannot be
    suppressed.
-   The team has a clear decision on whether the MVP can deliver the
    desired experience without a custom driver.

## 4.2 Phase 1 --- MVP

-   Windows system-tray application.
-   Android companion application.
-   Pairing and local connection.
-   Configurable switch shortcut.
-   Laptop / Phone mode indicator.
-   Keyboard-only, mouse-only, and both-device routing states.
-   Emergency return-to-laptop shortcut.
-   Connection-loss fallback.
-   Basic event forwarding for the input types proven in Phase 0.
-   Setup guide and diagnostics screen.

## 4.3 Phase 2 --- Enhanced experience

-   Better mouse movement and scroll handling.
-   Better key mapping and modifier handling.
-   Reconnection and network-change handling.
-   Per-device routing preferences.
-   Connection quality indicator.
-   Optional launch-at-login.
-   Input-device selection when multiple keyboards or mice are attached.
-   More Android compatibility testing.

## 4.4 Phase 3 --- Advanced native input

Investigate one of the following only after a feasibility review:

1.  A supported Bluetooth HID peripheral implementation.
2.  A signed Windows virtual-HID driver with an Android-side input
    receiver.
3.  Another documented, supportable native input transport.

This phase may require native Windows driver engineering, driver
signing, Android platform-specific work, or hardware compatibility
constraints. It is not part of the initial MVP commitment.

------------------------------------------------------------------------

# 5. Product requirements document (PRD)

## 5.1 Functional requirements

### FR-01: Default laptop mode

-   On first launch, InputBridge must start in Laptop mode.
-   Laptop mode means InputBridge does not intentionally forward user
    input to the phone.
-   If the app is not running, normal Windows input behavior must remain
    unaffected.

### FR-02: Configurable global shortcut

-   The user can configure a shortcut such as `Shift + Caps Lock`.
-   The shortcut must be detected while the InputBridge window is not
    focused.
-   The UI must show the recorded key combination.
-   The app must reject invalid or incomplete combinations.
-   The user must be able to restore a default shortcut.
-   The app must warn if a shortcut conflicts with a known system or
    application shortcut.

**Implementation note:** A low-level keyboard hook can detect many
global shortcuts, but shortcut handling must be tested for modifier
state, key-up events, keyboard layouts, elevated applications, and hook
failure. Do not make Caps Lock state changes unintentionally when using
it as a modifier.

### FR-03: Routing modes

The app must expose these modes:

  Mode                 Keyboard   Mouse
  -------------------- ---------- ---------
  Laptop               Windows    Windows
  Phone --- Both       Phone      Phone
  Phone --- Keyboard   Phone      Windows
  Phone --- Mouse      Windows    Phone
  Paused               Windows    Windows

The UI must clearly display the active mode.

### FR-04: Toggle behavior

-   Pressing the configured shortcut toggles between Laptop mode and the
    last selected Phone mode.
-   If the current state is Phone --- Keyboard or Phone --- Mouse, the
    user can still return to Laptop mode.
-   The app must not accidentally toggle multiple times because of
    key-repeat events.
-   A shortcut should be treated as one deliberate activation, not as
    repeated activations while held down.

### FR-05: Emergency return

-   A dedicated emergency shortcut must return all routing to Laptop
    mode.
-   It should be different from the normal toggle shortcut.
-   The emergency action must work even when the phone is disconnected.
-   If the main UI is frozen, the emergency mechanism should be as
    independent as practical.
-   A system-tray menu must also provide **Return to Laptop**.

### FR-06: Phone pairing

-   The Windows app must provide a pairing flow.
-   The Android app must display a pairing code or approve a pairing
    request.
-   Pairing must establish a trusted device identity.
-   The user must be able to revoke a paired device.
-   A phone must not accept input from an unknown laptop.

### FR-07: Local connection

-   The initial transport should use the same local network, including
    the Android phone hotspot.
-   Internet access must not be required.
-   The app must show whether the phone is connected, disconnected, or
    reconnecting.
-   The connection must be authenticated.
-   The app must not expose an unauthenticated input-control port to the
    wider network.

### FR-08: Keyboard forwarding

Subject to the selected Android input mechanism:

-   Forward supported key-down and key-up events.
-   Preserve modifier combinations where supported (Shift, Ctrl, Alt,
    and Windows/Meta).
-   Map special keys deliberately.
-   Handle key repeat.
-   Avoid stuck modifiers after a disconnect or mode switch.
-   Do not log key contents.

### FR-09: Mouse forwarding

Subject to the selected Android input mechanism:

-   Forward supported pointer movement.
-   Forward left and right button actions where supported.
-   Forward scroll events where supported.
-   Preserve button-down/button-up ordering.
-   Avoid stuck mouse buttons after disconnect.
-   Define coordinate scaling and screen-boundary behavior.
-   Show the phone's display dimensions and orientation to the Windows
    side if coordinate mapping is used.

### FR-10: Independent device selection

-   User can choose keyboard, mouse, or both.
-   A mode change must apply atomically as far as the underlying
    platform permits.
-   If one device cannot be routed, the app must not falsely show that
    both are routed.

### FR-11: Disconnect handling

If the phone disconnects while in Phone mode:

1.  Stop forwarding new events.
2.  Clear pending events.
3.  Release any forwarded keys/buttons where the receiver supports it.
4.  Return affected devices to Windows routing.
5.  Show a visible notification.
6.  Do not replay old input after reconnection.

### FR-12: System tray

The Windows app should provide:

-   Open InputBridge.
-   Current mode.
-   Switch to Phone.
-   Return to Laptop.
-   Pause.
-   Settings.
-   Exit.

### FR-13: Settings

Settings should include:

-   Normal toggle shortcut.
-   Emergency shortcut.
-   Default phone routing mode.
-   Auto-connect preference.
-   Launch at Windows startup.
-   Connection timeout.
-   Notifications.
-   Paired phone management.
-   Diagnostics and logs.

### FR-14: Privacy

-   No keystroke recording.
-   No clipboard collection by default.
-   No screenshots or screen recording by default.
-   No cloud relay.
-   No telemetry containing input content.
-   Diagnostic logs may contain event type, timestamp, connection
    status, and error code, but not typed text or sensitive payloads.

## 5.2 User experience requirements

-   The active mode must be visible without opening the main window.
-   Switching should feel immediate.
-   A successful switch should produce a short visual notification;
    sound should be optional.
-   Phone mode must be visually distinguishable from Laptop mode.
-   If the phone is unavailable, the UI must explain why Phone mode
    could not be activated.
-   The first-run setup must explain Android permissions and limitations
    before requesting them.

## 5.3 Success metrics

  -----------------------------------------------------------------------
  Metric                              Initial target
  ----------------------------------- -----------------------------------
  Shortcut response                   Under 150 ms on a normal, healthy
                                      system

  Local connection setup              Under 5 seconds after pairing,
                                      under normal network conditions

  Mode-state accuracy                 100% in automated state-machine
                                      tests

  Disconnect fallback                 Return to laptop routing within 1
                                      second of detecting loss

  Accidental repeated toggles         Zero in the defined shortcut test
                                      suite

  Input content in logs               Zero

  Pairing                             Only explicitly approved devices
                                      can connect
  -----------------------------------------------------------------------

These are engineering targets, not guaranteed performance claims. Actual
latency depends on the chosen Android injection method, network, device,
and Windows interception implementation.

------------------------------------------------------------------------

# 6. Software requirements specification (SRS)

## 6.1 System context

InputBridge contains two applications and a local communication channel.

``` text
┌──────────────────────────── Windows 11 ────────────────────────────┐
│                                                                    │
│  Physical keyboard                     Wireless mouse + USB dongle │
│         │                                         │                │
│         └────────────────┬────────────────────────┘                │
│                          ▼                                         │
│                Windows Input Layer                                 │
│                          │                                         │
│                InputBridge Windows Service/App                    │
│                ┌──────────────────────────────┐                    │
│                │ Shortcut Manager             │                    │
│                │ Routing State Machine        │                    │
│                │ Keyboard Adapter             │                    │
│                │ Mouse Adapter                │                    │
│                │ Network Client               │                    │
│                │ Tray UI / Settings           │                    │
│                └──────────────┬───────────────┘                    │
└──────────────────────────────┼─────────────────────────────────────┘
                               │
                      Authenticated local link
                       Wi-Fi / phone hotspot
                               │
┌──────────────────────────────┼─────────────────────────────────────┐
│                         Android phone                              │
│                               ▼                                    │
│                InputBridge Android Companion                      │
│                ┌──────────────────────────────┐                    │
│                │ Pairing / Authentication    │                    │
│                │ Connection Manager          │                    │
│                │ Event Decoder               │                    │
│                │ Input Capability Adapter     │                    │
│                │ Status / Diagnostics         │                    │
│                └──────────────┬───────────────┘                    │
│                               ▼                                    │
│                   Android-supported input path                    │
└────────────────────────────────────────────────────────────────────┘
```

## 6.2 Operating environment

### Windows

-   Windows 11, 64-bit.
-   Initial target: current supported Windows 11 builds.
-   Physical keyboard may be built-in or USB.
-   Mouse may use a USB wireless receiver/dongle.
-   Network: Wi-Fi connection to the Android hotspot or same local
    network.
-   No administrator privileges should be required for ordinary UI and
    networking. Some advanced input interception or driver approaches
    may require elevated installation and must be assessed separately.

### Android

-   Android 11 or later is a reasonable initial development target
    because wireless debugging was introduced in Android 11.
-   Initial test device: user's Vivo Android 15 phone.
-   Android companion app installed by the user.
-   Accessibility permission may be required for supported gesture
    control.
-   ADB/Wireless Debugging is a development/prototype route, not the
    recommended end-user production dependency.

## 6.3 External interface requirements

### Windows user interface

-   System-tray icon.
-   Main settings window.
-   Shortcut recorder.
-   Mode selector.
-   Connection state.
-   Pairing code display.
-   Error and diagnostic panel.

### Android user interface

-   Pairing approval.
-   Connection state.
-   Input capability status.
-   Permission explanation and settings link.
-   Disconnect button.
-   Diagnostics.

### Network interface

The Windows and Android applications communicate over a local
authenticated connection.

Suggested initial transport:

-   TCP with TLS, or
-   WebSocket over TLS.

For an initial local proof of concept, a simple TCP/WebSocket channel
may be used on a trusted hotspot, but production pairing and
authentication must be implemented before release.

## 6.4 Data requirements

Example message envelope:

``` json
{
  "protocolVersion": 1,
  "sessionId": "random-session-id",
  "sequence": 1042,
  "type": "input",
  "device": "keyboard",
  "event": {
    "action": "keyDown",
    "key": "A",
    "modifiers": ["SHIFT"],
    "timestamp": 1731930000000
  }
}
```

Example pointer message:

``` json
{
  "protocolVersion": 1,
  "sessionId": "random-session-id",
  "sequence": 1043,
  "type": "input",
  "device": "mouse",
  "event": {
    "action": "move",
    "x": 0.52,
    "y": 0.31,
    "coordinateSpace": "normalized",
    "timestamp": 1731930000010
  }
}
```

The examples define a proposed protocol shape. They are not a claim that
every Android input adapter can execute every event.

### Protocol rules

-   Use monotonically increasing sequence numbers per session.
-   Reject malformed or out-of-order messages.
-   Include a protocol version.
-   Authenticate the session.
-   Limit message size and event rate.
-   Do not store typed text in diagnostics.
-   Use normalized pointer coordinates (0.0--1.0) if the selected
    Android adapter needs coordinate mapping.
-   Send key-up/button-up events reliably.
-   On session end, clear the receiver's pressed-key/button state.

## 6.5 Error handling

  -----------------------------------------------------------------------
  Error                               Required behavior
  ----------------------------------- -----------------------------------
  Phone not found                     Stay in Laptop mode and show
                                      connection guidance

  Pairing rejected                    Do not establish an input session

  Authentication failure              Close connection and show error

  Network lost                        Stop forwarding and restore laptop
                                      routing

  Android permission missing          Explain required permission and
                                      disable unsupported capability

  Windows hook failure                Disable routing and restore normal
                                      Windows behavior

  Invalid shortcut                    Keep previous valid shortcut

  Phone app crashes                   Detect lost heartbeat and restore
                                      laptop routing

  Unsupported key                     Ignore safely and report capability
                                      limitation

  Malformed packet                    Reject packet and log non-sensitive
                                      error
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 7. Technical requirements document (TRD)

## 7.1 Recommended architecture

Use a modular architecture so that input capture, transport, Android
input injection, and UI can be changed independently.

### Windows modules

  -----------------------------------------------------------------------
  Module                              Responsibility
  ----------------------------------- -----------------------------------
  App Controller                      Owns application lifecycle

  Shortcut Manager                    Registers and detects global
                                      shortcuts

  Routing State Machine               Decides which device is routed
                                      where

  Keyboard Adapter                    Captures/maps keyboard events

  Mouse Adapter                       Captures/maps mouse events

  Input Suppression Adapter           Suppresses local events only where
                                      safely supported

  Network Client                      Authenticated connection to Android

  Pairing Manager                     Device identity and trust

  Tray UI                             Mode and quick actions

  Settings Store                      Persist user preferences

  Watchdog                            Detect failures and force safe
                                      state
  -----------------------------------------------------------------------

### Android modules

  Module                    Responsibility
  ------------------------- --------------------------------------------
  Pairing UI                Approve trusted laptop
  Connection Service        Maintain local connection
  Protocol Decoder          Validate and decode messages
  Capability Manager        Report supported input actions
  Accessibility Adapter     Perform supported gestures
  Input Method (optional)   Provide text-entry route where appropriate
  Status UI                 Connection, permissions, and mode
  Safety Manager            Stop input on disconnect or session expiry

## 7.2 Windows input capture and suppression

This is one of the highest-risk engineering areas.

### Windows Raw Input

Raw Input can identify and receive input data from devices, including
keyboards and mice. It is useful for:

-   Device identification.
-   Distinguishing physical keyboards and mice where the API provides
    device handles.
-   Reading key and mouse data.
-   Supporting multiple devices.

**Limitation:** Raw Input is not, by itself, a mechanism for preventing
the normal Windows input system from receiving the same event.

### Low-level hooks

Windows provides low-level keyboard and mouse hooks that can observe
and, in many ordinary desktop cases, suppress events by returning a
non-zero result.

Potential uses:

-   Detect the global toggle shortcut.
-   Suppress selected keyboard events while Phone mode is active.
-   Suppress selected mouse events while Phone mode is active.

Limitations and risks:

-   Hooks can time out or be removed.
-   They are not a universal solution for secure desktop, login, UAC,
    all elevated contexts, or every application.
-   A crash or deadlock in the hook path can create a poor input
    experience.
-   Some applications and security products may interact with hooks
    differently.
-   Hook callbacks must be extremely short; do not perform network I/O
    inside them.
-   A hook may not reliably distinguish every physical input device in
    the way the product needs.

### Recommended design

-   Keep hook callbacks minimal.
-   Put captured events into a bounded, non-blocking queue.
-   Send events from a separate worker thread.
-   Use a watchdog to detect stalled workers.
-   If the hook or routing layer fails, switch to a safe state and stop
    suppressing events.
-   Never suppress the emergency shortcut.
-   Do not attempt to suppress events on secure desktop or system login
    screens.

### Advanced alternative: virtual HID

A virtual HID driver could provide a more controlled device-routing
architecture, but it increases engineering, signing, installation,
compatibility, and security requirements. It should be considered only
after the MVP and a formal driver feasibility review.

## 7.3 Android input strategy

Android is the other major feasibility constraint.

### Strategy A: ADB over Wi-Fi (prototype)

Use Android Debug Bridge over Wireless Debugging to send controlled test
actions from the Windows development machine.

Advantages:

-   Fast way to validate the local connection and basic event mapping.
-   No custom Android input driver needed for the prototype.
-   Useful for scripted taps, swipes, and selected key events.

Disadvantages:

-   Requires Developer Options and Wireless Debugging setup.
-   Pairing and debugging permissions are not suitable as a normal
    consumer onboarding experience.
-   ADB is a developer tool, not the intended production transport.
-   It may not provide the exact mouse cursor, hover, button, or
    modifier behavior expected from a native mouse.
-   Android version and OEM behavior must be tested.

**Decision:** Use only for Phase 0 and internal testing.

### Strategy B: Android Accessibility Service

An Accessibility Service can support certain system-wide accessibility
interactions, including dispatching gestures when the user enables the
service.

Advantages:

-   Can support taps, swipes, and other supported gestures.
-   Does not require root.
-   Can be distributed as a normal Android application, subject to
    platform policies and disclosure requirements.

Limitations:

-   It is not a general-purpose replacement for Android's input driver.
-   Gesture injection is not identical to native mouse movement and
    keyboard input.
-   It may not provide full hover, pointer, scroll, or arbitrary
    key-event semantics.
-   The user must explicitly enable the service.
-   Google Play policy and accessibility-use declarations must be
    reviewed if distributed through Play.

**Decision:** Evaluate for MVP pointer gestures, with explicit
capability reporting.

### Strategy C: Custom input method (IME)

A custom Android keyboard can provide a route for text entry when the
user selects it as the active input method.

Advantages:

-   A supported Android keyboard extension point.
-   Useful for typing text into fields.
-   Can translate a defined set of keyboard input into text and editing
    actions.

Limitations:

-   An IME is not a universal system-level keyboard event injector.
-   It does not automatically provide arbitrary shortcuts or all
    hardware-key semantics.
-   It may not be active on every secure or special system surface.

**Decision:** Evaluate as a text-entry component, not as a complete
keyboard-routing solution.

### Strategy D: Bluetooth HID / native input

A true HID approach could make the phone receive input as though a
Bluetooth keyboard/mouse were connected.

However, the proposed setup requires the **laptop to act as the
Bluetooth HID peripheral**. Standard Windows application APIs do not
guarantee this role on ordinary laptop Bluetooth adapters. Support
depends on hardware, Windows stack, drivers, and implementation.

**Decision:** Treat as an advanced feasibility spike. Do not make it the
MVP's only architecture.

## 7.4 Transport choice

### Recommended first transport: local Wi-Fi

The phone hotspot can provide a local network. Internet access is not
required for the two devices to communicate, provided the hotspot
permits local device-to-device traffic.

Potential issues:

-   Some hotspot implementations isolate connected clients.
-   The laptop may switch networks.
-   Android may change its local IP address.
-   Battery optimization may suspend the companion app.
-   Firewall rules may block inbound connections.

Recommended behavior:

1.  Pair devices.
2.  Discover or configure the Android endpoint.
3.  Authenticate the connection.
4.  Exchange heartbeat messages.
5.  Reconnect after temporary network loss.
6.  Never replay queued input after reconnect.

### Bluetooth transport

Bluetooth can be considered for discovery or a future transport, but
Bluetooth data transport does not itself solve Android input injection.
Bluetooth HID is a separate role/profile problem.

## 7.5 State machine

The routing state must be explicit and centrally managed.

``` text
                  ┌────────────────┐
                  │   LAPTOP       │
                  │ keyboard: PC   │
                  │ mouse: PC      │
                  └───────┬────────┘
                          │ Toggle, phone connected
                          ▼
                  ┌────────────────┐
                  │ PHONE_BOTH     │
                  │ keyboard: phone│
                  │ mouse: phone   │
                  └───────┬────────┘
                          │ Toggle
                          ▼
                  ┌────────────────┐
                  │   LAPTOP       │
                  └────────────────┘

Additional states:
- PHONE_KEYBOARD
- PHONE_MOUSE
- PAUSED
- CONNECTING
- ERROR_SAFE
```

### State definitions

  State            Keyboard destination   Mouse destination
  ---------------- ---------------------- -------------------
  LAPTOP           Windows                Windows
  PHONE_BOTH       Android                Android
  PHONE_KEYBOARD   Android                Windows
  PHONE_MOUSE      Windows                Android
  PAUSED           Windows                Windows
  CONNECTING       Windows                Windows
  ERROR_SAFE       Windows                Windows

**Invariant:** No state should intentionally suppress a physical
device's local input unless the corresponding remote route is active and
considered healthy.

### Transition rules

-   Startup → LAPTOP.
-   Phone connection established → remain LAPTOP until user switches.
-   Toggle from LAPTOP → selected Phone mode, only if the required phone
    capability is ready.
-   Toggle from any Phone mode → LAPTOP.
-   Emergency shortcut → LAPTOP from every state.
-   Disconnect → ERROR_SAFE, then LAPTOP.
-   Hook failure → ERROR_SAFE.
-   User pauses → PAUSED.
-   Resume → LAPTOP unless the user explicitly switches again.

## 7.6 Event lifecycle

For each input event:

1.  Windows receives the physical event.
2.  InputBridge checks the active routing state.
3.  If the device is routed to Windows, allow normal local behavior.
4.  If the device is routed to Phone and the remote route is healthy,
    translate the event.
5.  Place it into a bounded queue.
6.  Send it to the authenticated Android session.
7.  Android validates session, sequence, type, and capability.
8.  The Android adapter executes the supported action.
9.  The receiver updates health/acknowledgement state.

Do not block a Windows hook callback while waiting for Android or
network acknowledgement.

## 7.7 Reliability and safety design

-   Laptop mode is the default.
-   A phone connection is required before Phone mode can activate.
-   Heartbeats detect dead sessions.
-   A bounded queue prevents memory growth.
-   Stale events are discarded after disconnect.
-   Pressed keys and buttons are released when the session ends, where
    supported.
-   Emergency return is local and must not depend on network
    availability.
-   If the app crashes, the operating system should regain ordinary
    input behavior as far as the selected interception method permits.
-   Do not run the input-routing engine inside the UI thread.
-   Do not require administrator privileges unless a later, separately
    reviewed driver implementation requires them.

------------------------------------------------------------------------

# 8. Security and privacy requirements

## 8.1 Threat model

Potential threats:

-   An unknown device connects and sends input.
-   Another device on the same hotspot attempts to control the phone.
-   A malicious local process connects to the listener.
-   Pairing credentials are exposed.
-   Input events are accidentally written to logs.
-   A stale session continues to send events after disconnect.

## 8.2 Required controls

1.  Explicit pairing approval on Android.
2.  Per-device identity and revocation.
3.  Authenticated session establishment.
4.  Encrypted transport for production.
5.  Random session identifiers and replay protection.
6.  Sequence validation.
7.  Message-size and event-rate limits.
8.  No cloud relay.
9.  No keystroke-content logging.
10. Clear disconnect and revoke controls.
11. Minimal Android permissions.
12. Explain why Accessibility permission is needed before asking the
    user to enable it.

## 8.3 Privacy principles

InputBridge handles sensitive user input. The product must:

-   Process input only while the user has deliberately enabled Phone
    mode.
-   Never store typed content.
-   Never collect passwords.
-   Never upload input events to a server.
-   Never enable hidden remote control.
-   Display a persistent or easily accessible indication when Phone mode
    is active.
-   Provide an immediate stop mechanism.

------------------------------------------------------------------------

# 9. Non-functional requirements

  -----------------------------------------------------------------------
  Category                            Requirement
  ----------------------------------- -----------------------------------
  Performance                         Local shortcut transition target
                                      under 150 ms

  Reliability                         Fail closed to Laptop mode when the
                                      phone route becomes unhealthy

  Availability                        Windows app can run in the system
                                      tray

  Security                            Only paired devices may establish a
                                      control session

  Privacy                             No typed-content logging

  Maintainability                     Input adapters separated from
                                      transport and UI

  Portability                         Android capability adapter isolates
                                      OEM-specific differences

  Usability                           One shortcut to switch; one
                                      emergency shortcut to recover

  Compatibility                       Test on Windows 11 and the target
                                      Vivo Android device

  Resource use                        Low idle CPU and memory; bounded
                                      queues

  Accessibility                       Settings usable with keyboard and
                                      screen reader
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 10. Proposed technology stack

This is a recommendation, not a fixed requirement. The proof of concept
should validate the stack before committing to it.

## 10.1 Windows application

**Recommended:** C#/.NET for the Windows tray application and
orchestration, with a small native component only if required for input
capture/interception.

Possible components:

-   C# / .NET 8 or later supported LTS version available at
    implementation time.
-   WPF or WinUI for settings UI.
-   Windows APIs for global shortcut and input integration.
-   Raw Input for device observation and identification.
-   Low-level hooks only for the tested suppression use case.
-   `ClientWebSocket` or a TLS TCP client for transport.
-   JSON or a compact versioned binary protocol.
-   Windows notification and system-tray integration.

Python can be useful for a quick prototype, but it is not the preferred
foundation for a robust low-level Windows input-routing product.

## 10.2 Android application

**Recommended:** Kotlin.

Possible components:

-   Android Studio.
-   Kotlin.
-   Android foreground service where appropriate and permitted.
-   Accessibility Service for supported gestures.
-   Input Method Service for optional text-entry support.
-   Network security configuration.
-   Pairing and diagnostics UI.

## 10.3 Protocol

-   WebSocket over TLS for a straightforward event stream.
-   JSON during early development for inspectability.
-   Consider a compact binary protocol only if profiling shows it is
    necessary.
-   Version every message and capability.

## 10.4 Development tools

-   Visual Studio / Rider for Windows.
-   Android Studio for Android.
-   Git and GitHub.
-   Wireshark for local network debugging.
-   Windows Event Viewer and structured application logs.
-   Android Logcat.
-   Automated unit and integration tests.

------------------------------------------------------------------------

# 11. API and protocol specification

## 11.1 Message types

  -----------------------------------------------------------------------
  Message                 Direction               Purpose
  ----------------------- ----------------------- -----------------------
  `hello`                 Both                    Protocol and app
                                                  version negotiation

  `pair_request`          Windows → Android       Request pairing

  `pair_approval`         Android → Windows       Approve or reject

  `authenticate`          Both                    Establish trusted
                                                  session

  `capabilities`          Android → Windows       Report supported input
                                                  types

  `mode`                  Windows → Android       Notify current routing
                                                  mode

  `input`                 Windows → Android       Carry a supported input
                                                  event

  `ack`                   Android → Windows       Acknowledge
                                                  receipt/processing

  `heartbeat`             Both                    Keep session health
                                                  known

  `release_all`           Windows → Android       Release pressed
                                                  keys/buttons if
                                                  supported

  `disconnect`            Both                    End session

  `error`                 Both                    Report a protocol or
                                                  capability error
  -----------------------------------------------------------------------

## 11.2 Capability negotiation

Android should report capabilities rather than allowing Windows to
assume all events are supported.

Example:

``` json
{
  "protocolVersion": 1,
  "type": "capabilities",
  "capabilities": {
    "keyboardText": true,
    "keyEvents": false,
    "pointerTap": true,
    "pointerSwipe": true,
    "pointerMove": false,
    "mouseButtons": false,
    "scroll": false
  }
}
```

The values above are illustrative. The Android app must report actual
capabilities of its installed adapter and permissions.

## 11.3 Input event types

Proposed event vocabulary:

-   `key_down`
-   `key_up`
-   `text_commit`
-   `pointer_move`
-   `pointer_down`
-   `pointer_up`
-   `pointer_scroll`
-   `release_all`

Do not send an event type that the receiver has not advertised as
supported.

------------------------------------------------------------------------

# 12. User interface specification

## 12.1 Windows main window

Suggested layout:

``` text
┌─────────────────────────────────────────────┐
│ InputBridge                                 │
├─────────────────────────────────────────────┤
│ Status: CONNECTED — Vivo phone              │
│                                             │
│ Current mode: LAPTOP                        │
│                                             │
│ [ Switch to Phone ]  [ Return to Laptop ]   │
│                                             │
│ Phone routing                               │
│ ( ) Keyboard + Mouse                        │
│ ( ) Keyboard only                           │
│ ( ) Mouse only                              │
│                                             │
│ Shortcut: Shift + Caps Lock                │
│ Emergency: Ctrl + Alt + F12                │
│                                             │
│ [ Settings ] [ Diagnostics ] [ Disconnect ]│
└─────────────────────────────────────────────┘
```

## 12.2 System-tray states

-   Laptop mode: neutral icon.
-   Phone mode: phone indicator.
-   Connecting: animated or clearly labeled status.
-   Error: warning indicator.

Do not rely only on color; include text or an accessible status label.

## 12.3 Android screens

1.  Welcome and explanation.
2.  Pairing approval.
3.  Connection status.
4.  Required permissions and capability status.
5.  Disconnect/revoke.
6.  Diagnostics.

------------------------------------------------------------------------

# 13. Detailed acceptance criteria

## AC-01: Startup safety

**Given** InputBridge has just started,\
**When** its services initialize,\
**Then** the state is Laptop mode and no input is forwarded to Android.

## AC-02: Shortcut toggles

**Given** the phone is paired and connected,\
**When** the user presses the configured shortcut once,\
**Then** the selected Phone mode becomes active exactly once.

## AC-03: Toggle back

**Given** Phone mode is active,\
**When** the user presses the configured shortcut again,\
**Then** all devices return to Windows.

## AC-04: Keyboard-only

**Given** Keyboard-only mode is selected,\
**When** the user types,\
**Then** supported keyboard events are sent to Android while mouse input
remains local to Windows.

## AC-05: Mouse-only

**Given** Mouse-only mode is selected,\
**When** the user moves/clicks the mouse,\
**Then** supported mouse events are sent to Android while keyboard input
remains local to Windows.

## AC-06: Phone unavailable

**Given** the phone is disconnected,\
**When** the user requests Phone mode,\
**Then** the app stays in Laptop mode and explains that the phone is
unavailable.

## AC-07: Disconnect while routing

**Given** Phone mode is active,\
**When** the connection is lost,\
**Then** forwarding stops, stale events are discarded, and the app
returns to safe local routing.

## AC-08: Emergency shortcut

**Given** any Phone mode is active,\
**When** the emergency shortcut is pressed,\
**Then** the app immediately requests Laptop mode without depending on
the phone.

## AC-09: Unknown device

**Given** an unpaired device attempts to connect,\
**When** it requests a session,\
**Then** the request is rejected until the user explicitly approves
pairing.

## AC-10: Privacy

**Given** a user types text,\
**When** diagnostics are written,\
**Then** the typed text and key content are not recorded.

------------------------------------------------------------------------

# 14. Testing strategy

## 14.1 Unit tests

-   Shortcut parsing and validation.
-   Modifier-key state tracking.
-   Routing state transitions.
-   Duplicate shortcut suppression.
-   Event serialization/deserialization.
-   Sequence-number validation.
-   Capability negotiation.
-   Timeout and heartbeat logic.
-   Queue overflow behavior.
-   Key/button release cleanup.

## 14.2 Windows integration tests

-   Built-in keyboard.
-   USB keyboard.
-   Wireless keyboard.
-   Wireless mouse with USB dongle.
-   Keyboard and mouse connected simultaneously.
-   Multiple keyboards/mice, if device selection is implemented.
-   Different keyboard layouts.
-   Caps Lock and Num Lock behavior.
-   Sleep/resume.
-   App crash and restart.
-   Normal and elevated applications.
-   Hook timeout and failure.
-   Emergency shortcut under network loss.

## 14.3 Android integration tests

-   Target Vivo phone.
-   Android 15.
-   Screen on/off.
-   Portrait and landscape.
-   Different display sizes and scaling.
-   Accessibility permission granted/denied.
-   IME selected/not selected.
-   Battery optimization enabled/disabled.
-   App backgrounded.
-   Wi-Fi hotspot toggled.
-   Phone locked/unlocked.
-   Incoming call or system overlay.
-   Supported and unsupported event types.

## 14.4 Network tests

-   Same phone hotspot.
-   Same Wi-Fi router.
-   Temporary Wi-Fi interruption.
-   IP address change.
-   Laptop sleep/resume.
-   Phone app process killed.
-   High event rate.
-   Malformed packet.
-   Duplicate packet.
-   Delayed packet.
-   Unknown client connection.

## 14.5 Safety tests

These are release blockers:

-   Disconnect never leaves Windows input intentionally suppressed.
-   Emergency shortcut is never forwarded as an ordinary phone key.
-   A stuck modifier is released or the local route is restored.
-   App shutdown restores normal local input behavior.
-   No stale input is replayed after reconnection.
-   The user can recover without touching the phone.

------------------------------------------------------------------------

# 15. Risks and mitigations

  -----------------------------------------------------------------------
  Risk                    Severity                Mitigation
  ----------------------- ----------------------- -----------------------
  Windows cannot safely   High                    Phase 0 proof; document
  suppress all physical                           supported contexts;
  input                                           investigate driver only
                                                  if necessary

  Android cannot inject   High                    Capability-based
  arbitrary keys globally                         design; ADB prototype;
                                                  Accessibility/IME
                                                  evaluation

  Laptop Bluetooth        High                    Do not assume Bluetooth
  adapter cannot act as                           HID; run a hardware/OS
  HID peripheral                                  feasibility spike

  Hotspot blocks local    Medium                  Test target phone
  client traffic                                  hotspot; offer
                                                  same-Wi-Fi fallback

  Hook crashes or times   High                    Minimal callback;
  out                                             watchdog; safe fallback

  Phone battery           Medium                  Explain supported
  optimization kills                              background
  service                                         configuration;
                                                  reconnect

  Input lag               Medium                  Local transport,
                                                  bounded queues,
                                                  coalesced pointer
                                                  movement

  Accidental input loss   High                    Default Laptop mode,
                                                  emergency shortcut,
                                                  disconnect fallback

  Security issue on local High                    Pairing,
  network                                         authentication,
                                                  encryption, rate
                                                  limiting

  OEM-specific Android    Medium                  Capability reporting
  behavior                                        and real-device test
                                                  matrix
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 16. Project plan and milestones

A suggested plan for one developer. Actual duration depends heavily on
the feasibility findings.

  -----------------------------------------------------------------------------------------
  Milestone               Work                                      Exit deliverable
  ----------------------- ----------------------------------------- -----------------------
  M0 --- Research         Validate Windows hooks, Android input     Feasibility report
                          options, hotspot connectivity             

  M1 --- Windows shell    Tray app, settings, shortcut recorder     Working Windows shell

  M2 --- Android shell    Pairing UI, connection service, status    Working Android
                                                                    companion

  M3 --- Network          Authenticated local session, heartbeat,   Stable two-device
                          reconnect                                 connection

  M4 --- State engine     Laptop/Phone/Both/Keyboard/Mouse/Paused   Tested routing state
                          states                                    machine

  M5 --- Input prototype  ADB or selected Android adapter           Demonstrated supported
                                                                    actions

  M6 --- Safety           Emergency shortcut, disconnect fallback,  Safety test pass
                          cleanup                                   

  M7 --- MVP polish       Installer, onboarding, diagnostics,       Internal MVP
                          documentation                             

  M8 --- Advanced         Bluetooth HID / virtual HID investigation Go/no-go report
  feasibility                                                       
  -----------------------------------------------------------------------------------------

**Important:** Do not start by building a large UI. The highest-risk
work is Windows input suppression and Android input injection. Prove
those first.

------------------------------------------------------------------------

# 17. Repository structure proposal

A possible monorepo:

``` text
inputbridge/
├── README.md
├── docs/
│   ├── PRD.md
│   ├── SRS.md
│   ├── TRD.md
│   ├── SECURITY.md
│   ├── TEST_PLAN.md
│   └── ADR/
│       ├── 0001-local-wifi-transport.md
│       ├── 0002-android-input-strategy.md
│       └── 0003-windows-input-capture.md
│
├── windows/
│   ├── InputBridge.sln
│   └── src/
│       ├── InputBridge.App/
│       ├── InputBridge.Core/
│       ├── InputBridge.Input/
│       ├── InputBridge.Transport/
│       ├── InputBridge.Pairing/
│       └── InputBridge.Tests/
│
├── android/
│   ├── settings.gradle.kts
│   └── app/
│       └── src/
│           ├── main/
│           └── test/
│
├── protocol/
│   ├── messages/
│   ├── schemas/
│   └── README.md
│
└── scripts/
    └── dev-setup/
```

## 17.1 Module boundaries

-   `Core`: state machine, settings models, event abstractions.
-   `Input`: Windows capture and suppression adapters.
-   `Transport`: local authenticated connection.
-   `Pairing`: device trust and session lifecycle.
-   `App`: tray UI, settings, notifications.
-   Android `connection`: socket/session management.
-   Android `input`: capability interfaces and platform-specific
    adapters.

------------------------------------------------------------------------

# 18. Suggested development backlog

## Epic A --- Windows foundation

-   [ ] Create Windows application project.
-   [ ] Add system-tray icon.
-   [ ] Add Laptop/Phone/Paused state model.
-   [ ] Add shortcut recorder.
-   [ ] Detect global shortcut.
-   [ ] Prevent key-repeat from toggling multiple times.
-   [ ] Add emergency shortcut.
-   [ ] Add structured, privacy-safe logs.

## Epic B --- Android foundation

-   [ ] Create Kotlin Android app.
-   [ ] Add onboarding screen.
-   [ ] Add pairing approval screen.
-   [ ] Add connection status.
-   [ ] Add capability report.
-   [ ] Add disconnect/revoke action.

## Epic C --- Network protocol

-   [ ] Define protocol version.
-   [ ] Implement local connection.
-   [ ] Implement pairing.
-   [ ] Implement authenticated session.
-   [ ] Implement heartbeat.
-   [ ] Implement reconnect.
-   [ ] Implement sequence validation.
-   [ ] Implement stale-event discard.

## Epic D --- Input adapters

-   [ ] Prototype keyboard capture.
-   [ ] Prototype mouse capture.
-   [ ] Test physical device identification.
-   [ ] Test local input suppression.
-   [ ] Prototype Android tap/swipe using ADB.
-   [ ] Evaluate Accessibility Service.
-   [ ] Evaluate optional IME.
-   [ ] Define capability matrix.
-   [ ] Implement key/button cleanup.

## Epic E --- Safety and release

-   [ ] Implement safe fallback.
-   [ ] Test app crash behavior.
-   [ ] Test phone disconnect behavior.
-   [ ] Test emergency shortcut.
-   [ ] Test Windows sleep/resume.
-   [ ] Test Android background behavior.
-   [ ] Complete privacy review.
-   [ ] Create installer and setup guide.

------------------------------------------------------------------------

# 19. Open technical decisions

These decisions must be resolved through prototypes rather than
assumptions.

  -----------------------------------------------------------------------
  Decision                Options                 Recommended next step
  ----------------------- ----------------------- -----------------------
  Windows language        C#, C++, Python         Start with C#
                                                  orchestration; native
                                                  code only where
                                                  necessary

  Windows input capture   Raw Input, low-level    Prototype Raw Input +
                          hooks, driver           hooks; document limits

  Android input           ADB, Accessibility,     ADB for prototype;
                          IME, HID                Accessibility/IME
                                                  feasibility for MVP

  Transport               Wi-Fi TCP, WebSocket,   Local WebSocket/TLS
                          Bluetooth               

  Pairing                 PIN, QR, approval code  One-time approval code
                                                  plus authenticated key

  Mouse behavior          Native pointer,         Prove capabilities on
                          tap/swipe mapping       the actual phone

  Startup behavior        Manual, launch at login Manual first; optional
                                                  startup later

  Distribution            Personal sideload, Play Sideload internal MVP;
                          Store                   review policy before
                                                  public distribution
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 20. Recommended implementation decision

For the first working version, use this architecture:

``` text
Windows 11
  C#/.NET tray application
  ├── Global shortcut manager
  ├── Routing state machine
  ├── Keyboard/mouse capture adapters
  ├── Safe local-input suppression experiment
  └── Authenticated WebSocket client
             │
             │ Phone hotspot / local Wi-Fi
             ▼
Android phone
  Kotlin companion application
  ├── Pairing and connection
  ├── Capability reporting
  ├── ADB-based prototype adapter (development only)
  ├── Accessibility gesture adapter (MVP candidate)
  └── Optional IME for text-entry support
```

### Why this is the recommended first step

-   It works with the user's existing laptop, USB mouse receiver, and
    Android phone without requiring a second physical keyboard.
-   It does not depend on internet access.
-   It validates the shortcut and routing experience early.
-   It keeps the Windows app independent of the Android input
    implementation.
-   It exposes the difficult platform limitations before substantial
    development effort is spent.

### What must not be promised yet

The first prototype should **not** be described as a complete
replacement for a Bluetooth keyboard/mouse. In particular, unrestricted
key injection, native mouse cursor movement, hover, scroll, all mouse
buttons, secure-screen operation, and universal suppression of local
Windows input are not guaranteed by the proposed ADB/Accessibility
architecture.

A successful feasibility spike should decide whether the MVP can meet
the exact desired behavior or whether a native HID/driver approach is
necessary.

------------------------------------------------------------------------

# 21. Definition of done for the first prototype

The first prototype is complete when:

1.  The Windows app runs in the system tray.
2.  The user can configure a shortcut.
3.  The shortcut changes the routing state exactly once per press.
4.  The Android app pairs with the Windows app over the phone hotspot.
5.  The Android app reports its actual supported input capabilities.
6.  At least one supported phone action can be triggered from the
    Windows side.
7.  The emergency shortcut returns the app to Laptop mode.
8.  Disconnecting the phone stops forwarding and returns the app to a
    safe state.
9.  The app does not store typed content.
10. A test report documents the exact limitations on the target Windows
    laptop and Vivo phone.

------------------------------------------------------------------------

# 22. References for engineering research

Use official documentation as the source of truth while implementing:

-   Microsoft Raw Input:
    https://learn.microsoft.com/windows/win32/inputdev/raw-input
-   Microsoft LowLevelKeyboardProc:
    https://learn.microsoft.com/windows/win32/winmsg/lowlevelkeyboardproc
-   Microsoft LowLevelMouseProc:
    https://learn.microsoft.com/windows/win32/winmsg/lowlevelmouseproc
-   Microsoft RegisterHotKey:
    https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-registerhotkey
-   Android AccessibilityService:
    https://developer.android.com/reference/android/accessibilityservice/AccessibilityService
-   Android dispatchGesture:
    https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#dispatchGesture(android.accessibilityservice.GestureDescription,android.accessibilityservice.AccessibilityService.GestureResultCallback,android.os.Handler)
-   Android InputMethodService:
    https://developer.android.com/reference/android/inputmethodservice/InputMethodService
-   Android Wireless Debugging / ADB:
    https://developer.android.com/tools/adb
-   Android foreground services:
    https://developer.android.com/develop/background-work/services/foreground-services

Check the current documentation and platform policies before
implementation because Windows and Android APIs and distribution
requirements can change.

------------------------------------------------------------------------

# 23. Final product principle

**InputBridge must always prioritize recoverability.**

The user should never be trapped in Phone mode because a phone
disconnected, a network failed, or an application crashed. Laptop mode
is the default, the emergency shortcut is local, and unsupported Android
input types must be reported honestly.

The core product promise is simple:

**One keyboard. One mouse. One shortcut. Switch control between laptop
and phone --- safely and transparently.**
