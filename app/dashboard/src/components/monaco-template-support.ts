import type * as Monaco from "monaco-editor/esm/vs/editor/editor.api.js";

export type TemplateVariable = { label: string; description: string };

export function containsTemplateExpression(value: string): boolean {
  return /\{[{%#]/.test(value);
}

export function templateExpressionPrefix(
  beforeCursor: string,
): string | undefined {
  const opening = Math.max(
    beforeCursor.lastIndexOf("{{"),
    beforeCursor.lastIndexOf("{%"),
  );

  const closing = Math.max(
    beforeCursor.lastIndexOf("}}"),
    beforeCursor.lastIndexOf("%}"),
  );

  if (opening < 0 || opening < closing) return;

  return beforeCursor.slice(opening + 2);
}

export function registerTemplateSupport(
  monaco: typeof Monaco,
  modelPath: string,
  language: string,
  variables: readonly TemplateVariable[],
): Monaco.IDisposable {
  const completions = monaco.languages.registerCompletionItemProvider(
    language,
    {
      triggerCharacters: ["{", ".", "|", " "],
      provideCompletionItems(model, position) {
        if (model.uri.toString() !== modelPath) return { suggestions: [] };

        const prefix = templateExpressionPrefix(
          model.getValue().slice(0, model.getOffsetAt(position)),
        );

        if (prefix === undefined) return { suggestions: [] };

        const token = /[\w.]*$/.exec(prefix)![0];
        const range = new monaco.Range(
          position.lineNumber,
          position.column - token.length,
          position.lineNumber,
          position.column,
        );

        return {
          suggestions: variables.map(({ label, description }) => ({
            label,
            insertText: label,
            documentation: description,
            range,
            kind: monaco.languages.CompletionItemKind.Variable,
          })),
        };
      },
    },
  );

  const hovers = monaco.languages.registerHoverProvider(language, {
    provideHover(model, position) {
      if (model.uri.toString() !== modelPath) return;

      const expression = templateExpressionPrefix(
        model.getValue().slice(0, model.getOffsetAt(position)),
      );

      if (expression === undefined) return;

      const word = model.getWordAtPosition(position);

      if (!word) return;

      const line = model.getLineContent(position.lineNumber);
      const left = line.slice(0, position.column - 1).match(/[\w.]*$/)![0];
      const right = line.slice(position.column - 1).match(/^[\w.]*/)![0];
      const variable = variables.find(
        ({ label }) => label === left + right || label === word.word,
      );

      if (variable)
        return {
          contents: [
            { value: `**${variable.label}**\n\n${variable.description}` },
          ],
        };
    },
  });
  // Jinja is validated by the server after rendering; native parsers cannot validate raw blocks.
  const markers = monaco.editor.onDidChangeMarkers((uris) => {
    if (!uris.some((uri) => uri.toString() === modelPath)) return;

    const model = monaco.editor.getModel(monaco.Uri.parse(modelPath));
    if (!model || !containsTemplateExpression(model.getValue())) return;

    for (const owner of ["json", "yaml"]) {
      if (monaco.editor.getModelMarkers({ owner, resource: model.uri }).length)
        monaco.editor.setModelMarkers(model, owner, []);
    }
  });

  return {
    dispose() {
      completions.dispose();
      hovers.dispose();
      markers.dispose();
    },
  };
}
