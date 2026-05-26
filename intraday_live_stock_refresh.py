import argparse
import json
import sqlite3
from datetime import datetime, time
from pathlib import Path

from portfolio_pipeline import (
    DB_PATH,
    KST,
    OUTPUT_DIR,
    apply_candidate_scenario_decisions,
    attach_kiwoom_live_snapshot,
    publish_portfolio_to_gcs,
    stock_model_summary,
)


def now_kst():
    return datetime.now(KST)


def is_market_refresh_window(dt):
    if dt.weekday() >= 5:
        return False
    return time(9, 0) <= dt.time() <= time(15, 40)


def init_schema(con):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS portfolio_stock_live_refresh_runs (
            refresh_id INTEGER PRIMARY KEY AUTOINCREMENT,
            as_of_date TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            status TEXT,
            source TEXT,
            success_count INTEGER,
            error_count INTEGER,
            errors_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolio_stock_live_snapshots (
            refresh_id INTEGER NOT NULL,
            as_of_date TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            latest_selection_date TEXT,
            model_display TEXT,
            live_price REAL,
            live_change_pct REAL,
            foreign_net_억원 REAL,
            institution_net_억원 REAL,
            individual_net_억원 REAL,
            pension_net_억원 REAL,
            source TEXT,
            raw_json TEXT,
            PRIMARY KEY (refresh_id, ticker),
            FOREIGN KEY (refresh_id) REFERENCES portfolio_stock_live_refresh_runs(refresh_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_stock_live_snapshots_ticker_time
            ON portfolio_stock_live_snapshots(ticker, fetched_at);
        """
    )
    con.execute("DROP VIEW IF EXISTS v_portfolio_stock_live_latest")
    con.execute(
        """
        CREATE VIEW v_portfolio_stock_live_latest AS
        SELECT s.*
        FROM portfolio_stock_live_snapshots s
        JOIN (
            SELECT ticker, MAX(fetched_at) AS fetched_at
            FROM portfolio_stock_live_snapshots
            GROUP BY ticker
        ) latest
          ON latest.ticker = s.ticker
         AND latest.fetched_at = s.fetched_at
        """
    )


def latest_portfolio_run_id(con):
    row = con.execute("SELECT MAX(run_id) FROM portfolio_runs").fetchone()
    return row[0] if row and row[0] is not None else None


def update_latest_portfolio_candidates(con, run_id, items):
    if run_id is None:
        return 0
    updated = 0
    for row in items:
        live = row.get("live_quote") or {}
        if not live:
            continue
        cur = con.execute(
            """
            UPDATE portfolio_stock_candidates
               SET live_price = ?,
                   live_change_pct = ?,
                   foreign_net_억원 = ?,
                   institution_net_억원 = ?,
                   individual_net_억원 = ?,
                   pension_net_억원 = ?
             WHERE run_id = ? AND ticker = ?
            """,
            (
                live.get("price"),
                live.get("change_pct"),
                live.get("foreign_net_억원"),
                live.get("institution_net_억원"),
                live.get("individual_net_억원"),
                live.get("pension_net_억원"),
                run_id,
                row.get("ticker"),
            ),
        )
        updated += cur.rowcount
    return updated


def save_refresh(live, asof_date):
    fetched_at = live.get("fetched_at") or now_kst().isoformat(timespec="milliseconds")
    with sqlite3.connect(DB_PATH) as con:
        con.execute("PRAGMA foreign_keys = ON")
        init_schema(con)
        cur = con.execute(
            """
            INSERT INTO portfolio_stock_live_refresh_runs(
                as_of_date, fetched_at, status, source, success_count, error_count, errors_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asof_date,
                fetched_at,
                live.get("status"),
                live.get("source"),
                live.get("success_count"),
                live.get("error_count"),
                json.dumps(live.get("errors", []), ensure_ascii=False),
            ),
        )
        refresh_id = cur.lastrowid
        rows = []
        for item in live.get("items", []):
            quote = item.get("live_quote") or {}
            if not quote:
                continue
            rows.append(
                (
                    refresh_id,
                    asof_date,
                    fetched_at,
                    item.get("ticker"),
                    item.get("name"),
                    item.get("latest_selection_date"),
                    item.get("model_display"),
                    quote.get("price"),
                    quote.get("change_pct"),
                    quote.get("foreign_net_억원"),
                    quote.get("institution_net_억원"),
                    quote.get("individual_net_억원"),
                    quote.get("pension_net_억원"),
                    quote.get("source"),
                    json.dumps(quote, ensure_ascii=False),
                )
            )
        con.executemany(
            """
            INSERT INTO portfolio_stock_live_snapshots(
                refresh_id, as_of_date, fetched_at, ticker, name, latest_selection_date,
                model_display, live_price, live_change_pct, foreign_net_억원,
                institution_net_억원, individual_net_억원, pension_net_억원, source, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        run_id = latest_portfolio_run_id(con)
        updated_candidates = update_latest_portfolio_candidates(con, run_id, live.get("items", []))
        return {
            "refresh_id": refresh_id,
            "run_id_updated": run_id,
            "updated_candidates": updated_candidates,
            "snapshot_rows": len(rows),
            "fetched_at": fetched_at,
            "status": live.get("status"),
            "source": live.get("source"),
            "errors": live.get("errors", []),
        }


def update_latest_portfolio_json(live, refresh_result):
    if live.get("status") != "ok":
        return {"status": "skipped", "reason": "live_status_not_ok"}
    latest_path = OUTPUT_DIR / "investment_portfolio_latest.json"
    if not latest_path.exists():
        return {"status": "skipped", "reason": "latest_portfolio_json_missing"}

    report = json.loads(latest_path.read_text(encoding="utf-8-sig"))
    live_by_ticker = {
        item.get("ticker"): item.get("live_quote")
        for item in live.get("items", [])
        if item.get("ticker") and item.get("live_quote")
    }
    candidates = report.get("stock_strategy", {}).get("candidates", [])
    updated = 0
    for candidate in candidates:
        quote = live_by_ticker.get(candidate.get("ticker"))
        if not quote:
            continue
        candidate["live_quote"] = quote
        updated += 1

    scenarios = report.get("etf_strategy", {}).get("portfolio_scenarios", [])
    if scenarios:
        refreshed_live = apply_candidate_scenario_decisions(
            {
                "status": live.get("status"),
                "source": live.get("source"),
                "asof_date": live.get("asof_date"),
                "fetched_at": live.get("fetched_at"),
                "success_count": live.get("success_count"),
                "error_count": live.get("error_count"),
                "errors": live.get("errors", []),
                "items": candidates,
            },
            scenarios,
        )
        report["stock_strategy"]["candidates"] = refreshed_live["items"]

    report.setdefault("stock_strategy", {})["live_data"] = {
        "status": live.get("status"),
        "source": live.get("source"),
        "asof_date": live.get("asof_date"),
        "fetched_at": live.get("fetched_at"),
        "success_count": live.get("success_count"),
        "error_count": live.get("error_count"),
        "errors": live.get("errors", []),
    }
    report["intraday_live_refresh"] = {
        "refresh_id": refresh_result.get("refresh_id"),
        "run_id_updated": refresh_result.get("run_id_updated"),
        "updated_candidates": refresh_result.get("updated_candidates"),
        "snapshot_rows": refresh_result.get("snapshot_rows"),
        "fetched_at": live.get("fetched_at"),
        "status": live.get("status"),
        "source": live.get("source"),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S%f")[:22]
    archive_path = OUTPUT_DIR / f"investment_portfolio_live_refresh_{stamp}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    latest_path.write_text(payload, encoding="utf-8")
    archive_path.write_text(payload, encoding="utf-8")
    return {
        "status": "updated",
        "updated_candidates": updated,
        "latest_json": str(latest_path),
        "archive_json": str(archive_path),
    }


def publish_live_portfolio_update(json_update_result, skip_gcs_publish):
    if skip_gcs_publish or json_update_result.get("status") != "updated":
        return {"status": "skipped"}
    try:
        publish_result = publish_portfolio_to_gcs(
            Path(json_update_result["latest_json"]),
            Path(json_update_result["archive_json"]),
        )
        return {"status": "ok", **publish_result}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-gcs-publish", action="store_true")
    args = parser.parse_args()

    dt = now_kst()
    if not args.force and not is_market_refresh_window(dt):
        print(json.dumps({"status": "skipped", "reason": "outside_market_refresh_window", "checked_at": dt.isoformat(timespec="seconds")}, ensure_ascii=False))
        return

    asof_date = args.asof or dt.strftime("%Y-%m-%d")
    stocks = stock_model_summary()
    live = attach_kiwoom_live_snapshot(stocks, asof_date)
    result = save_refresh(live, asof_date)
    json_update = update_latest_portfolio_json(live, result)
    gcs_publish = publish_live_portfolio_update(json_update, args.skip_gcs_publish)
    result["portfolio_json_update"] = json_update
    result["gcs_publish"] = gcs_publish
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
