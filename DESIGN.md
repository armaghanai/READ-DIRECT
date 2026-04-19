# Design Specification: Vibrant Scholarly Book Engine

## Overview
This document outlines the design system and aesthetic principles for the **Vibrant Scholarly Book Engine**. 

**Creative North Star: "The Modern Scriptorium"**
This system rejects the sterile, "template-first" look of modern search engines in favor of a high-end editorial experience. It is designed to feel like a digital archive curated by a scholar who appreciates both the weight of history and the velocity of modern technology.

---

## Technical Tokens

### Colors (Light Mode)
- **Primary:** `#002046` (Oxford Blue)
- **Surface:** `#fbf9f2` (Cream Parchment)
- **Secondary:** `#3b6934` (Scholarly Green)
- **Tertiary:** `#361900` / `#eb851c` (Burnt Orange)
- **Background:** `#fbf9f2`

### Typography
- **Headlines:** `Newsreader` (Serif) - Authoritative and book-like.
- **Body:** `Inter` (Sans-Serif) - Precise and readable.
- **Label:** `Inter`

### Shape & Spacing
- **Roundness:** `ROUND_FOUR` (Soft, well-worn book edges).
- **Spacing Scale:** `2`

---

# Design System Specification

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Modern Scriptorium."** 

This system rejects the sterile, "template-first" look of modern search engines in favor of a high-end editorial experience. It is designed to feel like a digital archive curated by a scholar who appreciates both the weight of history and the velocity of modern technology. We achieve this by breaking the traditional rigid grid—using intentional asymmetry, overlapping layers that mimic stacked folios, and a typography scale that demands attention. 

The goal is to move the user from a "utility search" mindset to an "exploratory discovery" mindset. We are not just showing data; we are presenting knowledge.

---

## 2. Colors: Tonal Architecture
The palette is built on a foundation of "Rich Creams" and "Deep Academic Blues," punctuated by "Burnt Orange" and "Scholarly Green."

### The "No-Line" Rule
To maintain a premium editorial feel, **1px solid borders are strictly prohibited for sectioning.** Boundaries must be defined through background color shifts or tonal transitions.
- Use `surface-container-low` (#f5f4ed) against a `surface` (#fbf9f2) background to define a sidebar.
- Use `surface-container-high` (#e9e8e1) to denote a tertiary content area.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers—like fine paper stacked on a desk. 
- **Base Layer:** `surface` (#fbf9f2).
- **In-Page Containers:** Use `surface-container-lowest` (#ffffff) for primary cards to make them "pop" against the cream background.
- **Overlays:** Use `surface-container-highest` (#e3e3dc) for transient elements like hover states on list items.

### The "Glass & Gradient" Rule
Flat color is the enemy of depth. 
- **Floating Elements:** Use `surface` colors at 85% opacity with a `backdrop-blur` of 20px for search bars or navigation headers.
- **Signature Textures:** For primary CTAs and Hero backgrounds, use a subtle linear gradient from `primary` (#002046) to `primary_container` (#1b365d) at a 135-degree angle. This adds "soul" and prevents the deep blue from feeling like a dead weight on the screen.

---

## 3. Typography: Editorial Authority
The typography leverages a high-contrast pairing: the intellectual gravity of **Newsreader** (Serif) and the technical precision of **Inter** (Sans-Serif).

- **Display & Headlines:** Use `newsreader`. These should be large and expressive. For `display-lg`, use tight letter-spacing (-0.02em) to create an authoritative, book-cover feel.
- **Body & Labels:** Use `inter`. For `body-lg`, maintain a generous line-height (1.6) to ensure long-form book descriptions are readable and inviting.
- **Functional Hierarchy:** All interaction points (buttons, tabs, inputs) must use `inter` in `label-md` or `title-sm` to ensure they feel like "tools" within the "library."

---

## 4. Elevation & Depth: Tonal Layering
We do not use shadows to \"lift\" objects; we use color to \"layer\" them.

- **The Layering Principle:** Place a `surface-container-lowest` card on a `surface-container-low` section. This creates a natural, soft lift that mimics physical paper without the clutter of drop shadows.
- **Ambient Shadows:** If an element must float (e.g., a modal), use an ultra-diffused shadow: `box-shadow: 0 20px 40px rgba(27, 28, 24, 0.06)`. The shadow color is derived from `on-surface` (#1b1c18), never pure black.
- **The "Ghost Border\" Fallback:** If a border is required for accessibility in input fields, use `outline-variant` (#c4c6cf) at **20% opacity**. It should be felt, not seen.
- **Glassmorphism:** Apply to global navigation headers. Using `surface_bright` at 80% opacity with a blur allows the \"vibrant\" book covers in the search results to bleed through softly as the user scrolls.

---

## 5. Components: Scholarly Primitives

### Buttons
- **Primary:** Gradient fill (`primary` to `primary_container`). Use `rounded-md` (0.375rem). Text is `on-primary` (#ffffff).
- **Secondary (The Scholarly Green):** Use `secondary` (#3b6934) for \"Add to Collection\" or \"Save\" actions. It signals growth and curation.
- **Tertiary (The Burnt Orange):** Use `tertiary` (#361900) or `on-tertiary_container` (#eb851c) for high-energy interactions like \"Buy Now\" or \"Live Auction.\"

### Cards & Search Results
- **Constraint:** Forbidden to use divider lines between search results.
- **Implementation:** Use `surface-container-low` for the card background. Use `body-sm` for metadata (ISBN, Date) and `headline-sm` for the book title. Separate items with 32px of vertical white space (using the Spacing Scale).

### Input Fields
- **Search Bar:** Large, centered, using `surface-container-lowest`. Use a 2px `primary` bottom-border only on `:focus` to mimic a traditional underlining of text.
- **Helper Text:** Must use `label-sm` in `on-surface-variant` (#44474e).

### Chips & Filters
- **Selection Chips:** Use `secondary_container` (#b9eeab) with `on-secondary-container` (#3f6d38) text. This provides a \"vibrant\" pop that signifies an active, energetic search.

---

## 6. Do's and Don'ts

### Do:
- **Embrace Asymmetry:** Offset book covers in a grid. Let some elements hang off the baseline to create an editorial, magazine-like flow.
- **Use \"White\" Space:** In this system, \"White Space\" is actually \"Cream Space\" (`surface`). Use it aggressively to separate concepts rather than using lines.
- **Layering:** Always check if a background color shift can solve a hierarchy problem before reaching for a shadow or border.

### Don't:
- **Avoid Purple:** Ensure no blue-to-red transitions occur. Stick to the deep, \"Oxford\" blues and \"Burnt\" oranges.
- **No Sharp Corners:** Avoid `none` (0px) roundedness for buttons or cards. It feels too brutalist. Use `md` or `lg` to maintain a \"well-worn book\" softness.
- **No High-Contrast Borders:** Never use a 100% opaque `outline` for a container. It breaks the \"Modern Scriptorium\" illusion of layered paper.
