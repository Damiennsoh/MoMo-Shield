'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Activity, Bell, ChevronDown, ChevronLeft, ChevronRight, Command, Fingerprint, LayoutDashboard, Menu, Moon, Network, Radio, Settings2, Shield, Smartphone, Sun, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStore } from '@/lib/useStore';

const navItems = [
  { href: '/', label: 'Command Center', icon: LayoutDashboard },
  { href: '/lab', label: 'Live Signal Lab', icon: Radio, marker: 'LAB' },
  { href: '/handset', label: 'Handset Simulator', icon: Smartphone },
  { href: '/#campaigns', label: 'Campaign Intelligence', icon: Network },
  { href: '/#threat-feed', label: 'Glance Threat Feed', icon: Fingerprint },
  { href: '/settings', label: 'Settings & API Keys', icon: Settings2 },
];
export function BrandMark() { return <span className="relative grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#ffcc00] text-[#17202a] shadow-[0_4px_18px_rgba(255,204,0,.16)]"><Shield size={20} strokeWidth={2.6} /><span className="absolute bottom-[8px] right-[9px] h-[3px] w-[7px] rounded-full bg-[#273039]" /></span>; }
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const connected = useStore((state) => state.connected);
  const backendReachable = useStore((state) => state.backendReachable);
  const avgLatencyMs = useStore((state) => state.avgLatencyMs);
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    const saved = window.localStorage.getItem('momo-shield-theme');
    const preferred = saved === 'light' || saved === 'dark' ? saved : window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    setTheme(preferred);
  }, []);
  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    window.localStorage.setItem('momo-shield-theme', next);
    setNotice(`${next === 'light' ? 'Light' : 'Dark'} theme enabled`);
    window.setTimeout(() => setNotice(''), 2400);
  };
  const title = pathname === '/lab' ? 'Live Signal Lab' : pathname === '/handset' ? 'Handset Simulator' : pathname === '/settings' ? 'Settings & API Keys' : 'Command Center';
  return <div className="console-bg min-h-screen" data-theme={theme}>
    <aside className={cn('fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-white/[.065] bg-[#0b1017]/95 py-5 backdrop-blur-xl transition-[width] duration-200 lg:flex', collapsed ? 'w-[78px] px-3' : 'w-[248px] px-4')}>
      <div className={cn('flex items-center', collapsed ? 'justify-center' : 'justify-between px-1')}><Link href="/" className={cn('flex items-center gap-3', collapsed && 'justify-center')} title="MoMo Shield"><BrandMark />{!collapsed && <span><span className="block text-[14px] font-bold tracking-[.01em] text-white">MoMo <span className="text-[#ffcc00]">Shield</span></span><span className="mt-0.5 block text-[9px] font-semibold uppercase tracking-[.19em] text-slate-600">Fraud intelligence</span></span>}</Link><button onClick={() => setCollapsed(!collapsed)} className={cn('grid h-7 w-7 place-items-center rounded-md border border-white/[.07] text-slate-600 transition hover:bg-white/[.05] hover:text-slate-200', collapsed && 'absolute -right-3 top-7 bg-[#0b1017]')} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{collapsed ? <ChevronRight size={13}/> : <ChevronLeft size={13}/>}</button></div>
      <div className={cn('mt-9 flex items-center justify-between', collapsed ? 'px-2' : 'px-2')}><span className="text-[9px] font-semibold uppercase tracking-[.18em] text-slate-600">{collapsed ? '—' : 'Workspace'}</span>{!collapsed && <span className="rounded border border-white/[.08] px-1.5 py-0.5 font-mono text-[8px] text-slate-500">ACCRA · GH</span>}</div>
      <nav className="mt-3 space-y-1" aria-label="Primary navigation">{navItems.map(({ href, label, icon: Icon, marker }) => { const active = href === '/' ? pathname === '/' : !href.startsWith('/#') && pathname === href; return <Link key={label} href={href} title={collapsed ? label : undefined} aria-current={active ? 'page' : undefined} className={cn('group flex h-10 items-center gap-3 rounded-lg text-[11px] font-medium transition', collapsed ? 'justify-center px-2' : 'px-3', active ? 'border border-[#ffcc00]/10 bg-[#ffcc00]/[.08] text-[#ffdb52]' : 'text-slate-500 hover:bg-white/[.045] hover:text-slate-200')}><Icon size={15} className={cn('shrink-0', active ? 'text-[#ffcc00]' : 'text-slate-500 group-hover:text-slate-300')} />{!collapsed && <><span className="flex-1">{label}</span>{marker && <span className="rounded bg-[#ffcc00]/10 px-1.5 py-0.5 text-[8px] font-bold tracking-wide text-[#ffdc59]">{marker}</span>}{active && <span className="h-1.5 w-1.5 rounded-full bg-[#ffcc00] shadow-[0_0_8px_#ffcc00]" />}</>}</Link>; })}</nav>
      {!collapsed && <><div className="mt-8 border-t border-white/[.06] pt-5"><p className="px-2 text-[9px] font-semibold uppercase tracking-[.18em] text-slate-600">Backend status</p><div className="mt-3 rounded-xl border border-white/[.06] bg-white/[.018] p-3"><div className="flex items-center gap-2 text-[10px] text-slate-400"><span className={cn('h-1.5 w-1.5 rounded-full', connected ? 'bg-emerald-400' : backendReachable ? 'bg-amber-300' : 'bg-rose-400')} /><span className="flex-1">Intelligence Core</span><span className={connected ? 'text-emerald-300' : backendReachable ? 'text-amber-300' : 'text-rose-300'}>{connected ? 'Streaming' : backendReachable ? 'Reconnecting' : 'Unavailable'}</span></div><p className="mt-2 pl-3.5 text-[9px] text-slate-600">Status reflects the live telemetry connection</p></div></div>
      <div className="mt-auto rounded-xl border border-white/[.07] bg-gradient-to-br from-[#141c25] to-[#0c1118] p-3.5"><div className="flex items-center gap-2"><div className="grid h-7 w-7 place-items-center rounded-lg bg-[#ffcc00]/10 text-[#ffcc00]"><Command size={14}/></div><div><p className="text-[10px] font-semibold text-slate-200">MoMo Shield Sandbox</p><p className="mt-0.5 text-[9px] text-slate-600">Sandbox · Intelligence Core API</p></div></div><div className="mt-3 flex items-center justify-between text-[9px]"><span className="text-slate-500">Region</span><span className="font-mono text-slate-400">af-south-1</span></div></div>
      <div className="mt-4 flex items-center gap-2 border-t border-white/[.06] pt-4"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-white/10 bg-slate-800 text-[10px] font-semibold text-slate-200">AD</div><div className="min-w-0 flex-1"><p className="truncate text-[10px] font-semibold text-slate-200">Ayine Damien</p><p className="text-[9px] text-slate-600">Security Analyst</p></div><ChevronDown size={13} className="text-slate-600"/></div></>}
    </aside>
    <div className={cn('min-h-screen transition-[padding] duration-200', collapsed ? 'lg:pl-[78px]' : 'lg:pl-[248px]')}>
      <header className="sticky top-0 z-30 flex h-[62px] items-center justify-between border-b border-white/[.06] bg-[#090d12]/85 px-4 backdrop-blur-xl md:px-7"><div className="flex items-center gap-3"><button className="grid h-8 w-8 place-items-center rounded-lg border border-white/[.09] text-slate-400 lg:hidden" onClick={() => setOpen(!open)} aria-label="Open navigation">{open ? <X size={16}/> : <Menu size={16}/>}</button><div className="hidden items-center gap-2 text-[10px] text-slate-600 sm:flex"><span>Workspace</span><span>/</span><span className="text-slate-300">{title}</span></div><span className="text-[11px] font-semibold text-slate-200 sm:hidden">{title}</span></div><div className="flex items-center gap-2 md:gap-4"><span className="hidden items-center gap-2 text-[10px] text-slate-500 md:flex"><span className="live-dot"/>Sandbox connection</span><span className="hidden h-4 w-px bg-white/10 md:block"/><span className="hidden items-center gap-1.5 text-[10px] text-slate-500 sm:flex"><Activity size={13} className="text-emerald-400"/><span>API latency · {avgLatencyMs != null ? `${avgLatencyMs} ms` : '—'}</span></span><button onClick={toggleTheme} className="grid h-9 w-9 place-items-center rounded-lg border border-white/[.08] text-slate-400 transition hover:bg-white/[.06]" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>{theme === 'dark' ? <Sun size={15}/> : <Moon size={15}/>}</button><button className="relative grid h-9 w-9 place-items-center rounded-lg border border-white/[.08] text-slate-400 transition hover:bg-white/[.06]" aria-label="Notifications"><Bell size={14}/><i className="absolute right-[7px] top-[6px] h-1.5 w-1.5 rounded-full bg-rose-400"/></button><div className="hidden h-7 w-7 place-items-center rounded-full border border-white/10 bg-slate-800 text-[9px] font-semibold text-slate-200 md:grid">AD</div></div></header>
      {open && <div className="fixed inset-0 z-40 bg-black/70 lg:hidden" onClick={() => setOpen(false)}><div className="h-full w-[280px] border-r border-white/10 bg-[#0b1017] p-5" onClick={(event) => event.stopPropagation()}><Link href="/" onClick={() => setOpen(false)} className="flex items-center gap-3"><BrandMark/><b className="text-sm text-white">MoMo <span className="text-[#ffcc00]">Shield</span></b></Link><nav className="mt-8 space-y-1">{navItems.map(({ href, label, icon: Icon }) => <Link key={label} href={href} onClick={() => setOpen(false)} className="flex h-11 items-center gap-3 rounded-lg px-3 text-xs text-slate-300 hover:bg-white/[.06]"><Icon size={15}/>{label}</Link>)}</nav></div></div>}
      <main className="mx-auto max-w-[1720px] px-4 pb-24 pt-6 md:px-7 md:pb-10 md:pt-7">{children}</main>
      <div className="sr-only" role="status" aria-live="polite">{notice}</div>
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-white/[.07] bg-[#0a0f16]/95 px-2 pb-[max(8px,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl lg:hidden" aria-label="Mobile navigation">{[{ href: '/', label: 'Overview', icon: LayoutDashboard }, { href: '/lab', label: 'Signal Lab', icon: Radio }, { href: '/handset', label: 'Handset', icon: Smartphone }, { href: '/settings', label: 'Settings', icon: Settings2 }].map(({ href, label, icon: Icon }) => <Link key={label} href={href} aria-current={pathname === href ? 'page' : undefined} className={cn('flex flex-col items-center gap-1 py-1 text-[9px]', pathname === href ? 'text-[#ffcc00]' : 'text-slate-600')}><Icon size={17}/>{label}</Link>)}</nav>
    </div>
  </div>;
}
