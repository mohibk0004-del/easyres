---
name: EasyRes
description: A precise match-prep console for fast Windows resolution switching.
colors:
  void-black: "#000000"
  raised-black: "#0a0a0a"
  graphite: "#121212"
  graphite-hover: "#1a1a1a"
  border-subtle: "#1f1f1f"
  border-default: "#2a2a2b"
  border-hover: "#3a3a3c"
  text-primary: "#f5f5f7"
  text-secondary: "#a1a1a6"
  text-muted: "#86868b"
  signal-blurple: "#5865f2"
  signal-blurple-hover: "#4752c4"
  destructive-red: "#dc2626"
  destructive-red-hover: "#ef4444"
typography:
  display:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.2
  headline:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1.3
  title:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.5
  label:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "1.5px"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
  3xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.signal-blurple}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "10px"
  button-secondary:
    backgroundColor: "{colors.graphite-hover}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "10px"
  button-destructive:
    backgroundColor: "{colors.destructive-red}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "10px"
  input-default:
    backgroundColor: "{colors.graphite}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "6px"
  preset-card:
    backgroundColor: "{colors.graphite}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    width: "124px"
    height: "76px"
---

# Design System: EasyRes

## Overview

**Creative North Star: "The Match Console"**

EasyRes is a compact dark utility designed for a competitive player preparing a display in a dim desktop environment. Its visual system is precise, tactical, and fast: dense enough for expert control, but quiet enough that current state and the next action dominate.

The interface uses restrained color, familiar Windows desktop affordances, and a consistent Inter hierarchy. It explicitly rejects RGB-heavy gamer software, neon cyberpunk decoration, bloated GPU control panels, ornamental dashboards, and ambiguous state.

**Key Characteristics:**

- Near-black structural surfaces with subtle tonal separation.
- Blurple reserved for focus, selection, and primary action.
- Compact controls built on an 8px spacing rhythm.
- Direct copy that distinguishes resolution state from monitor state.
- Motion used only to confirm state changes.

## Colors

The palette is a near-black neutral stack with cool white text and one crisp blurple signal color.

### Primary

- **Signal Blurple** (`signal-blurple`): Primary actions, keyboard focus, active selections, and current-state emphasis.
- **Deep Signal Blurple** (`signal-blurple-hover`): Hover and pressed response for accent controls.

### Tertiary

- **Destructive Red** (`destructive-red`): Explicitly destructive or high-risk actions only.
- **Bright Destructive Red** (`destructive-red-hover`): Hover response for destructive controls.

### Neutral

- **Void Black** (`void-black`): Window foundation.
- **Raised Black** (`raised-black`): Toolbars, panels, and elevated sections.
- **Graphite** (`graphite`): Inputs, presets, and resting controls.
- **Graphite Hover** (`graphite-hover`): Interactive hover surface.
- **Primary Frost** (`text-primary`): Main copy and values.
- **Secondary Silver** (`text-secondary`): Supporting copy.
- **Muted Steel** (`text-muted`): Labels and low-priority metadata.
- **Structural Borders** (`border-subtle`, `border-default`, `border-hover`): Separation and interaction feedback.

### Named Rules

**The Signal Rule.** Blurple communicates action or state. It is never ambient decoration.

**The Existing Palette Rule.** Preserve the current black, graphite, neutral-white, blurple, and red values during the overhaul.

## Typography

**Display Font:** Inter (with Segoe UI and sans-serif fallback)  
**Body Font:** Inter (with Segoe UI and sans-serif fallback)  
**Label/Mono Font:** Inter (with Segoe UI and sans-serif fallback)

**Character:** One compact sans-serif family keeps the utility native, legible, and operational. Weight and scale establish hierarchy without introducing a decorative display voice.

### Hierarchy

- **Display** (`display`): Current resolution and singular high-priority values.
- **Headline** (`headline`): Dialog titles and major screen headings.
- **Title** (`title`): Section and component titles.
- **Body** (`body`): Controls, supporting descriptions, and messages; prose stays within 65–75 characters where practical.
- **Label** (`label`): Compact uppercase section labels with deliberate tracking.

### Named Rules

**The Data First Rule.** Resolution and refresh values receive the strongest type; explanatory copy never competes with them.

## Elevation

EasyRes uses structural elevation: near-black tonal layers and one-pixel borders establish hierarchy. A diffuse window/dialog shadow separates the frameless shell from the desktop, but internal surfaces remain flat by default.

### Shadow Vocabulary

- **Window Ambient:** The main window uses the native Windows (DWM) shadow and, on Windows 11, native rounded corners. Tray-mode dialogs keep a Qt shadow (`0 10px 30px rgba(0, 0, 0, 0.59)`).
- **Sheet Lift:** In-window sheets sit on a 40% black dim with a soft painted shadow.

### Named Rules

**The Flat Interior Rule.** Internal surfaces use tone and borders, never stacks of shadows.

## Components

Controls feel compact, precise, and immediately responsive.

### Buttons

- **Shape:** Gently rounded rectangle (`lg`).
- **Primary:** Deep Signal Blurple (`signal-blurple-hover`) fill with Primary Frost text (5.9:1). White text never sits on `signal-blurple` (4.2:1).
- **Destructive:** Red tint fill with a red border and Primary Frost text.
- **Hover / Focus:** Border brightens on hover; focus changes border colour only, so nothing shifts. Buttons take focus from the keyboard only.
- **Secondary / Ghost / Tertiary:** Graphite surface for ordinary actions; transparent icon buttons for window chrome; red only for destructive actions.

### Chips

- **Style:** Small tinted status labels use accent text and a low-opacity accent surface.
- **State:** Text labels accompany color so status remains understandable without hue perception.

### Cards / Containers

- **Corner Style:** Softly rounded (`lg` or `xl`).
- **Background:** Raised Black or Graphite according to hierarchy.
- **Shadow Strategy:** Flat internally; Window Ambient applies only to the outer shell.
- **Border:** One-pixel structural border.
- **Internal Padding:** Compact `md` to `xl` spacing.

### Inputs / Fields

- **Style:** Graphite fill, one-pixel Structural Border, and a medium radius.
- **Focus:** Two-pixel Signal Blurple focus treatment.
- **Error / Disabled:** Destructive Red for error; muted text and reduced contrast for disabled state.

### Navigation

- **Sidebar:** Switch, Custom, Monitors, Hotkeys, with Settings pinned at the bottom. The selection is a tinted pill that slides between items. Below 900px of window width the sidebar collapses to a 60px icon rail.
- **Header:** The status strip (Current, Refresh, Mode, Monitors) and window controls. Empty header space drags the window; the maximize button supports Windows 11 Snap Layouts.
- **Recovery bar:** Always visible. Status message on the left, then Restore Native and Restore Native + Enable Monitors.
- **Keyboard:** Ctrl+1…5 switch pages, Ctrl+K opens the command palette, Ctrl+F searches resolutions, Ctrl+Shift+R restores native.

### Sheets

- **Style:** Raised Black card, `xl` radius, sliding down from under the header over a 40% dim. Replace dialogs while the window is visible.
- **Behavior:** Focus is trapped inside; Esc dismisses (Esc on the keep/revert sheet means revert); Enter triggers the right-most button.

### Resolution Tile

- **Style:** Painted tile showing resolution, then aspect ratio (or saved name), then refresh rate.
- **State:** The active mode gets a blurple border, a tinted fill and an "● Active" label. A pending switch shows a spinner and "Switching…". Saved modes use the custom graphite variant. Pressing scales the tile to 97%.

### Segmented Control

- **Style:** Graphite track with a border-grey thumb that slides to the selected segment. Arrow keys move the selection.

### Grouped List Rows

- **Style:** Settings-style rows inside one rounded panel, separated by inset hairlines. Title and optional subtitle on the left, control on the right.

### Hardware Monitor Toggle

- **Style:** A 44px by 24px switch; a checkable button, so screen readers announce its state. Each toggle is named after its monitor.
- **Behavior:** It changes hardware monitor state only when directly operated. Resolution controls never trigger it.

## Motion

Every animation is skipped when Windows "Animation effects" is off. No bounce or elastic curves.

| Interaction | Motion |
|---|---|
| Page change | 180 ms cross-fade, new page rises 8 px |
| Sidebar pill / segmented thumb | Critically damped spring, 220 ms |
| Tile press | Scale to 0.97, spring back on release |
| Active tile | Border and fill cross-fade, 150 ms |
| Sheet | In 200 ms (slide 12 px + fade + dim), out 140 ms ease-in |
| Status message | Fade in and rise 6 px; fades out after 4 s |
| Status values | 120 ms cross-fade |
| Toggle | 180 ms ease-out |

## Do's and Don'ts

### Do:

- **Do** preserve the exact existing palette tokens during the overhaul.
- **Do** make current display, resolution, refresh rate, and monitor state visible together.
- **Do** keep resolution actions and monitor power-state actions explicitly separate.
- **Do** provide keyboard navigation, visible focus, non-color cues, and reduced-motion behavior.
- **Do** use concise, technically accurate labels such as “Quick Picks” instead of unsupported testing claims.

### Don't:

- **Don't** build RGB-heavy gamer software, neon cyberpunk decoration, or a bloated GPU control panel.
- **Don't** obscure important display state behind an ornamental dashboard or ambiguous label.
- **Don't** use colored side-stripe borders on cards, monitor rows, callouts, or alerts.
- **Don't** use gradient text, decorative glass effects, nested cards, or identical card-grid sprawl.
- **Don't** let hotkeys or ordinary resolution actions enable or disable hardware monitors.
- **Don't** use decorative motion or bounce/elastic easing; motion must communicate state and respect reduced motion.
