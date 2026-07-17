"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type PropsWithChildren } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import {
  demoSessionEndedStorageKey,
  isDemoSessionMarkedEnded,
  markDemoSessionActive,
  markDemoSessionEnded,
  type DemoSessionLifecycle,
} from "@/lib/auth/session-lifecycle";
import type { IntakeTriageReceipt, Persona } from "@/lib/api/types";

interface DemoSessionValue {
  sessionLifecycle: DemoSessionLifecycle;
  persona: Persona;
  setPersona: (persona: Persona) => void;
  startSession: (persona: Persona) => void;
  endSession: () => void;
  intakeTriage: IntakeTriageReceipt | null;
  setIntakeTriage: (receipt: IntakeTriageReceipt | null) => void;
  encounterReview: {
    noteDraft: string;
    selectedProposalIds: string[];
  };
  updateEncounterReview: (next: { noteDraft?: string; selectedProposalIds?: string[] }) => void;
  resetSessionState: () => void;
}

const DemoSessionContext = createContext<DemoSessionValue | null>(null);

interface AppProvidersProps extends PropsWithChildren {
  initialPersona: Persona;
}

export function AppProviders({
  children,
  initialPersona,
}: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { refetchOnWindowFocus: false, retry: false },
          mutations: { retry: false },
        },
      }),
  );
  const [persona, updatePersona] = useState<Persona>(initialPersona);
  const [sessionLifecycle, setSessionLifecycle] = useState<DemoSessionLifecycle>("checking");
  const [intakeTriage, setIntakeTriage] = useState<IntakeTriageReceipt | null>(null);
  const [encounterReview, setEncounterReview] = useState({ noteDraft: "", selectedProposalIds: [] as string[] });

  const resetSessionState = useCallback(() => {
    setIntakeTriage(null);
    setEncounterReview({ noteDraft: "", selectedProposalIds: [] });
  }, []);

  useEffect(() => {
    function synchronizeLifecycle() {
      setSessionLifecycle(isDemoSessionMarkedEnded() ? "ended" : "active");
    }

    function handleStorage(event: StorageEvent) {
      if (event.key === demoSessionEndedStorageKey || event.key === null) synchronizeLifecycle();
    }

    synchronizeLifecycle();
    window.addEventListener("pageshow", synchronizeLifecycle);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("pageshow", synchronizeLifecycle);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  function setPersona(nextPersona: Persona) {
    updatePersona(nextPersona);
    resetSessionState();
  }

  function startSession(nextPersona: Persona) {
    markDemoSessionActive();
    setSessionLifecycle("active");
    updatePersona(nextPersona);
    resetSessionState();
  }

  function endSession() {
    markDemoSessionEnded();
    setSessionLifecycle("ended");
    updatePersona("provider");
    resetSessionState();
  }

  function updateEncounterReview(next: { noteDraft?: string; selectedProposalIds?: string[] }) {
    setEncounterReview((current) => ({ ...current, ...next }));
  }

  return (
    <QueryClientProvider client={queryClient}>
      <DemoSessionContext.Provider
        value={{ sessionLifecycle, persona, setPersona, startSession, endSession, intakeTriage, setIntakeTriage, encounterReview, updateEncounterReview, resetSessionState }}
      >
        <TooltipProvider>{children}</TooltipProvider>
      </DemoSessionContext.Provider>
    </QueryClientProvider>
  );
}

export function useDemoSession(): DemoSessionValue {
  const context = useContext(DemoSessionContext);
  if (!context) throw new Error("useDemoSession must be used inside AppProviders.");
  return context;
}
