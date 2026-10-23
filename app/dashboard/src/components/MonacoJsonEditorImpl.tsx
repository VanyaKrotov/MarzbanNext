import Editor, { loader, type OnMount } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api.js";
import { useEffect, useState } from "react";

import type { MonacoJsonMarker, MonacoJsonSchema } from "./MonacoJsonEditor";
import { registerSchema } from "./monaco-language-services";
import {
  containsTemplateExpression,
  registerTemplateSupport,
  type TemplateVariable,
} from "./monaco-template-support";

loader.config({ monaco });

type MonacoJsonEditorImplProps = {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  modelPath: string;
  schema?: MonacoJsonSchema;
  schemaUri?: string;
  onValidate?: (markers: MonacoJsonMarker[]) => void;
  language: "json" | "yaml" | "text";
  templateVariables?: readonly TemplateVariable[];
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
  templateVariables,
}: MonacoJsonEditorImplProps) {
  const theme = useSystemEditorTheme();
  const hasJinja = Boolean(
    templateVariables && containsTemplateExpression(value),
  );

  useEffect(() => {
    if (!schema || language === "text") return;

    return registerSchema(modelPath, language, schema, schemaUri);
  }, [language, modelPath, schema, schemaUri]);

  useEffect(() => {
    if (!templateVariables) return;
    const support = registerTemplateSupport(
      monaco,
      modelPath,
      language === "text" ? "plaintext" : language,
      templateVariables,
    );
    return () => support.dispose();
  }, [language, modelPath, templateVariables]);

  const handleMount: OnMount = (editor) => {
    if (templateVariables && containsTemplateExpression(editor.getValue()))
      return;
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
      onValidate={hasJinja ? () => onValidate?.([]) : onValidate}
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
        formatOnPaste: !hasJinja,
        formatOnType: !hasJinja,
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
