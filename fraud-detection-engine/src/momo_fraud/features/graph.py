"""Historical neighborhood aggregates for transaction graph features."""


def graph_feature_values(
    payer_week_events,
    payee_day_events,
    payee_week_events,
    current_payee,
):
    """Summarize prior graph neighborhoods without inspecting future edges."""
    prior_payees = {
        event[2] for event in payer_week_events if event[1] == "out" and event[2]
    }
    incoming_day = [event for event in payee_day_events if event[1] == "in"]
    incoming_week = [event for event in payee_week_events if event[1] == "in"]
    outgoing_day = [event for event in payee_day_events if event[1] == "out"]
    incoming_amount = sum(event[3] for event in incoming_day)
    outgoing_amount = sum(event[3] for event in outgoing_day)
    return {
        "payer_unique_payees_7d": len(prior_payees),
        "payer_new_payee": int(bool(current_payee) and current_payee not in prior_payees),
        "payee_in_count_24h": len(incoming_day),
        "payee_in_amount_24h": incoming_amount,
        "payee_unique_senders_24h": len({event[2] for event in incoming_day}),
        "payee_unique_senders_7d": len({event[2] for event in incoming_week}),
        "payee_out_amount_24h": outgoing_amount,
        "payee_pass_through_ratio": min(
            outgoing_amount / max(incoming_amount, 1.0), 10.0
        ),
    }

