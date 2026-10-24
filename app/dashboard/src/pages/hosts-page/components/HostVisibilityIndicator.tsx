import { useTranslation } from "react-i18next";

export function HostVisibilityIndicator({ isHidden }: { isHidden: boolean }) {
  const { t } = useTranslation();
  if (isHidden) return null;

  const label = t("hostsPage.visible");

  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className="inline-block size-2 shrink-0 rounded-full bg-primary"
    />
  );
}
