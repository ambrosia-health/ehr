import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TodayScreen } from "@/components/platform/today-screen";

describe("TodayScreen", () => {
  it("opens on the dermatologist-only operating model", () => {
    render(<TodayScreen />);

    expect(screen.getByRole("heading", { name: "You practice medicine. Ambrosia runs the clinic.", level: 1 })).toBeVisible();
    expect(screen.getByText("there is no administrative queue to manage.", { exact: false })).toBeVisible();
    expect(screen.getByText("Admin coverage")).toBeVisible();
    expect(screen.getByText("intake to payment, operated by Ambrosia")).toBeVisible();
  });

  it("keeps the dermatologist focused on clinical judgment", async () => {
    const user = userEvent.setup();
    render(<TodayScreen />);

    await user.click(screen.getByRole("button", { name: "Resolve 3 stops" }));
    const review = screen.getByRole("dialog", { name: "Sarah Mitchell" });

    await user.click(within(review).getByRole("button", { name: "Approve & release" }));
    expect(within(review).getByText("Decision approved and released.")).toBeVisible();
    await user.click(within(review).getByRole("button", { name: "Close" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Needs your judgment · 2" })).toBeVisible();
  });
});
