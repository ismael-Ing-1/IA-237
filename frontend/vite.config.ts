import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

import autoprefixer from "autoprefixer";
import tailwindcss from "tailwindcss";


export default defineConfig({
  plugins: [
    react(),
  ],

  server: {
    host: true,
    port: 5173,
  },

  preview: {
    host: true,
    port: 4173,
  },

  css: {
    postcss: {
      plugins: [
        /*
         * Tailwind is configured inline so the current frontend
         * does not require a separate tailwind.config.js file.
         *
         * This project intentionally uses Tailwind 3.4 because
         * src/styles/globals.css contains the classic:
         *
         * @tailwind base;
         * @tailwind components;
         * @tailwind utilities;
         */
        tailwindcss({
          content: [
            "./index.html",
            "./src/**/*.{js,ts,jsx,tsx}",
          ],

          theme: {
            extend: {},
          },

          plugins: [],
        }),

        autoprefixer(),
      ],
    },
  },

  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
