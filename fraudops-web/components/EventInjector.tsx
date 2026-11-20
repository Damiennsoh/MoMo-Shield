"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Assessment, SandboxEvent } from "@/lib/types";
import AssessmentCard from "./AssessmentCard";

export default function EventInjector() {
  const [kind, setKind] = useState<"transaction" | "device_binding">("transaction");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  // transaction fields
  const [txType, setTxType] = useState("P2P_SEND");
  const [amount, setAmount] = useState("150");
  const [ledger, setLedger] = useState(true);

  // device fields
  const [imei, setImei] = useState("869523067718411");
  const [action, setAction] = useState("NEW_DEVICE_LOGIN");

  const submit = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    const base = {
      event_id: `inj-${Date.now()}`,
      msisdn: "233240000001",
      timestamp: new Date().toISOString(),
    };
    const event: SandboxEvent =
      kind === "transaction"
        ? { ...base, event_type: "transaction", transaction_type: txType, amount: parseFloat(amount) || 0, counterparty_msisdn: "233550000099", ledger_verified: ledger }
        : { ...base, event_type: "device_binding", new_imei: imei, action };
    try {
      const a = await api.assess(event);
      setResult(a);
      if (a.risk_tier === "HIGH" || a.risk_tier === "MEDIUM") {
        await api
          .publishHandset({
            type: "warning",
            level: a.risk_tier,
            title: "FRAUD ALERT — EVENT INJECTOR",
            text: a.english_warning_message ?? a.guidance ?? "Verify through the official app before proceeding.",
            text_twi: a.twi_warning_message ?? undefined,
            scenario: "Synthetic Event Injector",
            sip_hangup: a.recommended_action === "SIMULATED_HOLD" || a.recommended_action === "FRAUDOPS_ALERT",
          })
          .catch(() => {});
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "injection failed — is the backend running?");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="panel p-5">
        <p className="label">Synthetic Event Injector</p>
        <p className="mt-1 text-sm text-slate-400">
          Validate one transaction or device-binding event at a time, using an isolated synthetic identity.
        </p>

        <div className="mt-4 flex gap-2">
          {(["transaction", "device_binding"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className={`rounded-lg px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors ${
                kind === k ? "bg-accent/15 text-accent" : "bg-ink-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {k === "transaction" ? "Transaction" : "Device binding"}
            </button>
          ))}
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {kind === "transaction" ? (
            <>
              <label className="block">
                <span className="label">Transaction type</span>
                <select value={txType} onChange={(e) => setTxType(e.target.value)} className="input mt-1.5">
                  <option>P2P_SEND</option>
                  <option>CREDIT</option>
                  <option>XTRACASH_LOAN</option>
                  <option>CASH_OUT</option>
                </select>
              </label>
              <label className="block">
                <span className="label">Amount (GHS)</span>
                <input type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className="input mt-1.5 font-mono" />
              </label>
              <label className="flex items-center gap-2 sm:col-span-2">
                <input type="checkbox" checked={ledger} onChange={(e) => setLedger(e.target.checked)} className="accent-[#FACC15]" />
                <span className="text-xs text-slate-400">Ledger-verified (core ledger confirms the credit/debit)</span>
              </label>
            </>
          ) : (
            <>
              <label className="block sm:col-span-2">
                <span className="label">New IMEI</span>
                <input value={imei} onChange={(e) => setImei(e.target.value)} className="input mt-1.5 font-mono" />
              </label>
              <label className="block sm:col-span-2">
                <span className="label">Binding action</span>
                <select value={action} onChange={(e) => setAction(e.target.value)} className="input mt-1.5">
                  <option>NEW_DEVICE_LOGIN</option>
                  <option>APP_INSTALL</option>
                  <option>SIM_SWAP</option>
                </select>
              </label>
            </>
          )}
        </div>

        <p className="mt-4 rounded-lg bg-ink-800/60 px-3 py-2 font-mono text-[11px] text-slate-500">
          msisdn: 233240000001 (synthetic) · isolated per event
        </p>

        <button className="btn btn-accent mt-5" onClick={submit} disabled={busy}>
          {busy ? "Assessing…" : "Inject & assess"}
        </button>
        {error && <p className="mt-3 text-xs text-risk-high">{error}</p>}
      </div>

      <div>
        {result ? (
          <AssessmentCard a={result} title="Injector — result" />
        ) : (
          <div className="panel flex h-full min-h-[220px] items-center justify-center p-6 text-center text-sm text-slate-500">
            Inject an event to see scoring, triggered rules, and the recommended action. HIGH results publish a warning to connected handsets.
          </div>
        )}
      </div>
    </div>
  );
}
