import { ArrowDown, ArrowUp } from "lucide-react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { HostCapabilities, HostType } from "../../../types";
import type { HostFormValues } from "../lib/form";
import { ClientBalancerFields } from "./ClientBalancerFields";

export function CompositionFields({
  hosts,
  capabilities,
  pending,
}: {
  hosts: HostType[];
  capabilities: HostCapabilities;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const ids = useWatch({ control: form.control, name: "linked_host_ids" });
  const positions = new Map(ids.map((id, index) => [id, index]));
  const ordered = [...hosts].sort(
    (left, right) =>
      (positions.get(left.id) ?? ids.length) -
      (positions.get(right.id) ?? ids.length),
  );
  const move = (index: number, delta: number) => {
    const next = [...ids];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    form.setValue("linked_host_ids", next, { shouldDirty: true });
  };
  return (
    <FieldGroup>
      <FieldDescription>{t("hostEditor.compositionHint")}</FieldDescription>
      <div className="flex max-h-64 flex-col gap-2 overflow-y-auto">
        {ordered.map((host) => (
          <div key={host.id} className="flex items-center gap-2">
            <label className="flex min-w-0 flex-1 items-center gap-2 text-sm">
              <Checkbox
                disabled={pending}
                checked={ids.includes(host.id)}
                onCheckedChange={(checked) =>
                  form.setValue(
                    "linked_host_ids",
                    checked
                      ? [...ids, host.id]
                      : ids.filter((id) => id !== host.id),
                    { shouldDirty: true },
                  )
                }
              />
              <span>
                {host.remark}{" "}
                <span className="text-muted-foreground">
                  ({host.inbound_tag}, {host.address})
                </span>
              </span>
            </label>
            {ids.includes(host.id) && (
              <>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  aria-label={t("hostEditor.moveUp")}
                  disabled={pending || ids.indexOf(host.id) === 0}
                  onClick={() => move(ids.indexOf(host.id), -1)}
                >
                  <ArrowUp />
                </Button>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  aria-label={t("hostEditor.moveDown")}
                  disabled={pending || ids.indexOf(host.id) === ids.length - 1}
                  onClick={() => move(ids.indexOf(host.id), 1)}
                >
                  <ArrowDown />
                </Button>
              </>
            )}
          </div>
        ))}
      </div>
      <Field>
        <FieldLabel htmlFor="balancer-remark">
          {t("hostEditor.profileRemark")}
        </FieldLabel>
        <Input
          id="balancer-remark"
          disabled={pending}
          {...form.register("balancer_remark")}
        />
      </Field>
      <Controller
        control={form.control}
        name="balancer_strategy"
        render={({ field }) => (
          <Field>
            <FieldLabel htmlFor="balancer-strategy">
              {t("hostEditor.strategy")}
            </FieldLabel>
            <Select
              value={field.value}
              onValueChange={field.onChange}
              disabled={pending}
            >
              <SelectTrigger id="balancer-strategy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {["least_ping", "least_load", "random", "round_robin"].map(
                    (value) => (
                      <SelectItem key={value} value={value}>
                        {t(`hostEditor.strategies.${value}`)}
                      </SelectItem>
                    ),
                  )}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        )}
      />
      <Field>
        <FieldLabel htmlFor="balancer-probe-url">
          {t("hostEditor.probeUrl")}
        </FieldLabel>
        <Input
          id="balancer-probe-url"
          disabled={pending}
          {...form.register("balancer_probe_url")}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="balancer-probe-interval">
          {t("hostEditor.probeInterval")}
        </FieldLabel>
        <Input
          id="balancer-probe-interval"
          type="number"
          min={10}
          max={86400}
          disabled={pending}
          {...form.register("balancer_probe_interval", { valueAsNumber: true })}
        />
        <FieldError errors={[form.formState.errors.balancer_probe_interval]} />
      </Field>
      <ClientBalancerFields capabilities={capabilities} pending={pending} />
    </FieldGroup>
  );
}
