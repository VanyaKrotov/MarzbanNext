import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import svgr from "vite-plugin-svgr";
import { visualizer } from "rollup-plugin-visualizer";
import { VitePWA } from "vite-plugin-pwa";
import { loadPwaConfiguration } from "./scripts/pwa-config.mjs";

// https://vitejs.dev/config/
export default defineConfig(async () => {
  const pwa = await loadPwaConfiguration();
  return {
    base: "./",
    define: {
      __PWA_OFFLINE_HTML__: JSON.stringify(pwa.offlineHtml),
      __PWA_OFFLINE_REVISION__: JSON.stringify(pwa.offlineRevision),
    },
    resolve: {
      tsconfigPaths: true,
    },
    plugins: [
      tailwindcss(),
      react({
        include: "**/*.tsx",
      }),
      svgr(),
      visualizer(),
      VitePWA({
        strategies: "injectManifest",
        srcDir: "src/pwa",
        filename: "sw.js",
        scope: "./",
        manifestFilename: "manifest.webmanifest",
        manifest: pwa.manifest,
        injectRegister: "script-defer",
        includeManifestIcons: false,
        injectManifest: { injectionPoint: undefined },
        devOptions: { enabled: false },
      }),
    ],
  };
});
