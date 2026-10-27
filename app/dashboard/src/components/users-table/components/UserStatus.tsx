import { CircleAlert, CircleCheck, Clock3, PauseCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Status } from "types/User";
import { relativeExpiryDate } from "utils/dateFormatter";

const statusStyles: Record<Status, string> = {
  active: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  connected: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  connecting: "border-blue-500/20 bg-blue-500/10 text-blue-600 dark:text-blue-400",
  disabled: "border-muted bg-muted text-muted-foreground",
  limited: "border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  expired: "border-destructive/20 bg-destructive/10 text-destructive",
  on_hold: "border-blue-500/20 bg-blue-500/10 text-blue-600 dark:text-blue-400",
  error: "border-destructive/20 bg-destructive/10 text-destructive",
};

const statusIcons: Record<Status, typeof CircleCheck> = {
  active: CircleCheck,
  connected: CircleCheck,
  connecting: Clock3,
  disabled: PauseCircle,
  limited: CircleAlert,
  expired: Clock3,
  on_hold: PauseCircle,
  error: CircleAlert,
};

export function UserStatus({
  status,
  expire,
  compact = false,
}: {
  status: Status;
  expire: number | null;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const Icon = statusIcons[status];
  const expiry = relativeExpiryDate(expire);

  return (
    <div className="flex min-w-0 items-center gap-2">
      <Badge variant="outline" className={statusStyles[status]}>
        <Icon />
        {!compact && t(`status.${status}`)}
      </Badge>
      {!compact && expire && (
        <span className="truncate text-xs text-muted-foreground">
          {t(expiry.status, { time: expiry.time })}
        </span>
      )}
    </div>
  );
}
