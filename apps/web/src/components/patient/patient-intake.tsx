"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CalendarCheck2,
  Camera,
  Check,
  CheckCircle2,
  Clock3,
  CreditCard,
  FileImage,
  HeartPulse,
  Info,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, endpoints } from "@/lib/api/client";
import { useDemoBootstrap } from "@/lib/api/hooks";
import type { BookedAppointment, IntakeSubmission, IntakeTriageReceipt } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const intakeSchema = z.object({
  reason: z.string().min(10, "Tell us a little more about what brought you in."),
  firstNoticed: z.string().min(1, "Choose when you first noticed the change."),
  change: z.array(z.string()).min(1, "Choose at least one change."),
  symptoms: z.array(z.string()).min(1, "Choose symptoms, or select none."),
  medications: z.string().min(1, "List medications, or enter none."),
  allergies: z.string().min(1, "List allergies, or enter none."),
  personalSkinCancerHistory: z.string().min(1, "Enter your personal skin-cancer history, or none."),
  familySkinCancerHistory: z.string().min(1, "Enter your family skin-cancer history, or none."),
  pharmacy: z.string().min(3, "Enter your preferred pharmacy."),
  urgentSigns: z.array(z.string()).min(1, "Answer the safety question before continuing."),
  appointmentSlot: z.string().min(1, "Choose an appointment time."),
  insurancePayer: z.string().min(2, "Enter your insurance carrier."),
  insuranceMemberId: z.string().min(4, "Enter a valid member ID."),
  treatmentConsent: z.boolean().refine((value) => value, "Treatment consent is required."),
  privacyConsent: z.boolean().refine((value) => value, "Privacy acknowledgment is required."),
  photographyConsent: z.boolean().refine((value) => value, "Clinical photography consent is required."),
});

type IntakeValues = z.infer<typeof intakeSchema>;

const stepFields: Array<Array<keyof IntakeValues>> = [
  ["reason", "firstNoticed"],
  ["change", "symptoms"],
  ["medications", "allergies", "personalSkinCancerHistory", "familySkinCancerHistory", "pharmacy"],
  ["urgentSigns"],
  [],
  ["appointmentSlot"],
  ["insurancePayer", "insuranceMemberId"],
  ["treatmentConsent", "privacyConsent", "photographyConsent"],
];

const steps = ["Concern", "Changes", "Health", "Safety", "Photo", "Time", "Coverage", "Review"];
const changes = ["Darker color", "Wider or larger", "Irregular edge", "Raised surface", "New colors"];
const symptoms = ["Itching", "Tenderness", "Bleeding", "Crusting", "No symptoms"];
const urgentSigns = ["Bleeding that will not stop", "Rapid change over days", "Fever or spreading redness", "Severe pain", "None of these"];
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function PatientIntake() {
  const router = useRouter();
  const { setIntakeTriage } = useDemoSession();
  const { data, mode, error, refetch } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const stepHeadingRef = useRef<HTMLHeadingElement>(null);
  const intakeMountedRef = useRef(false);
  const [submissionMessage, setSubmissionMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const form = useForm<IntakeValues>({
    resolver: zodResolver(intakeSchema),
    mode: "onTouched",
    defaultValues: {
      reason: "",
      firstNoticed: "",
      change: [],
      symptoms: [],
      medications: "",
      allergies: "",
      personalSkinCancerHistory: "",
      familySkinCancerHistory: "",
      pharmacy: "",
      urgentSigns: [],
      appointmentSlot: "",
      insurancePayer: "",
      insuranceMemberId: "",
      treatmentConsent: false,
      privacyConsent: false,
      photographyConsent: false,
    },
  });

  useEffect(() => {
    if (!data?.intake) return;
    const draft = data.intake.draft;
    if (!form.formState.isDirty) {
      form.reset({
        reason: draft.reason,
        firstNoticed: draft.firstNoticed,
        change: draft.change,
        symptoms: draft.symptoms,
        medications: draft.medications.join("; "),
        allergies: draft.allergies.join("; "),
        personalSkinCancerHistory: draft.personalSkinCancerHistory,
        familySkinCancerHistory: draft.familySkinCancerHistory,
        pharmacy: draft.pharmacy,
        urgentSigns: draft.urgentSigns,
        appointmentSlot: "",
        insurancePayer: data.intake.eligibility.payer,
        insuranceMemberId: data.intake.eligibility.memberId,
        treatmentConsent: false,
        privacyConsent: false,
        photographyConsent: false,
      });
      return;
    }
    if (!form.getFieldState("insurancePayer").isDirty) form.setValue("insurancePayer", data.intake.eligibility.payer);
    if (!form.getFieldState("insuranceMemberId").isDirty) form.setValue("insuranceMemberId", data.intake.eligibility.memberId);
  }, [data, form]);

  useEffect(() => {
    if (!intakeMountedRef.current) {
      intakeMountedRef.current = true;
      return;
    }
    stepHeadingRef.current?.focus();
  }, [step]);
  const values = useWatch({ control: form.control }) as IntakeValues;

  if (mode === "loading") return <div className="mx-auto max-w-5xl px-4 py-10"><PageLoading label="Opening your secure intake" /></div>;
  if (!data) return <div className="mx-auto max-w-5xl px-4 py-10"><PageError error={error} retry={refetch} /></div>;
  if (!data.intake || !data.patient) return <div className="mx-auto max-w-5xl px-4 py-10"><WorkspaceUnavailable title="Patient intake is not available for this role" /></div>;

  const progress = ((step + 1) / steps.length) * 100;
  const safetyAnswered = values.urgentSigns.length > 0;
  const hasUrgentSign = values.urgentSigns.some((item) => item !== "None of these");
  const selectedSlot = data.intake.availableSlots.find((slot) => slot.id === values.appointmentSlot);
  const eligibility = data.intake.eligibility;
  const overviewImage = data.patient.lesion.overviewImage;

  function toggleArray(field: "change" | "symptoms" | "urgentSigns", value: string, checked: boolean) {
    const current = form.getValues(field);
    let next = checked ? [...current.filter((item) => item !== value), value] : current.filter((item) => item !== value);
    if (field === "symptoms") {
      next = value === "No symptoms" && checked ? [value] : next.filter((item) => item !== "No symptoms");
    }
    if (field === "urgentSigns") {
      next = value === "None of these" && checked ? [value] : next.filter((item) => item !== "None of these");
    }
    form.setValue(field, next, { shouldDirty: true, shouldValidate: true });
  }

  async function nextStep() {
    const valid = stepFields[step].length === 0 || (await form.trigger(stepFields[step], { shouldFocus: true }));
    if (valid) setStep((current) => Math.min(current + 1, steps.length - 1));
  }

  async function submit(valuesToSubmit: IntakeValues) {
    setSubmitting(true);
    setSubmissionMessage(null);
    setIntakeTriage(null);
    const splitList = (value: string) => value.split(";").map((item) => item.trim()).filter(Boolean);
    const submission: IntakeSubmission = {
      reason: valuesToSubmit.reason,
      firstNoticed: valuesToSubmit.firstNoticed,
      change: valuesToSubmit.change,
      symptoms: valuesToSubmit.symptoms,
      urgentSigns: valuesToSubmit.urgentSigns,
      appointmentSlot: valuesToSubmit.appointmentSlot,
      insurancePayer: valuesToSubmit.insurancePayer,
      insuranceMemberId: valuesToSubmit.insuranceMemberId,
      medications: splitList(valuesToSubmit.medications),
      allergies: splitList(valuesToSubmit.allergies),
      personalSkinCancerHistory: valuesToSubmit.personalSkinCancerHistory,
      familySkinCancerHistory: valuesToSubmit.familySkinCancerHistory,
      pharmacy: valuesToSubmit.pharmacy,
      consents: { treatment: valuesToSubmit.treatmentConsent, privacy: valuesToSubmit.privacyConsent, photography: valuesToSubmit.photographyConsent },
      image: { fileId: overviewImage.id, sha256: overviewImage.sha256, synthetic: true },
    };
    try {
      const receipt = await apiRequest<{ appointment: BookedAppointment; triage: IntakeTriageReceipt }>(
        endpoints.intake,
        { method: "POST", body: submission },
      );
      if (receipt.appointment.slotId !== valuesToSubmit.appointmentSlot) {
        throw new Error("The server confirmed a different appointment slot. Nothing was changed in this view; refresh availability and try again.");
      }
      setIntakeTriage(receipt.triage);
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
      router.push("/patient/confirmation");
    } catch (submitError) {
      setSubmissionMessage(submitError instanceof Error ? submitError.message : "We could not submit your intake.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-10">
      <div className="mt-5 grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-24">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">Your visit</p>
            <ol className="mt-4 space-y-1">
              {steps.map((label, index) => (
                <li key={label} className={cn("flex items-center gap-3 rounded-md px-3 py-2 text-xs", index === step && "bg-primary/8 font-semibold text-primary", index < step && "text-foreground", index > step && "text-muted-foreground")}>
                  <span className={cn("flex size-5 items-center justify-center rounded-full border font-mono text-[9px]", index < step && "border-primary bg-primary text-primary-foreground", index === step && "border-primary text-primary")}>
                    {index < step ? <Check className="size-3" /> : index + 1}
                  </span>
                  {label}
                </li>
              ))}
            </ol>
            <div className="mt-6 rounded-lg border bg-card p-4">
              <div className="flex items-center gap-2 text-xs font-semibold"><ShieldCheck className="size-4 text-primary" /> Private & secure</div>
              <p className="mt-2 text-[11px] leading-4 text-muted-foreground">Your answers go directly to your care team and become part of a normalized intake record.</p>
            </div>
          </div>
        </aside>

        <div>
          <div className="mb-4 flex items-center justify-between text-xs text-muted-foreground lg:hidden"><span>{steps[step]}</span><span>{step + 1} of {steps.length}</span></div>
          <Progress value={progress} className="mb-5 h-1.5" aria-label={`Intake progress: step ${step + 1} of ${steps.length}`} />
          <Card className="overflow-hidden shadow-sm">
            <CardContent className="p-0">
              <form onSubmit={form.handleSubmit(submit)}>
                <div className="min-h-[520px] p-5 sm:p-8">
                  {step === 0 ? (
                    <div className="space-y-7">
                      <div><StatusBadge tone="info">About 4 minutes</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">Let’s understand what changed.</h1><p className="mt-2 text-sm leading-6 text-muted-foreground">Your answers help the care team choose the right visit and prepare before you arrive.</p></div>
                      <div><Label htmlFor="reason">What would you like us to look at?</Label><Textarea id="reason" className="mt-2 min-h-28 bg-background" {...form.register("reason")} aria-invalid={Boolean(form.formState.errors.reason)} aria-describedby={form.formState.errors.reason ? "reason-error" : undefined} /><p id="reason-error" role={form.formState.errors.reason ? "alert" : undefined} className="mt-1.5 text-xs text-destructive">{form.formState.errors.reason?.message}</p></div>
                      <div><Label htmlFor="first-noticed">When did you first notice the change?</Label><select id="first-noticed" className="mt-2 flex h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50" {...form.register("firstNoticed")} aria-invalid={Boolean(form.formState.errors.firstNoticed)} aria-describedby={form.formState.errors.firstNoticed ? "first-noticed-error" : undefined}><option value="">Choose a timeframe</option><option>Within the last week</option><option>1–4 weeks ago</option><option>1–3 months ago</option><option>3–6 months ago</option><option>More than 6 months ago</option></select><p id="first-noticed-error" role={form.formState.errors.firstNoticed ? "alert" : undefined} className="mt-1.5 text-xs text-destructive">{form.formState.errors.firstNoticed?.message}</p></div>
                    </div>
                  ) : null}

                  {step === 1 ? (
                    <div className="space-y-8">
                      <div><StatusBadge tone="ai"><Sparkles className="size-3" /> Helpful follow-up</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">What have you noticed?</h1><p className="mt-2 text-sm text-muted-foreground">Select everything that applies.</p></div>
                      <fieldset aria-invalid={Boolean(form.formState.errors.change)} aria-describedby={form.formState.errors.change ? "change-error" : undefined}><legend className="text-sm font-semibold">Changes over time</legend><div className="mt-3 grid gap-2 sm:grid-cols-2">{changes.map((item) => <label key={item} className={cn("flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm", values.change.includes(item) && "border-primary bg-primary/5")}><Checkbox checked={values.change.includes(item)} onCheckedChange={(checked) => toggleArray("change", item, checked === true)} />{item}</label>)}</div><p id="change-error" role={form.formState.errors.change ? "alert" : undefined} className="mt-1.5 text-xs text-destructive">{form.formState.errors.change?.message}</p></fieldset>
                      <fieldset aria-invalid={Boolean(form.formState.errors.symptoms)} aria-describedby={form.formState.errors.symptoms ? "symptoms-error" : undefined}><legend className="text-sm font-semibold">Symptoms</legend><div className="mt-3 grid gap-2 sm:grid-cols-2">{symptoms.map((item) => <label key={item} className={cn("flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm", values.symptoms.includes(item) && "border-primary bg-primary/5")}><Checkbox checked={values.symptoms.includes(item)} onCheckedChange={(checked) => toggleArray("symptoms", item, checked === true)} />{item}</label>)}</div><p id="symptoms-error" role={form.formState.errors.symptoms ? "alert" : undefined} className="mt-1.5 text-xs text-destructive">{form.formState.errors.symptoms?.message}</p></fieldset>
                    </div>
                  ) : null}

                  {step === 2 ? (
                    <div className="space-y-6">
                      <div><StatusBadge tone="info"><HeartPulse className="size-3" /> Health history</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">Help your dermatologist prepare.</h1><p className="mt-2 text-sm leading-6 text-muted-foreground">Review each field. Separate multiple medications or allergies with semicolons.</p></div>
                      <div className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="medications">Current medications</Label><Textarea id="medications" className="mt-1.5 min-h-20" {...form.register("medications")} aria-invalid={Boolean(form.formState.errors.medications)} aria-describedby={form.formState.errors.medications ? "medications-error" : undefined} /><p id="medications-error" role={form.formState.errors.medications ? "alert" : undefined} className="mt-1 text-xs text-destructive">{form.formState.errors.medications?.message}</p></div><div><Label htmlFor="allergies">Allergies and reactions</Label><Textarea id="allergies" className="mt-1.5 min-h-20" {...form.register("allergies")} aria-invalid={Boolean(form.formState.errors.allergies)} aria-describedby={form.formState.errors.allergies ? "allergies-error" : undefined} /><p id="allergies-error" role={form.formState.errors.allergies ? "alert" : undefined} className="mt-1 text-xs text-destructive">{form.formState.errors.allergies?.message}</p></div></div>
                      <div className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="personal-history">Personal skin-cancer history</Label><Textarea id="personal-history" className="mt-1.5 min-h-20" {...form.register("personalSkinCancerHistory")} aria-invalid={Boolean(form.formState.errors.personalSkinCancerHistory)} aria-describedby={form.formState.errors.personalSkinCancerHistory ? "personal-history-error" : undefined} /><p id="personal-history-error" role={form.formState.errors.personalSkinCancerHistory ? "alert" : undefined} className="mt-1 text-xs text-destructive">{form.formState.errors.personalSkinCancerHistory?.message}</p></div><div><Label htmlFor="family-history">Family skin-cancer history</Label><Textarea id="family-history" className="mt-1.5 min-h-20" {...form.register("familySkinCancerHistory")} aria-invalid={Boolean(form.formState.errors.familySkinCancerHistory)} aria-describedby={form.formState.errors.familySkinCancerHistory ? "family-history-error" : undefined} /><p id="family-history-error" role={form.formState.errors.familySkinCancerHistory ? "alert" : undefined} className="mt-1 text-xs text-destructive">{form.formState.errors.familySkinCancerHistory?.message}</p></div></div>
                      <div><Label htmlFor="pharmacy">Preferred pharmacy</Label><Input id="pharmacy" className="mt-1.5" {...form.register("pharmacy")} aria-invalid={Boolean(form.formState.errors.pharmacy)} aria-describedby={form.formState.errors.pharmacy ? "pharmacy-error" : undefined} /><p id="pharmacy-error" role={form.formState.errors.pharmacy ? "alert" : undefined} className="mt-1 text-xs text-destructive">{form.formState.errors.pharmacy?.message}</p></div>
                    </div>
                  ) : null}

                  {step === 3 ? (
                    <div className="space-y-7">
                      <div><StatusBadge tone="warning"><HeartPulse className="size-3" /> Safety check</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">Do any urgent warning signs apply?</h1><p className="mt-2 text-sm leading-6 text-muted-foreground">This helps us direct you to the right level of care. It is not a diagnosis.</p></div>
                      <fieldset className="space-y-2" aria-invalid={Boolean(form.formState.errors.urgentSigns)} aria-describedby={!safetyAnswered ? "urgent-signs-error" : undefined}>{urgentSigns.map((item) => <label key={item} className={cn("flex cursor-pointer items-center gap-3 rounded-lg border p-4 text-sm", values.urgentSigns.includes(item) && "border-primary bg-primary/5")}><Checkbox checked={values.urgentSigns.includes(item)} onCheckedChange={(checked) => toggleArray("urgentSigns", item, checked === true)} /><span className="flex-1">{item}</span></label>)}</fieldset>
                      {!safetyAnswered ? <Alert id="urgent-signs-error" role={form.formState.errors.urgentSigns ? "alert" : undefined}><Info className="size-4" /><AlertTitle>Answer required</AlertTitle><AlertDescription>{form.formState.errors.urgentSigns?.message ?? "Select every warning sign that applies, or explicitly choose “None of these.”"}</AlertDescription></Alert> : hasUrgentSign ? <Alert className="border-rose-200 bg-rose-50"><AlertTriangle className="size-4 text-rose-700" /><AlertTitle>Same-day clinical review recommended</AlertTitle><AlertDescription>Continue to send this information to the care team. If symptoms are severe or worsening, seek urgent care or call 911.</AlertDescription></Alert> : <Alert className="border-emerald-200 bg-emerald-50"><CheckCircle2 className="size-4 text-emerald-700" /><AlertTitle>No urgent warning signs reported</AlertTitle><AlertDescription>We can continue with dermatology scheduling.</AlertDescription></Alert>}
                    </div>
                  ) : null}

                  {step === 4 ? (
                    <div className="space-y-6">
                      <div><StatusBadge tone="info"><Camera className="size-3" /> Clinical photo</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">Add a clear photo of the spot.</h1><p className="mt-2 text-sm leading-6 text-muted-foreground">Use bright, even light. Include one close view and enough surrounding skin for orientation.</p></div>
                      <div className="grid gap-5 md:grid-cols-[1fr_220px]">
                        <div className="relative aspect-[3/2] overflow-hidden rounded-xl border bg-muted"><Image src={data.patient.lesion.overviewImage.url} alt={`Synthetic clinical photograph for ${data.patient.name}: ${data.patient.lesion.location}`} fill className="object-cover" sizes="(max-width: 768px) 100vw, 500px" priority /></div>
                        <div className="space-y-3"><div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><FileImage className="size-5" /></div><div><p className="text-sm font-semibold">Canonical synthetic image</p><p className="mt-1 break-all text-xs text-muted-foreground">{data.patient.lesion.overviewImage.name}</p></div><dl className="space-y-1 text-[11px] text-muted-foreground"><div className="flex justify-between"><dt>Type</dt><dd className="font-mono">{data.patient.lesion.overviewImage.type}</dd></div><div className="flex justify-between"><dt>Size</dt><dd className="font-mono">{Math.round(data.patient.lesion.overviewImage.size / 1024)} KB</dd></div><div className="flex justify-between"><dt>File ID</dt><dd className="max-w-28 truncate font-mono">{data.patient.lesion.overviewImage.id}</dd></div></dl><p className="text-[10px] leading-4 text-muted-foreground">This bundled demo photograph is already registered to Sarah’s synthetic file record. Production uploads require a private, API-authorized upload session.</p></div>
                      </div>
                    </div>
                  ) : null}

                  {step === 5 ? (
                    <div className="space-y-6">
                      <div><StatusBadge tone="success"><CalendarCheck2 className="size-3" /> Dermatology visit</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">Choose a time that works.</h1><p className="mt-2 text-sm text-muted-foreground">We found {data.intake.availableSlots.length} in-person appointments across available providers and locations.</p></div>
                      <RadioGroup value={values.appointmentSlot} onValueChange={(value) => form.setValue("appointmentSlot", value, { shouldDirty: true, shouldValidate: true })} className="space-y-2" aria-invalid={Boolean(form.formState.errors.appointmentSlot)} aria-describedby={form.formState.errors.appointmentSlot ? "appointment-slot-error" : undefined}>
                        {data.intake.availableSlots.map((slot) => <Label key={slot.id} htmlFor={slot.id} className={cn("flex cursor-pointer items-center gap-4 rounded-lg border p-4", values.appointmentSlot === slot.id && "border-primary bg-primary/5")}><RadioGroupItem id={slot.id} value={slot.id} /><span className="flex min-w-0 flex-1 items-center gap-4"><span className="flex size-10 items-center justify-center rounded-md bg-muted"><Clock3 className="size-4" /></span><span className="flex-1"><span className="block text-sm font-semibold">{slot.dayLabel} · {slot.timeLabel}</span><span className="block text-xs text-muted-foreground">{slot.dateLabel} · {slot.provider} · {slot.location}</span></span></span><StatusBadge tone="success">Available</StatusBadge></Label>)}
                      </RadioGroup>
                      <p id="appointment-slot-error" role={form.formState.errors.appointmentSlot ? "alert" : undefined} className="text-xs text-destructive">{form.formState.errors.appointmentSlot?.message}</p>
                    </div>
                  ) : null}

                  {step === 6 ? (
                    <div className="space-y-6">
                      <div><StatusBadge tone="success"><ShieldCheck className="size-3" /> Eligibility found</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">Your coverage is active.</h1><p className="mt-2 text-sm leading-6 text-muted-foreground">We ran a simulated real-time eligibility check using the information on file.</p></div>
                      <div className="grid gap-4 sm:grid-cols-2"><Card className="bg-muted/25"><CardContent className="space-y-3 p-5"><div className="flex items-center gap-2"><CreditCard className="size-4 text-primary" /><p className="text-sm font-semibold">{eligibility.payer} {eligibility.plan}</p></div><div className="space-y-2 text-xs"><div className="flex justify-between"><span className="text-muted-foreground">Network</span><span className="font-medium">{eligibility.network}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Specialist copay</span><span className="font-mono font-medium">{currency.format(eligibility.specialistCopay)}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Deductible remaining</span><span className="font-mono font-medium">{currency.format(eligibility.deductibleRemaining)}</span></div></div></CardContent></Card><Card className="border-emerald-200 bg-emerald-50/60"><CardContent className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">Estimated responsibility</p><p className="mt-2 font-mono text-4xl font-semibold tracking-[-0.05em] text-emerald-950">{currency.format(eligibility.estimatedResponsibility)}</p><p className="mt-2 text-xs leading-5 text-emerald-900/70">Includes estimated specialist visit and biopsy coinsurance. Your final amount depends on services performed and payer adjudication.</p></CardContent></Card></div>
                      <div className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="insurance-payer">Insurance carrier</Label><Input id="insurance-payer" className="mt-2" {...form.register("insurancePayer")} aria-invalid={Boolean(form.formState.errors.insurancePayer)} aria-describedby={form.formState.errors.insurancePayer ? "insurance-payer-error" : undefined} /><p id="insurance-payer-error" role={form.formState.errors.insurancePayer ? "alert" : undefined} className="mt-1.5 text-xs text-destructive">{form.formState.errors.insurancePayer?.message}</p></div><div><Label htmlFor="member-id">Member ID</Label><Input id="member-id" className="mt-2 font-mono" {...form.register("insuranceMemberId")} aria-invalid={Boolean(form.formState.errors.insuranceMemberId)} aria-describedby={form.formState.errors.insuranceMemberId ? "member-id-error" : undefined} /><p id="member-id-error" role={form.formState.errors.insuranceMemberId ? "alert" : undefined} className="mt-1.5 text-xs text-destructive">{form.formState.errors.insuranceMemberId?.message}</p></div></div>
                      <Alert><Info className="size-4" /><AlertTitle>Estimate, not a bill</AlertTitle><AlertDescription>No payment is collected to reserve this appointment.</AlertDescription></Alert>
                    </div>
                  ) : null}

                  {step === 7 ? (
                    <div className="space-y-6">
                      <div><StatusBadge tone="ai"><Sparkles className="size-3" /> Ready to book</StatusBadge><h1 ref={stepHeadingRef} tabIndex={-1} className="mt-3 text-2xl font-semibold tracking-[-0.035em] outline-none">Review your visit.</h1><p className="mt-2 text-sm text-muted-foreground">Your care team will receive this structured intake before your appointment.</p></div>
                      <div className="divide-y rounded-lg border bg-background"><div className="flex gap-4 p-4"><CalendarCheck2 className="mt-0.5 size-4 text-primary" /><div><p className="text-sm font-semibold">{selectedSlot ? `${selectedSlot.dayLabel}, ${selectedSlot.dateLabel} at ${selectedSlot.timeLabel}` : "Appointment time required"}</p><p className="text-xs text-muted-foreground">{selectedSlot ? `${selectedSlot.provider} · ${selectedSlot.location}` : "Return to the Time step to choose a slot."}</p></div></div><div className="flex gap-4 p-4"><Camera className="mt-0.5 size-4 text-primary" /><div><p className="text-sm font-semibold">Changing mole · left posterior shoulder</p><p className="text-xs text-muted-foreground">Photo attached · darkening, widening, occasional itch</p></div></div><div className="flex gap-4 p-4"><CreditCard className="mt-0.5 size-4 text-primary" /><div><p className="text-sm font-semibold">{eligibility.payer} · {eligibility.status.toLowerCase()} and {eligibility.network.toLowerCase()}</p><p className="text-xs text-muted-foreground">Estimated patient responsibility: {currency.format(eligibility.estimatedResponsibility)}</p></div></div></div>
                      <fieldset className="space-y-2" aria-invalid={Boolean(form.formState.errors.treatmentConsent || form.formState.errors.privacyConsent || form.formState.errors.photographyConsent)} aria-describedby={(form.formState.errors.treatmentConsent || form.formState.errors.privacyConsent || form.formState.errors.photographyConsent) ? "consent-error" : undefined}><legend className="sr-only">Required consents</legend><label className={cn("flex cursor-pointer gap-3 rounded-lg border p-3", values.treatmentConsent && "border-primary bg-primary/5")}><Checkbox checked={values.treatmentConsent} aria-invalid={Boolean(form.formState.errors.treatmentConsent)} onCheckedChange={(checked) => form.setValue("treatmentConsent", checked === true, { shouldDirty: true, shouldValidate: true })} /><span className="text-xs leading-5">I consent to evaluation and treatment for this dermatology concern.</span></label><label className={cn("flex cursor-pointer gap-3 rounded-lg border p-3", values.privacyConsent && "border-primary bg-primary/5")}><Checkbox checked={values.privacyConsent} aria-invalid={Boolean(form.formState.errors.privacyConsent)} onCheckedChange={(checked) => form.setValue("privacyConsent", checked === true, { shouldDirty: true, shouldValidate: true })} /><span className="text-xs leading-5">I acknowledge the privacy notice and secure electronic communication policy.</span></label><label className={cn("flex cursor-pointer gap-3 rounded-lg border p-3", values.photographyConsent && "border-primary bg-primary/5")}><Checkbox checked={values.photographyConsent} aria-invalid={Boolean(form.formState.errors.photographyConsent)} onCheckedChange={(checked) => form.setValue("photographyConsent", checked === true, { shouldDirty: true, shouldValidate: true })} /><span className="text-xs leading-5">I consent to clinical photography for care, comparison, and documentation.</span></label></fieldset>
                      <p id="consent-error" role={(form.formState.errors.treatmentConsent || form.formState.errors.privacyConsent || form.formState.errors.photographyConsent) ? "alert" : undefined} className="text-xs text-destructive">{form.formState.errors.treatmentConsent?.message ?? form.formState.errors.privacyConsent?.message ?? form.formState.errors.photographyConsent?.message}</p>
                      {submissionMessage ? <Alert variant="destructive"><AlertDescription>{submissionMessage}</AlertDescription></Alert> : null}
                    </div>
                  ) : null}
                </div>

                <div className="flex items-center justify-between border-t bg-muted/20 px-5 py-4 sm:px-8">
                  <Button type="button" variant="ghost" onClick={() => setStep((current) => Math.max(current - 1, 0))} disabled={step === 0}><ArrowLeft className="size-4" /> Back</Button>
                  <div className="hidden text-xs text-muted-foreground sm:block">Step {step + 1} of {steps.length}</div>
                  {step < steps.length - 1 ? <Button type="button" onClick={() => void nextStep()} data-testid="intake-next">Continue <ArrowRight className="size-4" /></Button> : <Button type="submit" disabled={submitting || mode !== "live"} data-testid="book-appointment">{mode !== "live" ? "Reconnect to book" : submitting ? "Booking…" : "Book appointment"} <CalendarCheck2 className="size-4" /></Button>}
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
