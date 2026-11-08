import { defineConfig } from "vite";
import solid from "vite-plugin-solid";

export default defineConfig({
  plugins: [
    solid(),
    {
      name: "dev:strip-public-prefix",
      apply: "serve",
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url?.startsWith("/public/")) {
            req.url = req.url.slice("/public".length);
          }
          next();
        });
      },
    },
  ],
  build: {
    target: "es2022",
  },
});
