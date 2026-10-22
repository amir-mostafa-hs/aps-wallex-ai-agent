# 03: Historical Candle Buffer & Feature Engine

**What to build:**
A robust market data store and multi-timeframe feature extraction engine that warms up historical OHLCV data from the official `/v1/udf/history` endpoint, resamples 1m base candles locally into 5m, 15m, and 1h intervals, and computes standardized quantitative features (price returns, ATR/volatility, relative volume, spread in bps, and orderbook imbalance) while strictly enforcing data freshness thresholds.

**Blocked by:**
01: Project Foundation, Core Types & Config

**Status:**
ready-for-agent

## Acceptance Criteria

- [ ] Ingests historical OHLCV candles from the TradingView UDF compatible endpoint for specified symbols and resolutions.
- [ ] Maintains a rolling in-memory buffer of recent candles for active symbols.
- [ ] Accurately resamples 1m base candles into higher timeframes (5m, 15m, 1h) without lookahead bias.
- [ ] Computes deterministic feature sets including percentage returns, ATR, relative volume, spread in basis points, and depth imbalance.
- [ ] Enforces data freshness validation: flags or rejects market snapshots older than 45 seconds and execution quotes older than 5 seconds.
- [ ] Tests verify resampling math, indicator calculations against known test vectors, and stale data rejection.
