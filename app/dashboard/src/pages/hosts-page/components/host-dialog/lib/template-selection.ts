import {
  commonTemplateFormats,
  hostTemplateFormats,
  type TemplateBindings,
} from "@/pages/subscription-templates-page/lib/formats";
import type { SubscriptionTemplate } from "@/pages/subscription-templates-page/lib/query";

type TemplateSelection = Pick<SubscriptionTemplate, "id" | "format">;

export function getHostTemplateOptions<
  T extends TemplateSelection & { is_default: boolean },
>(templates: readonly T[]): T[] {
  return templates.filter(
    (template) =>
      template.is_default ||
      hostTemplateFormats.some((format) => format === template.format),
  );
}

export function getSelectedHostTemplates<T extends TemplateSelection>(
  options: readonly T[],
  bindings: TemplateBindings,
): T[] {
  return options.filter((template) =>
    // Common formats use the current default even when their saved binding has an older ID.
    commonTemplateFormats.some((format) => format === template.format)
      ? bindings[template.format] !== undefined
      : bindings[template.format] === template.id,
  );
}

export function templateBindingsFromSelection(
  selected: readonly TemplateSelection[],
  previous: TemplateBindings,
): TemplateBindings {
  const bindings: TemplateBindings = {};
  for (const template of selected) {
    // A newly selected template replaces its format's previous choice, regardless of list order.
    if (
      bindings[template.format] === undefined ||
      template.id !== previous[template.format]
    ) {
      bindings[template.format] = template.id;
    }
  }
  return bindings;
}

export function templateChipLabel(
  template: Pick<SubscriptionTemplate, "format" | "name">,
) {
  return `${template.format}:${template.name}`;
}
