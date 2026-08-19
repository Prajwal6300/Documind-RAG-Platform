---
name: Humanist Editorial
colors:
  surface: '#faf9f5'
  surface-dim: '#dbdad6'
  surface-bright: '#faf9f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f4f0'
  surface-container: '#efeeea'
  surface-container-high: '#e9e8e4'
  surface-container-highest: '#e3e2df'
  on-surface: '#1b1c1a'
  on-surface-variant: '#54433e'
  inverse-surface: '#2f312e'
  inverse-on-surface: '#f2f1ed'
  outline: '#87736d'
  outline-variant: '#dac1ba'
  surface-tint: '#924a31'
  primary: '#8f482f'
  on-primary: '#ffffff'
  primary-container: '#ad5f45'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb59d'
  secondary: '#5f5e5d'
  on-secondary: '#ffffff'
  secondary-container: '#e2dfdd'
  on-secondary-container: '#636261'
  tertiary: '#5f5c53'
  on-tertiary: '#ffffff'
  tertiary-container: '#78746b'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbd0'
  primary-fixed-dim: '#ffb59d'
  on-primary-fixed: '#390c00'
  on-primary-fixed-variant: '#75331c'
  secondary-fixed: '#e5e2e0'
  secondary-fixed-dim: '#c9c6c4'
  on-secondary-fixed: '#1c1c1a'
  on-secondary-fixed-variant: '#474745'
  tertiary-fixed: '#e8e2d7'
  tertiary-fixed-dim: '#cbc6bb'
  on-tertiary-fixed: '#1d1b15'
  on-tertiary-fixed-variant: '#49473f'
  background: '#faf9f5'
  on-background: '#1b1c1a'
  surface-variant: '#e3e2df'
  body-text: '#3D3D3A'
  muted-text: '#6C6A64'
  canvas: '#FAF9F5'
  card-surface: '#EFE9DE'
  coral-accent: '#CC785C'
typography:
  display-lg:
    fontFamily: Source Serif 4
    fontSize: 48px
    fontWeight: '400'
    lineHeight: 56px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Source Serif 4
    fontSize: 32px
    fontWeight: '400'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Source Serif 4
    fontSize: 28px
    fontWeight: '400'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Source Serif 4
    fontSize: 24px
    fontWeight: '400'
    lineHeight: 32px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 280px
  content-max-width: 960px
  gutter: 24px
  margin-desktop: 40px
  margin-mobile: 20px
  search-height: 70px
---

## Brand & Style

The design system is rooted in the concept of **Technological Humanism**, specifically tailored for a premium AI document workspace. It rejects the sterile, high-gloss tropes of traditional SaaS in favor of an aesthetic that feels literary, grounded, and academic. The emotional goal is to evoke the focused tranquility of a high-end library or a modern scholarly journal, facilitating deep cognitive work rather than rapid-fire task switching.

The chosen style is **Minimalism** blended with **Editorial Tactility**. It prioritizes generous whitespace, a sophisticated serif-led typographic hierarchy, and a warm, low-fatigue color palette. Every element is designed to feel like "ink on paper," using subtle tonal shifts instead of aggressive shadows to create a sense of presence and permanence.

## Colors

The palette is anchored by the **Canvas**—a warm, tinted cream that serves as the foundation for the entire UI, significantly reducing eye strain compared to digital pure white. 

- **Primary (Coral Accent):** A signature warm earth tone (#CC785C) used sparingly for primary calls to action, active indicators, and critical brand moments.
- **Secondary (Primary Text):** A near-black (#141413) used for high-contrast headings to ensure maximum legibility against the canvas.
- **Tertiary (Card Surface):** A slightly deeper, parchment-like tone (#EFE9DE) used for structural elements like sidebars and container backgrounds to provide subtle hierarchy.
- **Neutral:** The base canvas color (#FAF9F5) which dictates the "airiness" of the workspace.
- **Functional Grays:** Body text (#3D3D3A) and Muted text (#6C6A64) are carefully tuned to maintain a soft, humanist contrast level that feels sophisticated rather than harsh.

## Typography

This system employs a classic editorial pairing to signal a humanist voice. 

- **Headlines:** Driven by **Source Serif 4**. To achieve a high-end editorial look, use regular weights with negative tracking. The tight letter-spacing mimics the density of traditional typesetting and creates a more sophisticated "ink-on-paper" visual.
- **Body & UI:** **Inter** provides the necessary technical clarity and functional reliability to balance the expressive headlines. It is used for all long-form reading, metadata, and interface controls.
- **Labels:** Use Inter with slightly increased letter-spacing and medium weights to ensure small-scale utility text remains legible and distinct from body copy.

## Layout & Spacing

The layout follows a **Fixed Grid** philosophy for the main workspace to ensure an optimal reading experience. The philosophy is "content-first," where the interface recedes to favor the document.

- **Sidebar:** A fixed 280px navigation area on the left, utilizing the Tertiary background color (#EFE9DE) to separate utility from the creative canvas.
- **Main Workspace:** A centered content column with a maximum width of 960px. This ensures line lengths remain within the comfortable 65–80 character range.
- **Vertical Rhythm:** All spacing is based on a 4px base unit. Generous 40px margins on desktop reinforce the "spacious editorial" feel.
- **Mobile Reflow:** On mobile devices, the sidebar transitions to a hidden drawer, and margins are reduced to 20px. The central column becomes fluid, spanning the full width of the viewport.

## Elevation & Depth

Hierarchy is communicated through **Tonal Layers** rather than heavy shadows. The system uses three primary surface tiers:

1.  **The Canvas (Level 0):** The base layer (#FAF9F5). All primary work happens here.
2.  **Container Tier (Level 1):** Elements like sidebars, feature cards, and suggested questions use the Tertiary color (#EFE9DE). These sit flat on the canvas, distinguished solely by color contrast.
3.  **Active/Floating Tier (Level 2):** Only high-priority interactive elements (like the search bar or modals) use elevation. This is achieved through an extremely soft, diffused ambient shadow—8% opacity of the Primary Text color—to suggest they are floating slightly above the page.

Avoid harsh borders or "glow" effects. For separation where color contrast is insufficient, use a 1px solid stroke in the Muted color (#6C6A64) at 15% opacity.

## Shapes

The shape language is refined and consistent, leaning toward **Rounded** to soften the geometric structure of the document grid.

- **Standard UI Elements:** Buttons, chips, and small inputs use a 0.5rem (8px) radius.
- **Primary Search Bar:** Uses a specific 16px radius to match its substantial 70px height, making it the most approachable element in the workspace.
- **Cards & Upload Areas:** Use a 1rem (16px) radius to create a soft, inviting container for suggested content and file drops.

## Components

- **Premium Search Bar:** The focal point of the AI experience. 70px height, 16px radius, with a subtle ambient shadow. Use the Canvas color for the background and a placeholder in the Muted tone.
- **Suggested Question Cards:** Rendered in the Card Surface color (#EFE9DE) with no border. Use the Headline-MD typography for the question text to make them feel like editorial suggestions rather than "buttons."
- **Buttons:** 
    - **Primary:** Coral Accent (#CC785C) background with white text.
    - **Secondary/Ghost:** 1px border using the Primary Text color at low opacity, or purely typographic with a small icon.
- **Upload Area:** A large, 16px rounded dashed-border container using the Muted color for the stroke. Use generous internal padding (64px+) to maintain the spacious aesthetic.
- **Input Fields:** Simple 1px bottom border or a subtle 0.5rem rounded box with a #EFE9DE background. Focus states should be indicated by a weight change in the border or a subtle Coral Accent indicator.
- **AI Response:** Should not be contained in a "chat bubble." The AI text should sit directly on the Canvas, distinguished from the user's input by the use of the Serif typeface for its primary output.