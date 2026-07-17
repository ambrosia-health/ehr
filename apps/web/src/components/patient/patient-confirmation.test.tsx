import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PatientConfirmation } from "@/components/patient/patient-confirmation";
import { AppProviders } from "@/components/system/app-providers";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

vi.mock("@/lib/api/hooks", () => ({
  useDemoBootstrap: () => ({
    data: {
      ...bootstrapFixture,
      intake: {
        ...bootstrapFixture.intake!,
        triage: { status: "staff_review", taskId: "task-urgent-1", notificationId: "notification-urgent-1", readinessStatus: "needs_review" },
        bookedAppointment: {
          id: "41111111-1111-4111-8111-111111111111",
          slotId: "12222222-2222-4222-8222-222222222222",
          providerId: "22222222-2222-4222-8222-222222222222",
          provider: "Dr. Imani Okafor",
          locationId: "32222222-2222-4222-8222-222222222222",
          location: "Midtown",
          startsAt: "2026-07-16T09:00:00-04:00",
          status: "booked",
        },
      },
    },
    mode: "live",
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("PatientConfirmation", () => {
  it("shows the exact persisted provider and location", () => {
    render(<AppProviders initialPersona="patient"><PatientConfirmation /></AppProviders>);
    expect(screen.getAllByText("Dr. Imani Okafor").length).toBeGreaterThan(0);
    expect(screen.getByText("Midtown")).toBeVisible();
    expect(screen.queryByText("Dr. Maya Chen")).not.toBeInTheDocument();
    expect(screen.getByTestId("intake-triage-receipt")).toHaveTextContent("task-urgent-1");
    expect(screen.getByTestId("intake-triage-receipt")).toHaveTextContent("needs review");
  });
});
