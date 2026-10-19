import { zodResolver } from "@hookform/resolvers/zod";
import { FC, useEffect } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { publicApi } from "service/http";
import { removeAuthToken, setAuthToken } from "utils/authStorage";
import { useTranslation } from "react-i18next";
import { AxiosError } from "axios";
import { useQuery } from "@tanstack/react-query";

import Logo from "assets/logo.svg?react";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldContent,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { REPO_URL } from "@/constants/Project";

import { Language } from "./components/Language";

const schema = z.object({
  username: z.string().min(1, "login.fieldRequired"),
  password: z.string().min(1, "login.fieldRequired"),
});

type Values = z.infer<typeof schema>;

const LoginPage: FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  let location = useLocation();
  const currentYear = new Date().getFullYear();
  const { data: version } = useQuery({
    queryKey: ["public-app-version"],
    queryFn: () => publicApi.get<string>("/version"),
  });
  const {
    register,
    formState: { errors, isSubmitting, isValid },
    setError,
    handleSubmit,
  } = useForm<Values>({
    resolver: zodResolver(schema),
  });

  useEffect(() => {
    removeAuthToken();

    if (location.pathname !== "/login") {
      navigate("/login", { replace: true });
    }
  }, []);

  return (
    <main className="flex! min-h-svh flex-auto flex-col px-4 py-10">
      <div className="fixed right-4 top-2">
        <Language />
      </div>
      <div className="flex flex-1 items-center justify-center pb-10">
        <form
          className="contents"
          onSubmit={handleSubmit(async ({ password, username }) => {
            try {
              const formData = new FormData();

              formData.append("username", username);
              formData.append("password", password);
              formData.append("grant_type", "password");

              const { access_token } = await publicApi.post<{
                access_token: string;
              }>("/admin/token", formData);

              setAuthToken(access_token);
              navigate("/", { replace: true });
            } catch (error) {
              if (error instanceof AxiosError) {
                setError("root", {
                  message:
                    error.response?.status === 401
                      ? t("login.invalidCredentials")
                      : error.response?.data?.detail ||
                        t("core.generalErrorMessage"),
                });
              } else {
                setError("root", { message: t("core.generalErrorMessage") });
              }
            }
          })}
        >
          <Card className="max-w-md w-full">
            <CardHeader>
              <CardTitle className="flex items-center gap-x-3">
                <Logo className="size-6" />
                {t("login.loginYourAccount")}
              </CardTitle>
              <CardDescription>{t("login.welcomeBack")}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-y-2">
              <Field>
                <FieldLabel>{t("username")}</FieldLabel>
                <FieldContent>
                  <Input placeholder="admin" {...register("username")} />
                </FieldContent>
                {errors?.username && (
                  <FieldError>
                    {t(errors?.username?.message as string)}
                  </FieldError>
                )}
              </Field>
              <Field>
                <FieldLabel>{t("password")}</FieldLabel>
                <FieldContent>
                  <Input
                    placeholder="********"
                    type="password"
                    {...register("password")}
                  />
                </FieldContent>
                {errors?.password && (
                  <FieldError>
                    {t(errors?.password?.message as string)}
                  </FieldError>
                )}
              </Field>

              {errors.root && (
                <p className="text-destructive mb-2 text-sm">
                  {errors.root.message}
                </p>
              )}
            </CardContent>
            <CardFooter>
              <Button className="w-full" size="lg" disabled={isSubmitting}>
                {t("login")}
              </Button>
            </CardFooter>
          </Card>
        </form>
      </div>
      <footer className="mx-auto flex w-full max-w-7xl flex-col gap-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <span className="text-center sm:text-left">
          {t("login.footerCopyright", {
            year: currentYear,
            product: "MarzbanNext",
            version: version ? `v${version}` : "",
          })}
        </span>
        <div className="flex items-center justify-center gap-4 sm:justify-end">
          <a
            className="font-medium text-foreground underline-offset-4 hover:underline"
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("navigation.repository")}
          </a>
          <a
            className="font-medium text-foreground underline-offset-4 hover:underline"
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("navigation.api")}
          </a>
        </div>
      </footer>
    </main>
  );
};

export default LoginPage;
