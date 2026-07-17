# Sarah Mitchell demo

Target: 12–15 minutes. The audience should leave with one idea: Ambrosia operates the complete dermatology practice through one connected clinical, patient-engagement and financial system.

Every person, image, message, result, claim and dollar is synthetic. Say once at the start: “Core Ambrosia records and workflows are functional; external healthcare and payment networks are deterministic simulations; AI runs on a pinned open-weights model on Modal when its output and provenance validate, with a visibly labeled deterministic fallback.”

Canonical personas: Sarah Mitchell (patient), Dr. Maya Chen (provider), Jordan Lee (clinical coordinator), Priya Shah (RCM specialist), and Alex Morgan (MSO owner).

## Preflight

For the managed hosted demo, open [ambrosia-ehr.vercel.app](https://ambrosia-ehr.vercel.app) and use the current presenter access code from the approved secret-sharing channel. The Vercel-to-Modal-to-Neon bindings, synthetic data, and model endpoint are platform-managed; do not copy cloud credentials or connection strings into a presenter machine.

For the zero-credential local demo:

```bash
make reset
make dev
# In a second terminal:
make demo-health
```

At the login screen, use the local presenter code from `.env` (`ambrosia-demo` in an untouched local template), then open the unlinked `/presenter` route if needed. Hosted environments use a rotated managed code, never the published local value. Confirm the control shows the canonical Sarah scenario, the model indicator is either `Live` with the pinned revision or `Deterministic fallback`, and simulated time is at the initial date. Keep browser zoom at 100% and close notifications containing unrelated data.

## Journey

| Chapter | Presenter action | Evidence to point out |
|---|---|---|
| 1. Patient initiation · 1:30 | As Sarah Mitchell, report a changing mole on the left posterior shoulder, answer warning-sign questions, attach the supplied synthetic photo, choose an offered slot and start intake. | Conversational follow-up, urgent-symptom screen, real appointment ID/state, preparation instructions. |
| 2. Intake and coverage · 1:00 | Complete lesion history, medications, allergies, personal/family skin-cancer history, pharmacy, insurance and consent; run eligibility and show estimate. | Normalized chart facts—not a PDF/blob; simulated payer source disclosed; benefits and patient responsibility reconcile. |
| 3. Command center · 1:00 | Switch to clinical staff/provider; open today’s schedule and Sarah’s readiness row. | Intake/coverage readiness, priority concern, work queues and AI pre-visit summary derived from the same record. |
| 4. AI-native encounter · 2:00 | Open Sarah’s encounter; review timeline and source-linked summary; play/use the synthetic transcript and generate the structured draft. | Transcript-to-note structure, draft/proposed labeling, model/fallback identity, human editability and provenance. |
| 5. Lesion intelligence · 1:00 | Select left posterior shoulder on the body map; compare prior/current image and record dimensions, morphology, border, pigment, change and symptoms. | One persistent lesion with ordered observations and linked photographs across time. |
| 6. Biopsy review-and-complete · 2:00 | Choose shave biopsy. Inspect proposed note/procedure/consent/specimen/pathology order/coding/aftercare/tasks; approve as clinician. | Nothing executes before review. Approval atomically signs the note and creates the coherent clinical/claim/audit graph. Signed text is locked; amendment remains available. |
| 7. Patient follow-up · 1:00 | Switch to Sarah; show visit summary, aftercare, result timing and warning signs. Ask the seeded routine question; return to care-team view. | AI drafts only from approved instructions; uncertainty routes to staff; delivery is explicitly simulated. |
| 8. Pathology safety · 1:30 | In presenter mode advance time and trigger pathology arrival; switch to provider, open the result, compare its links, review and approve the patient-friendly message/follow-up. | Patient → lesion/image → procedure → specimen → order → result chain; accountable task, review/notification/closure tracking; duplicate trigger is safe. |
| 9. Revenue cycle · 1:30 | Open Sarah’s claim and advance simulated responses through validated, submitted, accepted, adjudicated and paid. Then open the seeded denied claim, review evidence/recommendation, draft appeal, resubmit and show recovery. | Structured lines/events/payments/balance; simulated clearinghouse/remit labels; denial history is retained and recovered revenue is traceable. |
| 10. MSO outcomes · 1:00 | Open the owner dashboard and filter/time-window the practice metrics. | Appointment conversion, no-shows, response and signing time, pathology closure, acceptance/denial, A/R, revenue/visit, documentation time and work-avoided assumptions calculated from source records. |

## Critical assertions

During chapter 6, emphasize the record boundary: AI proposed a bundle; the clinician approved an exact version; the server re-authorized and committed it; audit and provenance show who/what/when. During chapter 8, emphasize safety: an open pathology result cannot disappear because review, notification and closure are independent accountable states. During chapter 9, emphasize operating leverage: clinical evidence flows into a structured claim and denial recovery without re-keying or erasing payer history.

## Presenter controls

- **Persona** changes the signed demo session; it does not merely hide UI controls.
- **Reset** targets only the canonical synthetic organization and restores a known seed version.
- **Advance time** moves the scenario clock and evaluates due durable events; it does not change the computer clock.
- **Pathology arrival / claim response** invoke idempotent provider adapters and normal domain commands.
- **Model indicator** discloses live Modal inference versus deterministic fallback.
- **Health** confirms API/database/seed/workflow state before the audience arrives.

Presenter controls must be absent in normal product mode. Never demonstrate them in an environment connected to real data/providers.

## Recovery without developer tools

| Symptom | Presenter action |
|---|---|
| Model is cold/unavailable | Continue with the labeled deterministic fallback; the proposal schema and approval path are identical. |
| A timeline event was clicked twice | Refresh the view; the idempotent event should show its original completed result, not duplicate records. |
| State drifted during rehearsal | Use presenter **Reset scenario**, sign in again, and run the built-in health check. |
| External delivery appears pending | Explain the explicit simulator, trigger the supplied response once, and show its integration event/task. |
| Any control breaks or health is red | Stop the walkthrough rather than claim success; use `make reset` and `make demo-health` before resuming. |

## Final line

“Sarah experienced one continuous journey; the practice received one coherent chart, safety workflow and financial record; the MSO can see and improve the operating system behind both.”
