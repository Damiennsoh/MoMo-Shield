"""Amount and transaction-history summaries for the point-in-time replay."""

import numpy as np


def transactional_feature_values(
    payer_1h,
    payer_24h,
    payer_7d,
    payer_30d,
    amount: float,
    transaction_limit: float,
    near_limit_fraction: float,
):
    outgoing_24h = [event for event in payer_24h if event[1] == "out"]
    incoming_24h = [event for event in payer_24h if event[1] == "in"]
    outgoing_30d = [event for event in payer_30d if event[1] == "out"]
    previous_amounts = [event[3] for event in outgoing_30d]
    prior_mean = float(np.mean(previous_amounts)) if previous_amounts else 0.0
    return {
        "payer_tx_count_1h": len(payer_1h),
        "payer_tx_count_24h": len(payer_24h),
        "payer_tx_count_7d": len(payer_7d),
        "payer_out_count_24h": len(outgoing_24h),
        "payer_out_amount_24h": sum(event[3] for event in outgoing_24h),
        "payer_in_amount_24h": sum(event[3] for event in incoming_24h),
        "payer_amount_mean_30d": prior_mean,
        "amount_vs_payer_mean": amount / max(prior_mean, 1.0),
        "amount_near_limit": int(
            amount >= transaction_limit * near_limit_fraction
        ),
        "amount_to_limit_ratio": amount / max(transaction_limit, 1.0),
    }
