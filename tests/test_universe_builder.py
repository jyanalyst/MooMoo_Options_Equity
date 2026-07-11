"""
Universe-builder pipeline tests — zero network.

Covers: candidate-pool pruning (ETF/fund/inactive/biotech/bad-fields,
dollar-volume ranking, pool cap), the profitability gate, sector-aware
percentile scoring (neutral 0.5 for single-stock sectors and missing metrics),
the 35% sector dominance cap, and that render_universe_file output exec()s
cleanly and exposes the full downstream contract.
"""

import pandas as pd

import universe_builder as ub


class StubClient:
    """FMPClient stand-in: canned screener rows, no HTTP."""

    def __init__(self, rows):
        self.rows = rows
        self.request_count = 0

    def company_screener(self, **kwargs):
        return self.rows

    def ratios_ttm(self, symbol, ttl_hours=24.0):
        return None


def _screener_row(
    symbol,
    price=100.0,
    volume=5_000_000,
    sector="Technology",
    industry="Software",
    **overrides,
):
    row = {
        "symbol": symbol,
        "companyName": f"{symbol} Inc",
        "sector": sector,
        "industry": industry,
        "price": price,
        "volume": volume,
        "marketCap": 50e9,
        "isEtf": False,
        "isFund": False,
        "isActivelyTrading": True,
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------- #
# Stage 1+2: pool prune
# --------------------------------------------------------------------------- #
def test_pool_prunes_etf_fund_inactive_biotech_and_bad_fields():
    rows = [
        _screener_row("GOOD"),
        _screener_row("ETF1", isEtf=True),
        _screener_row("FUND1", isFund=True),
        _screener_row("DEAD", isActivelyTrading=False),
        _screener_row("BIO", industry="Biotechnology"),
        _screener_row("NOPX", price=None),
        _screener_row("NOSEC", sector=None),
    ]
    pool = ub.fetch_candidate_pool(StubClient(rows))
    assert [p["ticker"] for p in pool] == ["GOOD"]


def test_pool_ranked_by_dollar_volume_and_capped(monkeypatch):
    monkeypatch.setattr(ub, "FUNDAMENTAL_POOL_CAP", 2)
    rows = [
        _screener_row("LOW", price=10.0, volume=1_000_000),  # $10M
        _screener_row("HIGH", price=100.0, volume=10_000_000),  # $1B
        _screener_row("MID", price=50.0, volume=2_000_000),  # $100M
    ]
    pool = ub.fetch_candidate_pool(StubClient(rows))
    assert [p["ticker"] for p in pool] == ["HIGH", "MID"]  # ranked, capped at 2


def test_pool_empty_screener_returns_empty():
    assert ub.fetch_candidate_pool(StubClient(None)) == []


# --------------------------------------------------------------------------- #
# Stage 4: profitability gate
# --------------------------------------------------------------------------- #
def _fundamentals_df(rows):
    return pd.DataFrame(rows)


def test_quality_gate_drops_none_and_negative_margin():
    df = _fundamentals_df(
        [
            {"ticker": "PROF", "operating_margin": 0.25},
            {"ticker": "LOSS", "operating_margin": -0.05},
            {"ticker": "ZERO", "operating_margin": 0.0},
            {"ticker": "UNKN", "operating_margin": None},
        ]
    )
    gated = ub.apply_quality_gate(df)
    assert list(gated["ticker"]) == ["PROF"]


def test_quality_gate_empty_df_passthrough():
    df = pd.DataFrame()
    assert ub.apply_quality_gate(df).empty


# --------------------------------------------------------------------------- #
# Stage 5: sector-aware percentile scoring
# --------------------------------------------------------------------------- #
def _scoring_df():
    return pd.DataFrame(
        [
            # Two-stock Tech sector: A dominates B on every margin metric
            {
                "ticker": "A",
                "sector": "Tech",
                "operating_margin": 0.40,
                "net_margin": 0.30,
                "gross_margin": 0.70,
                "dollar_volume": 4e9,
            },
            {
                "ticker": "B",
                "sector": "Tech",
                "operating_margin": 0.10,
                "net_margin": 0.05,
                "gross_margin": 0.30,
                "dollar_volume": 1e9,
            },
            # Single-stock sector: margins must rank neutral (0.5), not 1.0
            {
                "ticker": "SOLO",
                "sector": "Utilities",
                "operating_margin": 0.15,
                "net_margin": 0.10,
                "gross_margin": 0.40,
                "dollar_volume": 2e9,
            },
        ]
    )


def test_scores_rank_within_sector():
    out = ub.compute_quality_scores(_scoring_df())
    scores = dict(zip(out["ticker"], out["quality_score"]))
    # A: all sector percentiles 1.0, liquidity percentile 1.0 -> 100
    assert scores["A"] == 100.0
    # B: sector percentiles 0.5 (rank 1 of 2), liquidity 1/3
    expected_b = round((0.30 * 0.5 + 0.25 * 0.5 + 0.20 * 0.5 + 0.25 * (1 / 3)) * 100, 1)
    assert scores["B"] == expected_b
    # Output sorted by score descending
    assert list(out["quality_score"]) == sorted(out["quality_score"], reverse=True)


def test_single_stock_sector_scores_neutral():
    out = ub.compute_quality_scores(_scoring_df())
    solo = out.loc[out["ticker"] == "SOLO"].iloc[0]
    # margins neutral 0.5 each; liquidity global percentile 2/3
    expected = round((0.75 * 0.5 + 0.25 * (2 / 3)) * 100, 1)
    assert solo["quality_score"] == expected


def test_missing_metric_scores_neutral_never_nan():
    df = _scoring_df()
    df["net_margin"] = None  # entire metric missing
    out = ub.compute_quality_scores(df)
    assert out["quality_score"].notna().all()
    # A still tops: op/gross percentiles 1.0, net neutral 0.5
    a = out.loc[out["ticker"] == "A"].iloc[0]
    expected_a = round((0.30 * 1.0 + 0.25 * 0.5 + 0.20 * 1.0 + 0.25 * 1.0) * 100, 1)
    assert a["quality_score"] == expected_a


# --------------------------------------------------------------------------- #
# Stage 6: sector dominance cap
# --------------------------------------------------------------------------- #
def test_diversify_enforces_sector_cap_quality_first():
    # 10 Tech + 5 Other, Tech all higher-scored; target 10 -> cap = 3
    rows = [
        {"ticker": f"T{i}", "sector": "Tech", "quality_score": 90 - i}
        for i in range(10)
    ] + [
        {"ticker": f"O{i}", "sector": "Other", "quality_score": 50 - i}
        for i in range(5)
    ]
    df = pd.DataFrame(rows)  # already sorted by score desc
    final = ub.diversify(df, target_size=10)

    tech = final[final["sector"] == "Tech"]
    assert len(tech) == 3  # int(0.35 * 10) = 3, dominance cap enforced
    assert list(tech["ticker"]) == ["T0", "T1", "T2"]  # best Tech kept
    # Cap applies to every sector (dominance cap, not a Tech-only rule)
    assert len(final[final["sector"] == "Other"]) == 3
    assert len(final) == 6


# --------------------------------------------------------------------------- #
# Render: the generated file must exec() and expose the full contract
# --------------------------------------------------------------------------- #
def test_render_universe_file_execs_and_exposes_contract():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "company": "Apple",
                "sector": "Technology",
                "price": 190.0,
                "quality_score": 88.5,
            },
            {
                "ticker": "KO",
                "company": "Coca-Cola",
                "sector": "Consumer Staples",
                "price": 62.0,
                "quality_score": 71.0,
            },
        ]
    )
    content = ub.render_universe_file(df, screened=200, gated=188)

    ns = {}
    exec(compile(content, "universe_generated.py", "exec"), ns)

    # Downstream contract
    for name in (
        "WHEEL_UNIVERSE",
        "CAPITAL_REQUIREMENTS",
        "STOCK_METADATA",
        "EXCLUDED_TICKERS",
        "get_wheel_universe",
        "get_affordable_stocks",
        "format_moomoo_symbol",
        "strip_moomoo_prefix",
        "get_stock_metadata",
    ):
        assert name in ns, f"generated universe.py missing {name}"

    assert ns["WHEEL_UNIVERSE"] == ["AAPL", "KO"]
    assert ns["CAPITAL_REQUIREMENTS"]["AAPL"] == 19000
    assert ns["get_wheel_universe"](10000) == ["KO"]  # capital filter works
    assert ns["format_moomoo_symbol"]("KO") == "US.KO"
    assert ns["get_stock_metadata"]("AAPL")["sector"] == "Technology"
    # Unknown ticker falls back safely, never KeyErrors
    assert ns["get_stock_metadata"]("ZZZ")["sector"] == "Unknown"
