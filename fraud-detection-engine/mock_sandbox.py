#!/usr/bin/env python3
"""
mock_sandbox.py - generate a MOCK version of the InnoFemme sandbox dataset.

Purpose: rehearse your pipeline (features, point-in-time replay, models, plugin API)
BEFORE the real files arrive. Column names are GUESSES based on the docs; when you get
the real schema, edit the COLS mapping in your own code, not this file.

DO NOT report metrics measured on this data: your model will learn the assumptions
written in this script (circular). Use it only to build and debug.

Usage:  python mock_sandbox.py --out mock_data
Needs:  pip install numpy pandas
"""
import argparse
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--people", type=int, default=4000)
ap.add_argument("--tx", type=int, default=60000, help="honest transactions")
ap.add_argument("--cases", type=int, default=6000, help="fraud cases")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--out", default="mock_data")
ap.add_argument(
    "--total-transactions",
    type=int,
    default=None,
    help="rebalance the final transaction table to this exact row count",
)
ap.add_argument(
    "--fraud-fraction",
    type=float,
    default=None,
    help="fraction of final transactions that must be labeled fraud",
)
a = ap.parse_args()

rng = np.random.default_rng(a.seed)
os.makedirs(a.out, exist_ok=True)
START, DAYS, LIMIT = datetime(2026, 8, 22), 90, 5000.0
NETS, NETP = ["MTN", "Telecel", "AT"], [0.7, 0.2, 0.1]
PFX = {"MTN": "024", "Telecel": "050", "AT": "026"}
SENDER = {"MTN": "MTNMoMo", "Telecel": "TelecelCash", "AT": "ATMoney"}
REGIONS = ["Ashanti", "Greater Accra", "Northern", "Western", "Central", "Eastern", "Volta"]
used = set()


def new_number(net):
    while True:
        n = PFX[net] + "".join(map(str, rng.integers(0, 10, 7)))
        if n not in used:
            used.add(n)
            return n


def ts_rand(lo=0, hi=DAYS * 86400 - 86400):
    return START + timedelta(seconds=int(rng.integers(lo, hi)))


def mins(lo, hi):
    return timedelta(minutes=float(rng.uniform(lo, hi)))


# ---------------- people, sims, wallets ----------------
n_p = a.people
n_fraud_cards = 12
cards = [f"GHA-{i:09d}-{rng.integers(0, 10)}" for i in range(n_p + n_fraud_cards)]
people = pd.DataFrame({"ghana_card": cards,
                       "age": rng.integers(18, 80, len(cards)),
                       "region": rng.choice(REGIONS, len(cards))})
reg_points = [f"REG-{i:03d}" for i in range(30)]
bad_points = reg_points[:3]

sims, wallets, sim_events = [], [], []


def make_number(card, role, net=None, recent=False, bad=False):
    net = net or rng.choice(NETS, p=NETP)
    num = new_number(net)
    reg = (START + timedelta(days=int(rng.integers(-60, 30)))) if recent else \
          (START - timedelta(days=int(rng.integers(30, 2000))))
    pt = rng.choice(bad_points) if bad else rng.choice(reg_points)
    sims.append([num, net, card, reg, pt, None])
    sim_events.append([reg, num, "REGISTRATION", pt])
    wallets.append([num, net, role, int(rng.integers(1, 4)), round(float(rng.lognormal(5.5, 1.2)), 2), reg])
    return num


cust = [make_number(cards[i], "customer") for i in range(n_p)]
agents = [make_number(cards[i], "agent") for i in rng.choice(n_p, max(20, n_p // 30), replace=False)]
merchants = [make_number(cards[i], "merchant") for i in rng.choice(n_p, max(30, n_p // 16), replace=False)]
fraud_nums = [make_number(cards[n_p + int(rng.integers(0, n_fraud_cards))], "customer", recent=True, bad=True)
              for _ in range(40)]
mules = [make_number(cards[int(rng.integers(0, n_p))], "customer", recent=True, bad=bool(rng.random() < .5))
         for _ in range(80)]
fake_merchants = [make_number(cards[n_p + int(rng.integers(0, n_fraud_cards))], "merchant", recent=True, bad=True)
                  for _ in range(10)]
cust_arr = np.array(cust)
fw = 1.0 / np.arange(1, len(fraud_nums) + 1)          # a few fraud numbers do most of the work
fw /= fw.sum()

bank_accounts = pd.DataFrame({
    "account_no": [f"GCB-{i:07d}" for i in range(int(n_p * 0.4))],
    "ghana_card": rng.choice(cards[:n_p], int(n_p * 0.4)),
    "balance": np.round(rng.lognormal(8, 1.2, int(n_p * 0.4)), 2)})

txs, calls, texts, complaints = [], [], [], []


def add_tx(ts, typ, payer, payee, amt, scen=None, role=None, case=None):
    amt = round(float(amt), 2)
    fee = round(amt * 0.01, 2) if typ in ("p2p", "cash_out") else 0.0
    txs.append([ts, typ, payer, payee, amt, fee, int(scen is not None), scen, role, case])


def add_call(ts, a_, b_, lo=30, hi=300):
    calls.append([ts, a_, b_, int(rng.uniform(lo, hi))])


# ---------------- honest activity ----------------
for _ in range(a.tx):
    t = ts_rand()
    typ = rng.choice(["p2p", "cash_in", "cash_out", "merchant_pay"], p=[.45, .2, .2, .15])
    amt = float(np.clip(rng.lognormal(4.3, 1.0), 1, 4000))
    if rng.random() < 0.01:
        amt = float(rng.uniform(4800, 4999))              # honest near-limit (traders)
    c = rng.choice(cust_arr)
    if typ == "p2p":
        add_tx(t, typ, c, rng.choice(cust_arr), amt)
    elif typ == "cash_in":
        add_tx(t, typ, rng.choice(agents), c, amt)
    elif typ == "cash_out":
        add_tx(t, typ, c, rng.choice(agents), amt)
    else:
        add_tx(t, typ, c, rng.choice(merchants), amt)
for _ in range(40000):
    t = ts_rand()
    x, y = rng.choice(cust_arr, 2)
    add_call(t, x, y, 10, 900)
for _ in range(300):                                       # honest "family asks for money" pairs
    t = ts_rand()
    x, y = rng.choice(cust_arr, 2)
    amt = float(np.clip(rng.lognormal(4.5, 0.6), 20, 500))
    texts.append([t, x, y, f"Please send me GHS {amt:.0f}, I am at the station"])
    add_tx(t + mins(2, 30), "p2p", y, x, amt)
for c in rng.choice(cust_arr, int(n_p * 0.025), replace=False):     # honest SIM replacement + PIN reset
    t = ts_rand()
    pt = rng.choice(reg_points)
    sim_events.append([t, c, "SIM_REPLACEMENT", pt])
    sim_events.append([t + mins(5, 60), c, "PIN_RESET", pt])

# ---------------- fraud cases ----------------
SCEN = ["reversal_scam", "pin_phishing", "sim_swap", "agent_fraud", "mule_chain",
        "fake_promo", "rtp_abuse", "fake_merchant", "relative_impersonation", "limit_splitting"]
CAT = {"reversal_scam": "wrong_transfer", "pin_phishing": "payment_customer_didnt_make",
       "sim_swap": "sim_problem", "agent_fraud": "agent_dispute", "mule_chain": "something_else",
       "fake_promo": "something_else", "rtp_abuse": "payment_customer_didnt_make",
       "fake_merchant": "merchant_dispute", "relative_impersonation": "wrong_transfer",
       "limit_splitting": "payment_customer_didnt_make"}
for k in range(a.cases):
    s = SCEN[int(rng.integers(0, len(SCEN)))]
    case = f"FC{k:05d}"
    t0 = ts_rand()
    v = str(rng.choice(cust_arr))
    f = str(rng.choice(fraud_nums, p=fw))
    m = str(rng.choice(mules))
    ag = str(rng.choice(agents))
    amt = float(np.clip(rng.lognormal(6.0, 0.7), 100, 6000))
    bal = float(np.clip(rng.lognormal(6.5, 0.8), 150, 9000))
    if s == "reversal_scam":
        texts.append([t0, rng.choice(["MTN MoMo", "MTNMoM0", f]), v, f"Payment received for GHS {amt:.2f} from {f}."])
        add_call(t0 + mins(1, 4), f, v, 90, 400)
        add_tx(t0 + mins(5, 15), "p2p", v, f, amt, s, "victim_payment", case)
    elif s == "pin_phishing":
        add_call(t0, f, v, 120, 600)
        add_tx(t0 + mins(8, 20), "p2p", v, m, bal, s, "drain", case)
        add_tx(t0 + mins(25, 60), "cash_out", m, ag, bal * 0.98, s, "cashout", case)
    elif s == "sim_swap":
        pt = str(rng.choice(bad_points))
        sim_events.append([t0, v, "SIM_REPLACEMENT", pt])
        sim_events.append([t0 + mins(10, 40), v, "PIN_RESET", pt])
        add_tx(t0 + mins(45, 120), "p2p", v, m, bal, s, "drain", case)
        add_tx(t0 + mins(130, 240), "cash_out", m, ag, bal * 0.98, s, "cashout", case)
    elif s == "agent_fraud":
        add_call(t0, f, ag, 120, 600)
        add_tx(t0 + mins(5, 20), "float_transfer", ag, f, amt * 3, s, "float_sent", case)
        add_tx(t0 + mins(25, 90), "cash_out", f, str(rng.choice(agents)), amt * 2.9, s, "cashout", case)
    elif s == "mule_chain":
        src = bank_accounts.account_no.iloc[int(rng.integers(0, len(bank_accounts)))]
        chain = list(rng.choice(mules, int(rng.integers(3, 6)), replace=False))
        a0, t = amt * 3, t0
        add_tx(t, "bank_to_wallet", src, chain[0], a0, s, "mule_hop", case)
        for i in range(len(chain) - 1):
            t += mins(3, 25)
            a0 *= 0.98
            add_tx(t, "p2p", chain[i], chain[i + 1], a0, s, "mule_hop", case)
        add_tx(t + mins(5, 30), "cash_out", chain[-1], ag, a0 * 0.97, s, "cashout", case)
    elif s == "fake_promo":
        texts.append([t0, f, v, "CONGRATULATIONS! You won GHS 5000. Send a GHS 150 fee to claim your prize."])
        add_tx(t0 + mins(10, 90), "p2p", v, f, float(rng.choice([50, 100, 150, 200, 300])), s, "victim_payment", case)
    elif s == "rtp_abuse":
        add_call(t0, f, v, 60, 300)
        add_tx(t0 + mins(3, 12), "approval_debit", v, f, amt, s, "victim_payment", case)
    elif s == "fake_merchant":
        fm = str(rng.choice(fake_merchants))
        for _ in range(int(rng.integers(2, 6))):
            add_tx(t0 + timedelta(hours=float(rng.uniform(0, 72))), "merchant_pay", str(rng.choice(cust_arr)), fm,
                   float(np.clip(rng.lognormal(4.6, 0.5), 30, 600)), s, "victim_payment", case)
    elif s == "relative_impersonation":
        texts.append([t0, f, v, "Hi it is me, I changed my number. Please send GHS %d urgently, will explain" % int(amt // 50 * 50)])
        add_tx(t0 + mins(5, 40), "p2p", v, f, amt // 50 * 50, s, "victim_payment", case)
    else:  # limit_splitting
        total_pieces = int(rng.integers(5, 10))
        for i in range(total_pieces):
            add_tx(t0 + mins(i * 3, i * 3 + 8), "p2p", v, str(rng.choice(mules)), LIMIT * rng.uniform(0.93, 0.99),
                   s, "split_part", case)
    if rng.random() < 0.6:
        complaints.append([t0 + timedelta(hours=float(rng.uniform(1, 48))), v, CAT[s],
                           "I did not authorise this payment, please help."])

# ---------------- assemble and write ----------------
tx = pd.DataFrame(txs, columns=["timestamp", "type", "payer_number", "payee_number", "amount", "fee",
                                "is_fraud", "fraud_scenario", "fraud_role", "fraud_case"])
if a.total_transactions is not None or a.fraud_fraction is not None:
    if a.total_transactions is None or a.fraud_fraction is None:
        raise SystemExit("--total-transactions and --fraud-fraction must be used together")
    if a.total_transactions < 1:
        raise SystemExit("--total-transactions must be positive")
    if not 0 < a.fraud_fraction < 1:
        raise SystemExit("--fraud-fraction must be between 0 and 1")

    desired_fraud = int(round(a.total_transactions * a.fraud_fraction))
    desired_legitimate = a.total_transactions - desired_fraud
    fraud_rows = tx.loc[tx["is_fraud"] == 1]
    legitimate_rows = tx.loc[tx["is_fraud"] == 0]
    if len(fraud_rows) < desired_fraud:
        raise SystemExit(
            f"Generated only {len(fraud_rows):,} fraud rows; "
            f"{desired_fraud:,} are needed"
        )
    if len(legitimate_rows) < desired_legitimate:
        raise SystemExit(
            f"Generated only {len(legitimate_rows):,} legitimate rows; "
            f"{desired_legitimate:,} are needed"
        )

    fraud_keep = fraud_rows.sample(n=desired_fraud, random_state=a.seed)
    legitimate_keep = legitimate_rows.sample(
        n=desired_legitimate, random_state=a.seed
    )
    tx = pd.concat([fraud_keep, legitimate_keep], axis=0)
tx = tx.sort_values("timestamp").reset_index(drop=True)
tx.insert(0, "tx_id", [f"TX{i:07d}" for i in range(len(tx))])
for _, r in tx.iterrows():                                   # genuine network confirmation texts
    p = r.payer_number
    if not str(p).startswith("GCB"):
        net = next(n for n, px in PFX.items() if str(p).startswith(px))
        texts.append([r.timestamp + timedelta(seconds=2), SENDER[net], p,
                      f"Payment made for GHS {r.amount:.2f} to {r.payee_number}. Fee: GHS {r.fee:.2f}."])

pd.DataFrame(sims, columns=["number", "network", "ghana_card", "registered_at", "registration_point",
                            "last_replacement"]).to_csv(f"{a.out}/sims.csv", index=False)
se = pd.DataFrame(sim_events, columns=["timestamp", "number", "event", "registration_point"]).sort_values("timestamp")
se.to_csv(f"{a.out}/sim_events.csv", index=False)
people.to_csv(f"{a.out}/people.csv", index=False)
pd.DataFrame(wallets, columns=["number", "network", "role", "kyc_level", "balance", "opened_at"]).to_csv(
    f"{a.out}/wallets.csv", index=False)
bank_accounts.to_csv(f"{a.out}/bank_accounts.csv", index=False)
pd.DataFrame(calls, columns=["timestamp", "caller_number", "callee_number", "duration_s"]).sort_values(
    "timestamp").to_csv(f"{a.out}/calls.csv", index=False)
pd.DataFrame(texts, columns=["timestamp", "sender", "recipient_number", "body"]).sort_values(
    "timestamp").to_csv(f"{a.out}/texts.csv", index=False)
pd.DataFrame(complaints, columns=["timestamp", "number", "category", "body"]).sort_values(
    "timestamp").to_csv(f"{a.out}/complaints.csv", index=False)
tx.to_csv(f"{a.out}/transactions.csv", index=False)
tx.drop(columns=["is_fraud", "fraud_scenario", "fraud_role", "fraud_case"]).to_csv(
    f"{a.out}/transactions_blind.csv", index=False)

print(f"transactions: {len(tx)}  fraud share: {tx.is_fraud.mean():.1%}  cases: {tx.fraud_case.nunique()}")
print(tx.groupby("fraud_scenario").size().to_string())
print("wrote:", ", ".join(sorted(os.listdir(a.out))))
