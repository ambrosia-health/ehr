# Design QA — Ambrosia professional option 3

## Visual source and evidence

- Approved source: option 3, the light institutional “focused decision brief.”
- Normalized source capture: `.product-design/qa/option-3/reference-patient-viewport.jpg`.
- Final implementation capture: `.product-design/qa/option-3/implementation-patient-final.jpg`.
- Required source-left / implementation-right comparison: `.product-design/qa/option-3/comparison-final-reference-left-implementation-right.jpg`.
- Comparison viewport: 1265 × 712, Patients active, Sarah Mitchell’s first decision open and unapproved.
- Additional implementation captures cover Today, Patients, and Practice in `.product-design/qa/option-3/`.

## Comparison history

### Iteration 1

- P0: none.
- P1, decision hierarchy: the biopsy question wrapped to two lines, making the decision block taller than the source.
- P1, imagery: the clinical image crop hid most of the ruler and the dermoscopy crop was much tighter than the source.
- P2, page measure: the patient document was slightly wider than the source.

Fixes:

- Reduced the question’s responsive type ceiling so it remains a single decisive line at desktop widths.
- Adjusted the real clinical photograph’s focal point to retain the measurement ruler.
- Reframed the real dermoscopy asset against black so the complete lesion and optical field read like the source.
- Tightened the document measure from 1120 px to 1080 px and reduced the decision row’s vertical rhythm.

### Iteration 2 and final

- P0: none.
- P1: none.
- P2: none.
- P3, accepted asset fidelity: the implementation uses the repository’s owned synthetic patient and clinical photography, so fine image detail differs from the generated concept while composition, crop, and density match.
- P3, accepted icon fidelity: the source’s abstract brand glyph is represented by the closest existing Lucide glyph; no hand-built SVG or CSS asset was introduced.

## Required surface checks

- Shell: solid white 72 px app bar, blue active underline, three durable destinations, and restrained clinician identity match the source hierarchy. The former dark green sidebar is gone.
- Patient brief: patient context, decision, recommendation, confidence, deadline, primary action, paired images, and evidence table read as one bordered document rather than a card stack.
- Today: one prioritized decision, ruled evidence, a compact clinic table, and a quiet automation receipt keep attention on medical judgment.
- Patients: search, state filters, compact columns, one next action, and Sarah’s deep link remain functional without oversized cards.
- Practice: operating state, automation health, admin receipts, and advanced controls use flat, dense sections with thin rules.
- Typography and spacing: restrained Geist hierarchy, compact operational labels, 4–8 px radii, minimal shadow, and consistent 1080–1240 px page measures are applied across all routes.
- Color: mineral canvas, ink foreground, clinical blue actions, teal evidence/health, amber deadlines, and red-only safety semantics replace the wellness-green palette.
- Imagery: all patient and lesion assets use optimized `next/image`, useful alt text, explicit responsive sizes, and verified above-the-fold loading.
- Accessibility: headings, landmarks, table headers, links, buttons, dialogs, native disclosures, progress bars, labels, focus states, image alternatives, and polite approval status are present.
- Responsive behavior: the desktop navigation becomes a right-side mobile sheet; focused shell tests verify that all destinations remain reachable and the sheet closes after navigation.

## Interaction and runtime checks

- In-app Browser:
  - Today evidence expands inline; approving Sarah advances immediately to Jordan and updates the status receipt.
  - Patient Modify opens the editor and persists revised wording; Approve & release disables after release.
  - Patient search narrows to Sarah and the row opens the focused brief.
  - Practice Advanced controls opens and exposes policy metadata.
  - Command-K opens Ask Ambrosia; a suggested command returns a reviewable-plan receipt.
- Browser health: no application errors or warnings. Local-only Vercel Analytics and Speed Insights script notices remain informational logs, as expected outside a Vercel deployment.
- Automated gates: ESLint passed; TypeScript passed; all 26 Vitest tests across seven files passed; the optimized Next.js production build passed.
- Route surface: the production build exposes only `/`, `/_not-found`, `/patients`, `/patients/sarah-mitchell`, and `/practice`.
- Performance: final warm local document averages were 1.37 ms for `/`, 1.18 ms for `/patients`, 1.19 ms for `/patients/sarah-mitchell`, and 1.11 ms for `/practice`; all remained below the recorded pre-redesign measurements.

## Final assessment

The implementation now follows option 3’s professional clinical-document model across the entire product. The most consequential visual mismatches found in the first direct comparison were corrected and the final normalized side-by-side has no P0, P1, or P2 defects.

final result: passed
