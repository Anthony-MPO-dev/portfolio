import { type RouteConfig, index, route } from "@react-router/dev/routes";

// PROTOTYPE (phase 1, version 0): three visual directions for the author to pick from.
export default [
  index("routes/home.tsx"),
  route("a", "routes/a.tsx"),
  route("b", "routes/b.tsx"),
  route("c", "routes/c.tsx"),
] satisfies RouteConfig;
