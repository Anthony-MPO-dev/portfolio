// Texts of "Search what the bot knows", in the three languages the search reads (English by default; the visitor
// switches in the section). The facts themselves stay in English, the language of the fact base.
// Public API: copy, LANGS, Lang. Used by: fact-search.tsx. Tests: copy.test.ts.

export type Lang = "en" | "pt" | "fr";
export const LANGS: { id: Lang; label: string; name: string }[] = [
  { id: "en", label: "EN", name: "English" },
  { id: "pt", label: "PT", name: "Português" },
  { id: "fr", label: "FR", name: "Français" },
];

export const copy = {
  en: {
    label: "Search what the bot knows",
    lead: (n: number) =>
      `Ask anything about me. A small model on my server turns your question into numbers and finds the closest of the ${n} facts the bot knows. It reads English, Portuguese and French.`,
    placeholder: "Ask about Anthony",
    chips: [
      "How fast is his credit pipeline?",
      "Can he build a chatbot for my company?",
      "What did he fix in the support agent's search?",
      "Does Kai use ChromaDB?",
    ],
    search: "Search",
    searching: "Searching...",
    done: (n: number) => `The 5 closest of ${n} facts, found on my server.`,
    nothing: "Nothing in the facts is close to that. You can still ask the bot.",
    rate_limited: "That's a lot of searches. Try again in a minute.",
    invalid: "Questions can be up to 200 characters.",
    offline: "The search is off right now. Try again in a moment.",
    factsNote: "",
    ask: (q: string) => `Ask the bot: "${q}"`,
    askNote: "The search finds the passages. The bot answers in words.",
    caption:
      "Each dot is one fact; the one with the ring is your question. The model's 384 numbers are squeezed into 2 for the picture, so the list, which uses all of them, can disagree with the distances you see.",
    honest:
      "The chat skips this step: the whole fact base fits in its prompt. My RAG projects can't do that, so this is how they find a passage, here on the same facts. Your question goes to my server for the search and isn't kept.",
    sound: (on: boolean) => `Key sounds: ${on ? "on" : "off"}`,
    language: "Language",
    mapLabel: (n: number) => `Map of the ${n} facts`,
  },
  pt: {
    label: "Search what the bot knows",
    lead: (n: number) =>
      `Pergunte qualquer coisa sobre mim. Um modelo pequeno no meu servidor transforma a pergunta em números e acha os mais próximos entre os ${n} fatos que o bot conhece. Ele lê inglês, português e francês.`,
    placeholder: "Pergunte sobre o Anthony",
    chips: ["Quanto tempo leva a análise de crédito?", "Ele faz chatbots para empresas?", "Onde ele estudou?", "O Kai usa ChromaDB?"],
    search: "Buscar",
    searching: "Buscando...",
    done: (n: number) => `Os 5 mais próximos entre ${n} fatos, achados no meu servidor.`,
    nothing: "Nada nos fatos chega perto disso. Você ainda pode perguntar ao bot.",
    rate_limited: "Foram muitas buscas. Tente de novo em um minuto.",
    invalid: "A pergunta pode ter até 200 caracteres.",
    offline: "A busca está fora do ar agora. Tente de novo daqui a pouco.",
    factsNote: "Os trechos aparecem em inglês, a língua da base.",
    ask: (q: string) => `Perguntar ao bot: "${q}"`,
    askNote: "A busca acha os trechos. O bot responde com palavras.",
    caption:
      "Cada ponto é um fato; o que tem o anel é a sua pergunta. Os 384 números do modelo viram 2 para o desenho, então a lista, que usa todos, pode discordar das distâncias que você vê.",
    honest:
      "O chat pula esta etapa: a base de fatos inteira cabe no prompt dele. Nos meus projetos de RAG isso não cabe, então é assim que eles acham um trecho, aqui com os mesmos fatos. A pergunta vai para o meu servidor só para a busca e não é guardada.",
    sound: (on: boolean) => `Som das teclas: ${on ? "ligado" : "desligado"}`,
    language: "Idioma",
    mapLabel: (n: number) => `Mapa dos ${n} fatos`,
  },
  fr: {
    label: "Search what the bot knows",
    lead: (n: number) =>
      `Posez n'importe quelle question sur moi. Un petit modèle sur mon serveur transforme la question en nombres et trouve les plus proches parmi les ${n} faits que le bot connaît. Il lit l'anglais, le portugais et le français.`,
    placeholder: "Posez une question sur Anthony",
    chips: [
      "Combien de temps prend l'analyse de crédit ?",
      "Peut-il créer un chatbot pour mon entreprise ?",
      "Où a-t-il étudié ?",
      "Kai utilise-t-il ChromaDB ?",
    ],
    search: "Chercher",
    searching: "Recherche...",
    done: (n: number) => `Les 5 plus proches parmi ${n} faits, trouvés sur mon serveur.`,
    nothing: "Rien dans les faits n'est proche de cela. Vous pouvez quand même demander au bot.",
    rate_limited: "Beaucoup de recherches. Réessayez dans une minute.",
    invalid: "Une question peut faire jusqu'à 200 caractères.",
    offline: "La recherche est indisponible. Réessayez dans un instant.",
    factsNote: "Les passages s'affichent en anglais, la langue de la base.",
    ask: (q: string) => `Demander au bot : "${q}"`,
    askNote: "La recherche trouve les passages. Le bot répond avec des mots.",
    caption:
      "Chaque point est un fait ; celui avec l'anneau est votre question. Les 384 nombres du modèle sont réduits à 2 pour le dessin, donc la liste, qui les utilise tous, peut contredire les distances que vous voyez.",
    honest:
      "Le chat saute cette étape : toute la base de faits tient dans son prompt. Dans mes projets RAG ce n'est pas possible, alors c'est ainsi qu'ils trouvent un passage, ici sur les mêmes faits. Votre question va sur mon serveur pour la recherche et n'est pas conservée.",
    sound: (on: boolean) => `Son des touches : ${on ? "activé" : "désactivé"}`,
    language: "Langue",
    mapLabel: (n: number) => `Carte des ${n} faits`,
  },
} satisfies Record<Lang, unknown>;
