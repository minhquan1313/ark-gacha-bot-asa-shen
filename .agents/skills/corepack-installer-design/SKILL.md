---
name: corepack-installer-design
description: Project UI design reference for creating, redesigning, reviewing, or refining this app's launcher and desktop interface. Use when Codex works on UI layout, visual styling, PySide launcher pages, navigation, panels, buttons, custom window chrome, status displays, progress views, artwork placement, or design consistency. Apply the documented modern nostalgic 2010s installer-inspired direction: borderless dark cinematic shell, cyan neon accents, compact technical panels, readable spacing, and legal branding without piracy or crack wording.
---

# Retro CorePack/Repack Installer Inspired UI — Design Notes

> Goal: use the _nostalgic gamer installer_ feeling as visual inspiration for a modern app UI.
> This is not a clone of any specific installer, logo, or crack/repack brand. Keep the vibe, avoid copyrighted branding and piracy wording.

---

## 1. Core Feeling

The interface should feel like:

- A small self-contained launcher/installer window from the 2010s PC gaming era.
- Dark, cinematic, slightly “underground gamer tech”.
- Flashy enough to feel exciting, but still usable.
- A mix of sci-fi HUD, game launcher, Windows Phone tile layout, and old Inno/NSIS custom skin.
- “I am installing a game at 2 AM and the installer has better music than the game menu.”

Keywords:

`dark`, `neon`, `compact`, `game-art`, `cyber`, `glass`, `metal`, `progress-driven`, `music-enabled`, `status-heavy`, `nostalgic`, `slightly edgy but clean`.

---

## 2. Historical / Reference Pattern

The old CorePack-like installer ecosystem often overlaps with these UI/script families:

- Windows Phone Installer / WPI style
- WPI CorePack Style
- WPI CorePack Mixed
- Final CorePack Installer UI
- BlackBox-style compact installers
- Custom Inno Setup / FMXInno / ISFMXFW-based installer skins
- UltraARC / DiskSpan compression-era installer screens

Important design takeaway:

The design was not “normal desktop app UI”. It was closer to a mini game launcher with install controls attached.

---

## 3. Layout DNA

### Main Window

Preferred format:

- Borderless or custom-framed window.
- Fixed-size desktop panel.
- Landscape ratio.
- Recommended sizes:
  - `960 x 540`
  - `1000 x 600`
  - `1100 x 620`
  - `1280 x 720` for more cinematic versions

Avoid:

- Default OS title bar.
- Default Windows buttons.
- Plain white installer wizard pages.
- Big empty enterprise SaaS spacing.

### Typical Structure

```text
┌──────────────────────────────────────────────────────┐
│ Top chrome: logo / title / mini window controls       │
├───────────────┬──────────────────────────────────────┤
│ Left nav/tabs │ Main hero/game artwork + content      │
│               │                                      │
│ Status blocks │ Install options / destination / info  │
│               │                                      │
├───────────────┴──────────────────────────────────────┤
│ Progress bar / file status / speed / action buttons   │
└──────────────────────────────────────────────────────┘
```

### Core Sections

1. **Header bar**
   - App name, version, build label.
   - Small custom close/minimize icons.
   - Maybe one animated glow line under it.

2. **Hero image area**
   - Big game/anime/sci-fi artwork.
   - Dark overlay gradient for readability.
   - Logo or mode name over image.

3. **Navigation / tile area**
   - Start / Install / Settings / About / Credits / Music toggle.
   - Tiles can feel Windows Phone-inspired: square/rectangular blocks.

4. **Status panel**
   - Compact technical info:
     - Version
     - Required space
     - Install path
     - Current task
     - Time elapsed
     - Estimated remaining
     - Speed

5. **Progress area**
   - One main thick progress bar.
   - Optional small secondary progress bar.
   - Current file/status text below.
   - Keep it dramatic.

6. **Action buttons**
   - Install / Pause / Cancel / Finish.
   - Big primary CTA, smaller secondary buttons.

---

## 4. Visual Style

### Background

Use a layered dark background:

- Base: near-black blue or charcoal.
- Add subtle texture:
  - brushed metal
  - smoky gradient
  - faint grid
  - diagonal scanlines
  - soft particles
  - blurred game art
- Use a vignette around edges.

Recommended CSS-like values:

```css
--bg-main: #070a0f;
--bg-panel: rgba(10, 16, 25, 0.86);
--bg-panel-strong: rgba(3, 7, 12, 0.94);
--bg-glass: rgba(18, 28, 42, 0.55);
--border-soft: rgba(120, 220, 255, 0.18);
```

### Color Palette

Core palette:

- Black / charcoal base
- Cyan / electric blue accent
- White text
- Muted gray secondary text
- Optional yellow or orange highlight
- Optional green terminal accent for “processing” states

Suggested palette:

```css
--accent-cyan: #00d8ff;
--accent-blue: #2f80ff;
--accent-green: #6bff9e;
--accent-yellow: #ffd166;
--danger-red: #ff4d6d;

--text-main: #f4f8ff;
--text-muted: #8ea3b8;
--text-dim: #5f7285;
```

Use cyan as the main identity color. Use yellow sparingly for attention, not as a full theme.

### Borders

Common feel:

- Thin glowing strokes.
- 1px or 2px borders.
- Slight bevels.
- Inner shadow.
- Corners can be sharp or mildly rounded.

Recommended:

```css
border: 1px solid rgba(0, 216, 255, 0.26);
box-shadow:
  0 0 18px rgba(0, 216, 255, 0.12),
  inset 0 0 24px rgba(0, 216, 255, 0.06);
```

Avoid modern huge `border-radius: 32px`. This style likes sharper shapes.

Good radius range:

```css
--radius-small: 4px;
--radius-medium: 8px;
--radius-large: 12px;
```

---

## 5. Typography

### Font Direction

Use techno, condensed, square, or futuristic fonts.

Good font types:

- Orbitron
- Rajdhani
- Oxanium
- Eurostile-like
- Microgramma-like
- Agency FB style
- Exo 2
- Share Tech Mono

Hierarchy:

```text
App title:       condensed techno, uppercase, tracking wide
Section title:   small uppercase, cyan/white
Body text:       readable sans-serif
Status text:     monospace or tech mono
Numbers:         tabular/monospace
```

### Text Style

Use short, punchy labels:

- `READY TO INSTALL`
- `SYSTEM CHECK`
- `SELECT DESTINATION`
- `INSTALL QUEUE`
- `EXTRACTING DATA`
- `VERIFYING FILES`
- `FINALIZING SETUP`

Avoid long paragraphs in the main UI. Put long text in About/Readme modal.

---

## 6. Buttons

### Primary Button

Should feel chunky, glowing, and “game launcher”.

```text
[ INSTALL ]
[ START ]
[ LAUNCH ]
```

Style:

- Cyan gradient border.
- Dark fill.
- Glow on hover.
- Pressed state moves down 1px.
- Text uppercase with letter spacing.

Example button behavior:

```css
.button-primary {
  background: linear-gradient(180deg, rgba(0, 216, 255, 0.2), rgba(0, 80, 120, 0.2));
  border: 1px solid rgba(0, 216, 255, 0.55);
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}
.button-primary:hover {
  box-shadow: 0 0 22px rgba(0, 216, 255, 0.35);
}
```

### Secondary Buttons

Use muted glass:

```text
[ OPTIONS ] [ ABOUT ] [ MUSIC: ON ] [ VERIFY ]
```

### Danger Button

Cancel/delete actions should be red but still dark:

```text
[ CANCEL ]
```

Use red only where necessary. Don’t turn the whole UI into Christmas lights.

---

## 7. Progress Bar

This is one of the most important CorePack/repack-inspired elements.

### Design

- Thick horizontal bar.
- Neon fill.
- Dark empty track.
- Animated diagonal stripes or scanning highlight.
- Percentage displayed nearby or inside bar.
- Current task text below.

```text
EXTRACTING: Data_03.arc
████████████████░░░░░░░░░░  64%
Speed: 42.8 MB/s    ETA: 00:04:12
```

### Status Copy

Use dramatic but legitimate wording:

Good:

- `Preparing files...`
- `Extracting archive...`
- `Verifying package...`
- `Optimizing assets...`
- `Writing configuration...`
- `Finalizing...`

Avoid piracy/crack wording in the actual app:

- `Cracking protection`
- `Bypassing`
- `Injecting crack`
- `Keygen`
- `Loader`

For a legal app, use “repack-inspired” flavor without shady actions.

---

## 8. Sound / Music UX

Old repack installers often had background music. For modern app design, make it optional and respectful.

Recommended:

- Tiny music control in top/right or bottom/left.
- Default: off, or remember last user preference.
- Button states:
  - `MUSIC: ON`
  - `MUSIC: OFF`
- Add small equalizer animation if music is playing.
- Volume slider hidden behind settings.

Do not auto-blast music at 100%. Nostalgia is good; jumpscare installer is not good, chú Bình chịu không nổi đâu.

---

## 9. Animation Language

Keep animation mechanical and subtle.

Good animations:

- Scanline sweep across hero panel.
- Progress bar shimmer.
- Neon border pulse.
- Button hover glow.
- Tile slide-in.
- Status text typewriter effect.
- Tiny equalizer bars.
- Background particles moving slowly.

Avoid:

- Overly bouncy mobile UI animation.
- Huge modern SaaS fade effects.
- Too much blur that kills readability.
- Infinite intense flashing.

Motion timing:

```css
--fast: 120ms;
--normal: 220ms;
--slow: 600ms;
```

Easing:

```css
cubic-bezier(0.2, 0.8, 0.2, 1)
```

---

## 10. Icon Style

Icons should be:

- Simple line icons.
- 1.5px to 2px stroke.
- Cyan/white.
- Minimal fill.
- Slight outer glow on active state.

Recommended icon concepts:

- Install: downward arrow into tray
- Settings: cog
- Music: waveform or note
- Verify: shield/check
- Info: circle-i
- Folder/path: folder
- Close: X
- Minimize: dash

Avoid emoji-style icons inside the app UI. Use clean vector icons.

---

## 11. Panels / Cards

Panels should feel like old custom installer surfaces:

- Dark translucent surface.
- Thin cyan border.
- Internal separators.
- Header strip.
- Small labels.
- Compact data rows.

Example data card:

```text
┌ SYSTEM CHECK ─────────────────────┐
│ OS           Windows 10/11         │
│ Disk Space   42.5 GB required      │
│ Status       Ready                 │
└───────────────────────────────────┘
```

Use all-caps section headers.

---

## 12. Window Controls

Use custom controls:

```text
[ _ ] [ X ]
```

or icon-only:

```text
─  ×
```

Placement:

- Top-right.
- Small.
- Glow red on close hover.
- No default browser-looking controls if this is an Electron/Tauri/custom desktop app.

---

## 13. Recommended Screens

### 13.1 Splash / Boot Screen

Purpose: instantly create vibe.

Elements:

- App logo.
- Small version/build text.
- Loading spinner or scanline.
- Status line:
  - `Initializing interface...`
  - `Loading modules...`
  - `Checking assets...`

Duration should be short, max 1–2 seconds unless real loading is needed.

### 13.2 Home Screen

Elements:

- Hero image.
- Main CTA.
- Quick stats/status.
- Tile buttons.

CTA examples:

- `START`
- `INSTALL`
- `OPEN TOOL`
- `LAUNCH APP`

### 13.3 Setup / Config Screen

Elements:

- Install path or workspace path.
- Options toggles.
- Required disk space.
- Language / theme / audio controls.

### 13.4 Progress Screen

Elements:

- Large progress bar.
- Current task.
- Percentage.
- Speed/time info if relevant.
- Cancel/pause controls.

### 13.5 Finish Screen

Elements:

- Success state.
- Launch button.
- Open folder button.
- Changelog / credits small link.

---

## 14. Modernization Rules

The old style can become messy fast. To make it good in 2026:

### Keep

- Dark cinematic layout.
- Neon progress.
- Compact status panels.
- Custom chrome.
- Game artwork.
- Music toggle.
- Technical labels.

### Improve

- Accessibility.
- Contrast.
- Responsive scaling.
- Clear hierarchy.
- No unreadable tiny text.
- No malware-ish language.
- No overpacked controls.

### Remove / Avoid

- Fake “hacker” messages.
- Too many skull/flame effects.
- Piracy group branding.
- Aggressive autoplay music.
- Blinking text everywhere.
- Random low-res JPEG backgrounds.

---

## 15. Component Checklist

Use this when redesigning the app.

### Must Have

- [ ] Borderless dark shell
- [ ] Custom title/header bar
- [ ] Hero artwork area
- [ ] Cyan neon accent system
- [ ] Thick animated progress bar
- [ ] Compact technical status panel
- [ ] Big primary CTA
- [ ] Music toggle
- [ ] About/Credits modal
- [ ] Settings/options panel
- [ ] Small footer with version/build

### Nice To Have

- [ ] Scanline overlay
- [ ] Equalizer animation
- [ ] Tile navigation
- [ ] Terminal-style status log
- [ ] Glowing hover states
- [ ] Subtle particles
- [ ] Alternate accent themes
- [ ] “Compact mode” window

---

## 16. Design Tokens

```css
:root {
  --bg-main: #070a0f;
  --bg-panel: rgba(10, 16, 25, 0.86);
  --bg-panel-strong: rgba(3, 7, 12, 0.94);
  --bg-glass: rgba(18, 28, 42, 0.55);

  --accent-cyan: #00d8ff;
  --accent-blue: #2f80ff;
  --accent-green: #6bff9e;
  --accent-yellow: #ffd166;
  --danger-red: #ff4d6d;

  --text-main: #f4f8ff;
  --text-muted: #8ea3b8;
  --text-dim: #5f7285;

  --border-soft: rgba(120, 220, 255, 0.18);
  --border-active: rgba(0, 216, 255, 0.55);

  --shadow-cyan: 0 0 18px rgba(0, 216, 255, 0.22);
  --shadow-panel: 0 16px 50px rgba(0, 0, 0, 0.45);

  --radius-small: 4px;
  --radius-medium: 8px;
  --radius-large: 12px;

  --font-display: 'Orbitron', 'Rajdhani', 'Oxanium', sans-serif;
  --font-body: 'Inter', 'Segoe UI', sans-serif;
  --font-mono: 'Share Tech Mono', 'JetBrains Mono', monospace;
}
```

---

## 17. Sample UI Copy

### Header

```text
SHEN INSTALLER
Build 1.0.0 // Stable Channel
```

### Status

```text
SYSTEM READY
All required modules loaded.
```

### Progress

```text
EXTRACTING ASSETS
Data package 03/12
```

### Buttons

```text
INSTALL
OPTIONS
ABOUT
MUSIC: OFF
CANCEL
LAUNCH
```

### Finish

```text
INSTALL COMPLETE
Everything is ready. Launch when you're ready.
```

---

## 18. Suggested Direction For Chú Bình's App

For your app, use this as the main design direction:

**“Cute gaming tool wearing a dark repack-installer jacket.”**

Meaning:

- Keep the nostalgic CorePack installer skeleton.
- Add your personality through:
  - cute small mascot/icon
  - cyan/white/yellow brand colors
  - clean anime-ish artwork
  - less aggressive hacker text
  - more polished modern spacing

Recommended final vibe:

```text
Dark CorePack-style installer
+ modern game launcher polish
+ cute Shen branding
+ cyan/yellow anime tech accent
```

This keeps the nostalgic “legendary installer” feeling without making the app look suspicious or outdated.

---

## 19. Implementation Notes For Future UI Work

When asking for a UI mockup or React/Electron redesign, tell the designer/model:

```text
Create a desktop app UI inspired by nostalgic 2010s CorePack/repack game installers:
borderless dark cinematic window, cyan neon accents, compact tech panels,
large animated progress/status area, custom title bar, game-art hero panel,
Windows Phone Installer-like tile buttons, optional music toggle, scanline/glass effects.
Make it modern, legal, clean, readable, and avoid piracy/crack branding.
```

For a stronger cute-gaming version:

```text
Blend the retro repack installer aesthetic with cute anime gaming-tool branding:
dark cyan neon shell, compact panels, soft mascot/logo area, polished launcher-like UX,
subtle glow, no clutter, no piracy wording.
```

---

## 20. Source Notes

These notes were informed by public references around FileForums installer scripts and UI families, especially:

- FileForums premade installer collections listing WPI, BlackBox, Final CorePack Installer UI, WPI CorePack Mixed, WPI CorePack Style, CIU, UltraARC, and similar installer families.
- FileForums threads describing WPI CorePack Mixed and Final CorePack Installer UI updates/features.
- Inno Setup and graphical installer customization patterns: custom backgrounds, buttons, colors, progress bars, and full-window skinning.
