import { describe, expect, it } from "vitest";
import { initial, type Notice, reduce, type State } from "./state";

const ok = (reply: string, offerContact = false) =>
  ({ type: "answer", result: { status: "ok", reply, offerContact } }) as const;
const failed = (status: Notice) =>
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

  it.each(["offline", "resting", "rate_limited", "daily_limit", "conversation_limit", "blocked"] as const)(
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

  // the form sat at the end of the log, so messages sent while it was open landed above it, out of view (22/11)
  it("anchors the contact to the answer that offered it, so later messages come after it", () => {
    expect(offered.contactAt).toBe(1);
    const later = reduce(reduce(form, { type: "send", text: "Still there?" }), ok("Yes.", true));
    expect(later.contactAt).toBe(1);
    expect(reduce(later, { type: "clear" }).contactAt).toBeNull();
  });

  it("moves the offer down to a later one until the form is open", () => {
    const again = reduce(reduce(offered, { type: "send", text: "And?" }), failed("offline"));
    expect(again.contactAt).toBe(3);
    expect(again.contact.step).toBe("offered");
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

describe("streaming", () => {
  const piece = (text: string) => ({ type: "delta", text }) as const;

  it("shows the answer as it is written, then keeps the whole reply", () => {
    let s = reduce(reduce(sent(), piece("He is ")), piece("open."));
    expect(s.partial).toBe("He is open.");
    s = reduce(s, ok("He is open."));
    expect(texts(s)).toEqual(["you:Is he open to remote roles?", "bot:He is open."]);
    expect(s.partial).toBe("");
  });

  it("drops the written part when the reply ends blocked", () => {
    const s = reduce(reduce(sent(), piece("Sure, ")), failed("blocked"));
    expect(texts(s)).toEqual(["you:Is he open to remote roles?", "notice:blocked"]);
    expect(s.partial).toBe("");
  });

  it("ignores pieces and answers that arrive after the conversation was cleared", () => {
    const cleared = reduce(reduce(sent(), piece("late ")), { type: "clear" });
    expect(reduce(cleared, piece("more"))).toBe(cleared);
    expect(reduce(cleared, ok("late more"))).toBe(cleared);
  });
});

describe("files", () => {
  const start = (s: State, key: number, name = `f${key}.pdf`) => reduce(s, { type: "fileStart", key, name });
  const ready = (key: number, id = `id${key}`) =>
    ({ type: "fileDone", key, result: { status: "ok", id, summary: "pdf, 3 pages" } }) as const;

  it("shows each file while it uploads, then ready with its summary or refused with the reason", () => {
    let s = start(start(initial, 1), 2);
    expect(s.files.map((f) => f.state)).toEqual(["uploading", "uploading"]);
    s = reduce(reduce(s, ready(1)), { type: "fileDone", key: 2, result: { status: "refused", reason: "type" } });
    expect(s.files).toEqual([
      { key: 1, name: "f1.pdf", state: "ready", id: "id1", summary: "pdf, 3 pages" },
      { key: 2, name: "f2.pdf", state: "refused", reason: "type" },
    ]);
    expect(reduce(s, { type: "fileRemove", key: 1 }).files.map((f) => f.key)).toEqual([2]);
  });

  it("waits for every upload before sending", () => {
    const s = reduce(start(initial, 1), { type: "send", text: "What is this?" });
    expect(s.entries).toEqual([]);
  });

  it("sends the ready files' names with the message and clears the list", () => {
    let s = reduce(start(start(initial, 1), 2, "x.exe"), ready(1));
    s = reduce(s, { type: "fileDone", key: 2, result: { status: "refused", reason: "type" } });
    s = reduce(s, { type: "send", text: "What is this?" });
    expect(s.entries).toEqual([{ id: 0, from: "you", text: "What is this?", files: ["f1.pdf"] }]);
    expect(s.files).toEqual([]);
  });
});

it("clearing starts over", () => {
  expect(reduce(reduce(sent(), ok("Yes.", true)), { type: "clear" })).toEqual(initial);
});

describe("resume panel", () => {
  const offer = (reply = "Both are below.") => ({ type: "answer", result: { status: "ok", reply, offerContact: false, offerResume: true } }) as const;
  const offered = reduce(sent("His CV?"), offer());

  it("anchors the panel to the answer that offered it, with the standard pair", () => {
    expect(offered.resume).toEqual({ at: 1, token: null, company: "", role: "", note: null });
  });

  it("moves it down to a later offer while nothing was tailored", () => {
    expect(reduce(reduce(offered, { type: "send", text: "And a letter?" }), offer("Below.")).resume?.at).toBe(3);
  });

  it("keeps a tailored pair, and stays put after it", () => {
    const tailored = reduce(offered, { type: "resumeDone", result: { status: "ok", token: "tok", company: "Acme", role: "AI Engineer" } });
    expect(tailored.resume).toEqual({ at: 1, token: "tok", company: "Acme", role: "AI Engineer", note: "ok" });
    expect(reduce(reduce(tailored, { type: "send", text: "Thanks" }), offer("Below.")).resume?.at).toBe(1);
  });

  it("keeps the standard pair and says why when tailoring didn't happen", () => {
    const s = reduce(offered, { type: "resumeDone", result: { status: "rate_limited", token: "standard-en", company: "", role: "" } });
    expect(s.resume).toEqual({ at: 1, token: null, company: "", role: "", note: "rate_limited" });
  });

  it("is gone when the conversation is cleared", () => {
    expect(reduce(offered, { type: "clear" }).resume).toBeNull();
  });
});
