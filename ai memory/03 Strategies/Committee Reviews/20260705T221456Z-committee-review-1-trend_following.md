# Strategy Committee Memo - trend_following

Date: 2026-07-05T22:14:56.264416+00:00
Review: `committee-review-opt-4`
Status: `needs_review`
Approval: `pending`

## Decision

- Recommended decision: `reject_or_retest`
- Proposed mode: `research`
- Risk level: `high`
- Live execution allowed: `False`
- Human decision required: `True`

## Strategy Evidence

- Strategy: `trend_following`
- Universe: `nifty50`
- Timeframe: `None`
- Hypothesis: Legacy imported strategy/backtest candidate. Review assumptions before reuse.

## Backtest Evidence

- Backtest run: `19`
- Status: `completed`
- Total return: `-0.110505`
- Max drawdown: `-0.135427`
- Sharpe estimate: `-7.417277`
- Trades: `202`
- Artifact: `_ai_os_runtime/artifacts/backtests/20260705T215405Z-candidate_7.json`

## Optimization And Robustness

- Optimization run: `4`
- Optimizer type: `parameter_search_walk_forward_bootstrap`
- Best params: `{"lookback": 36}`
- Best test Sharpe: `-3.681485`
- Best walk-forward Sharpe: `-17.612444`
- Walk-forward folds: `3`
- Positive walk-forward folds: `0`
- Walk-forward consistency: `0.000000`
- Heatmap rows: `5`
- Artifact: `_ai_os_runtime/artifacts/optimizations/20260705T220501Z-candidate_7.json`

## Validation

- Validation review: `5`
- Validation status: `needs_review`
- Validation decision: `blocked_until_strategy_committee_review`
- Leakage risk: `unchecked`
- Overfit risk: `high`

## Warnings

- Best parameter set has negative walk-forward/test Sharpe; reject until broader data proves otherwise.
- Best parameter set is not consistent across walk-forward windows.

## Required Fixes

- Review optimizer selection bias
- Run broader data sample
- Run independent walk-forward windows
- Review Monte Carlo/bootstrap tails
- Approve or reject paper monitoring

## Validation Issues

- {"issue": "Best parameter set has negative walk-forward/test Sharpe; reject until broader data proves otherwise.", "severity": "high"}
- {"issue": "Best parameter set is not consistent across walk-forward windows.", "severity": "high"}

## Risk Summary

- Best walk-forward consistency: `0.000000`
- Best walk-forward Sharpe: `-17.612444`
- Optimizer status: `completed`
- Live execution allowed: `False`

## Kill Switch Template

- Daily loss limit: `1.000000%`
- Max drawdown stop: `3.000000%`
- Max open positions: `5`
- Disable on data gap: `True`
- Disable on validation reject: `True`
- Manual re-enable required: `True`

## Committee Conclusion

Reject or retest is the correct current decision. The evidence does not justify paper monitoring because walk-forward consistency is zero and robustness diagnostics are negative.

No paper trade, live alert, broker order, or capital allocation is authorized by this memo.
