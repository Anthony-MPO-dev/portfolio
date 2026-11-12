// Fixed English text of the chat panel: labels, notices and the contact form. The Portuguese copy comes with the
// /pt/ pages, after the author approves it. Used by: features/chat/chat.tsx, lead-form.tsx.
import type { FileRefusal } from "./api";
import type { Notice } from "./state";

export const copy = {
  launcher: "Ask about Anthony",
  title: "Ask about Anthony",
  sub: "An AI assistant that answers from Anthony's public profile. It can be wrong.",
  intro: "What do you want to know?",
  suggestions: ["Is he open to remote roles in the US or Europe?", "What has he built with RAG and ChromaDB?", "What does Insight AI & Automation build for companies?"],
  placeholder: "Ask about his Python, RAG or n8n work",
  send: "Send",
  files: {
    attach: "Attach an image, a PDF or a spreadsheet (up to 3)",
    reading: "Reading the file",
    remove: "Remove",
    refused: {
      type: "Only images, PDF, XLSX and CSV files work here.",
      too_big: "Too big. Images can be up to 5 MB, and PDF or XLSX files up to 10 MB.",
      unreadable: "I couldn't read this file.",
      no_text: "This PDF has no text. Send a picture of the page instead.",
      busy: "Busy right now. Try this file again in a minute.",
      too_many: "This conversation already has 10 files. Clear it to send more.",
      rate_limited: "You've sent today's 5 files. You can still ask in text.",
      offline: "Files are off right now. You can still ask in text.",
      challenge: "Cloudflare's browser check didn't come through. Allow challenges.cloudflare.com and try again.",
    } satisfies Record<FileRefusal, string>,
  },
  clear: "Clear",
  close: "Close",
  you: "You",
  bot: "Assistant",
  typing: "The assistant is typing",
  privacy:
    "Questions are kept for 30 days to improve the bot, and emails and phone numbers are removed before anything is stored. Files are read for the answer and deleted right after. Please don't send other people's personal data. Contact details you send to Anthony are kept for up to 12 months, and he deletes them if you ask. Before a conversation starts, Cloudflare checks that a real browser is sending it.",
  notices: {
    offline: "Offline right now. You can still reach Anthony below.",
    rate_limited: "You've asked a lot in the last hour. Try again in a little while, or reach Anthony below.",
    daily_limit: "That's it for today: you've used today's questions. Come back tomorrow, or reach Anthony below.",
    busy: "One moment, still answering your last message.",
    challenge:
      "Cloudflare's browser check didn't come through, so I can't start. An ad blocker or a work network may be stopping it: allow challenges.cloudflare.com and send again, or reach Anthony below.",
    resting: "Busy day. The assistant has answered all it can for today and comes back tomorrow, so reach Anthony below.",
    conversation_limit: "This conversation has used all 20 exchanges. Clear it to start over, or reach Anthony below.",
    invalid: "Messages can be up to 500 characters. A file waits 30 minutes at most, so attach it again if it expired.",
    blocked: "I can only help with questions about Anthony's work. You can also reach him below.",
  } satisfies Record<Notice, string>,
  talk: "Talk to Anthony",
  form: {
    name: "Name",
    company: "Company",
    email: "Email",
    linkedin: "LinkedIn",
    optional: "optional",
    linkedinHint: "Send me your LinkedIn and Anthony will connect with you.",
    kind: "What is it about?",
    hiring: "Hiring",
    project: "Project",
    submit: "Send to Anthony",
    error: "Check the fields. Name, company and a valid email are required.",
  },
  sentHiring: "Sent. Anthony will get back to you. For a quicker reply, message him on WhatsApp:",
  sentProject: "Sent. Anthony will reply by email.",
  emailFallback: "Please email Anthony at",
};
