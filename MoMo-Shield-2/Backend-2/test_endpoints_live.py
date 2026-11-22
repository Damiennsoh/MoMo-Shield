import urllib.request
import json
import time

def post(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.status, json.loads(res.read().decode("utf-8"))

def get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.status, json.loads(res.read().decode("utf-8"))

print("=== 1. TEST /knowledge-base ===")
st, kb = get("http://localhost:8001/api/v1/knowledge-base")
print(f"Status {st}: Loaded {kb.get('count')} chunks from KNUST Library")

print("\n=== 2. TEST /webhook/sandbox (SMS Phishing) ===")
st, res1 = post("http://localhost:8001/api/v1/webhook/sandbox", {
    "event_id": "test_sms_1",
    "msisdn": "+233240000101",
    "event_type": "sms",
    "timestamp": "2026-11-22T14:00:00Z",
    "payload": {"text": "MTN Notice: Your MoMo account has problem. Click http://momo-update.net to verify your PIN."}
})
print(f"Decision: {res1.get('action_taken')} | Score: {res1.get('risk_score')} | Latency: {res1.get('latency_ms')}ms")
print(f"Rules: {res1.get('triggered_rules')}")
print(f"RAG Match: {res1.get('kb_match')}")

print("\n=== 3. TEST /plugin (Hook 13: call.connect - Robocall Sweep) ===")
st, res2 = post("http://localhost:8001/api/v1/plugin", {
    "point": "call.connect",
    "institution": "mtn",
    "data": {
        "to": "+233240000102",
        "from": "+233559998888",
        "numbersTheCallerHasRungToday": 45,
        "callsBetweenThemBefore": 0
    }
})
print(f"Decision: {res2}")

print("\n=== 4. TEST /plugin (Hook 15: payment.authorize - Active Call Co-occurrence GH22) ===")
st, res3 = post("http://localhost:8001/api/v1/plugin", {
    "point": "payment.authorize",
    "institution": "mtn",
    "data": {
        "amount": 850,
        "payer": {
            "msisdn": "+233240000103",
            "onCallWith": "+233559998888"
        },
        "payee": {
            "msisdn": "+233201112222"
        }
    }
})
print(f"Decision: {res3}")

print("\n=== 5. TEST /plugin (Hook 11: sim.swap - NIA SIM Stacking Alert) ===")
st, res4 = post("http://localhost:8001/api/v1/plugin", {
    "point": "sim.swap",
    "institution": "mtn",
    "data": {
        "msisdn": "+233240000104",
        "ghanaCard": "GHA-729104829-1",
        "simsAlreadyOnThisGhanaCard": 7
    }
})
print(f"Decision: {res4}")

print("\n=== 6. TEST /demo/benchmark (Full 14 Scenarios) ===")
st, bench = post("http://localhost:8001/api/v1/demo/benchmark", {})
summary = bench.get("summary", {})
print(f"Bench Status {st}: Total Scenarios: {summary.get('total_incidents')}")
print(f"Frauds Caught: {summary.get('stopped_count')}/{summary.get('fraud_scenarios')}")
print(f"False Positives: {summary.get('false_positives')}")
print(f"Direct Cedis Protected: GH₵ {summary.get('ghc_protected', 0):,}")
print(f"Precision: {summary.get('precision')} | Recall: {summary.get('recall')}")
print(f"Average Decision Latency: {summary.get('avg_latency_ms')}ms")

print("\n=== 7. TEST /events (Hydration Feed) ===")
st, events = get("http://localhost:8001/api/v1/events")
print(f"Hydration Feed: {len(events.get('events', []))} events captured")

print("\nALL BACKEND API ENDPOINTS TESTED SUCCESSFULLY!")
