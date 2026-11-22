"""
Builds the precomputed Fraud Knowledge Base from the InnoFemme KNUST Case Study Library PDF.
Outputs:
  - MoMo-Shield-2/Backend-2/app/data/fraud_knowledge_base.json
  - MoMo-Shield-2/Frontend-2/public/data/fraud_knowledge_base.json
"""
import os
import re
import json
import math
from collections import Counter
import pypdf

PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "Mobile Money Fraud Case Study Library.pdf")
BACKEND_OUT = os.path.join(os.path.dirname(__file__), "app", "data", "fraud_knowledge_base.json")
FRONTEND_OUT = os.path.join(os.path.dirname(__file__), "..", "Frontend-2", "public", "data", "fraud_knowledge_base.json")

os.makedirs(os.path.dirname(BACKEND_OUT), exist_ok=True)
os.makedirs(os.path.dirname(FRONTEND_OUT), exist_ok=True)

BENIGN_CONTROLS = [
    {
        "id": "CTRL_ECG_POWER",
        "title": "ECG Electricity Prepaid Token Purchase",
        "channel": "USSD",
        "typology": "utility_payment",
        "psychological_levers": [],
        "is_benign": True,
        "summary": "Legitimate payment to Electricity Company of Ghana (ECG) for prepaid meter credit topup.",
        "sample_dialogue": "Payment of GHS 50.00 to ECG Prepaid Meter completed. Token: 4920-1928-4820-1928-4820. Fee: 0.00.",
        "red_flags": [],
        "source": "Ghana Utility Standards"
    },
    {
        "id": "CTRL_GWCL_WATER",
        "title": "Ghana Water Company Bill Payment",
        "channel": "USSD",
        "typology": "utility_payment",
        "psychological_levers": [],
        "is_benign": True,
        "summary": "Legitimate payment of monthly municipal water bill via verified merchant code.",
        "sample_dialogue": "Payment made to Ghana Water Company Ltd for Account 0482019482. Amount: GHS 85.00. Balance GHS 412.00.",
        "red_flags": [],
        "source": "Ghana Utility Standards"
    },
    {
        "id": "CTRL_CHURCH_TITHE",
        "title": "Religious Tithes and Community Offerings",
        "channel": "USSD",
        "typology": "donation",
        "psychological_levers": ["altruism"],
        "is_benign": True,
        "summary": "Sunday collection or weekly tithe sent to a verified registered church or charity merchant wallet.",
        "sample_dialogue": "Payment of GHS 100 to Church of Pentecost Central District Welfare Fund. Ref: Tithe Nov.",
        "red_flags": [],
        "source": "Verified Merchant Registry"
    },
    {
        "id": "CTRL_FAMILY_REMITTANCE",
        "title": "Family Living Support Remittance",
        "channel": "USSD",
        "typology": "p2p_transfer",
        "psychological_levers": ["family"],
        "is_benign": True,
        "summary": "Regular monthly remittance between longstanding family contacts with historical call and transfer logs.",
        "sample_dialogue": "Transfer of GHS 300 to Ama Owusu. Reason: Market money for mother.",
        "red_flags": [],
        "source": "Standard MoMo Behavior"
    },
    {
        "id": "CTRL_SALARY_PAYOUT",
        "title": "Corporate Payroll Bulk Payout",
        "channel": "USSD",
        "typology": "disbursement",
        "psychological_levers": [],
        "is_benign": True,
        "summary": "Scheduled payroll distribution from verified corporate business wallet into employee wallets.",
        "sample_dialogue": "You have received GHS 1,450.00 from Apex Logistics Ghana Ltd. Ref: Payroll Nov 2026.",
        "red_flags": [],
        "source": "Standard MoMo Behavior"
    },
    {
        "id": "CTRL_MTN_OFFICIAL_CARE",
        "title": "Official 100 Customer Care Helpline",
        "channel": "VOICE",
        "typology": "official_support",
        "psychological_levers": [],
        "is_benign": True,
        "summary": "Inbound customer assistance originating from verified telco shortcode (100 or 111) without PIN solicitation.",
        "sample_dialogue": "Welcome to MTN Customer Care. For English press 1, for Twi press 2. Remember MTN will never ask for your MoMo PIN.",
        "red_flags": [],
        "source": "Official MNO Channel"
    }
]

def tokenize(text: str) -> list[str]:
    """Tokenize into normalized word unigrams and character 3-grams for subword matching."""
    text = (text or "").lower()
    words = re.findall(r"[a-z0-9_]+", text)
    tokens = list(words)
    # Character 3-grams for Ghana slang & typos
    for w in words:
        if len(w) >= 4:
            for i in range(len(w) - 2):
                tokens.append(w[i:i+3])
    return tokens

def build_vector(tokens: list[str], vocab: dict[str, int]) -> list[float]:
    counts = Counter(tokens)
    vec = [0.0] * len(vocab)
    for t, cnt in counts.items():
        if t in vocab:
            vec[vocab[t]] = float(cnt)
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

def main():
    print(f"Reading PDF from {PDF_PATH}...")
    reader = pypdf.PdfReader(PDF_PATH)
    
    chunks = []
    
    # Process case pages 7 to 35
    for page_num in range(7, 36):
        text = reader.pages[page_num - 1].extract_text()
        if not text:
            continue
        m = re.search(r"(GH\d+|AF\d+)", text)
        if not m:
            continue
        case_id = m.group(1)
        
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        title = ""
        channel = "SMS / Voice"
        summary_lines = []
        
        for idx, l in enumerate(lines):
            if "B A C K  T O  I N D E X" in l and idx + 1 < len(lines):
                title = lines[idx + 1]
                if idx + 2 < len(lines) and not any(k in lines[idx + 2] for k in ["S E R V I C E", "C H A N N E L", "GHANA"]):
                    title += " " + lines[idx + 2]
            if "C H A N N E L" in l and idx + 1 < len(lines):
                channel = lines[idx + 1]
            if any(h in l for h in ["N A R R A T I V E", "T H E  P A T T E R N", "S U M M A R Y"]):
                summary_lines = lines[idx+1:idx+8]

        # Extract levers
        levers = []
        text_lower = text.lower()
        if "urgency" in text_lower or "immediate" in text_lower or "hurry" in text_lower:
            levers.append("urgency")
        if "loss" in text_lower or "refund" in text_lower or "wrong" in text_lower or "reversal" in text_lower:
            levers.append("loss_aversion")
        if "police" in text_lower or "officer" in text_lower or "mtn" in text_lower or "authority" in text_lower or "head office" in text_lower:
            levers.append("authority")
        if "fear" in text_lower or "arrest" in text_lower or "block" in text_lower or "freeze" in text_lower:
            levers.append("fear")
        if "prize" in text_lower or "win" in text_lower or "promo" in text_lower or "lottery" in text_lower:
            levers.append("greed")
        if "courtesy" in text_lower or "please" in text_lower or "help" in text_lower or "mepa wo kyew" in text_lower:
            levers.append("courtesy")

        if not levers:
            levers = ["social_engineering"]

        # Derive typology
        typology = "social_engineering"
        if "reversal" in text_lower or "wrong transfer" in text_lower:
            typology = "reversal_scam"
        elif "phish" in text_lower or "link" in text_lower or "pin" in text_lower:
            typology = "credential_harvesting"
        elif "nuisance" in text_lower or "calls" in text_lower:
            typology = "nuisance_call_coercion"
        elif "agent" in text_lower or "boss" in text_lower:
            typology = "agent_takeover"
        elif "swap" in text_lower or "device" in text_lower:
            typology = "device_takeover"

        clean_summary = " ".join(summary_lines) if summary_lines else text[:400].replace("\n", " ")
        clean_summary = clean_summary[:350]

        chunks.append({
            "id": case_id,
            "title": title or f"Case {case_id}",
            "channel": channel[:60],
            "typology": typology,
            "psychological_levers": levers,
            "is_benign": False,
            "summary": clean_summary,
            "sample_dialogue": text[200:550].replace("\n", " ").strip(),
            "red_flags": [
                "Unsolicited urgency or emotional pressure",
                "Request to approve USSD prompt or provide OTP/PIN",
                "Caller claims payment error or reversal"
            ],
            "source": f"InnoFemme KNUST Case Study Library (Page {page_num})"
        })

    # Add benign controls
    for b in BENIGN_CONTROLS:
        chunks.append(b)

    print(f"Total chunks assembled: {len(chunks)} ({len(chunks)-len(BENIGN_CONTROLS)} fraud dossiers + {len(BENIGN_CONTROLS)} benign controls)")

    # Build shared vocabulary
    all_tokens = []
    chunk_tokens = []
    for c in chunks:
        searchable_text = f"{c['id']} {c['title']} {c['typology']} {' '.join(c['psychological_levers'])} {c['summary']} {c['sample_dialogue']}"
        toks = tokenize(searchable_text)
        chunk_tokens.append(toks)
        all_tokens.extend(toks)

    # Top vocabulary terms
    token_counts = Counter(all_tokens)
    # Keep tokens appearing at least twice
    vocab = {token: idx for idx, (token, count) in enumerate(token_counts.most_common(1200))}
    print(f"Vocabulary size: {len(vocab)} terms")

    # Precompute vectors
    for i, c in enumerate(chunks):
        c["vector"] = build_vector(chunk_tokens[i], vocab)

    output_payload = {
        "metadata": {
            "version": "2.0.0",
            "source": "InnoFemme x Hack for Equity KNUST Kumasi Case Study Library",
            "total_chunks": len(chunks),
            "fraud_chunks": len(chunks) - len(BENIGN_CONTROLS),
            "benign_chunks": len(BENIGN_CONTROLS),
            "vocab_size": len(vocab)
        },
        "vocab": vocab,
        "chunks": chunks
    }

    with open(BACKEND_OUT, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)
    print(f"Saved backend knowledge base to {BACKEND_OUT} ({os.path.getsize(BACKEND_OUT)} bytes)")

    with open(FRONTEND_OUT, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)
    print(f"Saved frontend knowledge base to {FRONTEND_OUT} ({os.path.getsize(FRONTEND_OUT)} bytes)")

if __name__ == "__main__":
    main()
