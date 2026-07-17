"use client";

import { CheckCircle2, Command, Flower, Send } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const suggestions = [
  "Prepare my next patient",
  "Show unresolved clinical risks",
  "Explain today’s practice variance",
] as const;

interface AmbrosiaCommandProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AmbrosiaCommand({ open, onOpenChange }: AmbrosiaCommandProps) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request = query.trim();
    if (!request) return;

    setResponse(`Ambrosia prepared a reviewable plan for “${request}”. No records changed.`);
    setQuery("");
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto border-l border-border border-t-[3px] border-t-primary bg-card p-0 sm:max-w-[30rem]">
        <SheetHeader className="border-b border-border bg-background/70 px-6 py-7 text-left">
          <div className="flex size-9 items-center justify-center rounded-md border border-primary/20 bg-secondary text-primary">
            <Flower className="size-5" strokeWidth={2.4} aria-hidden="true" />
          </div>
          <SheetTitle className="pt-2 text-xl font-semibold tracking-[-0.035em] text-foreground">Ask Ambrosia</SheetTitle>
          <SheetDescription className="max-w-md text-[13px] leading-5 text-muted-foreground">
            Ask for preparation, explanation, or coordination. Ambrosia shows its plan before changing anything.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-7 px-6 py-6">
          <form
            onSubmit={submit}
            className="rounded-lg border border-input bg-card p-2 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15"
          >
            <label htmlFor="ambrosia-command" className="sr-only">Ask Ambrosia</label>
            <div className="flex items-center gap-2">
              <Flower className="ml-2 size-4 shrink-0 text-primary" strokeWidth={2.4} aria-hidden="true" />
              <Input
                id="ambrosia-command"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="What should Ambrosia prepare?"
                autoFocus
                className="h-11 border-0 bg-transparent px-1 text-sm shadow-none focus-visible:ring-0"
              />
              <Button type="submit" size="icon" className="rounded-md" aria-label="Send command" disabled={!query.trim()}>
                <Send className="size-4" />
              </Button>
            </div>
          </form>

          <section aria-labelledby="command-suggestions">
            <div className="flex items-center justify-between gap-4">
              <h2 id="command-suggestions" className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Useful right now</h2>
              <kbd className="inline-flex h-6 items-center gap-1 rounded-md border border-border bg-background px-2 font-mono text-[10px] text-muted-foreground">
                <Command className="size-3" />K
              </kbd>
            </div>
            <div className="mt-3 grid gap-2">
              {suggestions.map((suggestion) => (
                <button
                  type="button"
                  key={suggestion}
                  onClick={() => setQuery(suggestion)}
                  className="min-h-11 rounded-md border border-border bg-card px-4 py-3 text-left text-[13px] font-medium text-foreground transition-colors hover:border-primary/35 hover:bg-secondary/65 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </section>

          {response ? (
            <div role="status" className="flex items-start gap-3 rounded-md border border-evidence/20 bg-evidence-muted p-4 text-sm text-evidence-foreground">
              <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-evidence" />
              <div>
                <p className="font-semibold text-foreground">Plan ready for review</p>
                <p className="mt-1 text-xs leading-5">{response}</p>
              </div>
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
