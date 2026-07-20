import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProductWorkspace, ProductWorkspaceProvider } from "./product-workspace-provider";
import { createProductWorkspace } from "@/test/product-workspace";
import { ApiError } from "@/lib/api/client";

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", () => ({
  ApiError: class ApiError extends Error { constructor(message: string, public status: number) { super(message); } },
  apiRequest: apiRequestMock,
}));

function WorkspaceProbe() {
  const { workspace } = useProductWorkspace();
  return <p>{workspace.patient.name} · {workspace.session.displayName}</p>;
}

describe("ProductWorkspaceProvider", () => {
  beforeEach(() => apiRequestMock.mockReset());

  it("loads an authorized workspace directly from the shared endpoint", async () => {
    apiRequestMock.mockResolvedValue(createProductWorkspace());

    const { render } = await import("@testing-library/react");
    render(<ProductWorkspaceProvider><WorkspaceProbe /></ProductWorkspaceProvider>);

    expect(await screen.findByText("Sarah Mitchell · Dr. Maya Chen")).toBeVisible();
    expect(apiRequestMock).toHaveBeenCalledTimes(1);
    expect(apiRequestMock).toHaveBeenCalledWith("/api/demo/bootstrap", expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it("creates a signed provider session when the API reports no session", async () => {
    apiRequestMock
      .mockRejectedValueOnce(new ApiError("Authentication required", 401))
      .mockResolvedValueOnce({ session: { persona: "provider" } })
      .mockResolvedValueOnce(createProductWorkspace());

    const { render } = await import("@testing-library/react");
    render(<ProductWorkspaceProvider><WorkspaceProbe /></ProductWorkspaceProvider>);

    expect(await screen.findByText("Sarah Mitchell · Dr. Maya Chen")).toBeVisible();
    expect(apiRequestMock).toHaveBeenNthCalledWith(2, "/api/auth/demo/session", expect.objectContaining({ method: "POST", body: { persona: "provider" } }));
  });
});
