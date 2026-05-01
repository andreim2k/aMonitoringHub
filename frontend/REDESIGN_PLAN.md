# aMonitoringHub 2026 Redesign Plan

## 1. Vision & Aesthetic
- **Concept:** "Digital Sanctuary" - A serene yet powerful monitoring interface.
- **Style:** Apple (Cleanliness) + Linear (Precision) + Stripe (Elegance/Gradients).
- **Core Principles:**
    - **Bento Grid Layout:** Modular, organized, and visually satisfying.
    - **Depth & Texture:** Subtle noise, layered shadows, and refined glassmorphism.
    - **Typography First:** High-contrast hierarchy using Geist Sans.
    - **Motion:** Purposeful, fluid transitions (GSAP/CSS).

## 2. Design System

### Color Palette
- **Primary Background:** `#030303` (OLED Black) or `#0A0A0B` (Deep Charcoal).
- **Secondary Background:** `#121214` (Card background).
- **Accents:**
    - **Cyan/Blue:** `#38BDF8` (Temperature/Normal).
    - **Emerald:** `#10B981` (Air Quality - Good).
    - **Amber:** `#F59E0B` (Warning).
    - **Rose:** `#F43F5E` (Danger).
- **Border:** `rgba(255, 255, 255, 0.06)`.

### Typography
- **Headings:** Geist Sans (Bold/Black), tight tracking.
- **Body:** Geist Sans (Regular/Medium).
- **Mono:** Geist Mono (for data/timestamps).

### Components
- **The "Pulse":** A live status indicator in the top right.
- **Hero Metric:** The primary temperature/environment status in a large, bold bento card.
- **Metric Bento Cards:** Various sizes (1x1, 2x1, 2x2) for different data types.
- **Live Graphs:** Integrated sparklines within cards.
- **Control Bar:** Fixed bottom or floating top navigation for history/settings.

## 3. Functional Requirements
- **Real-time Updates:** Maintain existing SSE (Server-Sent Events) integration.
- **GraphQL Integration:** Use for historical data and initial state.
- **Responsive:** Fluid transition from desktop grid to mobile stack.
- **Performance:** Optimized CSS, minimal external dependencies (CDN for fonts/icons/Chart.js).

## 4. Implementation Steps
1. **Infrastructure:** Set up the HTML5 boilerplate with CDN links (Geist, Lucide, Chart.js, GSAP).
2. **Layout:** Build the Bento Grid using CSS Grid/Flexbox.
3. **Styling:** Apply the premium design system (Glass, Gradients, Borders).
4. **JS Logic:** Port and refactor existing SSE and Chart.js logic into a modern `App` module.
5. **Polishing:** Add animations, micro-interactions, and ensure accessibility.
