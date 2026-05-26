# Project Aria Visual Style Guide

> **Note:** This style guide is **optional**. Use it if you want your Aria webapp to match the official Project Aria visual identity. Feel free to use your own design system if preferred.

---

## Quick Reference — CSS Custom Properties

Copy this into your `:root` to use the official Project Aria design tokens:

```css
:root {
  /* ═══════════════════════════════════════════════════════════════════════════
     COLORS — PRIMARY
     ═══════════════════════════════════════════════════════════════════════════ */
  --color-primary-dark: #2C0D00;      /* Hero backgrounds, primary dark */
  --color-primary-accent: #18EED4;    /* Teal/Cyan — highlights, CTA accent */
  --color-primary-blue: #0064E0;      /* Meta Blue — primary CTA buttons */

  /* ═══════════════════════════════════════════════════════════════════════════
     COLORS — BACKGROUNDS
     ═══════════════════════════════════════════════════════════════════════════ */
  --bg-hero: #2C0D00;                 /* Hero section dark brown */
  --bg-dark-section-1: #0C292F;       /* Dark teal section */
  --bg-dark-section-2: #1C2B33;       /* Dark blue-gray section */
  --bg-light: #FFFFFF;                /* Default page/card background */
  --bg-off-white: #F7F5F2;            /* Warm light section background */
  --bg-nav: #FFFFFF;                  /* Navigation background */
  --bg-nav-pill: #F1F4F7;             /* Cool gray nav pill background */
  --bg-button-accent: #18EED4;        /* Accent button background */

  /* ═══════════════════════════════════════════════════════════════════════════
     COLORS — TEXT
     ═══════════════════════════════════════════════════════════════════════════ */
  --color-text-primary: #1C2B33;      /* Headings & body on light bg */
  --color-text-heading-dark: #222222; /* Alternative dark heading */
  --color-text-heading-brown: #2C0D00;/* Brown-tinted heading */
  --color-text-secondary: #344854;    /* Supporting text */
  --color-text-body: #465A69;         /* Standard body copy */
  --color-text-muted: #434343;        /* Muted secondary text */
  --color-text-label: #696969;        /* Labels, eyebrows, captions */
  --color-text-caption: #67788A;      /* Tertiary/caption text */
  --color-text-link: #3889EA;         /* In-content links */

  /* ═══════════════════════════════════════════════════════════════════════════
     BORDERS & SHADOWS
     ═══════════════════════════════════════════════════════════════════════════ */
  --border-divider: rgba(103, 120, 138, 0.2);
  --shadow-nav: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-card: 0 2px 4px rgba(0, 0, 0, 0.1), 0 8px 16px rgba(0, 0, 0, 0.1);

  /* ═══════════════════════════════════════════════════════════════════════════
     TYPOGRAPHY — FONTS
     ═══════════════════════════════════════════════════════════════════════════ */
  --font-display: "Optimistic Display Medium", Helvetica, Arial, sans-serif;
  --font-text: "Optimistic Text Normal", Helvetica, "Helvetica Neue", Arial, sans-serif;
  --font-text-bold: "Optimistic Text Bold", Helvetica, Arial, sans-serif;
  --font-text-base: "Optimistic Text", Helvetica, Arial, sans-serif;
  --font-mono: "Space Mono", Courier, monospace;

  /* ═══════════════════════════════════════════════════════════════════════════
     TYPOGRAPHY — SIZES
     ═══════════════════════════════════════════════════════════════════════════ */
  --text-hero: 96px;         /* Hero display text */
  --text-hero-mobile: 48px;  /* Hero on mobile */
  --text-display: 40px;      /* Large display */
  --text-h2: 36px;           /* Section headings */
  --text-h3: 26px;           /* Sub-section headings */
  --text-h4: 24px;           /* Card titles */
  --text-h5: 20px;           /* Small headings */
  --text-h6: 18px;           /* Mini headings */
  --text-body-lg: 16px;      /* Large body text */
  --text-body: 14px;         /* Standard body */
  --text-eyebrow: 12px;      /* Labels, eyebrows (UPPERCASE) */
  --text-caption: 10px;      /* Captions, credits */

  /* ═══════════════════════════════════════════════════════════════════════════
     TYPOGRAPHY — LINE HEIGHTS & LETTER SPACING
     ═══════════════════════════════════════════════════════════════════════════ */
  --leading-tight: 110%;
  --leading-display: 120%;
  --leading-normal: 140%;
  --leading-relaxed: 150%;
  --tracking-eyebrow: 0.48px;
  --tracking-display: 0.005em;
  --tracking-body: 0.03em;

  /* ═══════════════════════════════════════════════════════════════════════════
     BORDER RADIUS
     ═══════════════════════════════════════════════════════════════════════════ */
  --radius-sm: 8px;          /* Buttons, small cards */
  --radius-md: 24px;         /* Cards, nav pills */
  --radius-lg: 28px;         /* Large cards */
  --radius-pill: 40px;       /* Outlined pill buttons */
  --radius-full: 100px;      /* Full pill (nav, CTA) */

  /* ═══════════════════════════════════════════════════════════════════════════
     SPACING
     ═══════════════════════════════════════════════════════════════════════════ */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 20px;
  --space-2xl: 24px;
  --space-3xl: 32px;
  --space-4xl: 48px;
  --space-5xl: 72px;

  /* ═══════════════════════════════════════════════════════════════════════════
     LAYOUT
     ═══════════════════════════════════════════════════════════════════════════ */
  --nav-height: 76px;
  --nav-item-height: 44px;
  --max-width-page: 1600px;
  --max-width-content: 1349px;
  --max-width-narrow: 1205px;

  /* ═══════════════════════════════════════════════════════════════════════════
     BREAKPOINTS (use in @media queries)
     ═══════════════════════════════════════════════════════════════════════════ */
  /* Desktop: min-width: 1024px */
  /* Tablet:  max-width: 1023px */
  /* Mobile:  max-width: 767px */
  /* Small:   max-width: 480px */

  /* ═══════════════════════════════════════════════════════════════════════════
     TRANSITIONS
     ═══════════════════════════════════════════════════════════════════════════ */
  --transition-base: all 0.5s ease-in-out;
  --transition-fast: top 0.3s ease;
  --transition-hover: transform 0.5s ease;
}
```

---

## Button Styles

```css
/* Primary CTA — Meta Blue, full pill */
.button-primary {
  background: var(--color-primary-blue);
  color: white;
  border: none;
  border-radius: var(--radius-full);
  height: 44px;
  padding: 0 24px;
  font-family: var(--font-text-bold);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

/* Secondary — Dark gray, small radius */
.button-secondary {
  background: var(--color-text-body);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  height: 48px;
  padding: 0 24px;
  font-family: var(--font-text);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

/* Accent CTA — Teal, full pill */
.button-accent {
  background: var(--bg-button-accent);
  color: var(--color-text-primary);
  border: none;
  border-radius: var(--radius-full);
  padding: 12px 24px;
  font-family: var(--font-text-bold);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

/* Outlined (on dark backgrounds) — White border, pill */
.button-outlined {
  background: transparent;
  color: white;
  border: 1px solid white;
  border-radius: var(--radius-pill);
  padding: 12px 24px;
  font-family: var(--font-text-bold);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
```

---

## Navigation Style

```css
.navbar {
  position: sticky;
  top: 0;
  height: var(--nav-height);
  background: var(--bg-nav);
  box-shadow: var(--shadow-nav);
  display: flex;
  align-items: center;
  padding: 0 24px;
  z-index: 100;
}

.nav-pill {
  background: var(--bg-nav-pill);
  border-radius: var(--radius-md);
  padding: 8px 16px;
  font-family: var(--font-text-base);
  font-size: 16px;
  font-weight: 700;
}
```

---

## Card Style

```css
.card {
  background: var(--bg-light);
  border: 1px solid var(--border-divider);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: var(--space-2xl);
  transition: var(--transition-hover);
}

.card:hover {
  transform: scale(1.02);
}
```

---

## Typography Classes

```css
.text-hero {
  font-family: var(--font-display);
  font-size: var(--text-hero);
  line-height: var(--leading-display);
  font-weight: 500;
  letter-spacing: var(--tracking-display);
}

.text-h2 {
  font-family: var(--font-display);
  font-size: var(--text-h2);
  line-height: var(--leading-display);
  font-weight: 500;
  letter-spacing: var(--tracking-display);
}

.text-body {
  font-family: var(--font-text);
  font-size: var(--text-body);
  line-height: var(--leading-normal);
  color: var(--color-text-body);
}

.text-eyebrow {
  font-family: var(--font-text-bold);
  font-size: var(--text-eyebrow);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-eyebrow);
  text-transform: uppercase;
  color: var(--color-text-label);
}

.text-caption {
  font-family: var(--font-text);
  font-size: var(--text-caption);
  line-height: var(--leading-tight);
  color: var(--color-text-caption);
}
```

---

## Quick Start Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My Aria App</title>
  <style>
    :root {
      --color-primary-accent: #18EED4;
      --color-primary-blue: #0064E0;
      --bg-off-white: #F7F5F2;
      --color-text-primary: #1C2B33;
      --color-text-body: #465A69;
      --radius-full: 100px;
      --radius-md: 24px;
      --shadow-card: 0 2px 4px rgba(0,0,0,0.1), 0 8px 16px rgba(0,0,0,0.1);
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: var(--bg-off-white);
      color: var(--color-text-primary);
      font-family: system-ui, -apple-system, sans-serif;
      padding: 48px 24px;
    }

    h1 {
      font-size: 36px;
      margin-bottom: 16px;
    }

    h1 span {
      color: var(--color-primary-accent);
    }

    p {
      color: var(--color-text-body);
      font-size: 16px;
      line-height: 1.5;
      margin-bottom: 24px;
    }

    .card {
      background: white;
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-card);
      padding: 24px;
      max-width: 400px;
      margin-bottom: 24px;
    }

    .button-primary {
      background: var(--color-primary-blue);
      color: white;
      border: none;
      border-radius: var(--radius-full);
      padding: 12px 24px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      margin-right: 12px;
    }

    .button-accent {
      background: var(--color-primary-accent);
      color: var(--color-text-primary);
      border: none;
      border-radius: var(--radius-full);
      padding: 12px 24px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>My <span>Aria</span> App</h1>
    <p>Built with Project Aria visual style guide.</p>
    <button class="button-primary">Get Started</button>
    <button class="button-accent">Learn More</button>
  </div>
</body>
</html>
```
