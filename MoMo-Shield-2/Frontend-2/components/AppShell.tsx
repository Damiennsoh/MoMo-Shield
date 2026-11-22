'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  Activity,
  Bell,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Command,
  Fingerprint,
  LayoutDashboard,
  Menu,
  Moon,
  Network,
  Radio,
  RotateCcw,
  Settings2,
  Shield,
  Smartphone,
  Sun,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStore } from '@/lib/useStore';
import { resetDemoSession } from '@/lib/api';

const navItems = [
  { href: '/', label: 'Command Center', icon: LayoutDashboard },
  { href: '/lab', label: 'Live Signal Lab', icon: Radio, marker: 'LAB' },
  { href: '/handset', label: 'Handset Simulator', icon: Smartphone },
  { href: '/#campaigns', label: 'Campaign Intelligence', icon: Network },
  { href: '/#threat-feed', label: 'Glance Threat Feed', icon: Fingerprint },
  { href: '/settings', label: 'Settings & API Keys', icon: Settings2 },
];

export function BrandMark() {
  return (
    <span className="relative grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#ffcc00] text-[#0a0f16] shadow-[0_4px_20px_rgba(255,204,0,.25)]">
      <Shield size={22} strokeWidth={2.6} />
      <span className="absolute bottom-[9px] right-[10px] h-[3px] w-[8px] rounded-full bg-[#1e293b]" />
    </span>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const connected = useStore((state) => state.connected);
  const backendReachable = useStore((state) => state.backendReachable);
  const avgLatencyMs = useStore((state) => state.avgLatencyMs);
  const soundEnabled = useStore((state) => state.soundEnabled);
  const toggleSound = useStore((state) => state.toggleSound);
  const resetDemo = useStore((state) => state.resetDemo);

  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    const saved = window.localStorage.getItem('momo-shield-theme');
    const preferred =
      saved === 'light' || saved === 'dark'
        ? saved
        : window.matchMedia('(prefers-color-scheme: light)').matches
        ? 'light'
        : 'dark';
    setTheme(preferred);
  }, []);

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    window.localStorage.setItem('momo-shield-theme', next);
    setNotice(`${next === 'light' ? 'Light' : 'Dark'} theme enabled`);
    window.setTimeout(() => setNotice(''), 2400);
  };

  const handleSoundToggle = () => {
    toggleSound();
    const next = !soundEnabled;
    setNotice(next ? 'Internal demo sound enabled' : 'Internal demo sound muted (ideal for real phone demo)');
    window.setTimeout(() => setNotice(''), 3000);
  };

  const handleResetDemo = async () => {
    resetDemo();
    await resetDemoSession();
    setNotice('Session reset — Ready for new demo run');
    window.setTimeout(() => setNotice(''), 2400);
  };

  const title =
    pathname === '/lab'
      ? 'Live Signal Lab'
      : pathname === '/handset'
      ? 'Handset Simulator'
      : pathname === '/settings'
      ? 'Settings & API Keys'
      : 'Command Center';

  return (
    <div className="console-bg min-h-screen" data-theme={theme}>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-white/[.12] bg-[#090d14]/98 py-5 backdrop-blur-2xl transition-[width] duration-200 lg:flex shadow-2xl',
          collapsed ? 'w-[80px] px-3' : 'w-[256px] px-4'
        )}
      >
        <div className={cn('flex items-center', collapsed ? 'justify-center' : 'justify-between px-1')}>
          <Link href="/" className={cn('flex items-center gap-3', collapsed && 'justify-center')} title="MoMo Shield">
            <BrandMark />
            {!collapsed && (
              <span>
                <span className="block text-[15px] font-extrabold tracking-tight text-white">
                  MoMo <span className="text-[#ffcc00]">Shield</span>
                </span>
                <span className="mt-0.5 block text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">
                  Fraud Intelligence
                </span>
              </span>
            )}
          </Link>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={cn(
              'grid h-7 w-7 place-items-center rounded-md border border-white/[.12] text-slate-400 transition hover:bg-white/[.08] hover:text-white',
              collapsed && 'absolute -right-3 top-7 bg-[#090d14]'
            )}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>

        <div className={cn('mt-8 flex items-center justify-between', collapsed ? 'px-2' : 'px-2')}>
          <span className="text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">
            {collapsed ? '—' : 'Workspace'}
          </span>
          {!collapsed && (
            <span className="rounded-md border border-white/10 bg-white/[.04] px-2 py-0.5 font-mono text-[9px] font-semibold text-slate-300">
              ACCRA · GH
            </span>
          )}
        </div>

        <nav className="mt-3 space-y-1.5" aria-label="Primary navigation">
          {navItems.map(({ href, label, icon: Icon, marker }) => {
            const active = href === '/' ? pathname === '/' : !href.startsWith('/#') && pathname === href;
            return (
              <Link
                key={label}
                href={href}
                title={collapsed ? label : undefined}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'group flex h-10 items-center gap-3 rounded-lg text-xs font-semibold transition',
                  collapsed ? 'justify-center px-2' : 'px-3',
                  active
                    ? 'border border-[#ffcc00]/25 bg-[#ffcc00]/15 text-[#ffe066] shadow-sm'
                    : 'text-slate-300 hover:bg-white/[.07] hover:text-white'
                )}
              >
                <Icon
                  size={16}
                  className={cn('shrink-0', active ? 'text-[#ffcc00]' : 'text-slate-400 group-hover:text-slate-200')}
                />
                {!collapsed && (
                  <>
                    <span className="flex-1">{label}</span>
                    {marker && (
                      <span className="rounded bg-[#ffcc00]/20 px-1.5 py-0.5 text-[9px] font-extrabold tracking-wider text-[#ffcc00]">
                        {marker}
                      </span>
                    )}
                    {active && <span className="h-1.5 w-1.5 rounded-full bg-[#ffcc00] shadow-[0_0_8px_#ffcc00]" />}
                  </>
                )}
              </Link>
            );
          })}
        </nav>

        {!collapsed && (
          <>
            {/* Backend telemetry live status */}
            <div className="mt-7 border-t border-white/[.08] pt-4">
              <p className="px-2 text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">Backend Status</p>
              <div className="mt-2.5 rounded-xl border border-white/[.1] bg-white/[.03] p-3 shadow-inner">
                <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
                  <span
                    className={cn(
                      'h-2 w-2 rounded-full',
                      connected ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' : backendReachable ? 'bg-amber-400' : 'bg-rose-400'
                    )}
                  />
                  <span className="flex-1">Intelligence Core</span>
                  <span
                    className={cn(
                      'font-semibold',
                      connected ? 'text-emerald-300' : backendReachable ? 'text-amber-300' : 'text-rose-300'
                    )}
                  >
                    {connected ? 'Live Feed' : backendReachable ? 'Reconnecting' : 'Offline'}
                  </span>
                </div>
                <p className="mt-1.5 pl-4 text-[10px] text-slate-400">Active WebSocket telemetry connection</p>
              </div>
            </div>

            {/* Sandbox environment badge */}
            <div className="mt-auto rounded-xl border border-white/[.1] bg-gradient-to-br from-[#131b26] to-[#0a0f16] p-3.5 shadow-md">
              <div className="flex items-center gap-2.5">
                <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#ffcc00]/15 text-[#ffcc00]">
                  <Command size={15} />
                </div>
                <div>
                  <p className="text-xs font-bold text-white">MoMo Shield Sandbox</p>
                  <p className="mt-0.5 text-[10px] text-slate-400">InnoFemme · Middleware API</p>
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between text-[10px] border-t border-white/[.07] pt-2">
                <span className="text-slate-400 font-medium">Gateway Region</span>
                <span className="font-mono text-slate-200 font-semibold">af-south-1 (Accra)</span>
              </div>
            </div>

            {/* Analyst profile */}
            <div className="mt-3 flex items-center gap-2.5 border-t border-white/[.08] pt-3 px-1">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-white/20 bg-slate-800 text-xs font-bold text-white">
                AD
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-bold text-white">Ayine Damien</p>
                <p className="text-[10px] text-slate-400">Security Analyst</p>
              </div>
              <ChevronDown size={14} className="text-slate-400" />
            </div>
          </>
        )}
      </aside>

      {/* Main Area */}
      <div className={cn('min-h-screen transition-[padding] duration-200', collapsed ? 'lg:pl-[80px]' : 'lg:pl-[256px]')}>
        {/* Header Bar */}
        <header className="sticky top-0 z-30 flex h-[64px] items-center justify-between border-b border-white/[.1] bg-[#070b10]/90 px-4 backdrop-blur-xl md:px-7 shadow-sm">
          <div className="flex items-center gap-3">
            <button
              className="grid h-8 w-8 place-items-center rounded-lg border border-white/[.12] text-slate-300 lg:hidden"
              onClick={() => setOpen(!open)}
              aria-label="Open navigation"
            >
              {open ? <X size={16} /> : <Menu size={16} />}
            </button>
            <div className="hidden items-center gap-2 text-xs text-slate-400 sm:flex">
              <span className="font-medium">Workspace</span>
              <span>/</span>
              <span className="font-semibold text-white">{title}</span>
            </div>
            <span className="text-xs font-bold text-white sm:hidden">{title}</span>
          </div>

          <div className="flex items-center gap-2 md:gap-3">
            {/* Demo Reset button */}
            <button
              onClick={handleResetDemo}
              className="flex items-center gap-1.5 rounded-lg border border-white/[.14] bg-white/[.04] px-2.5 py-1.5 text-xs font-semibold text-slate-300 transition hover:bg-white/[.1] hover:text-white"
              title="Reset session state for clean demo run"
              aria-label="Reset demo session"
            >
              <RotateCcw size={13} className="text-[#ffcc00]" />
              <span className="hidden xl:inline">Reset Demo</span>
            </button>

            {/* Real phone / Sound mute option */}
            <button
              onClick={handleSoundToggle}
              className={cn(
                'flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold transition',
                soundEnabled
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                  : 'border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20'
              )}
              title={
                soundEnabled
                  ? 'Internal Demo Sound: ON (Click to mute laptop audio so it doesn’t interfere with real phone ring/voice)'
                  : 'Internal Demo Sound: MUTED (Protects real phone demonstration from laptop echo)'
              }
              aria-label={soundEnabled ? 'Mute internal audio' : 'Unmute internal audio'}
            >
              {soundEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
              <span className="hidden sm:inline">
                {soundEnabled ? 'Laptop Sound: ON' : 'Laptop Sound: MUTED (Phone Mode)'}
              </span>
            </button>

            <span className="hidden h-5 w-px bg-white/10 md:block" />

            {/* Sandbox Connection & Latency */}
            <span className="hidden items-center gap-2 text-xs font-medium text-slate-300 md:flex">
              <span className={cn('h-2 w-2 rounded-full', connected ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' : 'bg-amber-400')} />
              <span>Sandbox Link</span>
            </span>

            <span className="hidden items-center gap-1.5 text-xs font-medium text-slate-300 sm:flex">
              <Activity size={14} className="text-emerald-400" />
              <span>{avgLatencyMs != null ? `${avgLatencyMs} ms` : 'Standby'}</span>
            </span>

            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="grid h-9 w-9 place-items-center rounded-lg border border-white/[.12] bg-white/[.04] text-slate-200 transition hover:bg-white/[.1] hover:text-white"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {/* Notifications */}
            <button
              className="relative grid h-9 w-9 place-items-center rounded-lg border border-white/[.12] bg-white/[.04] text-slate-200 transition hover:bg-white/[.1] hover:text-white"
              aria-label="Notifications"
            >
              <Bell size={15} />
              <span className="absolute right-[8px] top-[7px] h-2 w-2 rounded-full bg-rose-500 shadow-[0_0_6px_#f43f5e]" />
            </button>

            <div className="hidden h-8 w-8 place-items-center rounded-full border border-white/20 bg-slate-800 text-xs font-bold text-white md:grid">
              AD
            </div>
          </div>
        </header>

        {/* Mobile Navigation Drawer */}
        {open && (
          <div className="fixed inset-0 z-40 bg-black/80 lg:hidden" onClick={() => setOpen(false)}>
            <div className="h-full w-[280px] border-r border-white/10 bg-[#090d14] p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
              <Link href="/" onClick={() => setOpen(false)} className="flex items-center gap-3">
                <BrandMark />
                <span className="text-base font-extrabold text-white">
                  MoMo <span className="text-[#ffcc00]">Shield</span>
                </span>
              </Link>
              <nav className="mt-8 space-y-2">
                {navItems.map(({ href, label, icon: Icon }) => (
                  <Link
                    key={label}
                    href={href}
                    onClick={() => setOpen(false)}
                    className="flex h-11 items-center gap-3 rounded-lg px-3 text-xs font-semibold text-slate-200 hover:bg-white/[.08]"
                  >
                    <Icon size={16} />
                    {label}
                  </Link>
                ))}
              </nav>
            </div>
          </div>
        )}

        {/* Content Body */}
        <main className="mx-auto max-w-[1720px] px-4 pb-24 pt-6 md:px-7 md:pb-10 md:pt-7">{children}</main>

        {/* Accessibility Toast */}
        <div className="sr-only" role="status" aria-live="polite">
          {notice}
        </div>

        {/* Mobile bottom nav */}
        <nav
          className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-white/[.1] bg-[#070b10]/98 px-2 pb-[max(8px,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl lg:hidden shadow-2xl"
          aria-label="Mobile navigation"
        >
          {[
            { href: '/', label: 'Overview', icon: LayoutDashboard },
            { href: '/lab', label: 'Signal Lab', icon: Radio },
            { href: '/handset', label: 'Handset', icon: Smartphone },
            { href: '/settings', label: 'Settings', icon: Settings2 },
          ].map(({ href, label, icon: Icon }) => (
            <Link
              key={label}
              href={href}
              aria-current={pathname === href ? 'page' : undefined}
              className={cn(
                'flex flex-col items-center gap-1 py-1 text-[10px] font-semibold',
                pathname === href ? 'text-[#ffcc00]' : 'text-slate-400'
              )}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
