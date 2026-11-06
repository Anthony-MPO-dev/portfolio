import type { Config } from "@react-router/dev/config";

// Static build: every route is prerendered to HTML, nginx serves the files.
export default {
  appDirectory: "src/app",
  ssr: false,
  prerender: true,
} satisfies Config;
