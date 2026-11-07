import { describe, expect, it } from "vitest";
import { initial, reduce, type State } from "./state";

const ok = (reply: string, offerContact = false) =>
  ({ type: "answer", result: { status: "ok", reply, offerContact } }) as const;
const failed = (status: "offline" | "rate_limited" | "busy" | "conversation_limit" | "invalid" | "blocked") =>
  ({ type: "answer", result: { status, reply: "", offerContact: false } }) as const;
const sent = (text = "Is he open to remote roles?") => reduce(initial, { type: "send", text });
const texts = (s: State) => s.entries.map((e) => (e.from === "notice" ? `notice:${e.notice}` : `${e.from}:${e.text}`));

describe("sending", () => {
  it("adds the visitor's message, trimmed, and waits for the answer", () => {
    const s = sent("  Is he open to remote roles?  ");
    expect(texts(s)).toEqual(["you:Is he open to remote roles?"]);
    expect(s.pending).toBe(true);
  });

  it("ignores a blank message and a second message while the first is pending", () => {
    expect(reduce(initial, { type: "send", text: "   " })).toBe(initial);
    const s = sent();
    expect(reduce(s, { type: "send", text: "again" })).toBe(s);
  });
});

describe("answers", () => {
  it("shows the reply as written and stops waiting", () => {
    const s = reduce(sent(), ok("Yes.\n- backend\n- AI"));
    expect(texts(s)).toEqual(["you:Is he open to remote roles?", "bot:Yes.\n- backend\n- AI"]);
    expect(s.pending).toBe(false);
    expect(s.contact.step).toBe("none");
  });

  it("offers the contact form when the model asks for it", () => {
    expect(reduce(sent(), ok("Talk to Anthony.", true)).contact.step).toBe("offered");
  });

  it.each(["offline", "rate_limited", "conversation_limit", "blocked"] as const)(
    "turns %s into a fixed notice and offers the contact",
    (status) => {
      const s = reduce(sent(), failed(status));
      expect(texts(s).at(-1)).toBe(`notice:${status}`);
      expect(s.contact.step).toBe("offered");
      expect(s.pending).toBe(false);
    },
  );

  it.each(["busy", "invalid"] as const)("turns %s into a notice without the contact", (status) => {
    const s = reduce(sent(), failed(status));
    expect(texts(s).at(-1)).toBe(`notice:${status}`);
    expect(s.contact.step).toBe("none");
  });
});

describe("contact", () => {
  const offered = reduce(sent(), ok("Talk to Anthony.", true));
  const form = reduce(offered, { type: "openForm" });

  it("opens the form from the offer", () => {
    expect(form.contact).toEqual({ step: "form", error: false });
  });

  it("shows the WhatsApp number only when the API sends it", () => {
    const hiring = reduce(form, { type: "leadDone", result: { status: "ok", whatsapp: "+15550100" } });
    expect(hiring.contact).toEqual({ step: "sent", whatsapp: "+15550100" });
    expect(reduce(form, { type: "leadDone", result: { status: "ok" } }).contact).toEqual({ step: "sent" });
  });

  it("keeps the form open with an error when the API refuses the fields", () => {
    expect(reduce(form, { type: "leadDone", result: { status: "invalid" } }).contact).toEqual({
      step: "form",
      error: true,
    });
  });

  it.each(["rate_limited", "unavailable"] as const)("falls back to the email address on %s", (status) => {
    expect(reduce(form, { type: "leadDone", result: { status } }).contact.step).toBe("email");
  });

  it("doesn't offer the form again after a lead was sent", () => {
    const done = reduce(form, { type: "leadDone", result: { status: "ok" } });
    const later = reduce(reduce(done, { type: "send", text: "thanks" }), ok("You're welcome.", true));
    expect(later.contact.step).toBe("sent");
  });
});

it("clearing starts over", () => {
  expect(reduce(reduce(sent(), ok("Yes.", true)), { type: "clear" })).toEqual(initial);
});
