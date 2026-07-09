# Cosmic Sci-Fi Design System

Use this reference when `lean-html-skill` generates or post-processes standalone HTML. This is a visual layer only. Preserve the original requirements, information architecture, data structures, interactions, and export behavior.

## Positioning

Define the visual language as:

> Human Interface for Interstellar Civilization

Blend:

- Future Civilization Interface
- Space Exploration System
- AI Command Center
- Quantum Technology Dashboard

The feel is NASA x SpaceX x quantum computing x future operating system. It should look like a professional product interface, not a game HUD or cheap cyberpunk page.

## Priority Order

1. Functionality
2. Information architecture
3. Readability
4. Cosmic visual experience

Never improve mood at the cost of usability, contrast, export controls, source links, or accessibility.

## Design Tokens

Use CSS variables.

```css
:root {
  --space-bg: #050816;
  --nebula: #081B33;
  --panel: #0B1228;
  --glass: rgba(15,25,50,0.65);
  --quantum: #00F5FF;
  --stellar: #8B5CFF;
  --galaxy: #FF4FD8;
  --solar: #FFD166;
}
```

Default pages should use a white/light background for readability. Provide a visible background control so the user can switch to the Cosmic deep-space background. The deep-space mode should keep glowing accents and transparent glass panels, but it is an option, not the default.

When applying the layer to an existing HTML page, override both Cosmic tokens and legacy page tokens. Many PAPER HTML pages use variables such as `--bg`, `--panel`, `--ink`, `--muted`, `--line`, `--accent`, and `--shadow`; the Cosmic layer must redefine these so existing components cannot keep white panels or low-contrast text.

Use one coordinated accent family per page:

- primary action/accent: Quantum Cyan
- secondary structural tint: Stellar Purple
- warnings/evidence: Solar Gold
- destructive/error: restrained rose
- success/saved state: soft green

Do not let controls drift into unrelated blues, generic white buttons, or multiple competing accent colors.

The background control is part of the visual layer only:

- default value: `light`
- optional value: `cosmic`
- persistence: browser `localStorage`
- scope: page-level background and visual token mode
- non-goals: no changes to generated content, information architecture, feedback JSON, source links, or import behavior

## Typography

- Display/title fonts: Orbitron, Space Grotesk, Exo 2.
- Body fonts: Inter, IBM Plex Sans, Roboto.
- Keep body text readable. Do not use display fonts for dense paragraphs.

## Components

Map ordinary components into Cosmic UI without changing their role.

- Card -> Quantum Glass Panel: translucent dark surface, subtle cyan border, restrained glow, clear internal hierarchy.
- Button -> Quantum Control Button: translucent surface, energy edge, hover glow, smooth transition.
- Navigation -> Orbital Navigation System: minimal command navigation with subtle orbital/track cues.
- Dashboard -> Mission Control Center: dense modules, status signals, information partitions, faint technical grid.
- Form -> System Input Console: high contrast fields, clear focus state, no hidden labels.

For generated report/news pages, explicitly style common classes such as `.news-card`, `.summary`, `aside.feedback-panel`, `.source-id`, `.category`, `.evidence`, `.saved-badge`, `.concept-chip`, `.primary`, `.secondary`, `.danger`, inputs, selects, and textareas. This is required because old page CSS often defines those components with white backgrounds.

Text hierarchy should not be "everything white":

- headings: near-white
- body text: pale blue-white
- metadata/labels/source lines: muted blue
- primary IDs: cyan chip with dark text
- categories: purple chip
- evidence/warnings: gold chip
- saved states: green chip

## Layout Language

Use semantic HTML as usual, but translate layout vocabulary:

- Header -> Command Navigation
- Hero -> Mission Briefing
- Dashboard -> Mission Control Center
- Statistics -> Cosmic Data Observatory
- Profile -> Explorer Identity Module
- Settings -> System Configuration Hub
- Login -> Space Gateway Authentication
- Search -> Deep Space Scanner

These are design mappings, not changes to the user's business meaning.

## Background

Default background should combine:

- deep-space gradient
- faint star dust
- low-opacity grid texture
- restrained nebula glow

Use these only when the user selects the Cosmic background mode. Use CSS radial and linear gradients. Avoid heavy canvas particles, large animation loops, or anything that slows report pages.

## Motion

Use only lightweight, slow, scientific motion:

- fade in
- weak glow pulse
- subtle scan-line feel
- hover energy on controls

Respect `prefers-reduced-motion`. Avoid fast flashes, large rotation, game-like movement, and decorative noise.

## Accessibility

- Preserve visible labels and keyboard-accessible controls.
- Keep focus states visible.
- Keep text contrast high on dark surfaces.
- Do not hide source links or feedback export controls behind purely decorative UI.
- Print styles should remain usable and should remove heavy background effects.
- Audit primary buttons so text is dark on cyan or light on dark; never white text on pale cyan.
- Audit form controls so placeholder text, labels, borders, and focus rings remain legible.
- The background toggle itself must remain visible and readable in both light and cosmic modes.

## Anti-Patterns

Avoid:

- game HUD styling
- excessive neon
- saturated purple-only themes
- cluttered animated particles
- decorative visuals that reduce reading speed
- changing content semantics to sound more sci-fi
- replacing actual functionality with visual metaphor
- adding new tokens without overriding old white-surface tokens
- all-white text hierarchy with no metadata/body/badge differentiation
- forcing a dark background as the default when the reader/report context benefits from light-mode readability
