from app.engine.rules import (
    RULES,
    check_content_credential_request,
    check_content_impersonation,
    check_content_urgency,
    check_gh01_fake_credit,
    check_gh18_device_takeover,
    check_velocity,
    check_gh15_phishing_link,
    check_gh19_nuisance_preconditioning,
    check_call_ussd_cooccurrence,
    check_task_momentum,
    check_money_mule,
    check_structuring,
    check_approve_to_receive,
    check_relative_new_number,
    check_prize_fee_scam,
    check_unverified_credit_claim,
    check_suspicious_content_precursor,
)
from app.models.schemas import EventType
from datetime import datetime, timezone


def _hist(msisdn_payload_pairs):
    return [
        {"msisdn": m, "payload": p, "timestamp": datetime.now(timezone.utc)}
        for m, p in msisdn_payload_pairs
    ]


def test_gh01_fake_credit_fires(make_event):
    history = _hist([("+233240000001", {"type": "sms_credit", "ledger_verified": False})])
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500})
    pts, desc = check_gh01_fake_credit(event, history)
    assert pts == 40
    assert "GH01" in desc


def test_gh01_does_not_fire_on_verified_credit(make_event):
    history = _hist([("+233240000001", {"type": "sms_credit", "ledger_verified": True})])
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500})
    pts, _ = check_gh01_fake_credit(event, history)
    assert pts == 0


def test_gh01_does_not_fire_without_prior_credit(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500})
    pts, _ = check_gh01_fake_credit(event, [])
    assert pts == 0


def test_gh01_ignores_small_transfers(make_event):
    history = _hist([("+233240000001", {"type": "sms_credit", "ledger_verified": False})])
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 50})
    pts, _ = check_gh01_fake_credit(event, history)
    assert pts == 0


def test_gh18_device_takeover(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "new_device_binding"})
    pts, desc = check_gh18_device_takeover(event, [])
    assert pts == 50
    assert "GH18" in desc


def test_velocity_fires_after_threshold(make_event):
    history = _hist([("+233240000001", {})] * 6)
    pts, desc = check_velocity(make_event(), history)
    assert pts == 20
    assert desc


def test_velocity_quiet_below_threshold(make_event):
    pts, _ = check_velocity(make_event(), _hist([("+233240000001", {})] * 5))
    assert pts == 0


def test_rules_registry_has_descriptions():
    assert len(RULES) == 24


def test_credential_request_sms_scores_high(make_event):
    event = make_event(EventType.SMS, {"text": "MTN here: reply with your PIN or OTP immediately to secure your account"})
    pts, desc = check_content_credential_request(event, [])
    assert pts == 45
    assert "Credential" in desc


def test_credential_request_voice_transcript(make_event):
    event = make_event(EventType.VOICE, {"transcript": "please tell me your mobile money PIN now"})
    pts, _ = check_content_credential_request(event, [])
    assert pts == 45


def test_benign_sms_scores_zero(make_event):
    event = make_event(EventType.SMS, {"text": "You received GHs 50 from Ama. New balance GHs 1,247.80."})
    assert check_content_credential_request(event, []) == (0, "")
    assert check_content_impersonation(event, []) == (0, "")
    assert check_content_urgency(event, []) == (0, "")


def test_impersonation_plus_secret(make_event):
    event = make_event(EventType.SMS, {"text": "MTN fraud department needs your OTP now"})
    pts, _ = check_content_impersonation(event, [])
    assert pts == 15


def test_transaction_events_skip_content_rules(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500, "text": "send PIN now"})
    assert check_content_credential_request(event, []) == (0, "")


def test_gh15_phishing_link_detection(make_event):
    event = make_event(EventType.SMS, {"text": "Click http://momo-gh-update.net/login to confirm your account PIN immediately"})
    pts, desc = check_gh15_phishing_link(event, [])
    assert pts == 45
    assert "GH15" in desc


def test_composite_call_ussd_cooccurrence(make_event):
    event = make_event(EventType.USSD, {"ussd_input": "*170#"})
    history = [{"event_type": "voice", "payload": {"status": "active"}}]
    pts, desc = check_call_ussd_cooccurrence(event, history)
    assert pts == 50
    assert "Composite" in desc


def test_money_mule_detection(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 1000})
    history = [{"payload": {"type": "credit", "amount": 1000}}]
    pts, desc = check_money_mule(event, history)
    assert pts == 40
    assert "GH02" in desc


def test_structuring_detection(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 950})
    history = [
        {"payload": {"type": "transfer_out", "amount": 900}},
        {"payload": {"type": "transfer_out", "amount": 920}},
    ]
    pts, desc = check_structuring(event, history)
    assert pts == 40
    assert "GH22" in desc


def test_approve_to_receive_detection(make_event):
    event = make_event(EventType.SMS, {"text": "Please approve the prompt on your phone to receive your reversal refund of GHS 500"})
    pts, desc = check_approve_to_receive(event, [])
    assert pts == 40
    assert "GH16" in desc


def test_relative_new_number_detection(make_event):
    event = make_event(EventType.SMS, {"text": "Mum, this is my new number, I had an accident and need help urgently, please reply with your PIN"})
    pts, desc = check_relative_new_number(event, [])
    assert pts == 30
    assert "GH19B" in desc


def test_reversal_scam_currency_first(make_event):
    event = make_event(EventType.SMS, {"text": "Hello, I mistakenly sent GHS 850.00 to your MoMo instead of my agent's number. Please check your balance and reverse it to 0541239876. I will send the transaction ID shortly. Please it's urgent, I need the money for hospital."})
    pts, desc = check_unverified_credit_claim(event, [])
    assert pts == 40
    assert "credit claim" in desc.lower()


def test_credit_claim_fee_demand(make_event):
    event = make_event(EventType.SMS, {"text": "Egpapy has sent GHS 40.00 to your MoMo wallet. To receive it, send GHS 5 activation fee to 0550001111"})
    pts, _ = check_unverified_credit_claim(event, [])
    assert pts == 40


def test_prize_fee_scam_detection(make_event):
    event = make_event(EventType.SMS, {"text": "CONGRATULATIONS! Your number has been randomly selected by MTN MoMo to receive a GHS 2,500 cash prize. To claim, send a GHS 50 processing fee to 0559871234. Valid for 24hrs only."})
    pts, desc = check_prize_fee_scam(event, [])
    assert pts == 40
    assert "GH23" in desc


def test_prize_without_fee_passes(make_event):
    event = make_event(EventType.SMS, {"text": "Congratulations! You won a hamper in our weekly draw. Visit the MTN office to collect your prize."})
    pts, _ = check_prize_fee_scam(event, [])
    assert pts == 0


def test_relative_impersonation_bail(make_event):
    event = make_event(EventType.SMS, {"text": "Daddy, it's your son Kojo. My phone was stolen so I'm using my friend's line. I'm at the police station and need GHS 200 urgently for bail. Pls send to this number. Don't call this line, just send the money quickly."})
    pts, desc = check_relative_new_number(event, [])
    assert pts == 30
    assert "GH19B" in desc


def test_benign_family_sms_no_score(make_event):
    event = make_event(EventType.SMS, {"text": "Hi mum, I reached Kumasi safely. Call me when you can."})
    assert check_relative_new_number(event, []) == (0, "")
    assert check_prize_fee_scam(event, []) == (0, "")


def _content_hist(text, minutes_ago=2):
    from datetime import timedelta
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return [{"event_type": "sms", "payload": {"text": text}, "timestamp": ts}]


def test_precursor_payment_after_distress_sms(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 200})
    history = _content_hist("Daddy it's your son Kojo, phone stolen, at police station need GHS 200 for bail urgently. Don't call, send money quickly.")
    pts, desc = check_suspicious_content_precursor(event, history)
    assert pts == 40
    assert "precursor" in desc.lower()


def test_precursor_payment_after_prize_sms(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 50})
    history = _content_hist("CONGRATULATIONS! You won GHS 2,500 prize. Send GHS 50 processing fee to claim.")
    pts, _ = check_suspicious_content_precursor(event, history)
    assert pts == 40


def test_precursor_ignores_stale_content(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 200})
    history = _content_hist("Daddy it's your son Kojo, need GHS 200 urgently, don't call, send money.", minutes_ago=60)
    pts, _ = check_suspicious_content_precursor(event, history)
    assert pts == 0


def test_precursor_ignores_benign_content(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 200})
    history = _content_hist("Your salary of GHS 2,500 has been credited. Have a great day!")
    pts, _ = check_suspicious_content_precursor(event, history)
    assert pts == 0


def test_precursor_ignores_sms_events(make_event):
    event = make_event(EventType.SMS, {"text": "scammy"})
    history = _content_hist("Daddy it's your son Kojo, need GHS 200 urgently, don't call.")
    pts, _ = check_suspicious_content_precursor(event, history)
    assert pts == 0


def test_limit_splitting_smurfing(make_event):
    from app.engine.rules import check_structuring
    history = [
        {"payload": {"type": "transfer_out", "amount": 300, "payee": {"msisdn": "0550000001"}}},
        {"payload": {"type": "transfer_out", "amount": 400, "payee": {"msisdn": "0550000002"}}},
        {"payload": {"type": "transfer_out", "amount": 250, "payee": {"msisdn": "0550000003"}}},
    ]
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500, "payee": {"msisdn": "0550000004"}})
    pts, desc = check_structuring(event, history)
    assert pts == 35
    assert "splitting" in desc.lower() or "GH22" in desc


def test_limit_splitting_same_recipient_no_fire(make_event):
    from app.engine.rules import check_structuring
    history = [
        {"payload": {"type": "transfer_out", "amount": 300, "payee": {"msisdn": "0550000001"}}},
        {"payload": {"type": "transfer_out", "amount": 400, "payee": {"msisdn": "0550000001"}}},
        {"payload": {"type": "transfer_out", "amount": 250, "payee": {"msisdn": "0550000001"}}},
    ]
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500, "payee": {"msisdn": "0550000001"}})
    pts, _ = check_structuring(event, history)
    assert pts == 0


def test_relative_impersonation_bro_script(make_event):
    event = make_event(EventType.SMS, {"text": "Bro it's me, my phone fell in water so I'm using my friend's number. I'm at the hospital and they want GHS 200.00. Pls send to this number now"})
    pts, desc = check_relative_new_number(event, [])
    assert pts == 30
    assert "GH19B" in desc


def test_benign_phone_fell_no_score(make_event):
    event = make_event(EventType.SMS, {"text": "Ma, the phone fell but I am fine. Call me when you can."})
    assert check_relative_new_number(event, []) == (0, "")
