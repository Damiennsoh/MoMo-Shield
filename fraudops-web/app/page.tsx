"use client";

import { useState } from "react";
import HeaderBar from "@/components/HeaderBar";
import Sidebar from "@/components/Sidebar";
import ScenarioReplay from "@/components/ScenarioReplay";
import LiveSignalLab from "@/components/LiveSignalLab";
import EventInjector from "@/components/EventInjector";
import ProviderReadiness from "@/components/ProviderReadiness";

export default function FraudOpsPage() {
  const [workspace, setWorkspace] = useState("replay");

  return (
    <div className="min-h-screen">
      <HeaderBar />
      <main className="mx-auto max-w-[1440px] px-4 py-5 sm:px-6 sm:py-7">
        <div className="mb-5 flex flex-col gap-2 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="label text-accent">Ghana · mobile money safety</p>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">Fraud operations center</h2>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-300">Explore how suspicious signals are assessed, explained, and surfaced to protect a mobile money user.</p>
          </div>
          <p className="text-xs font-medium text-slate-400">Judge demo <span className="mx-1 text-slate-600">/</span> Synthetic environment</p>
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:gap-5">
          <Sidebar active={workspace} onSelect={setWorkspace} />
          <section className="min-w-0 flex-1" aria-label="Active workspace">
            {workspace === "replay" && <ScenarioReplay />}
            {workspace === "lab" && <LiveSignalLab />}
            {workspace === "injector" && <EventInjector />}
            {workspace === "provider" && <ProviderReadiness />}
          </section>
        </div>
      </main>
    </div>
  );
}
