import { access, readFile } from "node:fs/promises";
import ts from "typescript";

const sourceRoot = new URL("../src/", import.meta.url);

export async function resolve(specifier, context, nextResolve) {
  let target;
  if (specifier.startsWith("@/"))
    target = new URL(specifier.slice(2), sourceRoot);
  else if (specifier.startsWith(".") && context.parentURL?.startsWith("file:"))
    target = new URL(specifier, context.parentURL);
  if (target) {
    for (const suffix of ["", ".ts", "/index.ts"]) {
      const candidate = new URL(target.href + suffix);
      if (!candidate.pathname.endsWith(".ts")) continue;
      try {
        await access(candidate);
        return { url: candidate.href, shortCircuit: true };
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
    }
  }
  return nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
  if (!url.startsWith("file:") || !url.endsWith(".ts"))
    return nextLoad(url, context);
  const source = await readFile(new URL(url), "utf8");
  const result = ts.transpileModule(source, {
    fileName: new URL(url).pathname,
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
  });
  return { format: "module", source: result.outputText, shortCircuit: true };
}
