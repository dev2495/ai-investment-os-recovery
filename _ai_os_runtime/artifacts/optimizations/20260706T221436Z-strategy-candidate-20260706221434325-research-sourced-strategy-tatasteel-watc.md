# Optimization - Research-sourced strategy: TATASTEEL watchlist [discovery_api_smoke2_20260707 #1]

- Candidate: `strategy-candidate-20260706221434325-research-sourced-strategy-tatasteel-watc`
- Template: `breakout`
- Status: `completed`
- Best params: `{"threshold": 0.001, "window": 6}`
- Best test Sharpe: -22.622822845837096
- Best test return: -0.003070
- Walk-forward folds: 2
- Walk-forward consistency: 0.00
- Monte Carlo p05 return: -0.009902938966382613

## Warnings

- Out-of-sample split is too small for production confidence.
- Best parameter set has negative walk-forward/test Sharpe; reject until broader data proves otherwise.
- Best parameter set is not consistent across walk-forward windows.
- Trade count is low; Monte Carlo and walk-forward results are weak evidence.
- OHLCV sample is thin; this run is a robustness pipeline proof.

Optimization output remains research-only until Model Validation and human approval.