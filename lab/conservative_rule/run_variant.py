"""
Runs one variant of the 10-year StockScanner backtest from the pre-registered
spec (claude/conservative-rule-test-spec.md, Stock project).

Does NOT edit StockScanner. It imports its run_backtest module and wraps
BacktestConfig so that same_bar_rule and gap_fills are set; every other
argument is passed straight through to run_backtest.main().

Usage (from inside the StockScanner checkout, at the pinned commit):
    python /path/to/run_variant.py current               # reference: must reproduce 1,105 trades
    python /path/to/run_variant.py conservative          # variant A (primary)
    python /path/to/run_variant.py conservative_gap      # variant B (gap fills)

Common args (same as the existing 10-year workflow):
    --start 2016-10-31 --end 2026-10-30 --capital 5000 --quiet
"""
import sys

VARIANTS = {
    "current":          {"same_bar_rule": "current",      "gap_fills": False},
    "conservative":     {"same_bar_rule": "conservative", "gap_fills": False},
    "conservative_gap": {"same_bar_rule": "conservative", "gap_fills": True},
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in VARIANTS:
        sys.exit(f"usage: run_variant.py {{{'|'.join(VARIANTS)}}} [run_backtest args...]")

    variant = sys.argv[1]
    settings = VARIANTS[variant]

    import run_backtest  # StockScanner's module, found in the current directory

    OriginalConfig = run_backtest.BacktestConfig

    def configured(*args, **kwargs):
        kwargs.setdefault("same_bar_rule", settings["same_bar_rule"])
        kwargs.setdefault("gap_fills", settings["gap_fills"])
        return OriginalConfig(*args, **kwargs)

    run_backtest.BacktestConfig = configured
    print(f"[run_variant] variant={variant} same_bar_rule={settings['same_bar_rule']} "
          f"gap_fills={settings['gap_fills']}", flush=True)

    # Hand the remaining args to run_backtest's own parser.
    sys.argv = ["run_backtest.py"] + sys.argv[2:]
    run_backtest.main()


if __name__ == "__main__":
    main()
