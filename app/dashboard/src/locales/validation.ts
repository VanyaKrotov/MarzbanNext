import { z } from "zod";

type Translate = (key: string, values?: Record<string, unknown>) => string;

export function configureValidationMessages(t: Translate) {
  z.setErrorMap((issue) => {
    let key = "validation.invalid";
    let values: Record<string, unknown> | undefined;

    if (issue.code === "invalid_type") {
      if (issue.received === "undefined" || issue.received === "null") {
        key = "login.fieldRequired";
      } else if (issue.expected === "integer") {
        key = "validation.integer";
      } else if (issue.expected === "number") {
        key = "validation.number";
      }
    } else if (issue.code === "invalid_string") {
      if (issue.validation === "url") key = "validation.url";
      if (issue.validation === "email") key = "validation.email";
      if (issue.path.at(-1) === "uplink_http_method")
        key = "validation.httpMethod";
      if (issue.path.at(-1) === "sub_update_interval")
        key = "validation.positiveInteger";
    } else if (issue.code === "too_small") {
      values = { count: String(issue.minimum) };
      if (issue.type === "string") {
        key =
          issue.minimum === 1 ? "login.fieldRequired" : "validation.minLength";
      } else if (issue.type === "array") {
        key = "validation.minItems";
      } else {
        key = issue.inclusive ? "validation.minimum" : "validation.greaterThan";
      }
    } else if (issue.code === "too_big") {
      values = { count: String(issue.maximum) };
      if (issue.type === "string") key = "validation.maxLength";
      else if (issue.type === "array") key = "validation.maxItems";
      else key = issue.inclusive ? "validation.maximum" : "validation.lessThan";
    } else if (issue.code === "custom") {
      const translationKey = issue.params?.translationKey;
      if (typeof translationKey === "string") key = translationKey;
      if (issue.path.at(-1) === "notify_days_left")
        key = "validation.dayThresholds";
      if (issue.path.at(-1) === "notify_reached_usage_percent")
        key = "validation.percentThresholds";
      if (issue.path.at(-1) === "value") key = "validation.httpUrl";
    }

    return { message: t(key, values) };
  });
}
