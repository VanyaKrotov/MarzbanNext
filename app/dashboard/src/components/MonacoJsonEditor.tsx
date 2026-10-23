import type { editor, json } from "monaco-editor";
import { forwardRef, lazy, Suspense, useId } from "react";

import { cn } from "@/lib/utils";
import type { TemplateVariable } from "./monaco-template-support";

export type MonacoJsonSchema = json.JSONSchema;
export type MonacoJsonMarker = editor.IMarker;

export type MonacoJsonEditorProps = {
  value: string;
  onChange: (value: string) => void;
  schema?: MonacoJsonSchema;
  schemaUri?: string;
  onValidate?: (markers: MonacoJsonMarker[]) => void;
  language?: "json" | "yaml" | "text";
  templateVariables?: readonly TemplateVariable[];
  className?: string;
  disabled?: boolean;
  invalid?: boolean;
  id?: string;
};

const MonacoJsonEditorImpl = lazy(() =>
  import("./MonacoJsonEditorImpl").then((module) => ({
    default: module.MonacoJsonEditorImpl,
  })),
);

export const MonacoJsonEditor = forwardRef<
  HTMLDivElement,
  MonacoJsonEditorProps
>(
  (
    {
      value,
      onChange,
      schema,
      schemaUri,
      onValidate,
      language = "json",
      templateVariables,
      className,
      disabled = false,
      invalid = false,
      id,
    },
    ref,
  ) => {
    const editorId = useId();
    // Reuse the model when the template language changes; do not leave old models alive.
    const modelPath = `inmemory://model/json-editor-${editorId.replace(/:/g, "")}`;

    return (
      <div
        ref={ref}
        id={id}
        data-slot="json-editor"
        data-disabled={disabled}
        data-invalid={invalid}
        aria-invalid={invalid}
        className={cn(
          "h-80 border border-input bg-background shadow-xs transition-[color,box-shadow]",
          "focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50",
          "data-[invalid=true]:border-destructive data-[invalid=true]:ring-3 data-[invalid=true]:ring-destructive/20",
          "data-[disabled=true]:cursor-not-allowed data-[disabled=true]:opacity-50",
          "dark:bg-input/30 dark:data-[invalid=true]:border-destructive/50 dark:data-[invalid=true]:ring-destructive/40",
          className,
        )}
      >
        <Suspense
          fallback={<div className="h-full w-full animate-pulse bg-muted/50" />}
        >
          <MonacoJsonEditorImpl
            value={value}
            onChange={onChange}
            disabled={disabled}
            modelPath={modelPath}
            schema={schema}
            schemaUri={schemaUri}
            onValidate={onValidate}
            language={language}
            templateVariables={templateVariables}
          />
        </Suspense>
      </div>
    );
  },
);

MonacoJsonEditor.displayName = "MonacoJsonEditor";
