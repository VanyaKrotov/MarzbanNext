import type { TemplateBindings } from "@/pages/subscription-templates-page/lib/formats";
import type { SubscriptionTemplate } from "@/pages/subscription-templates-page/lib/query";

type TemplateSelection = Pick<SubscriptionTemplate, "id" | "format">;

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
