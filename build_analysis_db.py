from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE_CSV = ROOT / "weekly_model_selection_20260301_20260515_full.csv"
DB_PATH = ROOT / "analysis.db"


def _to_int_nullable(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def load_events() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_CSV, dtype={"종목코드": str})
    df = df.rename(
        columns={
            "전략군": "strategy_family",
            "범위": "scope_key",
            "모델": "model_id",
            "순위": "rank_no",
            "종목코드": "ticker",
            "종목명": "name",
            "선정일": "selection_date",
            "선정일 종가": "selection_close",
            "선정일 시가총액": "selection_mcap",
            "보유종료일": "hold_end_date",
            "보유종료일 종가": "exit_close",
            "선정일 대비 종가 등락율(%)": "close_return_pct",
            "보유기간(일)": "holding_days",
            "점수": "score",
            "비중": "weight",
        }
    )
    df["ticker"] = df["ticker"].str.zfill(6)
    for col in ["rank_no", "selection_close", "selection_mcap", "exit_close", "holding_days"]:
        df[col] = _to_int_nullable(df[col])
    for col in ["close_return_pct", "score", "weight"]:
        df[col] = _to_float(df[col])
    df["event_key"] = (
        df["model_id"].astype(str)
        + "|"
        + df["selection_date"].astype(str)
        + "|"
        + df["ticker"].astype(str)
        + "|"
        + df["rank_no"].astype(str)
    )
    return df[
        [
            "event_key",
            "strategy_family",
            "scope_key",
            "model_id",
            "rank_no",
            "ticker",
            "name",
            "selection_date",
            "selection_close",
            "selection_mcap",
            "hold_end_date",
            "exit_close",
            "close_return_pct",
            "holding_days",
            "score",
            "weight",
        ]
    ]


def build_summary(events: pd.DataFrame) -> pd.DataFrame:
    summary = (
        events.groupby(["ticker", "name"], dropna=False)
        .agg(
            selection_count=("event_key", "count"),
            model_count=("model_id", "nunique"),
            first_selection_date=("selection_date", "min"),
            latest_selection_date=("selection_date", "max"),
            avg_return_pct=("close_return_pct", "mean"),
            median_return_pct=("close_return_pct", "median"),
            max_return_pct=("close_return_pct", "max"),
            min_return_pct=("close_return_pct", "min"),
            win_rate_pct=("close_return_pct", lambda s: (s > 0).mean() * 100),
            avg_holding_days=("holding_days", "mean"),
            latest_mcap=("selection_mcap", "last"),
        )
        .reset_index()
    )
    models = (
        events.sort_values(["ticker", "selection_date", "model_id"])
        .groupby("ticker")["model_id"]
        .apply(lambda s: ",".join(sorted(set(s.dropna().astype(str)))))
        .reset_index(name="selected_models")
    )
    summary = summary.merge(models, on="ticker", how="left")
    for col in ["avg_return_pct", "median_return_pct", "max_return_pct", "min_return_pct", "win_rate_pct", "avg_holding_days"]:
        summary[col] = summary[col].round(4)
    return summary


def create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        DROP VIEW IF EXISTS v_stock_latest_selection;
        DROP VIEW IF EXISTS v_model_weekly_top5;
        DROP TABLE IF EXISTS stock_selection_summary;
        DROP TABLE IF EXISTS model_selection_events;

        CREATE TABLE model_selection_events (
            event_key TEXT PRIMARY KEY,
            strategy_family TEXT,
            scope_key TEXT,
            model_id TEXT NOT NULL,
            rank_no INTEGER,
            ticker TEXT NOT NULL,
            name TEXT,
            selection_date TEXT NOT NULL,
            selection_close INTEGER,
            selection_mcap INTEGER,
            hold_end_date TEXT,
            exit_close INTEGER,
            close_return_pct REAL,
            holding_days INTEGER,
            score REAL,
            weight REAL
        );

        CREATE TABLE stock_selection_summary (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            selection_count INTEGER,
            model_count INTEGER,
            first_selection_date TEXT,
            latest_selection_date TEXT,
            avg_return_pct REAL,
            median_return_pct REAL,
            max_return_pct REAL,
            min_return_pct REAL,
            win_rate_pct REAL,
            avg_holding_days REAL,
            latest_mcap INTEGER,
            selected_models TEXT
        );

        CREATE TABLE IF NOT EXISTS stock_analysis_notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            analysis_date TEXT NOT NULL,
            thesis TEXT,
            risk TEXT,
            trade_strategy TEXT,
            watch_items TEXT,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );

        CREATE INDEX idx_events_ticker_date ON model_selection_events(ticker, selection_date);
        CREATE INDEX idx_events_model_date ON model_selection_events(model_id, selection_date);
        CREATE INDEX idx_events_return ON model_selection_events(close_return_pct);

        CREATE VIEW v_stock_latest_selection AS
        SELECT e.*
        FROM model_selection_events e
        JOIN (
            SELECT ticker, MAX(selection_date) AS latest_selection_date
            FROM model_selection_events
            GROUP BY ticker
        ) x
        ON e.ticker = x.ticker AND e.selection_date = x.latest_selection_date;

        CREATE VIEW v_model_weekly_top5 AS
        SELECT *
        FROM model_selection_events
        WHERE rank_no <= 5
        ORDER BY model_id, selection_date, rank_no;
        """
    )


def main() -> None:
    if not SOURCE_CSV.exists():
        raise FileNotFoundError(SOURCE_CSV)

    events = load_events()
    summary = build_summary(events)

    with sqlite3.connect(DB_PATH) as con:
        create_schema(con)
        events.to_sql("model_selection_events", con, if_exists="append", index=False)
        summary.to_sql("stock_selection_summary", con, if_exists="append", index=False)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS import_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        con.executemany(
            "INSERT OR REPLACE INTO import_metadata(key, value) VALUES (?, ?)",
            [
                ("source_csv", str(SOURCE_CSV)),
                ("event_rows", str(len(events))),
                ("summary_rows", str(len(summary))),
                ("date_min", str(events["selection_date"].min())),
                ("date_max", str(events["selection_date"].max())),
            ],
        )

    print(f"db={DB_PATH}")
    print(f"events={len(events)}")
    print(f"stocks={len(summary)}")
    print(f"models={events['model_id'].nunique()}")
    print(f"date_range={events['selection_date'].min()}..{events['selection_date'].max()}")


if __name__ == "__main__":
    main()
