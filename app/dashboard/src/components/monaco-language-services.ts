import * as monaco from "monaco-editor/esm/vs/editor/editor.api.js";
import type { MonacoJsonSchema } from "./MonacoJsonEditor";
import "monaco-editor/esm/vs/basic-languages/yaml/yaml.contribution.js";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { jsonDefaults } from "monaco-editor/esm/vs/language/json/monaco.contribution.js";
import JsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";
import YamlWorker from "./monaco-yaml.worker?worker";
import {
  configureMonacoYaml,
  type MonacoYaml,
  type JSONSchema as YamlSchema,
} from "monaco-yaml";

self.MonacoEnvironment = {
  getWorker(_moduleId, label) {
    if (label === "yaml") return new YamlWorker();
    return label === "json" ? new JsonWorker() : new EditorWorker();
  },
};

const schemaRegistry = new Map<
  string,
  {
    uri: string;
    fileMatch: string[];
    schema: MonacoJsonSchema;
    language: string;
  }
>();
let yamlService: MonacoYaml | undefined;

// monaco-yaml uses the pre-0.55 worker options; adapt them without patching Monaco globally.
const yamlMonaco = {
  ...monaco,
  editor: {
    ...monaco.editor,
    createWebWorker<T extends object>(
      options: monaco.editor.IInternalWebWorkerOptions & {
        createData?: unknown;
      },
    ) {
      const worker = new YamlWorker();
      worker.postMessage("ignore");
      worker.postMessage(options.createData);
      return monaco.editor.createWebWorker<T>({ worker });
    },
  },
};

const applySchemas = (language: "json" | "yaml") => {
  if (language === "json") {
    jsonDefaults.setDiagnosticsOptions({
      validate: true,
      allowComments: false,
      enableSchemaRequest: false,
      schemaValidation: "error",
      trailingCommas: "error",
      schemas: [...schemaRegistry.values()].filter(
        (entry) => entry.language === "json",
      ),
    });
    return;
  }
  const schemas = [...schemaRegistry.values()]
    .filter((entry) => entry.language === "yaml")
    .map(({ uri, fileMatch, schema }) => ({
      uri,
      fileMatch,
      schema: schema as YamlSchema,
    }));
  if (!yamlService && !schemas.length) return;
  const options = {
    enableSchemaRequest: false,
    validate: true,
    completion: true,
    hover: true,
    schemas,
  };
  if (yamlService) void yamlService.update(options);
  else yamlService = configureMonacoYaml(yamlMonaco, options);
};

export function registerSchema(
  modelPath: string,
  language: "json" | "yaml",
  schema: MonacoJsonSchema,
  schemaUri = `${modelPath}.schema.json`,
): () => void {
  schemaRegistry.set(modelPath, {
    uri: schemaUri,
    fileMatch: [modelPath],
    schema,
    language,
  });
  applySchemas(language);
  return () => {
    schemaRegistry.delete(modelPath);
    applySchemas(language);
  };
}
