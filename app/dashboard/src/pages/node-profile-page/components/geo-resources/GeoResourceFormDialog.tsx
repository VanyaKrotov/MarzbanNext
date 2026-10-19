import { DragEvent, useRef, useState } from "react";
import { FileArchive, LoaderCircle, Plus, UploadCloud } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { generateErrorMessage } from "utils/toastHandler";

import { CronScheduleInput } from "./CronScheduleInput";
import {
  useCreateRemoteGeoResourceMutation,
  useUploadGeoResourceMutation,
} from "./query";

type RemoteGeoResourceFormValues = {
  filename: string;
  url: string;
  cron: string;
};

type UploadGeoResourceFormValues = {
  file: File | null;
};

const remoteDefaultValues: RemoteGeoResourceFormValues = {
  filename: "",
  url: "",
  cron: "0 4 * * *",
};

const uploadDefaultValues: UploadGeoResourceFormValues = {
  file: null,
};

export function GeoResourceFormDialog({ nodeId }: { nodeId: number }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [confirmOverwrite, setConfirmOverwrite] = useState<
    "file" | "remote" | null
  >(null);
  const [lastUploadFile, setLastUploadFile] = useState<File | null>(null);
  const [lastRemoteValues, setLastRemoteValues] =
    useState<RemoteGeoResourceFormValues | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const upload = useUploadGeoResourceMutation(nodeId);
  const createRemote = useCreateRemoteGeoResourceMutation(nodeId);
  const pending = upload.isPending || createRemote.isPending;

  const resetForms = () => setResetKey((key) => key + 1);

  const close = () => {
    setOpen(false);
    setConfirmOverwrite(null);
    setLastUploadFile(null);
    setLastRemoteValues(null);
    resetForms();
  };

  const handleOpenChange = (value: boolean) => {
    setOpen(value);
    if (!value) {
      setConfirmOverwrite(null);
      setLastUploadFile(null);
      setLastRemoteValues(null);
      resetForms();
    }
  };

  const isConflict = (error: unknown) =>
    (error as { response?: { status?: number } })?.response?.status === 409;

  const submitFile = (file: File, overwrite = false) => {
    setLastUploadFile(file);
    upload.mutate(
      { file, overwrite },
      {
        onSuccess: close,
        onError: (error) =>
          isConflict(error)
            ? setConfirmOverwrite("file")
            : generateErrorMessage(error),
      },
    );
  };

  const submitRemote = (
    values: RemoteGeoResourceFormValues,
    overwrite = false,
  ) => {
    setLastRemoteValues(values);
    createRemote.mutate(
      { ...values, overwrite },
      {
        onSuccess: close,
        onError: (error) =>
          isConflict(error)
            ? setConfirmOverwrite("remote")
            : generateErrorMessage(error),
      },
    );
  };

  const confirmOverwriteSubmit = () => {
    if (confirmOverwrite === "file" && lastUploadFile) {
      submitFile(lastUploadFile, true);
    }
    if (confirmOverwrite === "remote" && lastRemoteValues) {
      submitRemote(lastRemoteValues, true);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogTrigger asChild>
          <Button size="sm">
            <Plus />
            {t("actions.add")}
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("geoResources.addTitle")}</DialogTitle>
            <DialogDescription>
              {t("geoResources.addDescription")}
            </DialogDescription>
          </DialogHeader>
          <Tabs defaultValue="upload">
            <TabsList className="w-full">
              <TabsTrigger value="upload">
                {t("geoResources.upload")}
              </TabsTrigger>
              <TabsTrigger value="remote">
                {t("geoResources.remote")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="upload" className="pt-4">
              <UploadGeoResourceForm
                key={`upload-${resetKey}`}
                pending={pending}
                onSubmit={(file) => submitFile(file)}
              />
            </TabsContent>
            <TabsContent value="remote" className="pt-4">
              <RemoteGeoResourceForm
                key={`remote-${resetKey}`}
                pending={pending}
                onSubmit={(values) => submitRemote(values)}
              />
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={confirmOverwrite !== null}
        onOpenChange={(value) => !value && setConfirmOverwrite(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("geoResources.overwriteTitle")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("geoResources.overwriteDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={confirmOverwriteSubmit}
            >
              {t("geoResources.overwrite")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

interface UploadGeoResourceFormProps {
  pending: boolean;
  onSubmit(file: File): void;
}

function UploadGeoResourceForm({
  pending,
  onSubmit,
}: UploadGeoResourceFormProps) {
  const { t } = useTranslation();
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const form = useForm<UploadGeoResourceFormValues>({
    defaultValues: uploadDefaultValues,
    mode: "onChange",
  });

  const submit = (values: UploadGeoResourceFormValues) => {
    if (values.file) {
      onSubmit(values.file);
    }
  };

  return (
    <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
      <Controller
        control={form.control}
        name="file"
        rules={{ required: true }}
        render={({ field }) => {
          const selectFile = (selected?: File) => {
            if (!selected) return;
            if (!selected.name.toLowerCase().endsWith(".dat")) {
              toast.error(t("geoResources.dropInvalid"));
              return;
            }
            field.onChange(selected);
          };

          const handleDrop = (event: DragEvent<HTMLDivElement>) => {
            event.preventDefault();
            setDragActive(false);
            selectFile(event.dataTransfer.files[0]);
          };

          return (
            <>
              <Input
                ref={fileInputRef}
                id="geo-file"
                type="file"
                accept=".dat"
                required
                className="sr-only"
                onChange={(event) => selectFile(event.target.files?.[0])}
              />
              <div
                role="button"
                tabIndex={0}
                className={
                  dragActive
                    ? "flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-primary bg-primary/10 p-6 text-center outline-none transition-colors"
                    : `flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-muted/20 p-6 text-center outline-none transition-colors hover:border-primary/60 hover:bg-muted/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 ${
                        pending ? "pointer-events-none opacity-60" : ""
                      }`
                }
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                onDragEnter={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setDragActive(false);
                }}
                onDrop={handleDrop}
              >
                <div className="flex size-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  {pending ? (
                    <LoaderCircle className="size-5 animate-spin" />
                  ) : field.value ? (
                    <FileArchive className="size-5" />
                  ) : (
                    <UploadCloud className="size-5" />
                  )}
                </div>
                <div className="space-y-1">
                  <p className="font-medium">
                    {field.value
                      ? field.value.name
                      : t("geoResources.dropHere")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {field.value
                      ? t("geoResources.selectedFile")
                      : t("geoResources.dropOrSelect")}
                  </p>
                </div>
              </div>
            </>
          );
        }}
      />
      <DialogFooter>
        <Button type="submit" disabled={!form.formState.isValid || pending}>
          {pending && <LoaderCircle className="animate-spin" />}
          {t("actions.upload")}
        </Button>
      </DialogFooter>
    </form>
  );
}

interface RemoteGeoResourceFormProps {
  pending: boolean;
  onSubmit(values: RemoteGeoResourceFormValues): void;
}

function RemoteGeoResourceForm({
  pending,
  onSubmit,
}: RemoteGeoResourceFormProps) {
  const { t } = useTranslation();
  const form = useForm<RemoteGeoResourceFormValues>({
    defaultValues: remoteDefaultValues,
    mode: "onChange",
  });

  return (
    <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
      <div className="space-y-2">
        <Label htmlFor="geo-filename">{t("geoResources.filename")}</Label>
        <Controller
          control={form.control}
          name="filename"
          rules={{ required: true }}
          render={({ field }) => (
            <Input
              id="geo-filename"
              placeholder="geoip.dat"
              required
              {...field}
            />
          )}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="geo-url">{t("geoResources.url")}</Label>
        <Controller
          control={form.control}
          name="url"
          rules={{ required: true }}
          render={({ field }) => (
            <Input
              id="geo-url"
              type="url"
              placeholder="https://example.com/geosite.dat"
              required
              {...field}
            />
          )}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="geo-cron">{t("geoResources.cron")}</Label>
        <Controller
          control={form.control}
          name="cron"
          rules={{ required: true }}
          render={({ field }) => (
            <CronScheduleInput
              id="geo-cron"
              name={field.name}
              value={field.value}
              required
              onBlur={field.onBlur}
              onChange={field.onChange}
            />
          )}
        />
        <p className="text-xs text-muted-foreground">
          {t("geoResources.cronHint")}
        </p>
      </div>
      <DialogFooter>
        <Button type="submit" disabled={!form.formState.isValid || pending}>
          {pending && <LoaderCircle className="animate-spin" />}
          {t("actions.add")}
        </Button>
      </DialogFooter>
    </form>
  );
}
