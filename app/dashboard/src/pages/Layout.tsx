import { FC } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  ChartArea,
  CodeXml,
  FolderGit2,
  HeartHandshake,
  LogOut,
  PieChart,
  Server,
  Waypoints,
  Languages,
  ExternalLink,
  ChevronsUpDown,
  Settings,
  FileCode,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import Logo from "assets/logo.svg?react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DOCUMENTATION_URL, REPO_URL } from "@/constants/Project";
import { LANGUAGES } from "@/lib/languages";
import { Button } from "@/components/ui/button";
import { useAdmin } from "@/hooks/use-admin";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorFallback } from "@/components/ErrorFallback";
import { DonationDialog } from "@/components/DonationDialog";
import { Badge } from "@/components/ui/badge";
import { api } from "@/service/http";

const NAVIGATION = [
  {
    titleKey: "navigation.panelOptions",
    children: [
      {
        icon: ChartArea,
        labelKey: "navigation.dashboard",
        to: "/",
      },
      {
        icon: PieChart,
        labelKey: "navigation.stats",
        to: "/stats",
      },
      {
        icon: Server,
        labelKey: "navigation.nodes",
        sudoOnly: true,
        to: "/nodes",
      },
      {
        icon: Waypoints,
        labelKey: "navigation.hosts",
        sudoOnly: true,
        to: "/hosts",
      },
      {
        icon: FileCode,
        labelKey: "navigation.subscriptionTemplates",
        sudoOnly: true,
        to: "/subscription-templates",
      },
      {
        icon: Settings,
        labelKey: "navigation.settings",
        sudoOnly: true,
        to: "/settings",
      },
    ],
  },
] as const;

const GLOBAL_NAVIGATION = [
  {
    icon: CodeXml,
    labelKey: "navigation.api",
    href: "/docs",
  },
  {
    icon: FolderGit2,
    labelKey: "navigation.repository",
    href: REPO_URL,
  },
  // {
  //   icon: BookOpen,
  //   labelKey: "navigation.documentation",
  //   href: DOCUMENTATION_URL,
  // },
] as const;

const Layout: FC = () => {
  const { admin, error, isFetched, isPending } = useAdmin();
  const { t, i18n } = useTranslation();
  const { pathname } = useLocation();
  const { data: version } = useQuery({
    queryKey: ["app-version"],
    queryFn: () => api.get<string>("/version"),
  });

  if (!admin && (!isFetched || isPending)) {
    return <LayoutSkeleton />;
  }

  if (!admin) {
    return <ErrorFallback error={error} />;
  }

  const { username, is_sudo } = admin;
  const navigation = NAVIGATION.map(({ children, ...group }) => ({
    ...group,
    children: children.filter((item) => is_sudo || !("sudoOnly" in item)),
  }));

  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="flex flex-row items-center gap-x-3 p-4 pt-6">
          <Logo className="size-6" />
          <span className="font-medium">MarzbanNext</span>
          {version && (
            <Badge variant="outline" className="-ml-1.5 px-1 mt-0.5">
              v{version}
            </Badge>
          )}
        </SidebarHeader>
        <SidebarContent>
          {navigation.map(({ children, titleKey }) => (
            <SidebarGroup key={titleKey}>
              <SidebarGroupLabel>{t(titleKey)}</SidebarGroupLabel>
              <SidebarGroupContent className="flex flex-col gap-1">
                {children.map(({ icon: Icon, labelKey, to }) => (
                  <SidebarMenuItem key={to}>
                    <SidebarMenuButton asChild isActive={pathname === to}>
                      <Link to={to}>
                        <Icon />
                        {t(labelKey)}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
          <SidebarGroup>
            <SidebarGroupLabel>{t("navigation.global")}</SidebarGroupLabel>
            <SidebarGroupContent className="flex flex-col gap-1">
              {GLOBAL_NAVIGATION.map(({ href, icon: Icon, labelKey }) => (
                <SidebarMenuItem key={href}>
                  <SidebarMenuButton asChild>
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      <Icon />
                      {t(labelKey)}
                      <ExternalLink className="size-3.5! text-muted-foreground ml-auto" />
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
              <SidebarMenuItem>
                <DonationDialog
                  trigger={
                    <SidebarMenuButton>
                      <HeartHandshake />
                      {t("navigation.donation")}
                    </SidebarMenuButton>
                  }
                />
              </SidebarMenuItem>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton>
                <Languages />
                {LANGUAGES.find(({ value }) => value === i18n.language)
                  ?.label || "English"}
                <ChevronsUpDown className="ml-auto text-muted-foreground" />
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuRadioGroup
                value={i18n.language}
                onValueChange={i18n.changeLanguage}
              >
                {LANGUAGES.map(({ label, value }) => (
                  <DropdownMenuRadioItem value={value} key={value}>
                    {label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <SidebarSeparator className="mx-0" />
          <SidebarMenu>
            <SidebarMenuItem className="flex items-center gap-x-2">
              <Avatar>
                <AvatarImage src="https://heroui-assets.nyc3.cdn.digitaloceanspaces.com/avatars/blue.jpg" />
                <AvatarFallback className="uppercase">
                  {username.slice(0, 2)}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col gap-y-0.5 ml-0.5">
                <p className="text-md font-medium">{username}</p>
                <p className="text-xs text-muted-foreground">
                  {is_sudo ? "Super admin" : "Admin"}
                </p>
              </div>
              <Button size="icon" asChild className="ml-auto" variant="ghost">
                <Link to="/login" replace>
                  <LogOut />
                </Link>
              </Button>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>
      <div className="min-w-0 flex-1 px-4 pb-4 max-w-[1920px] mx-auto">
        <Outlet />
      </div>
    </SidebarProvider>
  );
};

function LayoutSkeleton() {
  return (
    <div className="flex min-h-svh w-full bg-background">
      <aside className="hidden w-64 shrink-0 border-r bg-sidebar p-4 md:flex md:flex-col">
        <div className="flex items-center gap-3 px-1 py-2">
          <Skeleton className="size-6 rounded-md" />
          <Skeleton className="h-5 w-28" />
        </div>

        <div className="mt-8 space-y-7">
          {Array.from({ length: 3 }).map((_, groupIndex) => (
            <div className="space-y-3" key={groupIndex}>
              <Skeleton className="h-3 w-24" />
              {Array.from({ length: groupIndex === 1 ? 5 : 4 }).map(
                (_, itemIndex) => (
                  <div
                    className="flex items-center gap-3 rounded-md px-2 py-1.5"
                    key={itemIndex}
                  >
                    <Skeleton className="size-4 rounded-sm" />
                    <Skeleton className="h-4 w-28" />
                  </div>
                ),
              )}
            </div>
          ))}
        </div>

        <div className="mt-auto space-y-4 border-t pt-4">
          <Skeleton className="h-9 w-full" />
          <div className="flex items-center gap-3">
            <Skeleton className="size-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-16" />
            </div>
            <Skeleton className="size-8" />
          </div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col gap-5 p-4 max-w-[1920px] mx-auto">
        <div className="flex items-center gap-3 md:hidden">
          <Skeleton className="size-9" />
          <Skeleton className="h-5 w-28" />
        </div>
        <div className="flex items-center justify-between gap-4 py-3">
          <div className="space-y-2">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-64 max-w-[60vw]" />
          </div>
          <Skeleton className="size-9" />
        </div>
        <div className="grid gap-3 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton className="h-20 rounded-xl" key={index} />
          ))}
        </div>
        <Skeleton className="min-h-72 flex-1 rounded-xl" />
      </main>
    </div>
  );
}

export default Layout;
