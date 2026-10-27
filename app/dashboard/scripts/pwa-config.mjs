import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);

const manifest = {
  name: "MarzbanNext",
  short_name: "MarzbanNext",
  start_url: "./",
  scope: "./",
  display: "standalone",
  theme_color: "#ffffff",
  background_color: "#ffffff",
  prefer_related_applications: false,
  icons: [
    {
      src: "./statics/favicon/android-chrome-192x192.png",
      sizes: "192x192",
      type: "image/png",
      purpose: "any",
    },
    {
      src: "./statics/favicon/android-chrome-512x512.png",
      sizes: "512x512",
      type: "image/png",
      purpose: "any",
    },
  ],
};

export async function loadPwaConfiguration() {
  const locales = ["en", "ru", "fa", "zh"];
  const [template, worker, ...dictionaries] = await Promise.all([
    readFile(new URL("src/pwa/offline.html", root), "utf8"),
    readFile(new URL("src/pwa/sw.js", root), "utf8"),
    ...locales.map(async (locale) => {
      const data = JSON.parse(await readFile(
        new URL(`public/statics/locales/${locale}.json`, root), "utf8",
      ));
      return Object.fromEntries(["title", "description", "retry"].map((key) => {
        const value = data[`pwa.offline.${key}`];
        if (!value) throw new Error(`Missing ${locale} PWA offline translation: ${key}`);
        return [key, value];
      }));
    }),
  ]);
  const translations = Object.fromEntries(locales.map((locale, index) => [locale, dictionaries[index]]));
  const html = template.replace(
    "__OFFLINE_TRANSLATIONS__",
    JSON.stringify(translations).replaceAll("<", "\\u003c"),
  );
  const revision = createHash("sha256").update(html).update(worker).digest("hex").slice(0, 16);
  return {
    manifest,
    offlineHtml: html,
    offlineRevision: revision,
  };
}
