# EasyRes UI Overhaul Plan

## Outcome

Turn EasyRes into a focused match-prep console where active display state, quick switching, and recovery are obvious at a glance. Preserve the existing black, graphite, neutral-white, and blurple palette. Keep resolution changes and hardware monitor changes independent in both layout and behavior.

## Product Direction

- **North star:** The Match Console.
- **Character:** Precise, tactical, fast.
- **Scene:** A competitive player checks and switches display state on a dim desktop seconds before joining a match.
- **Color strategy:** Restrained. Blurple marks selection, focus, and primary action only.
- **Anti-goals:** No RGB-heavy gamer styling, neon cyberpunk effects, ornamental dashboards, nested cards, or GPU-control-panel density.

## Information Architecture

### 1. Command Header

Keep app identity and window controls compact. Add selected display, global hotkey status, and update state as readable controls, not decorative badges. When an update is available, the update control downloads, verifies, replaces, and restarts EasyRes inside the app instead of sending users to GitHub.

### 2. Display Status

Show current resolution, refresh rate, selected monitor, and hardware monitor state in one compact status band. Use text and icon/state labels so color is never the only cue.

### 3. Resolution Browser

Make this the dominant workspace. Present every Windows-reported resolution in a compact, searchable list grouped by aspect ratio, with refresh-rate choice next to the selected mode. Put pinned/favorite modes first. One clear Apply action owns the resolution change.

### 4. Quick Toggle Setup

Keep hotkey and target together beside the resolution browser. Explain the invariant directly: switching never changes hardware monitor state. Show registration failure inline and expose the current native/stretch pairing.

### 5. Advanced Resolution Creation

Move EDID injection behind an Advanced disclosure. Use progressive fields, inline validation, detected refresh rates, and a concise risk summary before the final action. Do not describe modes as tested unless that claim is backed by device-specific evidence.

### 6. Hardware Monitors

Place hardware controls in a separate, clearly labeled section with per-device state. Toggling a monitor is always explicit. Never couple this section to resolution cards, hotkeys, or Restore Native.

### 7. Recovery Bar

Keep a persistent bottom action bar with two distinct commands: Restore Native and Restore Native + Enable Monitors. Make the latter the visually stronger warning because it changes two system states.

## Interaction Rules

- Applying a resolution changes resolution only.
- Hotkey switching changes resolution only.
- Restore Native changes resolution only.
- Monitor power state changes only through a monitor toggle or an action explicitly labeled “Enable Monitors.”
- Risky operations show consequences before execution and report success/failure near the initiating control.
- Keyboard order follows visual order; every control has visible focus and an accessible name.
- Motion communicates state in 150–250 ms and respects Windows reduced-motion settings.

## Key States

- No display detected.
- Display detected with no modes returned yet.
- Modes loading or retrying after a driver restart.
- Native mode active.
- Non-native mode active.
- Hotkey registered, unavailable, or invalid.
- Hardware monitor enabled, disabled, changing, or failed.
- Custom mode valid, invalid, duplicate, injection pending, injected, or failed.
- Resolution apply pending, accepted, failed, or reverted.
- Update available and update check failed.
- Update download pending, downloading, verified, installing, failed, or unavailable in source mode.

## Delivery Phases

### Phase 1: Foundations

Consolidate inline QSS into semantic tokens and reusable components. Add complete default, hover, focus, pressed, disabled, loading, error, and selected states. Wire reduced motion into all animations.

### Phase 2: Shell and Status

Build compact command header, display selector, status band, and persistent recovery bar. Remove decorative hero treatment and long-page dependence.

### Phase 3: Resolution Workflow

Replace preset-card sprawl with grouped/searchable modes, favorites, refresh selection, active state, and a single Apply flow. Integrate hotkey target configuration without coupling monitor state.

### Phase 4: Advanced and Hardware Controls

Move custom EDID creation into progressive disclosure. Rebuild hardware monitor controls as an isolated subsystem with explicit state feedback.

### Phase 5: Dialogs, Tray, and Copy

Align settings, onboarding, confirmation messages, error handling, update installation, and tray actions with the same component and language system. Remove unsupported safety claims and duplicated actions.

### Phase 6: Verification

Test on Windows 10 and 11 across 100%, 125%, 150%, and 200% scaling; compact laptop and large desktop layouts; keyboard-only use; reduced motion; high contrast; no-display and multi-display cases; failed hotkey registration; failed EDID/driver operations; and every monitor-state invariant.

## Acceptance Criteria

- Main switch workflow is understandable without scrolling at the default window size.
- Active display, resolution, refresh rate, and monitor state are visible together.
- All Windows-reported modes remain available; quick picks are described as common, not tested.
- Hotkey and ordinary resolution actions never enable or disable a monitor.
- Only explicitly labeled monitor actions alter hardware monitor state.
- Every interactive component has keyboard focus and non-color state cues.
- Existing palette values remain unchanged.
- Update flow installs inside the packaged app with verification, restart, and rollback messaging; source mode explains why automatic replacement is unavailable.
- No nested cards, accent side stripes, decorative gradients, glass effects, or gratuitous motion ship in the overhaul.
