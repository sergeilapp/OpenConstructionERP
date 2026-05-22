import { useState, useRef, useEffect, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, Link, useLocation } from "react-router-dom";
import {
  Eye,
  EyeOff,
  Mail,
  Lock,
  Globe,
  ChevronDown,
  X,
  Github,
  Users,
  ArrowUpRight,
  Pencil,
  ShieldCheck,
  Zap,
  Brain,
  FileSpreadsheet,
  CalendarClock,
  TrendingUp,
  Boxes,
  Database,
  BarChart3,
  Upload,
  FileCheck,
  Box,
  Ruler,
  Layers,
  PenTool,
  FolderOpen,
  ClipboardList,
} from "lucide-react";
import { Button, Input, Logo, LogoWithText, CountryFlag } from "@/shared/ui";
import { useAuthStore } from "@/stores/useAuthStore";
import { useBrandingStore } from "@/stores/useBrandingStore";
import { BrandingEditorModal } from "@/app/layout/CustomBranding";
import { extractErrorMessageFromBody } from "@/shared/lib/api";
import { AuthBackground } from "./AuthBackground";
import { SUPPORTED_LANGUAGES } from "@/app/i18n";

export function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setTokens = useAuthStore((s) => s.setTokens);
  // White-label brand (same localStorage store the in-app sidebar editor
  // writes to). When a tenant has set a logo / company name we show it
  // on the login card instead of the default OpenConstructionERP wordmark.
  const {
    mode: brandMode,
    logoDataUrl: brandLogo,
    companyName: brandName,
  } = useBrandingStore();
  const brandCustomised = brandMode === "logo" || brandMode === "text";
  // `?next=/path` lets guarded routes send the user back to where they wanted
  // to go after login. Falls back to `/` for direct visits.
  const nextPath = (() => {
    try {
      const params = new URLSearchParams(location.search);
      const next = params.get("next");
      if (next && next.startsWith("/") && !next.startsWith("//")) return next;
    } catch {
      /* ignore */
    }
    return "/";
  })();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rememberMe, setRememberMe] = useState(
    () => localStorage.getItem("oe_remember") === "1",
  );
  const [langOpen, setLangOpen] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [brandOpen, setBrandOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(true);
  const [demoLoading, setDemoLoading] = useState<string | null>(null);
  const langRef = useRef<HTMLDivElement>(null);

  const currentLang =
    SUPPORTED_LANGUAGES.find((l) => l.code === i18n.language) ??
    SUPPORTED_LANGUAGES[0]!;

  // Clear form on mount (prevents pre-fill after logout)
  useEffect(() => {
    setEmail("");
    setPassword("");
    setError("");
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(e.target as Node))
        setLangOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/v1/users/auth/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const parsed = extractErrorMessageFromBody(data);
        setError(
          parsed || t("auth.invalid_credentials", "Invalid email or password"),
        );
        return;
      }
      const data = await res.json();
      setTokens(data.access_token, data.refresh_token, rememberMe, email);
      navigate(nextPath, { replace: true });
    } catch {
      setError(
        t(
          "auth.connection_error",
          "Unable to connect to server. Please try again.",
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const demoAccounts = [
    {
      email: "demo@openestimator.io",
      name: "Admin",
      role: t("auth.demo_role_admin", "Administrator"),
      color: "bg-blue-500",
      letter: "A",
    },
    {
      email: "manager@openestimator.io",
      name: "Thomas Müller",
      role: t("auth.demo_role_manager", "Manager"),
      color: "bg-[#7cd0ff]",
      letter: "M",
    },
  ];

  const handleDemoLogin = async (demoEmail: string) => {
    setDemoLoading(demoEmail);
    setError("");
    setEmail("");
    setPassword("");
    try {
      // Use the dedicated demo-login endpoint (v2.6.22) which mints tokens
      // for seeded demo accounts without a password — necessary because the
      // backend seeder generates a fresh `secrets.token_urlsafe(16)` per
      // install (BUG-D01) and the frontend has no way to read it.
      let res = await fetch("/api/v1/users/auth/demo-login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: demoEmail }),
      });

      // Fallback path: if the server is older than v2.6.22 it returns 404
      // for /demo-login/. Try the legacy login + auto-register pair so
      // existing deployments don't break the moment we ship the new client.
      if (res.status === 404) {
        res = await fetch("/api/v1/users/auth/login/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: demoEmail, password: "DemoPass1234!" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => null);
          const parsedMsg = extractErrorMessageFromBody(errData) ?? "";
          if (
            parsedMsg.includes("Invalid") ||
            parsedMsg.includes("not found") ||
            res.status === 401
          ) {
            const regRes = await fetch("/api/v1/users/auth/register/", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                email: demoEmail,
                password: "DemoPass1234!",
                full_name: (demoEmail.split("@")[0] ?? "Demo User")
                  .replace(/[._]/g, " ")
                  .replace(/\b\w/g, (c) => c.toUpperCase()),
              }),
            });
            if (regRes.ok) {
              res = await fetch("/api/v1/users/auth/login/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  email: demoEmail,
                  password: "DemoPass1234!",
                }),
              });
            }
          }
        }
      }

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const parsed = extractErrorMessageFromBody(data);
        setError(
          parsed ||
            t("auth.demo_login_failed", "Demo login failed. Please try again."),
        );
        return;
      }
      const data = await res.json();
      setTokens(data.access_token, data.refresh_token, false, demoEmail);
      navigate(nextPath, { replace: true });
    } catch {
      setError(
        t(
          "auth.connection_error",
          "Unable to connect to server. Please try again.",
        ),
      );
    } finally {
      setDemoLoading(null);
    }
  };

  /* Benefits list — reserved for future hero section layout
  const benefits = [
    { icon: HardDrive, color: 'text-emerald-500 bg-emerald-500/10', title: t('login.benefit.local', 'Your data stays on your computer'), desc: t('login.benefit.local_desc', 'No cloud. No third-party servers. Full control.') },
    { icon: ShieldCheck, color: 'text-blue-500 bg-blue-500/10', title: t('login.benefit.open_source', '100% open source'), desc: t('login.benefit.open_source_desc', 'Transparent code. No vendor lock-in.') },
    { icon: Globe2, color: 'text-violet-500 bg-violet-500/10', title: t('login.benefit.standards', 'International standards'), desc: t('login.benefit.standards_desc', '55,000+ cost items across 48 regional databases worldwide.') },
    { icon: Brain, color: 'text-amber-500 bg-amber-500/10', title: t('login.benefit.ai', 'AI-assisted estimation'), desc: t('login.benefit.ai_desc', 'Smart suggestions. You decide, AI assists.') },
    { icon: Zap, color: 'text-rose-500 bg-rose-500/10', title: t('login.benefit.allinone', 'BOQ + 4D + 5D + Tendering'), desc: t('login.benefit.allinone_desc', 'Full workflow in one tool.') },
    { icon: Users, color: 'text-cyan-500 bg-cyan-500/10', title: t('login.benefit.free', 'Free for everyone'), desc: t('login.benefit.free_desc', 'No fees. No limits. By estimators.') },
  ]; */

  return (
    <div className="relative grid h-screen grid-cols-1 lg:grid-cols-2 bg-surface-secondary overflow-hidden">
      <AuthBackground />

      {/* Local style block — premium glass variant + drifting orb keyframes
          scoped to the login page. Pattern mirrors LoginPageNext.tsx. */}
      <style>{`
        .login-glass-pro {
          background:
            linear-gradient(135deg, rgba(255,255,255,0.78) 0%, rgba(255,255,255,0.62) 100%);
          backdrop-filter: blur(28px) saturate(180%);
          -webkit-backdrop-filter: blur(28px) saturate(180%);
          border: 1px solid rgba(255, 255, 255, 0.85);
          box-shadow:
            0 36px 80px -28px rgba(14, 165, 233, 0.30),
            0 14px 36px -12px rgba(15, 23, 42, 0.12),
            0 2px 6px -1px rgba(15, 23, 42, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 0.95),
            inset 0 0 0 1px rgba(255, 255, 255, 0.35);
        }
        .dark .login-glass-pro {
          background:
            linear-gradient(135deg, rgba(22, 26, 36, 0.78) 0%, rgba(15, 17, 23, 0.66) 100%);
          border-color: rgba(255, 255, 255, 0.08);
          box-shadow:
            0 30px 80px -24px rgba(14, 165, 233, 0.35),
            0 12px 40px -12px rgba(0, 0, 0, 0.55),
            0 2px 6px -2px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.12),
            inset 0 0 0 1px rgba(255, 255, 255, 0.04);
        }
        .login-glass-pro::after {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: inherit;
          pointer-events: none;
          background:
            radial-gradient(120% 80% at 0% 0%, rgba(14, 165, 233, 0.05), transparent 65%);
          mix-blend-mode: soft-light;
        }
        .dark .login-glass-pro::after {
          background:
            radial-gradient(120% 80% at 0% 0%, rgba(14, 165, 233, 0.18), transparent 60%),
            radial-gradient(120% 80% at 100% 100%, rgba(139, 92, 246, 0.16), transparent 60%);
          mix-blend-mode: screen;
        }
        @keyframes login-orb-drift-a {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50%      { transform: translate3d(30px, -22px, 0) scale(1.08); }
        }
        @keyframes login-orb-drift-b {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50%      { transform: translate3d(-26px, 28px, 0) scale(0.94); }
        }
        @keyframes login-orb-drift-c {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50%      { transform: translate3d(20px, 32px, 0) scale(1.05); }
        }
        .login-orb-a { animation: login-orb-drift-a 12s ease-in-out infinite; }
        .login-orb-b { animation: login-orb-drift-b 14s ease-in-out infinite; }
        .login-orb-c { animation: login-orb-drift-c 10s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .login-orb-a, .login-orb-b, .login-orb-c { animation: none; }
        }
      `}</style>

      {/* ── Ambient mesh blobs (LEFT half only) ─────────────────────────
          Restrained palette — single faint sky blob behind the marketing
          column so the headline / stats sit on a near-white field.
          Dark mode keeps the original richer blob set for depth. */}
      <div className="absolute inset-y-0 left-0 right-1/2 z-0 pointer-events-none overflow-hidden hidden lg:block">
        <div className="absolute top-[-12%] left-[-6%] w-[520px] h-[520px] rounded-full bg-sky-300/10 dark:bg-oe-blue/35 blur-[120px] animate-blob-slow-1 mix-blend-screen" />
        <div className="absolute bottom-[-18%] right-[2%] w-[400px] h-[400px] rounded-full bg-cyan-200/8 dark:bg-violet-500/35 blur-[110px] animate-blob-slow-4 mix-blend-screen hidden dark:block" />
      </div>

      {/* Mobile-only ambient blobs (single column layout) */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden lg:hidden">
        <div className="absolute top-[-12%] left-[-6%] w-[520px] h-[520px] rounded-full bg-sky-300/12 dark:bg-oe-blue/35 blur-[110px] animate-blob-slow-1 mix-blend-screen" />
      </div>

      {/* Language — top right (enlarged for /login so it's discoverable). */}
      <div className="absolute top-4 right-4 z-30" ref={langRef}>
        <button
          onClick={() => setLangOpen(!langOpen)}
          className="flex items-center gap-2 rounded-xl border border-border-light bg-surface-elevated/85 backdrop-blur-sm px-4 py-2 text-sm font-medium text-content-secondary hover:bg-surface-elevated hover:border-oe-blue/30 transition-colors shadow-sm"
        >
          <Globe size={16} className="text-content-tertiary" />
          <CountryFlag code={currentLang.country} size={20} />
          <span className="hidden sm:inline">{currentLang.name}</span>
          <ChevronDown
            size={14}
            className={`text-content-tertiary transition-transform ${langOpen ? "rotate-180" : ""}`}
          />
        </button>
        {langOpen && (
          <div className="absolute right-0 mt-2 w-64 max-h-80 overflow-y-auto rounded-xl border border-border-light bg-surface-elevated shadow-xl py-1 animate-stagger-in">
            {SUPPORTED_LANGUAGES.map((lang) => {
              const isActive = i18n.language === lang.code;
              const english =
                "english" in lang
                  ? (lang as { english?: string }).english
                  : undefined;
              return (
                <button
                  key={lang.code}
                  onClick={() => {
                    i18n.changeLanguage(lang.code);
                    setLangOpen(false);
                  }}
                  className={`flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors ${isActive ? "bg-oe-blue/8 text-oe-blue font-medium" : "text-content-primary hover:bg-surface-secondary"}`}
                >
                  <CountryFlag code={lang.country} size={18} />
                  <span className="truncate">
                    {lang.name}
                    {english && (
                      <span className="ml-1 text-2xs text-content-tertiary">
                        ({english})
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Right column on lg+: marketing & benefits.
          Order swap (lg:order-2) puts the form on the left so it's the
          first thing the eye lands on — primary action priority. */}
      <div className="hidden lg:flex relative z-10 lg:order-2 flex-col justify-center pl-14 xl:pl-20 pr-12 xl:pr-16 py-6 overflow-hidden">
        {/* Marketing column showcase — color lives here. Sky/cyan mesh +
            slow-drifting orbs + faint noise grain. The form column on the
            left stays a clean white field; this column carries the visual
            weight. */}
        <div className="absolute inset-0 pointer-events-none -z-10" aria-hidden>
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 90% 70% at 70% 25%, rgba(14,165,233,0.16), transparent 65%)," +
                "radial-gradient(ellipse 80% 60% at 25% 85%, rgba(56,189,248,0.12), transparent 65%)," +
                "radial-gradient(ellipse 60% 50% at 90% 75%, rgba(125,211,252,0.10), transparent 65%)",
            }}
          />
          <div
            className="absolute inset-0 hidden dark:block"
            style={{
              background:
                "radial-gradient(ellipse 80% 60% at 70% 20%, rgba(14,165,233,0.22), transparent 60%)," +
                "radial-gradient(ellipse 70% 60% at 30% 90%, rgba(139,92,246,0.18), transparent 60%)",
            }}
          />
          <div className="absolute top-[8%] right-[8%] w-[420px] h-[420px] rounded-full bg-sky-300/45 dark:bg-sky-500/35 blur-[100px] login-orb-a" />
          <div className="absolute bottom-[6%] left-[10%] w-[360px] h-[360px] rounded-full bg-cyan-200/40 dark:bg-violet-500/30 blur-[100px] login-orb-b" />
          <div className="absolute top-[42%] right-[34%] w-[280px] h-[280px] rounded-full bg-white/55 dark:bg-white/0 blur-[80px] login-orb-c" />
          <div
            className="absolute inset-0 opacity-[0.04] dark:opacity-[0.07] mix-blend-overlay"
            style={{
              backgroundImage:
                "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.5 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")",
            }}
          />
        </div>

        {/* Eyebrow pill */}
        <div
          className="mb-5 animate-stagger-in"
          style={{ animationDelay: "0ms" }}
        >
          <span className="inline-flex items-center gap-2 rounded-full bg-emerald-500/[0.08] dark:bg-emerald-400/[0.1] px-3.5 py-1.5">
            <span className="relative flex h-[6px] w-[6px]">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex rounded-full h-[6px] w-[6px] bg-emerald-500" />
            </span>
            <span className="text-[11px] font-medium tracking-[0.04em] text-emerald-700 dark:text-emerald-300">
              Open Source
            </span>
          </span>
        </div>

        {/* Marketing headline — kept as h2 because the form panel below has the
            authoritative h1 (visually hidden, always present in DOM). */}
        <h2
          className="text-[32px] xl:text-[36px] font-semibold text-content-primary leading-[1.08] tracking-[-0.025em] animate-stagger-in"
          style={{ animationDelay: "60ms" }}
        >
          {t("login.hero_h_a", { defaultValue: "The" })}{" "}
          <span className="bg-gradient-to-r from-oe-blue to-sky-500 bg-clip-text text-transparent">
            #1
          </span>{" "}
          {t("login.hero_h_b", { defaultValue: "open-source workspace for" })}{" "}
          <span className="bg-gradient-to-r from-oe-blue to-sky-500 bg-clip-text text-transparent">
            {t("login.hero_h_c", {
              defaultValue: "construction project management",
            })}
          </span>
        </h2>

        {/* Subhead */}
        <p
          className="mt-5 text-[17px] text-content-secondary/70 leading-[1.65] tracking-[-0.008em] max-w-[420px] animate-stagger-in"
          style={{ animationDelay: "120ms" }}
        >
          {t("login.hero_desc", {
            defaultValue:
              "Plan, estimate, schedule, tender — every step of a project on one professional platform.",
          })}
        </p>

        {/* Stats row */}
        <div
          className="mt-5 flex items-center gap-5 animate-stagger-in"
          style={{ animationDelay: "180ms" }}
        >
          {[
            {
              value: "55K+",
              label: t("login.stat_costs", { defaultValue: "cost items‌⁠‍" }),
            },
            {
              value: "24",
              label: t("login.stat_langs", { defaultValue: "languages‌⁠‍" }),
            },
            {
              value: "48",
              label: t("login.stat_regions", { defaultValue: "regions‌⁠‍" }),
            },
            {
              value: "6",
              label: t("login.stat_cad", { defaultValue: "CAD formats‌⁠‍" }),
            },
            {
              value: "100+",
              label: t("login.stat_modules", { defaultValue: "modules‌⁠‍" }),
            },
            {
              value: "12",
              label: t("login.stat_sections", { defaultValue: "sections‌⁠‍" }),
            },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-[22px] font-semibold text-content-primary tracking-tight">
                {s.value}
              </div>
              <div className="text-[11px] text-content-tertiary mt-0.5">
                {s.label}
              </div>
            </div>
          ))}
        </div>

        {/* Divider */}
        <div
          className="mt-5 mb-4 h-px bg-gradient-to-r from-content-primary/[0.06] via-content-primary/[0.1] to-transparent animate-stagger-in"
          style={{ animationDelay: "220ms" }}
        />

        {/* Module honeycomb — proper pointy-top hex grid where every cell
            shares an edge with its neighbours. Layout is intentionally
            wider on the top/bottom rows (6 cells) than on the middle
            row (5 cells) so it reads as a real, naturally-extending
            honeycomb. Every cell is a real module — no decorative
            placeholders. Math:
              hex width   = 88px (left vertex to right vertex)
              hex height  = 100px (top vertex to bottom vertex)
              row stride  = 75px (3/4 of height — pointy-top step)
              column step = 88px (one hex width on the same row)
              alternating rows are offset by 44px (half a hex) — that's
              what makes the slanted edges meet exactly. */}
        <div
          className="relative mt-1 mr-auto h-[280px] w-[560px] max-w-full overflow-hidden animate-stagger-in"
          style={{ animationDelay: "260ms" }}
        >
          {(
            [
              // Top row (y = -75) — 6 cells, offset by 44.
              {
                x: -220,
                y: -75,
                icon: ShieldCheck,
                label: t("login.mod.local", { defaultValue: "Local" }),
              },
              {
                x: -132,
                y: -75,
                icon: Brain,
                label: t("login.mod.ai", { defaultValue: "AI" }),
              },
              {
                x: -44,
                y: -75,
                icon: Ruler,
                label: t("login.mod.takeoff", { defaultValue: "Takeoff" }),
              },
              {
                x: 44,
                y: -75,
                icon: PenTool,
                label: t("login.mod.cad", { defaultValue: "CAD" }),
              },
              {
                x: 132,
                y: -75,
                icon: Box,
                label: t("login.mod.bim", { defaultValue: "BIM" }),
              },
              {
                x: 220,
                y: -75,
                icon: TrendingUp,
                label: t("login.mod.cost5d", { defaultValue: "5D" }),
              },
              // Mid row (y = 0) — 5 cells aligned on the same axis.
              {
                x: -176,
                y: 0,
                icon: Database,
                label: t("login.mod.costs", { defaultValue: "Costs" }),
              },
              {
                x: -88,
                y: 0,
                icon: FileSpreadsheet,
                label: t("login.mod.boq", { defaultValue: "BOQ" }),
              },
              {
                x: 0,
                y: 0,
                icon: Layers,
                label: t("login.mod.core", { defaultValue: "Workspace" }),
                accent: true,
              },
              {
                x: 88,
                y: 0,
                icon: CalendarClock,
                label: t("login.mod.schedule", { defaultValue: "Schedule" }),
              },
              {
                x: 176,
                y: 0,
                icon: BarChart3,
                label: t("login.mod.tender", { defaultValue: "Tendering" }),
              },
              // Bottom row (y = 75) — 6 cells, offset by 44.
              {
                x: -220,
                y: 75,
                icon: Zap,
                label: t("login.mod.realtime", { defaultValue: "Realtime" }),
              },
              {
                x: -132,
                y: 75,
                icon: Boxes,
                label: t("login.mod.resources", { defaultValue: "Resources" }),
              },
              {
                x: -44,
                y: 75,
                icon: ClipboardList,
                label: t("login.mod.tasks", { defaultValue: "Tasks" }),
              },
              {
                x: 44,
                y: 75,
                icon: FileCheck,
                label: t("login.mod.validate", { defaultValue: "Validate" }),
              },
              {
                x: 132,
                y: 75,
                icon: FolderOpen,
                label: t("login.mod.files", { defaultValue: "Files" }),
              },
              {
                x: 220,
                y: 75,
                icon: Upload,
                label: t("login.mod.exports", { defaultValue: "Exports" }),
              },
            ] as const
          ).map((cell, idx) => {
            const isAccent = "accent" in cell && cell.accent === true;
            const Icon = cell.icon;
            return (
              // Outer wrapper handles ABSOLUTE POSITIONING only — its
              // transform is the hex-grid offset and must never be
              // overridden by an animation. Animations live on the inner
              // cell so they don't fight with our positioning maths.
              <div
                key={idx}
                className="absolute top-1/2 left-1/2"
                style={{
                  transform: `translate(calc(-50% + ${cell.x}px), calc(-50% + ${cell.y}px))`,
                }}
              >
                <div
                  className={`relative flex flex-col items-center justify-center w-[88px] h-[100px] animate-fade-in transition-transform duration-300 hover:scale-[1.05] ${
                    isAccent ? "text-white" : "text-content-primary"
                  }`}
                  style={{
                    animationDelay: `${280 + idx * 35}ms`,
                    animationFillMode: "both",
                    clipPath:
                      "polygon(50% 2%, 100% 26%, 100% 74%, 50% 98%, 0% 74%, 0% 26%)",
                    background: isAccent
                      ? "linear-gradient(135deg, #0ea5e9 0%, #0284c7 65%, #0369a1 100%)"
                      : "linear-gradient(180deg, rgba(255,255,255,0.97), rgba(244,250,255,0.82))",
                    boxShadow: isAccent
                      ? "0 18px 32px -12px rgba(14,165,233,0.55), inset 0 1px 0 rgba(255,255,255,0.35)"
                      : "0 8px 18px -8px rgba(15,23,42,0.10), inset 0 1px 0 rgba(255,255,255,0.9), inset 0 0 0 1px rgba(14,165,233,0.06)",
                  }}
                >
                  <Icon
                    size={isAccent ? 22 : 18}
                    strokeWidth={isAccent ? 2 : 1.65}
                    className={isAccent ? "" : "text-oe-blue/90"}
                  />
                  <span
                    className={`mt-[5px] text-[10px] font-semibold tracking-[-0.01em] ${
                      isAccent ? "text-white/95" : "text-content-primary/85"
                    }`}
                  >
                    {cell.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Value props — restored as a clean two-up grid with refined
            typography (no boxed icon backgrounds, accent rule above each
            title) so the marketing column lands on something concrete
            after the honeycomb. */}
        <div className="mt-2 flex flex-wrap items-start gap-x-5 gap-y-2 animate-stagger-in" style={{ animationDelay: '320ms' }}>