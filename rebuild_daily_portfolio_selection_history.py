import argparse
import csv
import json
import sqlite3
from pathlib import Path

import portfolio_pipeline as pp


ROOT = Path(r"D:\QuantAnalysis")
OUTPUT_DIR = ROOT / "outputs"
DOCS_DIR = ROOT / "docs" / "portfolio"
BASE_RANKING_JSON = OUTPUT_DIR / "stock_reactivity_ranking_20260513_20260527_top10.json"
LATEST_PORTFOLIO_JSON = OUTPUT_DIR / "investment_portfolio_latest.json"


def price_db_uri():
    return f"file:///{pp.PRICE_DB_PATH.as_posix()}?mode=ro&immutable=1"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def close_map(tickers, dates):
    if not tickers or not dates:
        return {}
    placeholders_tickers = ",".join("?" for _ in tickers)
    placeholders_dates = ",".join("?" for _ in dates)
    query = f"""
        SELECT ticker, date, close
        FROM prices_daily
        WHERE ticker IN ({placeholders_tickers})
          AND date IN ({placeholders_dates})
          AND close IS NOT NULL
    """
    out = {}
    with sqlite3.connect(price_db_uri(), uri=True) as con:
        for ticker, date, close in con.execute(query, [*tickers, *dates]):
            out[(ticker, date)] = float(close)
    return out


def latest_close_map(tickers, end_date):
    if not tickers:
        return {}
    placeholders = ",".join("?" for _ in tickers)
    query = f"""
        SELECT ticker, date, close
        FROM prices_daily
        WHERE ticker IN ({placeholders})
          AND date <= ?
          AND close IS NOT NULL
        ORDER BY ticker, date DESC
    """
    out = {}
    with sqlite3.connect(price_db_uri(), uri=True) as con:
        for ticker, date, close in con.execute(query, [*tickers, end_date]):
            out.setdefault(ticker, (date, float(close)))
    return out


def index_close_map(index_names, dates):
    if not index_names or not dates:
        return {}
    placeholders_names = ",".join("?" for _ in index_names)
    placeholders_dates = ",".join("?" for _ in dates)
    query = f"""
        SELECT index_name, date, close
        FROM market_index_daily
        WHERE index_name IN ({placeholders_names})
          AND date IN ({placeholders_dates})
          AND close IS NOT NULL
    """
    out = {}
    with sqlite3.connect(pp.market_db_uri(), uri=True) as con:
        for index_name, date, close in con.execute(query, [*index_names, *dates]):
            out[(index_name, date)] = float(close)
    return out


def pct_return(current, base):
    if current is None or base in (None, 0):
        return None
    return round((current / base - 1) * 100, 2)


def latest_rows_from_current_report():
    if not LATEST_PORTFOLIO_JSON.exists():
        return []
    report = read_json(LATEST_PORTFOLIO_JSON)
    date = report.get("as_of_date")
    rows = []
    for item in report.get("stock_strategy", {}).get("candidates", []):
        reactivity = item.get("reactivity") or {}
        momentum = item.get("momentum") or {}
        live = item.get("live_quote") or {}
        rows.append(
            {
                "date": date,
                "rank": reactivity.get("rank"),
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "score": reactivity.get("score"),
                "status": reactivity.get("status"),
                "ret5d": momentum.get("return_5d_pct"),
                "rel5d": momentum.get("relative_return_5d_pct"),
                "models": item.get("model_display"),
                "live_price": live.get("price"),
                "model_selection_date": item.get("model_selection_date") or "2026-05-13",
            }
        )
    return rows


def build_rows(end_date):
    base = read_json(BASE_RANKING_JSON)
    rows = list(base.get("rows", []))
    current_rows = latest_rows_from_current_report()
    if current_rows and current_rows[0].get("date") == end_date:
        rows = [row for row in rows if row.get("date") != end_date]
        rows.extend(current_rows)
    rows = [row for row in rows if row.get("date") <= end_date]
    rows.sort(key=lambda row: (row.get("date"), row.get("rank") or 999))
    return rows


def enrich(rows, end_date):
    tickers = sorted({row["ticker"] for row in rows})
    dates = sorted({row["date"] for row in rows} | {end_date})
    prices = close_map(tickers, dates)
    latest_prices = latest_close_map(tickers, end_date)
    markets = pp.load_candidate_markets([{"ticker": ticker} for ticker in tickers])
    index_names = sorted({"KOSPI" if markets.get(ticker) != "KOSDAQ" else "KOSDAQ" for ticker in tickers})
    index_dates = set(dates)
    index_dates.update(date for date, _close in latest_prices.values())
    index_prices = index_close_map(index_names, sorted(index_dates))
    enriched = []
    for row in rows:
        ticker = row["ticker"]
        portfolio_date = row["date"]
        market = markets.get(ticker) or "KOSPI"
        benchmark = "KOSDAQ" if market == "KOSDAQ" else "KOSPI"
        selection_price = prices.get((ticker, portfolio_date)) or row.get("live_price")
        evaluation_date, evaluation_price = latest_prices.get(ticker, (end_date, None))
        if portfolio_date == end_date and row.get("live_price") is not None:
            evaluation_price = row.get("live_price") or selection_price
            evaluation_date = end_date
        elif evaluation_price is None and portfolio_date == end_date:
            evaluation_price = selection_price
            evaluation_date = end_date
        benchmark_start = index_prices.get((benchmark, portfolio_date))
        benchmark_end = index_prices.get((benchmark, evaluation_date))
        stock_return = pct_return(evaluation_price, selection_price)
        benchmark_return = pct_return(benchmark_end, benchmark_start)
        enriched.append(
            {
                "portfolio_selection_date": portfolio_date,
                "model_selection_date": row.get("model_selection_date") or base_model_selection_date(),
                "rank": row.get("rank"),
                "ticker": ticker,
                "name": row.get("name"),
                "models": row.get("models"),
                "score": row.get("score"),
                "status": row.get("status"),
                "portfolio_selection_close": selection_price,
                "evaluation_date": evaluation_date,
                "evaluation_close": evaluation_price,
                "return_from_portfolio_selection_pct": stock_return,
                "benchmark_index": benchmark,
                "benchmark_return_pct": benchmark_return,
                "relative_to_index_pct": (
                    round(stock_return - benchmark_return, 2)
                    if stock_return is not None and benchmark_return is not None
                    else None
                ),
                "ret5d_at_selection_pct": row.get("ret5d"),
                "relative_5d_at_selection_pctp": row.get("rel5d"),
            }
        )
    return enriched


def base_model_selection_date():
    rows = list(csv.DictReader(pp.STOCK_SELECTION_CSV.open("r", encoding="utf-8-sig", newline="")))
    return max(row["선정일"] for row in rows)


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows, path):
    lines = [
        "# 일별 포트폴리오 선정 이력",
        "",
        "- `포트폴리오선정일`: 해당 날짜에 QuantAnalysis 포트폴리오 점수로 상위 10개에 선정된 날짜",
        "- `모델선정일`: Quant 전략모델 원천 후보군에 편입된 날짜",
        "",
    ]
    for date in sorted({row["portfolio_selection_date"] for row in rows}):
        lines.append(f"## {date}")
        lines.append("| 순위 | 코드 | 종목 | 점수 | 상태 | 모델 | 선정일종가 | 평가일 | 평가가 | 수익률 | 지수대비 |")
        lines.append("|---:|---|---|---:|---|---|---:|---|---:|---:|---:|")
        for row in [r for r in rows if r["portfolio_selection_date"] == date]:
            lines.append(
                f"| {row['rank']} | {row['ticker']} | {row['name']} | {row['score']} | {row['status']} | "
                f"{row['models']} | {pp.fmt(row['portfolio_selection_close'])} | {row['evaluation_date']} | "
                f"{pp.fmt(row['evaluation_close'])} | {pp.fmt(row['return_from_portfolio_selection_pct'])}% | "
                f"{pp.fmt(row['relative_to_index_pct'])}%p |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", default="2026-05-28")
    args = parser.parse_args()

    rows = enrich(build_rows(args.end), args.end)
    stamp = args.end.replace("-", "")
    json_path = OUTPUT_DIR / f"daily_portfolio_selection_history_20260513_{stamp}.json"
    csv_path = OUTPUT_DIR / f"daily_portfolio_selection_history_20260513_{stamp}.csv"
    md_path = DOCS_DIR / f"daily_portfolio_selection_history_20260513_{stamp}.md"
    payload = {
        "rule": "전체 Quant 주간 후보 101개를 매 거래일 포트폴리오 반응성 점수로 재채점하여 상위 10개 선정",
        "portfolio_selection_date_definition": "해당 날짜에 포트폴리오 점수 상위 10개로 선정된 날짜",
        "model_selection_date_definition": "Quant 전략모델 원천 후보군에 편입된 날짜",
        "evaluation_date": args.end,
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(rows, csv_path)
    write_markdown(rows, md_path)
    print(json_path)
    print(csv_path)
    print(md_path)
    first = [row for row in rows if row["portfolio_selection_date"] == "2026-05-13" and row["rank"] == 1]
    if first:
        print(f"first_2026-05-13={first[0]['ticker']} {first[0]['name']}")


if __name__ == "__main__":
    main()
