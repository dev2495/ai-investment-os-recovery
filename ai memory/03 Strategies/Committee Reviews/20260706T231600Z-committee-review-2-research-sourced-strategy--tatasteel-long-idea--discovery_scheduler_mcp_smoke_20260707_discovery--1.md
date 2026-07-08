# Strategy Committee Memo - Research-sourced strategy: TATASTEEL long idea [discovery_scheduler_mcp_smoke_20260707_discovery #1]

Date: 2026-07-06T23:16:00.705190+00:00
Review: `committee-review-opt-14`
Status: `needs_review`
Approval: `pending`

## Decision

- Recommended decision: `reject_or_retest`
- Proposed mode: `research`
- Risk level: `high`
- Live execution allowed: `False`
- Human decision required: `True`

## Strategy Evidence

- Strategy: `Research-sourced strategy: TATASTEEL long idea [discovery_scheduler_mcp_smoke_20260707_discovery #1]`
- Universe: `NSE`
- Timeframe: `5m`
- Hypothesis: bull regime; momentum=0.89, breakout=1.00, vol_spike=0.91. Risk: ATR(14)=4.4, ann vol=27.55%.

## Backtest Evidence

- Backtest run: `30`
- Status: `completed`
- Total return: `-0.009045`
- Max drawdown: `-0.009755`
- Sharpe estimate: `-27.673631`
- Trades: `6`
- Artifact: `_ai_os_runtime/artifacts/backtests/20260706T222854Z-strategy-candidate-20260706222852898-research-sourced-strategy-tatasteel-long.json`

## Optimization And Robustness

- Optimization run: `14`
- Optimizer type: `parameter_search_walk_forward_bootstrap`
- Best params: `{"threshold": 0.001, "window": 6}`
- Best test Sharpe: `-22.622823`
- Best walk-forward Sharpe: `-32.861496`
- Walk-forward folds: `2`
- Positive walk-forward folds: `0`
- Walk-forward consistency: `0.000000`
- Heatmap rows: `9`
- Artifact: `_ai_os_runtime/artifacts/optimizations/20260706T222854Z-strategy-candidate-20260706222852898-research-sourced-strategy-tatasteel-long.json`

## Validation

- Validation review: `46`
- Validation status: `needs_review`
- Validation decision: `blocked_until_strategy_committee_review`
- Leakage risk: `unchecked`
- Overfit risk: `high`

## Warnings

- Out-of-sample split is too small for production confidence.
- Best parameter set has negative walk-forward/test Sharpe; reject until broader data proves otherwise.
- Best parameter set is not consistent across walk-forward windows.
- Trade count is low; Monte Carlo and walk-forward results are weak evidence.
- OHLCV sample is thin; this run is a robustness pipeline proof.

## Required Fixes

- Review optimizer selection bias
- Run broader data sample
- Run independent walk-forward windows
- Review Monte Carlo/bootstrap tails
- Approve or reject paper monitoring

## Validation Issues

- {"issue": "Out-of-sample split is too small for production confidence.", "severity": "high"}
- {"issue": "Best parameter set has negative walk-forward/test Sharpe; reject until broader data proves otherwise.", "severity": "high"}
- {"issue": "Best parameter set is not consistent across walk-forward windows.", "severity": "high"}
- {"issue": "Trade count is low; Monte Carlo and walk-forward results are weak evidence.", "severity": "high"}
- {"issue": "OHLCV sample is thin; this run is a robustness pipeline proof.", "severity": "high"}

## Risk Summary

- Best walk-forward consistency: `0.000000`
- Best walk-forward Sharpe: `-32.861496`
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
