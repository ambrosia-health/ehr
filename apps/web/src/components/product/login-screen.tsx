"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  CircleDollarSign,
  HeartPulse,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiAction, endpoints } from "@/lib/api/client";
import { demoBootstrapQueryKey } from "@/lib/api/hooks";
import type { Persona } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const loginSchema = z.object({
  persona: z.enum(["patient", "provider", "clinical", "biller", "owner"]),
  presenterCode: z.string(),
});

type LoginValues = z.infer<typeof loginSchema>;

const personas: Array<{ id: Persona; name: string; title: string; icon: typeof UserRound; destination: string }> = [
  { id: "provider", name: "Dr. Maya Chen", title: "Dermatologist", icon: Stethoscope, destination: "/command-center" },
  { id: "patient", name: "Sarah Mitchell", title: "Patient", icon: UserRound, destination: "/patient/start" },
  { id: "clinical", name: "Jordan Lee", title: "Clinical coordinator", icon: UsersRound, destination: "/command-center" },
  { id: "biller", name: "Priya Shah", title: "RCM specialist", icon: CircleDollarSign, destination: "/rcm" },
  { id: "owner", name: "Alex Morgan", title: "MSO owner", icon: BarChart3, destination: "/mso" },
];

export function LoginScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { sessionLifecycle, startSession } = useDemoSession();
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { persona: "provider", presenterCode: "" },
  });
  const selectedPersona = useWatch({ control: form.control, name: "persona" });

  useEffect(() => {
    if (sessionLifecycle === "ended") queryClient.removeQueries({ queryKey: demoBootstrapQueryKey });
  }, [queryClient, sessionLifecycle]);

  useEffect(() => {
    if (selectedPersona !== "owner") form.setValue("presenterCode", "", { shouldDirty: false });
  }, [form, selectedPersona]);

  async function submit(values: LoginValues) {
    setSubmitting(true);
    setMessage(null);
    const presenterRequested = values.presenterCode.length > 0;

    if (presenterRequested && values.persona !== "owner") {
      setMessage("Presenter access starts with the MSO owner persona. Choose Alex Morgan, then enter the presenter credential.");
      setSubmitting(false);
      return;
    }

    try {
      await apiAction(
        endpoints.demoSession,
        { persona: values.persona, presenterCode: values.presenterCode || undefined },
      );
      queryClient.removeQueries({ queryKey: demoBootstrapQueryKey });
      startSession(values.persona);
      const destination = personas.find((persona) => persona.id === values.persona)?.destination ?? "/command-center";
      router.push(destination);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "We could not start the demo session.");
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[var(--patient-background)] px-4 py-8 sm:px-6 lg:py-12">
      <div className="mx-auto grid max-w-6xl overflow-hidden rounded-2xl border bg-card shadow-[0_24px_80px_-36px_rgba(27,54,45,0.35)] lg:grid-cols-[1.05fr_0.95fr]">
        <section className="p-6 sm:p-10 lg:p-12">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground"><HeartPulse className="size-5" /></span>
            <div><p className="font-semibold tracking-[-0.03em]">Ambrosia Health</p><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">AI-native dermatology OS</p></div>
          </div>
          <div className="mt-10">
            <StatusBadge tone="success">Synthetic demo environment</StatusBadge>
            <h1 className="mt-4 max-w-xl text-balance text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">One continuous record from changing lesion to closed loop.</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">Follow Sarah Mitchell across patient access, a dermatologist-reviewed encounter, pathology safety, payment, and practice performance—without losing the clinical thread.</p>
          </div>

          <form className="mt-8 space-y-6" onSubmit={form.handleSubmit(submit)}>
            <fieldset>
              <legend className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">Enter as</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {personas.map((persona) => {
                  const Icon = persona.icon;
                  const selected = selectedPersona === persona.id;
                  return (
                    <button
                      key={persona.id}
                      type="button"
                      className={cn("flex items-center gap-3 rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", selected ? "border-primary bg-primary/6" : "bg-background hover:bg-muted/60")}
                      onClick={() => form.setValue("persona", persona.id, { shouldDirty: true })}
                      aria-pressed={selected}
                      data-testid={`persona-${persona.id}`}
                    >
                      <span className={cn("flex size-9 items-center justify-center rounded-md", selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}><Icon className="size-4" /></span>
                      <span><span className="block text-xs font-semibold">{persona.name}</span><span className="block text-[11px] text-muted-foreground">{persona.title}</span></span>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {selectedPersona === "owner" ? <div className="rounded-lg border bg-muted/30 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold"><LockKeyhole className="size-3.5" /> Presenter access <span className="font-normal text-muted-foreground">(optional)</span></div>
              <Label htmlFor="presenter-code" className="sr-only">Presenter access code</Label>
              <Input id="presenter-code" className="mt-3 bg-background" type="password" placeholder="Access code" autoComplete="one-time-code" {...form.register("presenterCode")} />
              <p className="mt-2 text-[11px] leading-4 text-muted-foreground">Unlocks persona switching, canonical reset, simulated events, and service health. The domain API validates this separate capability.</p>
            </div> : null}

            {message ? <Alert variant="destructive"><ShieldCheck className="size-4" /><AlertTitle>Session not started</AlertTitle><AlertDescription>{message}</AlertDescription></Alert> : null}
            <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={submitting} data-testid="enter-demo">
              {submitting ? "Opening workspace…" : "Enter Ambrosia"} <ArrowRight className="size-4" />
            </Button>
          </form>
        </section>

        <aside className="relative hidden overflow-hidden border-l bg-primary p-10 text-primary-foreground lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.15em] text-primary-foreground/70"><Sparkles className="size-4" /> Today’s demo</div>
            <h2 className="mt-5 text-3xl font-semibold tracking-[-0.04em]">From concern to closure—with every handoff visible.</h2>
            <p className="mt-3 text-sm leading-6 text-primary-foreground/70">One clinician review creates the signed note, procedure, specimen, order, aftercare, claim, and closure task as linked records.</p>
          </div>
          <ol className="space-y-0">
            {["Patient starts a lesion visit", "AI prepares the encounter", "Clinician reviews every proposal", "Pathology closes the loop", "RCM recovers revenue", "MSO sees operating leverage"].map((chapter, index) => (
              <li key={chapter} className="flex gap-4 border-t border-white/15 py-4">
                <span className="font-mono text-xs text-primary-foreground/55">0{index + 1}</span>
                <span className="text-sm font-medium">{chapter}</span>
              </li>
            ))}
          </ol>
          <p className="text-xs leading-5 text-primary-foreground/65">All names, records, images, claims, and financial amounts in this environment are synthetic.</p>
        </aside>
      </div>
    </main>
  );
}
