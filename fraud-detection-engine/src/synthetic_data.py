import numpy as np
import pandas as pd


def generate_communication_data(n_per_class: int = 250, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    fraudulent_templates = [
        "Your MoMo account will be suspended. Call this number immediately.",
        "Congratulations! You have won GHS 5,000. Send your details to claim the prize.",
        "I am an MTN agent. Provide your OTP so we can reverse the failed transfer.",
        "This is customer support. Share your PIN right now or lose account access.",
        "Your account is blocked. Confirm the verification code immediately.",
        "Urgent: dial the code and send money to secure your wallet.",
        "A refund is waiting for you. Pay a small release fee to claim it.",
        "We detected suspicious activity. Do not contact the app; send the one-time code now.",
        "Your SIM will be disconnected today. Reply with your PIN to keep the number.",
        "A bank representative needs your OTP to stop an unauthorized debit.",
        "Transfer GHS 200 to this recovery account or your balance will be frozen.",
        "There is an unexpected payment in your account. Confirm your credentials to collect it.",
        "Call our helpline now and provide the code appearing on your phone.",
        "Send the verification code within five minutes or we will close your wallet.",
        "You have been selected for an investment bonus. First transfer an activation fee.",
        "The delivery agent will not release your parcel until you share a one-time password.",
    ]
    legitimate_templates = [
        "Your transaction of GHc100 was successful.",
        "Thank you for contacting MTN customer support.",
        "Your OTP was used to approve your recent account activity.",
        "Please remember to verify your payment details before transferring money.",
        "Your monthly statement is available in the app.",
        "The recipient confirmed receipt of the funds.",
        "Your balance update is ready in the official MoMo application.",
        "This is a confirmation that the payment was completed successfully.",
        "Please keep your PIN private and do not share it with anyone.",
        "Your scheduled transfer will take place after you approve it in the app.",
        "Customer support cannot ask you to reveal your one-time password.",
        "The charge on your account matches the merchant payment you authorised.",
        "A receipt for your recent transfer is available under transaction history.",
        "No action is required if you recognise this payment.",
        "You can review transaction limits and fees inside your MoMo account.",
        "The service desk received your enquiry and will respond through the app.",
        "Thank you for verifying your identity using the secure in-app process.",
        "Your cash-out request was successful and a receipt has been issued.",
        "Please contact official support only through the number displayed in the app.",
    ]
    rows = []
    for label, templates in [(1, fraudulent_templates), (0, legitimate_templates)]:
        for i in range(n_per_class):
            template = templates[int(rng.integers(len(templates)))]
            rows.append({
                "event_id": f"{'F' if label else 'L'}{i:04d}",
                "user_id": f"USER{int(rng.integers(1, 51)):03d}",
                "event_type": "SMS" if i % 4 else "call",
                "sender_number": f"+233{int(rng.integers(500000000, 599999999))}",
                "message": template,
                "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=int(rng.integers(0, 100000))),
                "is_fraudulent": label,
            })
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def generate_transaction_data(n: int = 1000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        fraud = int(rng.random() < 0.3)
        if fraud:
            amount = int(rng.integers(500, 5000))
            new_recipient = int(rng.random() < 0.85)
            suspicious_sms = int(rng.random() < 0.75)
            suspicious_call = int(rng.random() < 0.65)
            otp_request = int(rng.random() < 0.70)
            new_device = int(rng.random() < 0.45)
        else:
            amount = int(rng.integers(20, 1200))
            new_recipient = int(rng.random() < 0.15)
            suspicious_sms = int(rng.random() < 0.04)
            suspicious_call = int(rng.random() < 0.03)
            otp_request = int(rng.random() < 0.03)
            new_device = int(rng.random() < 0.08)
        rows.append({
            "transaction_id": f"TXN{i:05d}",
            "user_id": f"USER{int(rng.integers(1, 51)):03d}",
            "amount": amount,
            "recipient": f"REC{int(rng.integers(1, 500)):03d}",
            "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=int(rng.integers(0, 100000))),
            "is_new_recipient": new_recipient,
            "recent_suspicious_sms": suspicious_sms,
            "recent_suspicious_call": suspicious_call,
            "otp_request": otp_request,
            "new_device": new_device,
            "is_fraudulent": fraud,
        })
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
