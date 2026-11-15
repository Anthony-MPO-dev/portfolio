import { type RouteConfig, index, route } from "@react-router/dev/routes";

// The home page and /services, in English at the root and in Portuguese under /pt/ (the same modules: each page
// reads its language from the path, lib/lang.ts).

export default [
  index("routes/home.tsx"),
  route("services", "routes/services.tsx"),
  route("pt", "routes/home.tsx", { id: "pt-home" }),
  route("pt/services", "routes/services.tsx", { id: "pt-services" }),
] satisfies RouteConfig;
