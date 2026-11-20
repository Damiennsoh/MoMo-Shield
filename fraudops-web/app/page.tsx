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
      <HeaderBar activeWorkspace={workspace} onNavigate={setWorkspace} />
      <main className="mx-auto max-w-[1440px] px-5 py-6">
        <div className="flex flex-col gap-6 lg:flex-row">
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
