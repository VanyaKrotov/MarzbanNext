export const HOST_VARIABLES = [
  "SERVER_IP",
  "SERVER_IPV6",
  "USERNAME",
  "DATA_USAGE",
  "DATA_LEFT",
  "DATA_LIMIT",
  "DAYS_LEFT",
  "EXPIRE_DATE",
  "TIME_LEFT",
  "STATUS_TEXT",
  "STATUS_EMOJI",
  "PROTOCOL",
  "TRANSPORT",
] as const;

// GUI presets from Xray's TLS registry. Specific client cores may support a subset.
export const TLS_FINGERPRINTS = [
  "chrome",
  "firefox",
  "safari",
  "ios",
  "android",
  "edge",
  "360",
  "qq",
  "random",
  "randomized",
  "randomizednoalpn",
  "unsafe",
] as const;
