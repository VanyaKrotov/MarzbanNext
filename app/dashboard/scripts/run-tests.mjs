import { readdir } from "node:fs/promises";
import { register } from "node:module";

register("./test-loader.mjs", import.meta.url);
const directory = new URL("../tests/", import.meta.url);
const files = (await readdir(directory))
  .filter((name) => name.endsWith(".test.ts"))
  .sort();
for (const file of files) await import(new URL(file, directory).href);
