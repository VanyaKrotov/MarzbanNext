import Editor, { loader, type OnMount } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api.js";
import "monaco-editor/esm/vs/basic-languages/yaml/yaml.contribution.js";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { jsonDefaults } from "monaco-editor/esm/vs/language/json/monaco.contribution.js";
import JsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";
import { useEffect, useState } from "react";

import type { MonacoJsonMarker, MonacoJsonSchema } from "./MonacoJsonEditor";

loader.config({ monaco });

self.MonacoEnvironment = {
  getWorker(_moduleId, label) {
    return label === "json" ? new JsonWorker() : new EditorWorker();
  },
};

type MonacoJsonEditorImplProps = {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  modelPath: string;
  schema?: MonacoJsonSchema;
  schemaUri?: string;
  onValidate?: (markers: MonacoJsonMarker[]) => void;
  language: "json" | "yaml" | "text";
};

const schemaRegistry = new Map<
  string,
  { uri: string; fileMatch: string[]; schema: MonacoJsonSchema }
>();

const applySchemas = () => {
  jsonDefaults.setDiagnosticsOptions({
    validate: true,
    allowComments: false,
    enableSchemaRequest: false,
    schemaValidation: "error",
    trailingCommas: "error",
    schemas: [...schemaRegistry.values()],
  });
};

const getSystemTheme = () =>
  window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "vs-dark"
    : "light";

const useSystemEditorTheme = () => {
  const [theme, setTheme] = useState<"vs-dark" | "light">(getSystemTheme);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const updateTheme = () =>
      setTheme(mediaQuery.matches ? "vs-dark" : "light");

    mediaQuery.addEventListener("change", updateTheme);
    return () => mediaQuery.removeEventListener("change", updateTheme);
  }, []);

  return theme;
};

export function MonacoJsonEditorImpl({
  value,
  onChange,
  disabled,
  modelPath,
  schema,
  schemaUri,
  onValidate,
  language,
}: MonacoJsonEditorImplProps) {
  const theme = useSystemEditorTheme();

  useEffect(() => {
    if (!schema || language !== "json") return;

    schemaRegistry.set(modelPath, {
      uri: schemaUri ?? `${modelPath}.schema.json`,
      fileMatch: [modelPath],
      schema,
    });
    applySchemas();

    return () => {
      schemaRegistry.delete(modelPath);
      applySchemas();
    };
  }, [language, modelPath, schema, schemaUri]);

  const handleMount: OnMount = (editor) => {
    editor.getAction("editor.action.formatDocument")?.run();
  };

  return (
    <Editor
      height="100%"
      language={language === "text" ? "plaintext" : language}
      path={modelPath}
      theme={theme}
      value={value}
      onChange={(nextValue) => onChange(nextValue ?? "")}
      onMount={handleMount}
      onValidate={onValidate}
      loading={<div className="h-full w-full animate-pulse bg-muted/50" />}
      options={{
        automaticLayout: true,
        bracketPairColorization: { enabled: true },
        contextmenu: true,
        detectIndentation: false,
        folding: true,
        fontFamily:
          'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
        fontSize: 12,
        formatOnPaste: true,
        formatOnType: true,
        glyphMargin: false,
        lineDecorationsWidth: 8,
        lineNumbersMinChars: 3,
        minimap: { enabled: false },
        padding: { top: 12, bottom: 12 },
        readOnly: disabled,
        renderLineHighlight: "line",
        scrollBeyondLastLine: false,
        smoothScrolling: true,
        tabSize: 2,
        wordWrap: "on",
      }}
    />
  );
}
