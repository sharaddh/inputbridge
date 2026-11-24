# InputBridge --- Product Quality, UX & Launch Readiness Review

**Repository:** https://github.com/sharaddh/inputbridge\
**Review date:** 22 November 2026\
**Review type:** Public-repository static review + user-reported device
testing\
**Status:** Functional MVP; not yet launch-ready

------------------------------------------------------------------------

## 1. Executive assessment

InputBridge has a meaningful working foundation: QR pairing, Windows TCP
hosting, Android companion connectivity, routing modes, low-level
Windows hooks, an Android Accessibility Service, an IME, and a visual
cursor overlay.

The main user-reported problems are: - Android cursor movement feels
laggy. - Cursor appears flickery/glitchy. - Visible cursor tip does not
line up with the actual pointer/click point. - Windows and Android UI
feel like engineering tools rather than a polished product. - The
product needs deeper personalization and customization before public
release.

The repository gives concrete leads. The Windows controller currently
sets `MOVE_SEND_INTERVAL = 1.0 / 30.0`, capping pointer forwarding at
about 30 updates/second. The Android service posts cursor work to the
main thread and updates a `WindowManager` overlay rather than rendering
against the display frame clock. Windows coordinates are normalized
against the Windows display, then independently mapped into Android
screen dimensions and status/navigation bar areas. The overlay is
positioned by its top-left origin, while the cursor's active hotspot is
not an explicit configurable anchor.

**Overall recommendation:** Do not add a large number of new features
yet. First fix pointer latency and coordinate accuracy, then redesign
the core UI, add meaningful customization, and complete security and
release hardening.

### Launch-readiness scorecard

  ------------------------------------------------------------------------------
  Area                  Assessment                                      Priority
  --------------------- --------------------------- ----------------------------
  Core concept          Clear and useful                                Maintain

  QR pairing            Good MVP foundation                                   P2

  Routing modes         Good MVP foundation                                   P1

  Pointer smoothness    User reports lag; code has                            P0
                        30 Hz cap                   

  Cursor hotspot        User reports offset;                                  P0
                        coordinate spaces need      
                        validation                  

  Android input         Accessibility gestures, not                        P0/P1
  semantics             native pointer              

  Windows UI            Functional, prototype-like                            P1

  Android UI            Functional, setup-oriented                            P1

  Customization         Limited                                               P1

  Security              HMAC                             P0 before public launch
                        integrity/authentication,   
                        no TLS per README           

  Signing/package       Evaluation certificate only             P0 before public
                                                                    distribution

  Device QA             Limited device-level smoke                            P0
                        testing documented          
  ------------------------------------------------------------------------------

## 2. Scope and limitations

This is a static review of the public repository, not a runtime test. I
reviewed the README, build-status document, Windows input
capture/controller/UI, Android activity/layout, and Android cursor
service. I did not install the APK or run the Windows build on the
target Vivo phone and laptop, so the reported symptoms are treated as
user-observed defects correlated with plausible code-level causes---not
as independently measured results.

Files reviewed: - `README.md`, `FINAL_BUILD_STATUS.md` -
`windows/src/inputbridge/app.py` -
`windows/src/inputbridge/controller.py` -
`windows/src/inputbridge/input_capture.py` -
`android/.../MainActivity.kt` -
`android/.../InputAccessibilityService.kt` -
`android/.../res/layout/activity_main.xml`

## 3. Existing strengths to preserve

-   QR pairing avoids manual IP and code entry.
-   One-time pairing token and HMAC-signed messages are implemented.
-   Laptop, Both, Keyboard-only, Mouse-only, Pause, and emergency return
    modes exist.
-   Windows hook callbacks are kept short; network work happens on a
    worker thread.
-   Bounded queue and watchdog are present.
-   Disconnect handling attempts to restore local laptop input.
-   Android reports input capabilities.
-   Cursor and UI update coalescing have already received a performance
    pass.
-   README documents limitations rather than claiming full native HID
    behavior.

These are useful foundations. Improve them incrementally instead of
rewriting the whole product without measurements.

------------------------------------------------------------------------

# PART A --- P0 POINTER EXPERIENCE

## 4. Fix cursor lag, stutter and flicker

### 4.1 Likely cause: 30 Hz forwarding limit

`windows/src/inputbridge/controller.py` defines:

``` python
MOVE_SEND_INTERVAL = 1.0 / 30.0
```

This caps movement forwarding at approximately 30 updates per second
before network jitter, Android main-thread scheduling, overlay layout
and display presentation. A phone running at 60/90/120 Hz can visibly
show stepped pointer movement at a 30 Hz input cadence.

### Required changes

-   Replace the fixed 30 Hz sender with a latest-value, paced sender.
-   Start with a 60 Hz target on a stable 60 Hz phone.
-   Support higher rates only when the phone refresh rate and measured
    transport latency justify them.
-   Keep only the newest pending absolute pointer position; do not queue
    a long history of movement.
-   Do not send unchanged coordinates.
-   Preserve button-down, button-up and wheel ordering; these must not
    be dropped when movement is coalesced.
-   Prioritize click/button transitions over pointer movement.
-   Never replay stale movement after a network delay or reconnect.
-   Avoid aggressive smoothing by default: it can make the pointer look
    smooth but trail behind the physical mouse.

**Acceptance criteria** - At least 55 visible cursor updates/second on a
stable 60 Hz setup. - No growing pointer queue during fast movement. -
No visible multi-step jumps under normal hotspot conditions. - Cursor
follows the latest physical mouse position without a long trail. -
Button transitions remain reliable.

### 4.2 Render on Android display frames

The Android service coalesces movement with a `Handler` runnable and
updates the overlay using `WindowManager.updateViewLayout`. Coalescing
is good, but the cursor is not synchronized with display presentation.

Recommended pipeline:

1.  Network thread receives coordinates and writes the latest point to a
    thread-safe holder.
2.  Schedule at most one frame callback using `Choreographer`.
3.  On the next display frame, read the newest point.
4.  Update the overlay once.
5.  If newer input arrives, use it on the next frame.
6.  Do no network work, logging, metric lookup or expensive allocation
    in the frame callback.

Keep the cursor view and drawing path stable. Do not recreate the view
on normal movement.

**Do not add smoothing until direct tracking is correct.** If optional
smoothing is later added, provide an off/low setting and ensure it does
not introduce noticeable input lag.

### 4.3 Separate visual movement from gesture execution

The overlay cursor is visual, while clicks are dispatched using
`AccessibilityService.dispatchGesture`. These are separate mechanisms
and can disagree.

Required changes: - One shared coordinate transform must drive both
cursor placement and tap/swipe injection. - Clicks must use the latest
pointer point, not a stale pending point. - Button-down and button-up
must form a coherent interaction. - Drag must be implemented only if the
Android gesture adapter supports it reliably. - Report unsupported
interactions honestly.

------------------------------------------------------------------------

## 5. Fix cursor hotspot and coordinate alignment

### 5.1 Likely source of the offset

The Android cursor view has a fixed size and draws an arrow beginning at
`(0, 0)`. The overlay window's `params.x` and `params.y` are set from
the mapped pointer coordinate. This assumes the window's top-left is
exactly the cursor's active hotspot and that overlay coordinates match
gesture coordinates.

The current Y mapping also uses display metrics plus resource-derived
status/navigation bar heights. These may not match the actual usable
window/inset space on all Android versions, gesture navigation modes,
cutouts and OEM implementations.

### 5.2 Add an explicit hotspot model

Create a cursor configuration:

``` text
CursorStyle
  widthDp
  heightDp
  hotspotX
  hotspotY
  shape
  scale
  fillColor
  outlineColor
  outlineWidth
```

Position the overlay using:

``` text
overlayLeft = pointerScreenX - hotspotX
overlayTop  = pointerScreenY - hotspotY
```

Do not bury offsets in unexplained constants. The same
`pointerScreenX/pointerScreenY` must be used for click injection.

### 5.3 Use one coordinate-space pipeline

Define and test: - Windows physical screen coordinates. - Windows
normalized coordinates. - Android logical display coordinates. - Android
content coordinates. - Android overlay coordinates. - Android gesture
coordinates.

``` text
Windows screen point
        |
        v
Normalize against selected Windows display bounds
        |
        v
Map into Android content/display bounds
        |
        +------> Cursor hotspot placement
        |
        +------> Accessibility gesture point
```

Use current Android `WindowMetrics` and `WindowInsets` where appropriate
rather than assuming resource dimensions always describe the usable
area. Handle status bar, navigation bar (gesture and three-button
modes), display cutouts, orientation, density, display changes, edge
clamping, and Windows scaling/multiple monitors.

### 5.4 Add a calibration screen

-   Show a crosshair at a known target coordinate.
-   Show the cursor over it.
-   Let the user click the crosshair center.
-   Calculate the visual/click displacement.
-   Store device-specific correction.
-   Provide Reset calibration.

The default mapping must be correct without calibration. Calibration is
a fallback for OEM-specific differences, not a replacement for a correct
transform.

**Acceptance criteria** - Cursor arrow tip and actual click point align
within 2--3 physical display pixels at center and corners. - No
consistent vertical offset in portrait or landscape. - No drift after
rotation or display-size changes. - Cursor remains within display
bounds. - Top/bottom edge clicks map correctly. - Overlay refresh does
not cause pointer jumps.

## 6. Be honest about the Android mouse model

The current overlay is a visual cursor, not a true Android hardware
mouse pointer. Accessibility gestures do not automatically provide
native hover, pointer capture, all button semantics, wheel behavior or
reliable desktop-style drag.

### Current limitations to disclose

-   No native hover behavior.
-   No guaranteed native drag behavior.
-   Right-click is not automatically equivalent to a native context-menu
    click.
-   Middle/back buttons may map to system actions rather than normal
    mouse semantics.
-   Scroll is represented as a swipe gesture, not a native mouse wheel.
-   Some apps will not respond like desktop applications.

### Product modes

**Touch Pointer (MVP-compatible)** - Visual cursor overlay. - Tap and
swipe. - Scroll translated into gestures. - Clearly documented
compatibility limits.

**Native Mouse (advanced)** - True Android pointer semantics, hover,
button state, wheel and drag. - Requires a validated native HID or
supported platform input path. - Do not describe the current
Accessibility gesture implementation as native mouse support.

------------------------------------------------------------------------

# PART B --- PRODUCT UI AND PERSONALIZATION

## 7. Redesign the Windows application

### Current problem

The Windows app is a Tkinter panel with mode buttons, a permanently
visible QR code, connection/capability information, settings and a raw
log panel. It works as a developer control panel but exposes too many
technical concepts to a normal user.

### Proposed home screen

``` text
┌─────────────────────────────────────────────────────────────┐
│ INPUTBRIDGE                         Connected ●  Settings  │
│ Your devices, working as one.                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│       LAPTOP  ────────────────  PHONE                       │
│                                                             │
│                 PHONE CONNECTED                              │
│                                                             │
│       Current control                                        │
│       ┌─────────────────────────────────────────────┐       │
│       │  ● Laptop                                   │       │
│       │  Keyboard  → Laptop                         │       │
│       │  Mouse     → Laptop                         │       │
│       └─────────────────────────────────────────────┘       │
│                                                             │
│                 [ Switch to Phone ]                          │
│                                                             │
│       Quick routing                                          │
│       [ Both ] [ Keyboard ] [ Mouse ] [ Pause ]              │
│                                                             │
│       Shortcut  Shift + Caps Lock          [ Edit ]         │
│       Emergency Ctrl + Alt + F12            [ Edit ]         │
│       Phone: Vivo • Wi-Fi • Signal: Good                     │
│                                                             │
│       [ Device settings ] [ Diagnostics ]                    │
└─────────────────────────────────────────────────────────────┘
```

### Design principles

-   One primary action: Switch to Phone / Return to Laptop.
-   One unmistakable current-mode indicator.
-   Routing options are secondary controls.
-   Connection state is visible but not dominant.
-   QR pairing appears in first-run/disconnected states, not as the
    permanent main focus.
-   Raw logs live under Diagnostics.
-   Emergency return remains easy to find.
-   Consistent typography, spacing, icons and color tokens.
-   Light and dark themes.
-   Native Windows conventions where practical.

### Technology recommendation

Tkinter is acceptable for an internal prototype. For a launchable
Windows product, evaluate WinUI 3 or WPF with a polished design system.
Keep the existing controller and input engine behind a clean interface;
do not rewrite them just to change the UI.

### Windows settings

**General:** launch at startup, start minimized, switch notifications,
sound, start in Laptop mode.\
**Shortcuts:** toggle, emergency, pause, conflict detection, restore
defaults.\
**Devices:** phone nickname, re-pair/revoke, auto-connect.\
**Input:** default routing, pointer rate (only supported values), mouse
sensitivity, scroll sensitivity/direction, button mapping.\
**Appearance:** System/Light/Dark, accent color, compact/comfortable
density, tray icon.\
**Advanced:** diagnostics, log export, connection timeout, developer
mode.

## 8. Redesign the Android companion

### Proposed home screen

``` text
┌────────────────────────────────────┐
│ InputBridge                    ⚙   │
│                                    │
│         ● Connected                │
│         Sharad's Laptop             │
│                                    │
│  ┌──────────────────────────────┐  │
│  │       INPUT STATUS           │  │
│  │   Keyboard       Ready       │  │
│  │   Pointer        Ready       │  │
│  │   Accessibility  Enabled     │  │
│  └──────────────────────────────┘  │
│                                    │
│  Laptop is controlling this phone  │
│                                    │
│  [ Disconnect ]                    │
│                                    │
│  Cursor appearance                 │
│  [ Preview ] [ Customize ]         │
│                                    │
│  Setup checklist                   │
│  ✓ Pair laptop                     │
│  ✓ Accessibility                   │
│  ○ Keyboard setup                  │
│                                    │
│  [ Help & diagnostics ]            │
└────────────────────────────────────┘
```

Requirements: - Material 3 components and dynamic color where
available. - Proper app bar and consistent navigation. - Clear
connection chips and plain-language capability labels. - Guided
permission checklist instead of unexplained technical buttons. - Explain
why Accessibility and IME permissions are needed. - Hide raw logs under
Diagnostics. - Add cursor preview/customization. - Support dark mode,
larger text and responsive layouts. - Clear disconnect and revoke
actions.

## 9. Make it personal and customizable

Personalization should cover the workflow, not just an accent color.

### Device identity

-   Rename laptop and phone.
-   Show the paired device name on both sides.
-   Remember preferred routing mode.
-   Optional custom device icon/avatar.
-   Design for multiple trusted devices later, even if the MVP supports
    one phone.

### Shortcuts

-   Record any valid shortcut.
-   Live key-combination preview.
-   Modifier support and conflict warning.
-   Separate Toggle, Emergency, Pause and Return-to-Laptop shortcuts.
-   Restore defaults.
-   Prevent emergency and toggle shortcuts from being identical.

### Cursor appearance

-   Shape: classic arrow, compact arrow, dot, crosshair.
-   Size: small, medium, large, custom.
-   Fill and outline colors.
-   Outline thickness and opacity.
-   Optional shadow.
-   Optional click ripple.
-   Optional pointer trail (off by default).
-   Hotspot calibration.
-   Reset to default.
-   Live preview.

Default should be crisp, high contrast and distraction-free.

### Mouse preferences

-   Pointer speed multiplier.
-   Scroll speed and direction.
-   Button mapping.
-   Click feedback.
-   Edge behavior.
-   Pointer update mode: Auto / Low latency / Battery saver.

### Appearance

-   System / Light / Dark.
-   Accent presets and custom accent.
-   Compact / Comfortable layout.
-   Reduced motion.
-   High contrast.
-   Localization-ready string resources.

### Profiles

-   Work: laptop default.
-   Phone control: both devices to phone.
-   Typing: keyboard only.
-   Navigation: mouse only.

Profiles may store routing defaults, shortcut behavior, cursor
preferences and appearance. Startup and disconnect must still return
safely to Laptop mode.

------------------------------------------------------------------------

# PART C --- ENGINEERING AND LAUNCH HARDENING

## 10. Add latency instrumentation before tuning

Do not guess whether delay is in Windows capture, queueing, network
transport, Android scheduling or overlay presentation.

Record monotonic timestamps at: 1. Windows hook capture. 2. Windows
queue enqueue. 3. Windows send. 4. Android receive. 5. Android frame
callback. 6. Android overlay update. 7. Accessibility gesture dispatch
and result.

Metrics: - Captured/sent/received pointer updates per second. -
Coalesced/dropped movement count. - Queue depth and maximum depth. -
Median/p95/p99 latency where measurable. - Capture-to-send duration. -
Receive-to-render duration. - Frame callback interval. - Gesture
dispatch success/failure. - Display refresh rate. - Screen
dimensions/insets. - Connection quality where available.

Add a simple Pointer Performance diagnostics page. Never log typed text,
key contents, secrets or pairing tokens. Show "Not available" rather
than inventing a metric.

## 11. Improve mouse event correctness

-   Preserve button-down/up ordering.
-   Handle left, right, middle, back and forward explicitly.
-   Do not silently map middle-click to Recents or right-click to Back.
-   Treat scroll delta consistently.
-   Coalesce wheel bursts without excessive gesture dispatch.
-   Define drag behavior and test it.
-   Use the latest pointer coordinate for clicks.
-   Release held button/key state after disconnect or mode switch.
-   Report unsupported actions accurately.

## 12. Improve Windows event processing

Preserve the short hook callback and worker-thread design.

-   Use a latest-value slot for pointer movement.
-   Keep key and button transitions in an ordered reliable queue.
-   Prevent pointer movement from filling the queue.
-   Prioritize button/key transitions.
-   Add queue/drop counters and explicit overflow policy.
-   Keep network writes outside hook callbacks.
-   Add clean shutdown handling.
-   Review `ShowCursor` counter handling: restore exactly the visibility
    changes made by InputBridge rather than assuming a fixed number of
    increments/decrements restores the original state.
-   Test multiple monitors and Windows display scaling.
-   Treat physical device selection as a separate feature; low-level
    hooks do not automatically provide robust per-device identity.

## 13. Security before public launch

The README says the transport has no TLS/encryption. HMAC provides
message integrity/authentication, not confidentiality. This is
acceptable only for a trusted-network evaluation MVP.

Before public distribution: - Add TLS or another reviewed
authenticated-encryption transport. - Secure pairing-key lifecycle and
rotation. - Revoke paired devices. - Store credentials using platform
secure storage. - Rate-limit connection attempts. - Validate message
types, ranges and sizes. - Reject stale timestamps and replayed
sequences. - Never log tokens, typed content or sensitive input. -
Explain trusted-network requirements. - Review Android Accessibility/IME
disclosures and distribution policies. - Publish security policy and
vulnerability contact.

## 14. Packaging and release quality

### Windows

-   Signed installer.
-   Clean uninstall.
-   Start menu shortcut.
-   Optional startup.
-   Update strategy.
-   Version display.
-   Crash diagnostics without input content.
-   No console window in normal use.
-   Settings preserved across upgrades.
-   Uninstall stops services and restores local input.

### Android

-   Production signing key managed securely.
-   Versioned release process.
-   Guided permission onboarding.
-   App icon and screenshots.
-   Privacy policy and store listing.
-   OEM compatibility testing.
-   Crash-free startup/reconnect tests.
-   Upgrade and pairing migration.

### Customer documentation

-   Supported Windows/Android versions.
-   Known limitations.
-   Setup guide with screenshots.
-   Troubleshooting.
-   Permission explanations.
-   Network requirements.
-   Uninstall/revoke instructions.
-   Checksums and release notes.

------------------------------------------------------------------------

# PART D --- ACCEPTANCE TEST PLAN

## 15. Pointer quality tests

  ID     Test                       Pass criteria
  ------ -------------------------- -------------------------------------------
  P-01   Slow horizontal movement   No visible stepping/flicker
  P-02   Fast movement              Tracks latest position without long trail
  P-03   Diagonal movement          No axis skew or jitter
  P-04   Fine movement              Stable and controllable
  P-05   Center click               Visible tip and click location align
  P-06   Four corner clicks         No offset or clipping
  P-07   Top inset                  Correct mapping
  P-08   Bottom inset               Correct mapping
  P-09   Rotate phone               Remaps without stale position
  P-10   Display size change        Metrics refresh
  P-11   Hotspot congestion         No unbounded queue
  P-12   20-minute session          No progressive lag or memory growth
  P-13   Disconnect while moving    Laptop input restored safely
  P-14   Move and click rapidly     Click uses current pointer position
  P-15   Drag test                  Matches documented capability

## 16. UI usability tests

-   A new user can pair without developer documentation.
-   Current Laptop/Phone ownership is unmistakable.
-   User can return to Laptop in one action.
-   User can find and change shortcuts.
-   User can preview and customize the cursor.
-   Permission purpose is understandable.
-   Disconnection can be diagnosed without reading raw logs.
-   Light/dark modes work.
-   UI works at different Windows scaling settings and Android font
    sizes.
-   Keyboard navigation and screen-reader labels exist.

------------------------------------------------------------------------

# PART E --- PRIORITIZED IMPLEMENTATION PLAN

## 17. Sprint 1: Pointer correctness and performance (P0)

-   [ ] Add end-to-end monotonic timestamps.
-   [ ] Add pointer counters and queue metrics.
-   [ ] Replace fixed 30 Hz sender with latest-value paced sender.
-   [ ] Target 60 Hz on a stable 60 Hz phone.
-   [ ] Use Android `Choreographer` for cursor rendering.
-   [ ] Keep only latest pointer coordinate per frame.
-   [ ] Use one coordinate transform for overlay and gestures.
-   [ ] Add explicit cursor hotspot coordinates.
-   [ ] Use current window metrics/insets.
-   [ ] Recalculate mapping on rotation/display changes.
-   [ ] Fix edge clamping using hotspot, not only overlay rectangle.
-   [ ] Add calibration diagnostics.
-   [ ] Verify center and four-corner clicks.

**Exit condition:** Pointer feels direct, movement is smooth under
normal conditions, and visible tip matches the actual click point.

## 18. Sprint 2: Interaction behavior (P0/P1)

-   [ ] Click uses latest pointer coordinate.
-   [ ] Validate button-down/up ordering.
-   [ ] Reliable release-all behavior.
-   [ ] Improve scroll delta mapping.
-   [ ] Define right/middle/back/forward mappings.
-   [ ] Define and test drag support.
-   [ ] Label current implementation Touch Pointer.
-   [ ] Do not claim native mouse behavior until proven.

## 19. Sprint 3: UI redesign (P1)

-   [ ] Windows home screen centered on one primary switch action.
-   [ ] QR pairing only in first-run/disconnected state.
-   [ ] Raw logs moved to Diagnostics.
-   [ ] Clear device and mode indicators.
-   [ ] Android home screen with setup checklist.
-   [ ] Material 3 styling and dark mode.
-   [ ] Consistent typography, spacing, icons and color tokens.
-   [ ] Accessible labels and larger text.
-   [ ] In-app help and troubleshooting.

## 20. Sprint 4: Personalization (P1)

-   [ ] Custom device names.
-   [ ] Shortcut recorder and conflict detection.
-   [ ] Separate toggle/pause/emergency shortcuts.
-   [ ] Cursor shape, size, color and outline controls.
-   [ ] Cursor live preview.
-   [ ] Hotspot calibration.
-   [ ] Mouse speed and scroll settings.
-   [ ] Light/Dark/System theme.
-   [ ] Accent color and density.
-   [ ] Named profiles.
-   [ ] Persist settings across updates.

## 21. Sprint 5: Launch hardening (P0)

-   [ ] Encrypted transport.
-   [ ] Secure credential storage and revocation.
-   [ ] Android permission disclosures.
-   [ ] Production signing and installer.
-   [ ] Clean uninstall.
-   [ ] Sleep/resume testing.
-   [ ] OEM compatibility tests.
-   [ ] Privacy/security documentation.
-   [ ] Crash/diagnostics review.
-   [ ] Public release notes and support guide.

------------------------------------------------------------------------

# PART F --- PRODUCT POSITIONING AND DEFINITION OF DONE

## 22. Product positioning

**InputBridge --- One keyboard. One mouse. Two screens.**

A lightweight companion that lets users switch their existing laptop
keyboard and mouse between Windows and Android.

Product promises: - Fast switching. - Simple QR pairing. - Clear device
status. - Customizable shortcuts. - Personal cursor and mouse
settings. - Safe return to laptop control. - Local connection without
requiring internet access.

Avoid claims until proven: - "Native Android mouse support." - "Zero
latency." - "Works with every Android app." - "Full keyboard support
everywhere." - "No permissions required." - "Secure on any Wi-Fi
network."

Use honest terms such as "Touch Pointer" for the current Accessibility
gesture implementation. Claim "low latency" only after measuring it on
supported devices.

## 23. Proposed default settings

  Setting                 Default
  ----------------------- -----------------------------
  Startup mode            Laptop
  Toggle shortcut         Shift + Caps Lock
  Emergency shortcut      Ctrl + Alt + F12
  Default phone routing   Both
  Pointer update mode     Auto, 60 Hz target
  Cursor shape            Classic arrow
  Cursor size             Medium
  Cursor fill/outline     White / dark
  Cursor trail            Off
  Click ripple            Off
  Mouse sensitivity       1.0×
  Scroll direction        User configurable
  Theme                   System
  Start minimized         Off initially
  Auto-connect            On after explicit pairing
  Diagnostics             Non-sensitive metadata only

These are proposed defaults and should be validated with real users.

## 24. Definition of launch-ready

### Pointer and input

-   Cursor is smooth and responsive on the supported test matrix.
-   Cursor tip and click coordinate are aligned.
-   Rotation and insets do not cause drift.
-   No pointer backlog accumulates.
-   Unsupported mouse behavior is disclosed.
-   Disconnect and emergency recovery always work.

### Product experience

-   First-time setup is guided.
-   Windows and Android have a coherent visual identity.
-   Current routing mode is unmistakable.
-   Shortcuts, cursor, mouse and appearance are customizable.
-   Logs are separated from normal use.
-   Dark mode and accessibility basics are supported.

### Security and distribution

-   Transport is encrypted and authenticated.
-   Pairing credentials can be revoked.
-   No input content is logged.
-   Production signing is in place.
-   Installer/uninstaller are tested.
-   Privacy and support documentation are published.

### Quality

-   Tests run on the actual target phone and representative Android
    devices.
-   Windows scaling and display configurations are tested.
-   Long-session testing shows no progressive lag or memory leak.
-   Public beta feedback channel exists.

## 25. Final recommendation

Do the work in this order:

1.  **Make the cursor accurate:** fix the coordinate transform and
    hotspot so visible arrow tip and actual click point are identical.
2.  **Make the cursor smooth:** remove the 30 Hz bottleneck, use a
    latest-value movement pipeline, and render on Android display
    frames.
3.  **Make mouse behavior honest:** distinguish the current
    Accessibility-based Touch Pointer from a future native mouse mode.
4.  **Make the app feel finished:** redesign Windows and Android around
    connection, current mode, and one primary action.
5.  **Make it personal:** add shortcut, cursor, mouse, theme,
    device-name and profile customization.
6.  **Make it safe to distribute:** encrypt transport, production-sign
    builds, test installers, and publish permission/privacy
    documentation.

**Do not spend the next development cycle adding more features. Spend it
making the pointer feel right.** If pointer movement and click accuracy
are not excellent, the product's central promise will not feel reliable,
regardless of how attractive the settings screen becomes.

------------------------------------------------------------------------

## Appendix A --- Code areas to revisit

  --------------------------------------------------------------------------------------------
  Area                    File                                         Focus
  ----------------------- -------------------------------------------- -----------------------
  Windows pointer pacing  `windows/src/inputbridge/controller.py`      `MOVE_SEND_INTERVAL`,
                                                                       pending-move policy

  Windows pointer capture `windows/src/inputbridge/input_capture.py`   Coordinate
                                                                       normalization, capture
                                                                       cadence, queue policy

  Android cursor overlay  `android/.../InputAccessibilityService.kt`   Cursor view, hotspot,
                                                                       WindowManager placement

  Android coordinate      `android/.../InputAccessibilityService.kt`   `screenX`, `screenY`,
  mapping                                                              insets and display
                                                                       bounds

  Android gesture         `android/.../InputAccessibilityService.kt`   Tap/swipe coordinate
  injection                                                            consistency and
                                                                       dispatch result

  Windows UI              `windows/src/inputbridge/app.py`             Tkinter hierarchy,
                                                                       settings, logs, mode
                                                                       controls

  Android UI              `android/.../MainActivity.kt`                Status rendering and
                                                                       setup flow

  Android layout          `android/.../res/layout/activity_main.xml`   Card hierarchy and
                                                                       visual design

  Security                `docs/SECURITY.md`, `net_server.py`,         TLS, key lifecycle,
                          `BridgeClient.kt`                            validation, storage
  --------------------------------------------------------------------------------------------

## Appendix B --- Repository observations

The README describes the current version as a QR-only functional MVP. It
documents a visual cursor overlay and Accessibility-based tap/swipe
behavior rather than native hover. It also states that transport
encryption is not yet implemented and the release certificate is for
evaluation.

The build-status document records a 30 Hz pointer movement coalescing
decision and an Android performance pass that cached cursor geometry and
coalesced UI/log updates. Those are useful improvements, but the
reported device experience calls for another measurement-led performance
pass.

**End of report.**
