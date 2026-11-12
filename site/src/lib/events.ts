// Window events two features share without importing each other (the chat is a lazy chunk).
// CHAT_ASK: the fact search's "Ask the bot" sends a question (detail: string); the chat opens and sends it.
// Public API: CHAT_ASK. Used by: features/fact-search/fact-search.tsx, features/chat/chat.tsx.
export const CHAT_ASK = "chat:ask";
