"""Observed fund-flow ledger — the forensic trail behind Recovery Mode.

Every plug-in event that carries a directed relationship between two parties
(SMS sender→recipient, caller→called party, payer→payee, requester→customer,
bank transfer legs) is appended here as an immutable edge. Unlike the
per-subscriber EventWindow (30-minute correlation memory), this ledger is
cross-subscriber and survives longer — it is the raw material for the
Syndicate Graph and the post-incident evidence pack.

In-memory ring buffer: correct for a single worker, and honestly scoped —
it records what THIS deployment observed, not the whole network. Entries
carry only event-supplied claims; nothing here asserts verified identity.
"""
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

log = get_logger(__name__)

_MAX_EDGES = 1000
# Relationship-bearing plug-in points → edge kind. Lifecycle hooks
# (pin.set, wallet.open, kyc.upgrade…) are not money/comms flow and are skipped.
_EDGE_KINDS = {
    "sms.deliver": "sms",
    "call.connect": "call",
    "payment.authorize": "payment",
    "payment.receive": "payment",
    "payment.request": "payment_request",
    "switch.route": "switch",
    "transfer.authorize": "bank_transfer",
}


def _norm_party(value: Any) -> str:
    """Canonical party key: digits only, Ghana 233… → 0… so +23324…,
    23324… and 024… collapse to one node."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("233") and len(digits) == 12:
        digits = "0" + digits[3:]
    return digits


def _msisdn_of(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("msisdn") or value.get("account") or "").strip()
    return str(value or "").strip()


class FundFlowLedger:
    def __init__(self, maxlen: int = _MAX_EDGES):
        self._edges: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def observe(
        self,
        point: str,
        data: Dict[str, Any],
        protected_msisdn: str,
        decision: str,
        event_id: str,
    ) -> None:
        """Record a directed edge if this plug-in point carries one."""
        kind = _EDGE_KINDS.get(point)
        if not kind:
            return
        src = dst = ""
        amount = None
        if point in ("sms.deliver", "call.connect"):
            src = str(data.get("from") or "").strip()
            dst = protected_msisdn
        elif point in ("payment.authorize", "payment.receive", "switch.route"):
            payer = data.get("payer") if isinstance(data.get("payer"), dict) else {}
            payee = data.get("payee") if isinstance(data.get("payee"), dict) else {}
            src = _msisdn_of(payer)
            dst = _msisdn_of(payee) or (protected_msisdn if point == "payment.receive" else "")
            try:
                amount = float(data.get("amount") or 0) or None
            except (TypeError, ValueError):
                amount = None
        elif point == "payment.request":
            requester = data.get("requester") if isinstance(data.get("requester"), dict) else {}
            src = _msisdn_of(requester)
            dst = protected_msisdn
            try:
                amount = float(data.get("amount") or 0) or None
            except (TypeError, ValueError):
                amount = None
        elif point == "transfer.authorize":
            src = str(data.get("fromAccount") or "").strip()
            dst = str(data.get("toWallet") or "").strip()
            try:
                amount = float(data.get("amount") or 0) or None
            except (TypeError, ValueError):
                amount = None
        src = _norm_party(src)
        dst = _norm_party(dst)
        if not src or not dst or src == dst:
            return
        edge = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": kind,
            "point": point,
            "src": src,
            "dst": dst,
            "amount": amount,
            "decision": decision,
            "event_id": event_id,
        }
        with self._lock:
            self._edges.append(edge)

    def snapshot(self, limit: int = 400) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._edges)[-limit:]

    def edges_for(self, msisdn: str, limit: int = 200) -> List[Dict[str, Any]]:
        """All observed edges touching a number, oldest→newest."""
        target = _norm_party(msisdn)
        if not target:
            return []
        with self._lock:
            return [
                e for e in self._edges
                if e["src"] == target or e["dst"] == target
            ][-limit:]

    def mule_stats(self, msisdn: str, window_seconds: int = 3600) -> Dict[str, Any]:
        """Cross-subscriber fan-in/fan-out profile for mule-ring detection.

        A mule wallet shows many DISTINCT inbound payers (victims) and/or
        fan-out to consolidation points within the window — patterns no
        per-subscriber EventWindow can see. Returns counts only; scoring
        policy lives in the caller."""
        target = _norm_party(msisdn)
        if not target:
            return {"in_payers": 0, "out_payees": 0, "in_amount": 0.0, "out_amount": 0.0}
        cutoff = time.time() - window_seconds
        in_payers, out_payees = set(), set()
        in_amount = out_amount = 0.0
        with self._lock:
            edges = [e for e in self._edges if e["ts"] >= cutoff]
        for e in edges:
            # payment = telco wallet legs; bank_transfer/switch = cross-rail
            # legs — mule chains hop across rails, so all money edges count.
            if e["kind"] not in ("payment", "bank_transfer", "switch"):
                continue
            amt = e.get("amount") or 0.0
            if e["dst"] == target:
                if e["src"]:
                    in_payers.add(e["src"])
                in_amount += amt
            if e["src"] == target:
                if e["dst"]:
                    out_payees.add(e["dst"])
                out_amount += amt
        return {
            "in_payers": len(in_payers),
            "out_payees": len(out_payees),
            "in_amount": round(in_amount, 2),
            "out_amount": round(out_amount, 2),
        }

    def clear(self) -> None:
        with self._lock:
            self._edges.clear()


fund_flow_ledger = FundFlowLedger()
