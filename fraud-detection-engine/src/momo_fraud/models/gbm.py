"""Gradient-boosted classifier — LightGBM with sensible fraud defaults."""


def make_gbm(random_state: int = 7, n_estimators: int = 400):
    """LightGBM classifier; sample weights are supplied by the caller."""
    from lightgbm import LGBMClassifier

    return LGBMClassifier(
        n_estimators=n_estimators,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=40,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=random_state,
        n_jobs=-1,
        verbose=-1,
    )
