"""Call and SIM/PIN signals derived from strictly prior events."""

from datetime import timedelta


def _within(records, timestamp, window):
    start = timestamp - window
    return [record for record in records if start < record[0] < timestamp]


def _hours_since(latest, number, event_name, timestamp, cap_hours):
    event_time = latest.get((number, event_name))
    if event_time is None:
        return cap_hours
    return min((timestamp - event_time).total_seconds() / 3600.0, cap_hours)


def sim_call_feature_values(
    payer,
    payee,
    calls,
    sim_events,
    latest_sim_event,
    timestamp,
    call_minutes,
    sim_hours,
    history_hours,
):
    call_window = timedelta(minutes=call_minutes)
    sim_window = timedelta(hours=sim_hours)
    payer_calls = _within(calls.get(payer, ()), timestamp, call_window)
    payee_calls = _within(calls.get(payee, ()), timestamp, call_window)
    payer_sim = _within(sim_events.get(payer, ()), timestamp, sim_window)
    payee_sim = _within(sim_events.get(payee, ()), timestamp, sim_window)
    payer_replacements = sum(event[1] == "sim_replacement" for event in payer_sim)
    payer_resets = sum(event[1] == "pin_reset" for event in payer_sim)
    payee_replacements = sum(event[1] == "sim_replacement" for event in payee_sim)
    payee_resets = sum(event[1] == "pin_reset" for event in payee_sim)
    return {
        "payer_calls_window": len(payer_calls),
        "payee_calls_window": len(payee_calls),
        "call_before_tx": int(bool(payer_calls)),
        "payer_hours_since_sim_replacement": _hours_since(
            latest_sim_event, payer, "sim_replacement", timestamp, history_hours
        ),
        "payer_hours_since_pin_reset": _hours_since(
            latest_sim_event, payer, "pin_reset", timestamp, history_hours
        ),
        "payee_hours_since_sim_replacement": _hours_since(
            latest_sim_event, payee, "sim_replacement", timestamp, history_hours
        ),
        "payee_hours_since_pin_reset": _hours_since(
            latest_sim_event, payee, "pin_reset", timestamp, history_hours
        ),
        "payer_sim_replacement_count_window": payer_replacements,
        "payer_pin_reset_count_window": payer_resets,
        "payee_sim_replacement_count_window": payee_replacements,
        "payee_pin_reset_count_window": payee_resets,
        "payer_sim_and_pin_reset_window": int(
            payer_replacements > 0 and payer_resets > 0
        ),
    }
