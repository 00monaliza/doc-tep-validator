import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RU } from "./i18n";
import AccessRequest from "./sections/AccessRequest";

const fill = async () => {
  await userEvent.type(screen.getByLabelText(RU["access.email"]), "expert@bureau.kz");
  await userEvent.type(screen.getByLabelText(RU["access.org"]), "ТОО «Бюро»");
};

describe("access request (Review Focus 2)", () => {
  it("sends once even on a double click and thanks the user", async () => {
    let resolve!: (r: Response) => void;
    const fetchMock = vi.fn(() => new Promise<Response>(r => { resolve = r; }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AccessRequest />);
    await fill();
    const send = screen.getByRole("button", { name: RU["access.send"] });
    await userEvent.dblClick(send);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolve(new Response(JSON.stringify({ ok: true })));
    expect(await screen.findByText(RU["access.done"])).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("shows the server's refusal", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Слишком много заявок с этой почты, попробуйте завтра" }), { status: 429 })));
    render(<AccessRequest />);
    await fill();
    await userEvent.click(screen.getByRole("button", { name: RU["access.send"] }));
    expect(await screen.findByRole("alert")).toHaveTextContent("попробуйте завтра");
    vi.unstubAllGlobals();
  });

  it("the bot trap is invisible and out of the tab order", () => {
    render(<AccessRequest />);
    const trap = document.querySelector('input[name="website"]')!;
    expect(trap).toHaveAttribute("tabindex", "-1");
    expect(trap.closest("[aria-hidden='true']")).not.toBeNull();
  });
});
