import { CalendarIcon, Clock3, Dices } from "lucide-react";
import { useState } from "react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { addYears } from "date-fns";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { resetStrategy } from "constants/UserSettings";
import { relativeExpiryDate } from "utils/dateFormatter";

import {
  formatTimeValue,
  getCalendarLocale,
  getDateLocaleCode,
  mergeExpiryDate,
  mergeExpiryTime,
  timestampToDate,
} from "../lib/calendar";
import { generateUsername, UserFormValues } from "../lib/form";

type UserFormSectionProps = {
  disabled: boolean;
  isEditing: boolean;
  serverError: string | null;
};

export function UserFormSection({
  disabled,
  isEditing,
  serverError,
}: UserFormSectionProps) {
  const { t, i18n } = useTranslation();
  const form = useFormContext<UserFormValues>();
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [dataLimit, userStatus, selectedExpire] = useWatch({
    control: form.control,
    name: ["data_limit", "status", "expire"],
  });
  const isOnHold = userStatus === "on_hold";
  const selectedDate = timestampToDate(selectedExpire);

  return (
    <div className="space-y-4">
      <Controller
        name="username"
        control={form.control}
        render={({ field }) => (
          <Field data-invalid={Boolean(form.formState.errors.username)}>
            <div className="flex items-center justify-between">
              <FieldLabel htmlFor="user-username">{t("username")}</FieldLabel>
              {!isEditing && (
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  onClick={() => field.onChange(generateUsername())}
                >
                  <Dices />
                  {t("actions.generate")}
                </Button>
              )}
            </div>
            <div className="flex items-center gap-3">
              <Input
                id="user-username"
                disabled={disabled || isEditing}
                aria-invalid={Boolean(form.formState.errors.username)}
                {...field}
              />
              <Controller
                name="status"
                control={form.control}
                render={({ field: statusField }) => (
                  <Field orientation="horizontal" className="w-auto">
                    <Switch
                      id="user-status"
                      checked={
                        isEditing
                          ? statusField.value === "active"
                          : statusField.value === "on_hold"
                      }
                      disabled={disabled}
                      onCheckedChange={(checked) =>
                        statusField.onChange(
                          isEditing
                            ? checked
                              ? "active"
                              : "disabled"
                            : checked
                              ? "on_hold"
                              : "active",
                        )
                      }
                    />
                    <FieldLabel
                      htmlFor="user-status"
                      className="whitespace-nowrap"
                    >
                      {isEditing
                        ? t(`status.${statusField.value}`)
                        : t("userDialog.onHold")}
                    </FieldLabel>
                  </Field>
                )}
              />
            </div>
            <FieldError errors={[form.formState.errors.username]} />
          </Field>
        )}
      />

      <Field data-invalid={Boolean(form.formState.errors.data_limit)}>
        <FieldLabel htmlFor="user-data-limit">
          {t("userDialog.dataLimit")}
        </FieldLabel>
        <Controller
          name="data_limit"
          control={form.control}
          render={({ field }) => (
            <InputGroup>
              <InputGroupInput
                id="user-data-limit"
                type="number"
                min="0"
                step="any"
                disabled={disabled}
                value={field.value ?? ""}
                onChange={field.onChange}
                aria-invalid={Boolean(form.formState.errors.data_limit)}
              />
              <InputGroupAddon align="inline-end">GB</InputGroupAddon>
            </InputGroup>
          )}
        />
        <FieldError errors={[form.formState.errors.data_limit]} />
      </Field>

      {Boolean(dataLimit && dataLimit > 0) && (
        <Field>
          <FieldLabel htmlFor="user-data-limit-reset">
            {t("userDialog.periodicUsageReset")}
          </FieldLabel>
          <Controller
            name="data_limit_reset_strategy"
            control={form.control}
            render={({ field }) => (
              <Select
                value={field.value}
                disabled={disabled}
                onValueChange={field.onChange}
              >
                <SelectTrigger id="user-data-limit-reset" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {resetStrategy.map((strategy) => (
                      <SelectItem value={strategy.value} key={strategy.value}>
                        {t(`userDialog.resetStrategy${strategy.title}`)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      )}

      <Field
        data-invalid={Boolean(
          isOnHold
            ? form.formState.errors.on_hold_expire_duration
            : form.formState.errors.expire,
        )}
      >
        <FieldLabel
          htmlFor={isOnHold ? "user-on-hold-duration" : "user-expire-date"}
        >
          {isOnHold
            ? t("userDialog.onHoldExpireDuration")
            : t("userDialog.expiryDate")}
        </FieldLabel>
        {isOnHold ? (
          <Controller
            name="on_hold_expire_duration"
            control={form.control}
            render={({ field }) => (
              <InputGroup>
                <InputGroupInput
                  id="user-on-hold-duration"
                  type="number"
                  min="0"
                  step="any"
                  disabled={disabled}
                  value={field.value ?? ""}
                  onChange={(event) => {
                    form.setValue("expire", null);
                    field.onChange(event);
                  }}
                />
                <InputGroupAddon align="inline-end">
                  {t("userDialog.days")}
                </InputGroupAddon>
              </InputGroup>
            )}
          />
        ) : (
          <Controller
            name="expire"
            control={form.control}
            render={({ field }) => (
              <div className="flex overflow-hidden rounded-md border border-input shadow-xs focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
                <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      id="user-expire-date"
                      type="button"
                      variant="ghost"
                      className="min-w-0 flex-1 justify-start rounded-none border-0 shadow-none"
                      disabled={disabled}
                      onBlur={field.onBlur}
                      ref={field.ref}
                    >
                      <CalendarIcon />
                      <span className="truncate">
                        {selectedDate
                          ? selectedDate.toLocaleDateString(
                              getDateLocaleCode(i18n.resolvedLanguage),
                            )
                          : t("userDialog.expiryDate")}
                      </span>
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={selectedDate}
                      locale={getCalendarLocale(i18n.resolvedLanguage)}
                      disabled={{
                        before: new Date(new Date().setHours(0, 0, 0, 0)),
                      }}
                      captionLayout="dropdown"
                      endMonth={addYears(new Date(), 10)}
                      onSelect={(date) => {
                        if (!date) return;
                        form.setValue("on_hold_expire_duration", null);
                        field.onChange(mergeExpiryDate(date, selectedDate));
                        setCalendarOpen(false);
                      }}
                    />
                    {selectedDate && (
                      <div className="border-t p-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="w-full"
                          onClick={() => {
                            field.onChange(null);
                            setCalendarOpen(false);
                          }}
                        >
                          {t("actions.clear")}
                        </Button>
                      </div>
                    )}
                  </PopoverContent>
                </Popover>
                <div className="w-px bg-border" />
                <div className="relative w-32">
                  <Input
                    id="user-expire-time"
                    type="time"
                    className="h-full w-full rounded-none border-0 pe-9 shadow-none focus-visible:ring-0 [&::-webkit-calendar-picker-indicator]:absolute [&::-webkit-calendar-picker-indicator]:end-3 [&::-webkit-calendar-picker-indicator]:size-4 [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-0"
                    disabled={disabled || !selectedDate}
                    value={formatTimeValue(selectedDate)}
                    onChange={(event) => {
                      if (!selectedDate || !event.target.value) return;
                      field.onChange(
                        mergeExpiryTime(selectedDate, event.target.value),
                      );
                    }}
                    onBlur={field.onBlur}
                    aria-label={t("userDialog.expiryTime")}
                  />
                  <Clock3 className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                </div>
              </div>
            )}
          />
        )}
        {!isOnHold && selectedExpire && (
          <FieldDescription>
            {t(relativeExpiryDate(selectedExpire).status, {
              time: relativeExpiryDate(selectedExpire).time,
            })}
          </FieldDescription>
        )}
        <FieldError
          errors={[
            isOnHold
              ? form.formState.errors.on_hold_expire_duration
              : form.formState.errors.expire,
          ]}
        />
      </Field>

      <Field data-invalid={Boolean(form.formState.errors.note)}>
        <FieldLabel htmlFor="user-note">{t("userDialog.note")}</FieldLabel>
        <Controller
          name="note"
          control={form.control}
          render={({ field }) => (
            <Textarea
              id="user-note"
              disabled={disabled}
              value={field.value ?? ""}
              onChange={field.onChange}
              onBlur={field.onBlur}
              name={field.name}
              ref={field.ref}
            />
          )}
        />
        <FieldError errors={[form.formState.errors.note]} />
      </Field>

      {serverError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          {serverError}
        </div>
      )}
    </div>
  );
}
