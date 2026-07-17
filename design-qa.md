# Design QA — Ambrosia AI-native clinic platform

## Visual truth and implementation evidence

- Selected visual truth:
  - `.product-design/reference/ai-native-living-dayline.png`
  - `.product-design/reference/ai-native-suite/care-horizons.png`
  - `.product-design/reference/ai-native-suite/sarah-care-agent.png`
  - `.product-design/reference/ai-native-suite/clinic-intelligence.png`
- Full-view comparisons, with reference and implementation in the same image:
  - `.product-design/qa/command-center-comparison.png`
  - `.product-design/qa/care-horizons-comparison.png`
- Cross-screen evidence: `.product-design/qa/platform-contact-sheet.png`
- Focused implementation evidence:
  - `.product-design/qa/today-viewport-final.png`
  - `.product-design/qa/today-horizons-final.png`
  - `.product-design/qa/sarah-agent-final.png`
  - `.product-design/qa/schedule-final.png`
  - `.product-design/qa/inbox-final.png`
  - `.product-design/qa/results-final.png`
  - `.product-design/qa/revenue-final.png`
  - `.product-design/qa/operations-final.png`
  - `.product-design/qa/patient-plan-final.png`
- Responsive evidence:
  - `.product-design/qa/today-mobile.png`
  - `.product-design/qa/inbox-mobile.png`
- Desktop viewport/state: 1339 × 865, authenticated as Dr. Maya Chen, July 17 synthetic clinic state, `Now` horizon selected.
- Mobile viewport/state: 390 × 844, same authenticated clinic state.

## Comparison history

### Iteration 1

- P0: none.
- P1: none.
- P2, layout: long care rails exceeded their available panel width, obscuring downstream communication, revenue, and closure stages on Today and Sarah's agent.
- P2, evidence quality: `fullPage` capture was unreliable around fixed navigation and AgentDock surfaces, producing DPR-scaled crops for some screens.

Fixes:

- Added a responsive compact care-rail mode, narrowed Today's patient identity column, and used the compact rail in Today, Sarah's agent, and Schedule. Final DOM measurements show no rail overflow: Today `479 px` viewport/`479 px` scroll width; Sarah `688 px` viewport/`688 px` scroll width.
- Re-captured canonical viewport states and used a two-state Today story for the cross-screen board. Full-view reference comparisons use normalized, same-state viewport captures.

### Iteration 2 and final

- P0: none.
- P1: none.
- P2: none remaining.
- P3: dense compact horizons intentionally truncate long step labels while preserving every stage marker, status, sequence, and outcome. Full text is present in the patient agent and associated details.
- P3: forced local backend restarts generated historical bootstrap-timeout and LCP telemetry warnings. The stable stack completed every tested route and interaction without application exceptions; subsequent client-side navigation remained responsive.

## Required surface checks

- Typography: restrained clinical hierarchy, compact operational labels, tabular metrics, and readable patient copy preserve the selected reference's professional density.
- Spacing and layout: the forest sidebar, cream canvas, fixed operating header, exception-first decisions, longitudinal care rails, and contextual right panels remain aligned across all nine screens.
- Colors and tokens: forest, warm cream, amber human-stop, muted waiting, red risk, and green completion states map consistently across clinical, communication, and financial work.
- Imagery: Sarah's generated fictional portrait is sharp, naturally cropped, and integrated as a real Next Image asset. Existing synthetic lesion imagery remains source-backed and includes useful alt text.
- Icons: Lucide icons are used consistently with matched stroke weight, sizing, and semantic meaning. No fake SVG or CSS-art assets are present.
- Copy and content: every screen names the work, reason for stopping, accountable owner, permission boundary, next action, and downstream release in plain clinical language.
- Viewport resilience: desktop and mobile have no document-level horizontal overflow. Mobile collapses to a menu, stacks stats and content, preserves primary actions, and keeps AgentDock available.
- Accessibility: semantic headings, landmarks, buttons, links, dialogs, tab states, search labels, image alt text, keyboard focusability, and practical mobile targets are present.
- States and interactions verified in-browser:
  - Today decision review and six-action release
  - patient portfolio search and Sarah navigation
  - Sarah biopsy-plan approval
  - schedule visit selection
  - grounded patient-response approval and delivery
  - pathology disposition and closure receipt
  - revenue exception approval and release
  - Operations intelligence switching
  - patient visit confirmation
- Runtime checks: TypeScript, ESLint, all 56 component tests across 19 files, and the Next.js production build pass. Twenty routes were generated.

## Final assessment

The platform now reads as one AI operating layer rather than separate EHR modules: clinicians manage only consequential stops, every patient retains a visible long-horizon agent, communication and revenue remain linked to the same care goal, and the patient sees a simpler version of the identical plan. The selected reference's hierarchy, palette, density, and human-boundary model are preserved across the complete clinic workflow.

final result: passed
