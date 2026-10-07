"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useMemo, useState } from "react";
import {
  Bell,
  ChevronDown,
  ChevronRight,
  FileText,
  Gavel,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  ShieldCheck,
  UserRound,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ThemeToggle } from "@/components/common/theme-provider";
import { useAuth } from "@/lib/auth-context";
import type { User, UserRole } from "@/types/auth";

const roleLabels: Record<UserRole, string> = {
  OWNER: "Will Owner",
  MEMBER: "Member",
  WITNESS: "Witness",
  BENEFICIARY: "Beneficiary",
  LAWYER_VERIFIER: "Legal Verifier",
  ADMINISTRATOR: "Administrator",
};

type NavigationLink = { label: string; href: string; icon: LucideIcon };
type NavigationGroup = NavigationLink & { children?: NavigationLink[] };

const roleNavigation: Record<UserRole, NavigationGroup[]> = {
  OWNER: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "My Profile", href: "/profile", icon: UserRound },
    { label: "My Will", href: "/dashboard/wills", icon: FileText, children: [
      { label: "Will Overview", href: "/dashboard/wills", icon: FileText },
      { label: "Beneficiaries", href: "/dashboard/wills#beneficiaries", icon: Users },
    ] },
    { label: "People", href: "/dashboard#people", icon: Users, children: [
      { label: "Lawyer", href: "/dashboard#people", icon: Gavel },
      { label: "Witness", href: "/dashboard#people", icon: UserCheck },
      { label: "Beneficiaries", href: "/dashboard/wills#beneficiaries", icon: Users },
    ] },
    { label: "Verification", href: "/dashboard#verification", icon: ShieldCheck },
    { label: "Notifications", href: "/dashboard#notifications", icon: Bell },
    { label: "Security", href: "/dashboard#security", icon: ShieldCheck, children: [
      { label: "Account Settings", href: "/profile", icon: UserRound },
      { label: "Change Password", href: "/profile#change-password", icon: ShieldCheck },
    ] },
  ],
  MEMBER: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "My Profile", href: "/profile", icon: UserRound },
    { label: "My Will", href: "/dashboard/wills", icon: FileText, children: [
      { label: "Will Overview", href: "/dashboard/wills", icon: FileText },
      { label: "Beneficiaries", href: "/dashboard/wills#beneficiaries", icon: Users },
    ] },
    { label: "People", href: "/dashboard#role-workspace", icon: Users, children: [
      { label: "My Relationships", href: "/dashboard#role-workspace", icon: Users },
    ] },
    { label: "Notifications", href: "/dashboard#notifications", icon: Bell },
    { label: "Security", href: "/dashboard#security", icon: ShieldCheck, children: [
      { label: "Account Settings", href: "/profile", icon: UserRound },
      { label: "Change Password", href: "/profile#change-password", icon: ShieldCheck },
    ] },
  ],
  BENEFICIARY: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "My Profile", href: "/profile", icon: UserRound },
    { label: "People", href: "/dashboard#role-workspace", icon: Users, children: [
      { label: "My Relationships", href: "/dashboard#role-workspace", icon: Users },
    ] },
    { label: "Verification", href: "/dashboard#verification", icon: ShieldCheck },
    { label: "Notifications", href: "/dashboard#notifications", icon: Bell },
    { label: "Security", href: "/dashboard#security", icon: ShieldCheck, children: [
      { label: "Account Settings", href: "/profile", icon: UserRound },
      { label: "Change Password", href: "/profile#change-password", icon: ShieldCheck },
    ] },
  ],
  WITNESS: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "My Profile", href: "/profile", icon: UserRound },
    { label: "People", href: "/dashboard#role-workspace", icon: Users, children: [
      { label: "Lawyer", href: "/dashboard#role-workspace", icon: Gavel },
      { label: "Witness", href: "/dashboard#role-workspace", icon: UserCheck },
    ] },
    { label: "Verification", href: "/dashboard#verification", icon: ShieldCheck },
    { label: "Notifications", href: "/dashboard#notifications", icon: Bell },
    { label: "Security", href: "/dashboard#security", icon: ShieldCheck, children: [
      { label: "Account Settings", href: "/profile", icon: UserRound },
      { label: "Change Password", href: "/profile#change-password", icon: ShieldCheck },
    ] },
  ],
  LAWYER_VERIFIER: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "My Profile", href: "/profile", icon: UserRound },
    { label: "Verification", href: "/dashboard#role-workspace", icon: ShieldCheck },
    { label: "Notifications", href: "/dashboard#notifications", icon: Bell },
    { label: "Security", href: "/dashboard#security", icon: ShieldCheck, children: [
      { label: "Account Settings", href: "/profile", icon: UserRound },
      { label: "Change Password", href: "/profile#change-password", icon: ShieldCheck },
    ] },
  ],
  ADMINISTRATOR: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "My Profile", href: "/profile", icon: UserRound },
    { label: "Notifications", href: "/dashboard#notifications", icon: Bell },
    { label: "Security", href: "/dashboard#security", icon: ShieldCheck, children: [
      { label: "Account Settings", href: "/profile", icon: UserRound },
      { label: "Change Password", href: "/profile#change-password", icon: ShieldCheck },
    ] },
  ],
};

function avatarUrl(url: string | null | undefined) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  const apiOrigin = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/api\/v1\/?$/, "");
  return `${apiOrigin}${url}`;
}

export function DashboardShell({ children, profileUser }: { children: ReactNode; profileUser?: User | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user: authUser, signOut, busy } = useAuth();
  const user = profileUser ?? authUser;
  const [search, setSearch] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({ "My Will": true, People: true, Security: true });
  const links = user ? roleNavigation[user.role] : roleNavigation.MEMBER;
  const visibleLinks = useMemo(
    () => links.flatMap((group) => {
      const query = search.trim().toLowerCase();
      if (!query) return [group];
      if (group.label.toLowerCase().includes(query)) return [group];
      const children = group.children?.filter((child) => child.label.toLowerCase().includes(query));
      return children?.length ? [{ ...group, children }] : [];
    }),
    [links, search],
  );
  const name = user ? `${user.first_name} ${user.last_name}`.trim() : "WillChain Member";

  async function handleSignOut() {
    await signOut();
    router.push("/login");
  }

  return (
    <div className="dashboard-shell">
      <aside className={`dashboard-sidebar ${mobileOpen ? "is-open" : ""}`}>
        <Link href="/dashboard" className="dashboard-sidebar-brand" onClick={() => setMobileOpen(false)}>
          <span className="dashboard-logo"><ShieldCheck size={20} /></span>
          <span><strong>WillChain SL</strong><small>Secure wills. Trusted futures.</small></span>
        </Link>
        <nav aria-label="Role-specific navigation" className="dashboard-sidebar-nav">
          {visibleLinks.map(({ label, href, icon: Icon, children }) => {
            const targetPath = href.split("#")[0];
            const active = pathname === targetPath && (targetPath !== "/dashboard" || href === "/dashboard");
            return (
              <div key={label}>
                {children ? (
                  <button type="button" className={`dashboard-nav-link dashboard-nav-group ${active ? "active" : ""}`} aria-expanded={Boolean(expandedGroups[label])} onClick={() => setExpandedGroups((current) => ({ ...current, [label]: !current[label] }))}>
                    <Icon size={17} /><span>{label}</span>{expandedGroups[label] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>
                ) : (
                  <Link href={href} aria-current={active ? "page" : undefined} className={`dashboard-nav-link ${active ? "active" : ""}`} onClick={() => setMobileOpen(false)}>
                    <Icon size={17} /> <span>{label}</span>
                  </Link>
                )}
                {children && (expandedGroups[label] || Boolean(search.trim())) && <div className="dashboard-nav-children">{children.map((child) => {
                  const ChildIcon = child.icon;
                  return <Link key={`${label}-${child.label}`} href={child.href} className="dashboard-nav-child" onClick={() => setMobileOpen(false)}><ChildIcon size={14} /><span>{child.label}</span></Link>;
                })}</div>}
              </div>
            );
          })}
          {visibleLinks.length === 0 && <p className="dashboard-no-results">No matching navigation.</p>}
        </nav>
        <div className="dashboard-sidebar-private"><ShieldCheck size={17} /><span><strong>Protected Workspace</strong><small>Your data is secure and private.</small></span></div>
      </aside>

      {mobileOpen && <button type="button" className="dashboard-sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <button type="button" className="dashboard-mobile-menu" aria-label={mobileOpen ? "Close navigation" : "Open navigation"} aria-expanded={mobileOpen} onClick={() => setMobileOpen((open) => !open)}>{mobileOpen ? <X size={19} /> : <Menu size={19} />}</button>
          <label className="dashboard-search"><Search size={16} /><input aria-label="Search navigation" placeholder="Search navigation..." value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="dashboard-topbar-actions">
            <ThemeToggle />
            <Link href="/dashboard#notifications" className="dashboard-notification-button" aria-label="View notifications"><Bell size={18} /></Link>
            {user && <div className="dashboard-user-menu">
              <button type="button" className="dashboard-user-chip" aria-haspopup="menu" aria-expanded={profileMenuOpen} onClick={() => setProfileMenuOpen((open) => !open)}>
                <span className="dashboard-user-avatar">{avatarUrl(user.avatar) ? <img src={avatarUrl(user.avatar)} alt="" /> : name.slice(0, 1).toUpperCase()}</span>
                <span><strong>{name}</strong><small>{roleLabels[user.role]}</small></span>
                <ChevronDown size={14} />
              </button>
              {profileMenuOpen && <div className="dashboard-user-dropdown" role="menu">
                <Link href="/profile" role="menuitem" onClick={() => setProfileMenuOpen(false)}>My Profile</Link>
                <Link href="/dashboard" role="menuitem" onClick={() => setProfileMenuOpen(false)}>Dashboard</Link>
                <button type="button" role="menuitem" disabled={busy} onClick={handleSignOut}><LogOut size={14} /> Sign out</button>
              </div>}
            </div>}
          </div>
        </header>
        <main className="dashboard-content">{children}</main>
        <footer className="dashboard-footer"><span>WillChain SL</span><span>Protected Workspace</span><span>Secure access by role</span></footer>
      </div>
    </div>
  );
}
