"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Paperclip,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

import { PageHeader, StatusBadge } from "@/components/product/page-elements";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, endpoints } from "@/lib/api/client";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { formatInTimeZone } from "@/lib/date";
import { cn } from "@/lib/utils";

interface MessageReceipt {
  messageId: string;
  sentAt: string;
  status: string;
  triage: "routine" | "staff_review";
  triageTaskId?: string;
}

interface ConversationReadReceipt {
  conversationId: string;
  changedCount: number;
  readAt: string;
}

export function MessagingWorkspace() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [receipt, setReceipt] = useState<MessageReceipt | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [openedConversationIds, setOpenedConversationIds] = useState<Set<string>>(() => new Set());
  const [readingConversationId, setReadingConversationId] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);

  if (mode === "loading") return <PageLoading label="Loading secure messages" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (!data.patient) return <WorkspaceUnavailable title="Patient conversations are not available for your role" />;
  const activePersona = data.session.persona;
  const isPatient = activePersona === "patient";
  const filteredConversations = data.conversations.filter((item) => !searchQuery.trim() || [item.patient, item.subject, ...item.messages.map((message) => message.body)].some((value) => value.toLowerCase().includes(searchQuery.trim().toLowerCase())));
  const conversation = data.conversations.find((item) => item.id === activeConversationId) ?? data.conversations[0];
  if (!conversation) return <WorkspaceUnavailable title="No authorized conversations" description="There are no secure threads available to the active patient or care-team session." />;
  const aiDraft = conversation.messages.find((message) => message.aiDraft);
  const outgoingBody = draft || (isPatient ? "" : aiDraft?.body ?? "");
  const conversationId = conversation.id;
  const conversationInitials = conversation.patient.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  const responseMetric = data.metrics.find((metric) => metric.id === "response");
  const visibleUnread = data.conversations.reduce((total, item) => total + (openedConversationIds.has(item.id) ? 0 : item.unread), 0);

  async function openConversation(conversationToOpen: string) {
    setActiveConversationId(conversationToOpen);
    setDraft("");
    setReceipt(null);
    setSendError(null);
    setReadError(null);
    if (mode !== "live") return;
    setReadingConversationId(conversationToOpen);
    try {
      await apiRequest<ConversationReadReceipt>(endpoints.conversationRead(conversationToOpen), { method: "POST", body: {} });
      setOpenedConversationIds((current) => new Set(current).add(conversationToOpen));
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
    } catch (conversationError) {
      setReadError(conversationError instanceof Error ? conversationError.message : "The conversation could not be marked read.");
    } finally {
      setReadingConversationId(null);
    }
  }

  async function sendMessage() {
    if (mode !== "live" || !outgoingBody.trim()) return;
    setSending(true);
    setSendError(null);
    try {
      const nextReceipt = await apiRequest<MessageReceipt>(endpoints.conversationMessages(conversationId), { method: "POST", body: { body: outgoingBody.trim(), approveAiDraftId: !isPatient && aiDraft ? aiDraft.id : undefined } });
      setReceipt(nextReceipt);
      setDraft("");
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
    } catch (messageError) {
      setSendError(messageError instanceof Error ? messageError.message : "The message could not be sent.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader eyebrow={isPatient ? "Patient portal" : "Patient engagement"} title="Secure messages" description={isPatient ? "Ask your care team a question and keep every instruction with your visit." : "AI drafts routine answers from approved instructions; uncertainty and clinical change route to staff review."} actions={isPatient ? <StatusBadge tone="success"><ShieldCheck className="size-3" /> Secure</StatusBadge> : <>{responseMetric ? <StatusBadge tone={responseMetric.value == null ? "neutral" : responseMetric.tone}><Clock3 className="size-3" /> Median reply {responseMetric.value ?? "N/A"}</StatusBadge> : null}<span data-testid="messaging-unread-count"><StatusBadge tone={visibleUnread ? "warning" : "success"}>{visibleUnread} unread</StatusBadge></span></>} />

      <Card className="min-h-[680px] overflow-hidden">
        <CardContent className="grid min-h-[680px] p-0 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="border-b lg:border-b-0 lg:border-r">
            <div className="border-b p-4"><div className="relative"><Search className="absolute left-3 top-2.5 size-3.5 text-muted-foreground" /><Input className="h-8 pl-8 text-xs" placeholder="Search conversations" aria-label="Search conversations" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} /></div></div>
            <div className="p-2">
              {filteredConversations.length === 0 ? <p className="px-3 py-8 text-center text-xs text-muted-foreground">No conversations match this search.</p> : filteredConversations.map((item) => { const unread = openedConversationIds.has(item.id) ? 0 : item.unread; const initials = item.patient.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase(); return <button key={item.id} type="button" onClick={() => void openConversation(item.id)} className={cn("flex w-full gap-3 rounded-lg p-3 text-left", item.id === conversation.id && "bg-primary/6")} aria-label={`Open conversation with ${item.patient}: ${item.subject}`} aria-busy={readingConversationId === item.id} data-conversation-id={item.id}><Avatar className="size-9"><AvatarFallback className="bg-primary text-xs text-primary-foreground">{initials}</AvatarFallback></Avatar><span className="min-w-0 flex-1"><span className="flex items-center justify-between"><span className="text-xs font-semibold">{item.patient}</span><span className="font-mono text-[9px] text-muted-foreground">{item.messages.at(-1) ? formatInTimeZone(item.messages.at(-1)!.sentAt, data.organization.timezone, { hour: "numeric", minute: "2-digit" }) : ""}</span></span><span className="mt-1 block truncate text-[11px] font-medium">{item.subject}</span><span className="mt-1 flex items-center gap-1"><StatusBadge tone={item.risk === "routine" ? "success" : "warning"} className="h-4 text-[9px]">{item.risk === "routine" ? "Routine" : "Staff review"}</StatusBadge>{unread ? <span className="ml-auto flex size-4 items-center justify-center rounded-full bg-primary font-mono text-[8px] text-primary-foreground" data-testid={`conversation-unread-${item.id}`}>{unread}</span> : null}</span></span></button>; })}
            </div>
          </aside>

          <section className="flex min-w-0 flex-col">
            <header className="flex items-center border-b p-4"><div className="flex items-center gap-3"><Avatar className="size-9"><AvatarFallback>{conversationInitials}</AvatarFallback></Avatar><div><h2 className="text-sm font-semibold">{conversation.subject}</h2><p className="text-[10px] text-muted-foreground">{conversation.patient} · Visit-linked secure thread</p></div></div></header>
            <div className="flex-1 space-y-4 overflow-y-auto bg-muted/15 p-4 sm:p-6">
              <div className="mx-auto max-w-3xl space-y-4">
                {conversation.messages.map((message) => {
                  const fromPatient = message.sender === conversation.patient;
                  return (
                    <div key={message.id} className={cn("flex", fromPatient ? "justify-start" : "justify-end")}>
                      <div className={cn("max-w-[88%] rounded-xl border p-4 sm:max-w-[72%]", message.aiDraft ? "border-violet-200 bg-violet-50" : fromPatient ? "bg-card" : "border-primary/15 bg-primary text-primary-foreground")}>
                        {message.aiDraft ? <div className="mb-2 flex items-center justify-between gap-3"><StatusBadge tone="ai"><Sparkles className="size-3" /> AI draft</StatusBadge><span className="text-[9px] text-violet-800">Requires approval</span></div> : null}
                        <p className={cn("text-xs leading-5", message.aiDraft && "text-violet-950")}>{message.body}</p>
                        <p className={cn("mt-2 text-[9px]", message.aiDraft ? "text-violet-800/70" : fromPatient ? "text-muted-foreground" : "text-primary-foreground/65")}>{message.sender} · {formatInTimeZone(message.sentAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</p>
                      </div>
                    </div>
                  );
                })}
                {receipt ? <div className="flex justify-end"><div className="max-w-[72%] rounded-xl border border-emerald-200 bg-emerald-50 p-4" data-testid="message-receipt" data-triage={receipt.triage}><div className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-700" /><p className="text-xs font-semibold text-emerald-950">{receipt.status}</p></div><p className="mt-1 font-mono text-[9px] text-emerald-800">{receipt.messageId} · {formatInTimeZone(receipt.sentAt, data.organization.timezone, { hour: "numeric", minute: "2-digit" })}</p>{receipt.triage === "staff_review" ? <p className="mt-2 text-[10px] text-amber-800">Routed to staff task {receipt.triageTaskId}</p> : null}</div></div> : null}
              </div>
            </div>

            <div className="border-t bg-card p-4">
              <div className="mx-auto max-w-3xl space-y-3">
                {!isPatient && aiDraft && !draft ? <Alert className="border-violet-200 bg-violet-50"><Sparkles className="size-4 text-violet-700" /><AlertTitle>Grounded reply ready</AlertTitle><AlertDescription>This draft uses only approved biopsy aftercare. Review or edit it before sending.</AlertDescription></Alert> : null}
                {isPatient ? <Textarea aria-label="Message your care team" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask a question about your biopsy or aftercare…" className="min-h-20 resize-none" /> : <Textarea aria-label={`Reply to ${conversation.patient}`} value={outgoingBody} onChange={(event) => setDraft(event.target.value)} className="min-h-24 resize-none" />}
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-2 text-[10px] text-muted-foreground">{isPatient ? <><ShieldCheck className="size-3.5" /> New or uncertain symptoms route to clinical staff.</> : <><Sparkles className="size-3.5 text-violet-600" /> AI never sends without an approved policy or human review.</>}</div><div className="flex justify-end gap-2"><Button variant="ghost" size="icon-sm" aria-label="Attachments unavailable in synthetic demo" title="Attachments unavailable in synthetic demo" disabled><Paperclip /></Button><Button onClick={() => void sendMessage()} disabled={mode !== "live" || sending || !outgoingBody.trim()} data-testid="send-message">{sending ? "Sending…" : isPatient ? "Send securely" : aiDraft && !draft ? "Approve & send" : "Send reply"} <Send className="size-3.5" /></Button></div></div>
                {mode !== "live" ? <Alert className="border-amber-200 bg-amber-50"><AlertTriangle className="size-4 text-amber-700" /><AlertDescription>Messaging is read-only while the domain API is unavailable.</AlertDescription></Alert> : null}
                {sendError ? <Alert variant="destructive"><AlertTitle>Message not sent</AlertTitle><AlertDescription>{sendError}</AlertDescription></Alert> : null}
                {readError ? <Alert variant="destructive"><AlertTitle>Read status not saved</AlertTitle><AlertDescription>{readError}</AlertDescription></Alert> : null}
              </div>
            </div>
          </section>
        </CardContent>
      </Card>
    </div>
  );
}
