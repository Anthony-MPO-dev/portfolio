import { type RouteConfig, index, route } from "@react-router/dev/routes";

// The home page and /services. The Portuguese pages (/pt/) come once the author approves their texts.

export default [index("routes/home.tsx"), route("services", "routes/services.tsx")] satisfies RouteConfig;
