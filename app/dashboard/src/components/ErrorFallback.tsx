import { Component, type ErrorInfo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

type GlobalErrorBoundaryProps = {
  children: ReactNode;
};

type GlobalErrorBoundaryState = {
  error: unknown;
};

function getErrorDetail(error: unknown): string | null {
  if (error instanceof Error) {
    return error.message.trim() || null;
  }

  if (typeof error === "string") {
    return error.trim() || null;
  }

  if (error && typeof error === "object") {
    const response = "response" in error ? error.response : undefined;
    const responseData =
      response && typeof response === "object" && "data" in response
        ? response.data
        : undefined;

    for (const source of [responseData, error]) {
      if (!source || typeof source !== "object") continue;

      const errorData = source as Record<string, unknown>;

      for (const key of ["detail", "message", "statusText"] as const) {
        if (typeof errorData[key] === "string") {
          const message = errorData[key].trim();
          if (message) return message;
        }
      }
    }
  }

  return null;
}

export function ErrorFallback({ error }: { error?: unknown }) {
  const { t } = useTranslation();
  const errorDetail = getErrorDetail(error);

  const reload = () => window.location.reload();
  const goHome = () => {
    window.location.hash = "#/";
    window.location.reload();
  };

  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-background p-4 sm:p-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,var(--color-destructive),transparent_28%),radial-gradient(circle_at_bottom_right,var(--color-primary),transparent_32%)] opacity-[0.08]" />
      <Empty className="relative max-w-2xl flex-none rounded-2xl border border-border/70 bg-card/90 px-6 py-12 text-card-foreground shadow-2xl shadow-black/5 backdrop-blur sm:px-12">
        <EmptyHeader>
          <EmptyMedia
            variant="icon"
            className="size-14 rounded-2xl bg-destructive/10 text-destructive ring-1 ring-destructive/15 [&_svg]:size-7"
          >
            <AlertTriangle />
          </EmptyMedia>
          <EmptyTitle className="text-xl sm:text-2xl">
            {t("errorBoundary.title")}
          </EmptyTitle>
          <EmptyDescription className="max-w-md">
            {t("errorBoundary.description")}
          </EmptyDescription>
        </EmptyHeader>

        <EmptyContent>
          {errorDetail && (
            <details className="group w-full rounded-lg border bg-muted/40 text-start">
              <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium outline-none marker:hidden">
                {t("errorBoundary.details")}
              </summary>
              <div className="border-t px-4 py-3">
                <code className="block max-h-32 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">
                  {errorDetail}
                </code>
              </div>
            </details>
          )}

          <div className="flex w-full flex-col gap-2 sm:flex-row sm:justify-center">
            <Button type="button" onClick={reload}>
              <RefreshCw />
              {t("actions.reload")}
            </Button>
            <Button type="button" variant="outline" onClick={goHome}>
              <Home />
              {t("errorBoundary.home")}
            </Button>
          </div>
        </EmptyContent>
      </Empty>
    </main>
  );
}

export class GlobalErrorBoundary extends Component<
  GlobalErrorBoundaryProps,
  GlobalErrorBoundaryState
> {
  state: GlobalErrorBoundaryState = {
    error: null,
  };

  static getDerivedStateFromError(error: unknown): GlobalErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught dashboard error", error, errorInfo);
  }

  render() {
    if (this.state.error) {
      return <ErrorFallback error={this.state.error} />;
    }

    return this.props.children;
  }
}
