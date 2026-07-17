import { z } from "zod";

import { ApiError } from "@/lib/api/client";
import type { DemoBootstrap } from "@/lib/api/types";

const personaSchema = z.enum(["patient", "provider", "clinical", "biller", "owner"]);
const objectOrNull = z.object({}).loose().nullable();

const demoBootstrapSchema = z.object({
  session: z.object({
    authenticated: z.boolean(),
    persona: personaSchema,
    presenter: z.boolean(),
  }).loose(),
  organization: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    location: z.string().min(1),
    timezone: z.string().min(1),
  }).loose(),
  scenario: z.object({
    id: z.string().min(1),
    chapter: z.number(),
    chapterLabel: z.string().min(1),
    currentTime: z.string().min(1),
    modelMode: z.enum(["live", "deterministic_fallback"]),
  }).loose(),
  personas: z.array(z.object({ id: personaSchema }).loose()).min(1),
  intake: objectOrNull,
  commandCenter: objectOrNull,
  patient: objectOrNull,
  schedule: z.array(z.unknown()),
  queues: z.array(z.unknown()),
  encounter: objectOrNull,
  pathology: objectOrNull,
  conversations: z.array(z.unknown()),
  claims: z.array(z.unknown()),
  financialContext: objectOrNull,
  metrics: z.array(z.unknown()),
  health: z.array(z.unknown()),
  triggerIds: objectOrNull,
}).loose();

export function parseDemoBootstrap(value: unknown): DemoBootstrap {
  const parsed = demoBootstrapSchema.safeParse(value);
  if (!parsed.success) {
    throw new ApiError("The API returned an invalid workspace response.", 502, parsed.error.issues);
  }
  return parsed.data as unknown as DemoBootstrap;
}
