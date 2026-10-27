import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { loadPwaConfiguration } from "../scripts/pwa-config.mjs";

async function worker(scope = "https://panel.example/dashboard/") {
  const config = await loadPwaConfiguration();
  const source = await readFile(new URL("../src/pwa/sw.js", import.meta.url), "utf8");
  const handlers = new Map<string, (event: unknown) => void>();
  const storage = new Map<string, Map<string, Response>>();
  let network: () => Promise<Response> = async () => new Response("from server");
  runInNewContext(source, {
    __PWA_OFFLINE_HTML__: config.offlineHtml,
    __PWA_OFFLINE_REVISION__: config.offlineRevision,
    URL, Response,
    fetch: () => network(),
    self: {
      registration: { scope },
      addEventListener: (type: string, handler: (event: unknown) => void) => handlers.set(type, handler),
      skipWaiting: async () => {},
      clients: { claim: async () => {} },
    },
    caches: {
      keys: async () => [...storage.keys()],
      delete: async (key: string) => storage.delete(key),
      open: async (key: string) => {
        if (!storage.has(key)) storage.set(key, new Map());
        const cache = storage.get(key)!;
        return {
          put: async (url: string, response: Response) => cache.set(url, response),
          match: async (url: string) => cache.get(url)?.clone(),
        };
      },
    },
  });
  const lifecycle = async (type: string) => {
    let work: Promise<unknown> | undefined;
    handlers.get(type)!({ waitUntil: (promise: Promise<unknown>) => { work = promise; } });
    await work;
  };
  const request = (url: string, options: { method?: string; mode?: string; authorization?: boolean } = {}) => {
    let response: Promise<Response> | undefined;
    handlers.get("fetch")!({
      request: {
        url, method: options.method ?? "GET", mode: options.mode ?? "navigate",
        headers: new Headers(options.authorization ? { Authorization: "Bearer secret" } : {}),
      },
      respondWith: (promise: Promise<Response>) => { response = promise; },
    });
    return response;
  };
  return { storage, lifecycle, request, offline: () => { network = async () => { throw new Error("offline"); }; } };
}

test("service worker caches only an offline document and never handles API, assets, or authenticated requests", async () => {
  const instance = await worker();
  await instance.lifecycle("install");
  assert.equal(instance.storage.size, 1);
  assert.equal([...instance.storage.values()][0].size, 1);
  for (const [url, options] of [
    ["https://panel.example/api/users", {}],
    ["https://panel.example/dashboard/", { method: "POST" }],
    ["https://panel.example/dashboard/", { authorization: true }],
    ["https://panel.example/dashboard/", { mode: "cors" }],
    ["https://panel.example/dashboard/statics/index.js", {}],
    ["https://panel.example/sub/example", {}],
    ["https://other.example/dashboard/", {}],
  ] as const) assert.equal(instance.request(url, options), undefined);

  assert.equal(await (await instance.request("https://panel.example/dashboard/")!).text(), "from server");
  instance.offline();
  const fallback = await instance.request("https://panel.example/dashboard/?from=app")!;
  const html = await fallback.text();
  assert.match(html, /Нет соединения/);
  assert.match(html, /localStorage.getItem\("i18nextLng"\)/);
  assert.doesNotMatch(html, /__OFFLINE_TRANSLATIONS__|__OFFLINE_HTML__/);
  assert.equal([...instance.storage.values()][0].size, 1);
});

test("activation removes only old offline caches for its own dashboard scope", async () => {
  const instance = await worker("https://panel.example/custom/panel/");
  instance.storage.set("unrelated-app", new Map());
  instance.storage.set("marzban-offline:https://panel.example/dashboard/:old", new Map());
  instance.storage.set("marzban-offline:https://panel.example/custom/panel/:old", new Map());
  await instance.lifecycle("install");
  await instance.lifecycle("activate");
  assert.equal(instance.storage.size, 3);
  assert.equal(instance.storage.has("marzban-offline:https://panel.example/custom/panel/:old"), false);
  instance.offline();
  assert.equal((await instance.request("https://panel.example/custom/panel/index.html")!).status, 200);
});

test("manifest launches from the deployment directory and references the existing PNG icons", async () => {
  const root = new URL("../public/", import.meta.url);
  const { manifest } = await loadPwaConfiguration();
  for (const base of ["https://panel.example/", "https://panel.example/dashboard/", "https://panel.example/custom/panel/"]) {
    const manifestUrl = new URL("manifest.webmanifest", base);
    for (const property of ["start_url", "scope"]) {
      assert.equal(new URL(manifest[property], manifestUrl).href, base);
    }
  }
  // An omitted id defaults to start_url; relative ids resolve against the origin
  // and would conflate independent dashboard installations on the same domain.
  assert.equal("id" in manifest, false);
  assert.equal(manifest.display, "standalone");
  for (const icon of manifest.icons) {
    const png = await readFile(new URL(icon.src, root));
    const [width, height] = icon.sizes.split("x").map(Number);
    assert.equal(png.readUInt32BE(16), width);
    assert.equal(png.readUInt32BE(20), height);
  }
});
