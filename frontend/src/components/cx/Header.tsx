import { NavLink } from "react-router-dom";
import { PackageSearch, UsersRound, LifeBuoy, Bot } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { to: "/", label: "Overview", icon: null, testid: "nav-overview" },
  { to: "/data-quality", label: "Data Audit", icon: PackageSearch, testid: "nav-data-quality" },
  { to: "/segments", label: "Segments & Lapse", icon: UsersRound, testid: "nav-segments" },
  { to: "/triage", label: "Ticket Triage", icon: LifeBuoy, testid: "nav-triage" },
  { to: "/copilot", label: "Policy & Refund Agent", icon: Bot, testid: "nav-copilot" },
];

export default function Header() {
  return (
    <header className="sticky top-0 z-40 h-14 border-b border-border/60 bg-[#0b0e14]/85 backdrop-blur-xl dark:bg-[#0b0e14]/85">
      <div className="mx-auto flex h-full max-w-[1600px] items-center gap-4 px-4 sm:px-6 lg:px-8">
        <NavLink to="/" data-testid="nav-brand" className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary font-heading text-sm font-bold text-primary-foreground">
            i
          </span>
          <span className="font-heading text-sm font-semibold tracking-tight">
            Instamart CX Copilot
          </span>
        </NavLink>
        <span
          data-testid="header-dataset-pill"
          className="hidden items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-[11px] font-medium text-muted-foreground md:flex"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Synthetic 12.3k dataset · offline mock LLM
        </span>
        <nav className="ml-auto flex items-center gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.to === "/"}
              data-testid={t.testid}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors duration-150",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted",
                )
              }
            >
              {t.icon && <t.icon className="h-3.5 w-3.5" />}
              {t.label}
            </NavLink>
          ))}
        </nav>
        <span
          data-testid="header-currency-pill"
          className="hidden rounded-full border border-border bg-muted px-2.5 py-1 font-mono text-[11px] text-muted-foreground lg:block"
        >
          INR ₹
        </span>
      </div>
    </header>
  );
}