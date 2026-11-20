import type { Scenario } from "./types";

const T = (iso: string) => iso;

export const SCENARIOS: Scenario[] = [
  {
    id: "GH01",
    name: "Fake Credit → Refund Scam",
    caseRef: "GH01",
    description:
      "Spoofed credit SMS claims money entered the wallet; an immediate inbound voice call demands a 'refund' or threatens account blocking.",
    tier: "HIGH",
    expectedScore: 85,
    steps: [
      {
        delay_ms: 0,
        note: "Spoofed credit SMS hits the victim handset",
        event: {
          event_id: "gh01-1",
          msisdn: "233240000001",
          event_type: "transaction",
          transaction_type: "CREDIT",
          amount: 850,
          counterparty_msisdn: "233200000099",
          timestamp: T("2026-11-26T10:14:02Z"),
          ledger_verified: false,
        },
      },
      {
        delay_ms: 1400,
        note: "Fraudster calls, impersonating support with authority + loss-aversion script",
        event: {
          event_id: "gh01-2",
          msisdn: "233240000001",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript:
            "Mepa wo kyew, this is MTN Head Office. We wrongly credited your account. If you do not return the money your MoMo will be blocked today. Give me the PIN to reverse it.",
          timestamp: T("2026-11-26T10:15:10Z"),
          language_hint: "twi-en",
          input_source: "curated_fixture",
        },
      },
      {
        delay_ms: 2400,
        note: "Victim coached into an outbound 'refund' transfer while on the call",
        event: {
          event_id: "gh01-3",
          msisdn: "233240000001",
          event_type: "transaction",
          transaction_type: "P2P_SEND",
          amount: 850,
          counterparty_msisdn: "233550000077",
          timestamp: T("2026-11-26T10:17:31Z"),
          ledger_verified: true,
        },
      },
    ],
  },
  {
    id: "GH18",
    name: "Cross-Device Wallet Takeover",
    caseRef: "GH18",
    description:
      "Caller extracts app-registration OTP and MoMo PIN, then binds the victim's wallet to an attacker's device.",
    tier: "HIGH",
    expectedScore: 92,
    steps: [
      {
        delay_ms: 0,
        note: "OTP extraction call",
        event: {
          event_id: "gh18-1",
          msisdn: "233240000002",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript:
            "Hello, I am calling from Telecel Cash. We are upgrading your wallet. Read me the six-digit code you just received so we secure your account.",
          timestamp: T("2026-11-26T11:02:05Z"),
          language_hint: "en",
          input_source: "curated_fixture",
        },
      },
      {
        delay_ms: 2000,
        note: "New device binding follows high-risk OTP activity",
        event: {
          event_id: "gh18-2",
          msisdn: "233240000002",
          event_type: "device_binding",
          new_imei: "869523067718411",
          action: "NEW_DEVICE_LOGIN",
          timestamp: T("2026-11-26T11:04:44Z"),
        },
      },
      {
        delay_ms: 1600,
        note: "Attacker attempts PIN-gated balance drain",
        event: {
          event_id: "gh18-3",
          msisdn: "233240000002",
          event_type: "transaction",
          transaction_type: "P2P_SEND",
          amount: 1230,
          counterparty_msisdn: "233200000088",
          timestamp: T("2026-11-26T11:05:31Z"),
          ledger_verified: true,
        },
      },
    ],
  },
  {
    id: "GH17",
    name: "Fake Support → Wallet Drain + XtraCash",
    caseRef: "GH17",
    description:
      "Impersonated support sends a link; hurried code entry drains the wallet and activates an unauthorized micro-loan.",
    tier: "HIGH",
    expectedScore: 88,
    steps: [
      {
        delay_ms: 0,
        note: "Phishing SMS with look-alike link",
        event: {
          event_id: "gh17-1",
          msisdn: "233240000003",
          event_type: "communication",
          channel: "SMS",
          text_or_transcript:
            "Dear customer, your MoMo account has been limited. Verify within 24hrs to avoid suspension: http://mtn-momo-verify.example/form",
          timestamp: T("2026-11-26T12:20:11Z"),
          language_hint: "en",
          input_source: "curated_fixture",
        },
      },
      {
        delay_ms: 2200,
        note: "Primary wallet emptied",
        event: {
          event_id: "gh17-2",
          msisdn: "233240000003",
          event_type: "transaction",
          transaction_type: "P2P_SEND",
          amount: 460,
          counterparty_msisdn: "233550000090",
          timestamp: T("2026-11-26T12:26:52Z"),
          ledger_verified: true,
        },
      },
      {
        delay_ms: 1800,
        note: "Unauthorized XtraCash micro-loan activation right after drain",
        event: {
          event_id: "gh17-3",
          msisdn: "233240000003",
          event_type: "transaction",
          transaction_type: "XTRACASH_LOAN",
          amount: 200,
          counterparty_msisdn: null,
          timestamp: T("2026-11-26T12:27:40Z"),
          ledger_verified: true,
        },
      },
    ],
  },
  {
    id: "GH02",
    name: "Reversal Syndicate",
    caseRef: "GH02",
    description:
      "Coordinated callers target agents with repeated 'mistaken transfer' stories; forged receipts carry invalid transaction IDs.",
    tier: "MEDIUM",
    expectedScore: 61,
    steps: [
      {
        delay_ms: 0,
        note: "First reversal call",
        event: {
          event_id: "gh02-1",
          msisdn: "233240000004",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript:
            "Please, I sent money to your number by mistake. Can you reverse it? My brother is sick and needs it back urgently.",
          timestamp: T("2026-11-26T13:01:00Z"),
          language_hint: "twi-en",
          input_source: "curated_fixture",
        },
      },
      {
        delay_ms: 2000,
        note: "Same script from a second number within minutes (fan-out)",
        event: {
          event_id: "gh02-2",
          msisdn: "233240000004",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript:
            "Good afternoon, I mistakenly transferred GHS 300 to your MoMo. Kindly send it back, my child school fees dey inside.",
          timestamp: T("2026-11-26T13:03:18Z"),
          language_hint: "pidgin",
          input_source: "curated_fixture",
        },
      },
    ],
  },
  {
    id: "GH15",
    name: "Fake Business Listing → PIN Harvest",
    caseRef: "GH15",
    description:
      "Fake search/map listings divert customers to web forms that pair wallet MSISDNs with 4-digit PIN patterns.",
    tier: "MEDIUM",
    expectedScore: 58,
    steps: [
      {
        delay_ms: 0,
        note: "Phishing form submission pairing MSISDN + PIN pattern",
        event: {
          event_id: "gh15-1",
          msisdn: "233240000005",
          event_type: "communication",
          channel: "SMS",
          text_or_transcript:
            "CONFIRM ORDER: To complete your payment to 'Adom Ventures', enter your MoMo PIN on the secure form: http://checkout-adom.example/pay — never share it with the merchant.",
          timestamp: T("2026-11-26T14:10:33Z"),
          language_hint: "en",
          input_source: "curated_fixture",
        },
      },
    ],
  },
  {
    id: "GH19",
    name: "Nuisance Call Swarm → Fake Helper",
    caseRef: "GH19",
    description:
      "Three-plus short calls from distinct uncontacted numbers within 30 minutes fatigue the victim before a 'telecom helper' offers relief.",
    tier: "MEDIUM",
    expectedScore: 55,
    steps: [
      {
        delay_ms: 0,
        note: "Nuisance burst: call 1 (2s, unanswered)",
        event: {
          event_id: "gh19-1",
          msisdn: "233240000006",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript: "[2-second silent call, unanswered]",
          timestamp: T("2026-11-26T15:00:00Z"),
          language_hint: "unknown",
          input_source: "curated_fixture",
        },
      },
      {
        delay_ms: 1200,
        note: "Nuisance burst: call 2 (4s, unanswered, distinct number)",
        event: {
          event_id: "gh19-2",
          msisdn: "233240000006",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript: "[4-second silent call, unanswered, new caller ID]",
          timestamp: T("2026-11-26T15:04:00Z"),
          language_hint: "unknown",
          input_source: "curated_fixture",
        },
      },
      {
        delay_ms: 1200,
        note: "Nuisance burst: call 3 (3s, unanswered, third distinct number)",
        event: {
          event_id: "gh19-3",
          msisdn: "233240000006",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript: "[3-second silent call, unanswered, third new caller ID]",
          timestamp: T("2026-11-26T15:07:00Z"),
          language_hint: "unknown",
          input_source: "curated_fixture",
        },
      },
      {
        delay_ms: 1800,
        note: "'Helper' call arrives right after the swarm",
        event: {
          event_id: "gh19-4",
          msisdn: "233240000006",
          event_type: "communication",
          channel: "VOICE",
          text_or_transcript:
            "We noticed strange calls on your line. I am from the fraud desk and I can block them — just confirm the code I send you.",
          timestamp: T("2026-11-26T15:11:00Z"),
          language_hint: "en",
          input_source: "curated_fixture",
        },
      },
    ],
  },
  {
    id: "BASE",
    name: "Legitimate High-Value Transfer (Baseline)",
    caseRef: "Control",
    description:
      "A normal, ledger-verified credit followed by a lawful P2P transfer. Scores LOW to prove false-positive control and frictionless approval.",
    tier: "LOW",
    expectedScore: 15,
    steps: [
      {
        delay_ms: 0,
        note: "Ledger-verified salary credit",
        event: {
          event_id: "base-1",
          msisdn: "233240000007",
          event_type: "transaction",
          transaction_type: "CREDIT",
          amount: 3200,
          counterparty_msisdn: "233302224455",
          timestamp: T("2026-11-26T16:00:00Z"),
          ledger_verified: true,
        },
      },
      {
        delay_ms: 2500,
        note: "Lawful P2P transfer to a known contact",
        event: {
          event_id: "base-2",
          msisdn: "233240000007",
          event_type: "transaction",
          transaction_type: "P2P_SEND",
          amount: 1500,
          counterparty_msisdn: "233244556677",
          timestamp: T("2026-11-26T16:05:30Z"),
          ledger_verified: true,
        },
      },
    ],
  },
];

export const EXAMPLE_MESSAGES = [
  {
    label: "GH01 · Fake credit + refund demand",
    channel: "SMS" as const,
    text: "You have received GHS 850.00 from Ama K. Ref: 88142. If this is a mistake, call us immediately or your account will be blocked.",
  },
  {
    label: "GH18 · OTP extraction (Twi/English)",
    channel: "VOICE" as const,
    text: "Mepa wo kyew, this is MTN Head Office. We wrongly credited your account. If you do not return the money your MoMo will be blocked today. Give me the PIN to reverse it.",
  },
  {
    label: "GH15 · Phishing form",
    channel: "SMS" as const,
    text: "CONFIRM ORDER: To complete your payment to 'Adom Ventures', enter your MoMo PIN on the secure form: http://checkout-adom.example/pay",
  },
  {
    label: "Legitimate · Salary credit",
    channel: "SMS" as const,
    text: "You have received GHS 3,200.00 from KNUST Payroll. Ref: 00912. Balance: GHS 5,710.20. Thank you for using MoMo.",
  },
];

export const TWI_WARNING =
  "Nsaa wo PIN anaa OTP nkyere obiara. Sesa wo account no fa app no so na hwe wo sika so.";

export const EN_WARNING =
  "Do not share a PIN, OTP, or verification code. Stop responding and verify through the official app or a known support contact.";
