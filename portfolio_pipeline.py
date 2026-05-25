import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests


ROOT = Path(r"D:\QuantAnalysis")
OUTPUT_DIR = ROOT / "outputs"
DOCS_DIR = ROOT / "docs"
PORTFOLIO_DOCS_DIR = DOCS_DIR / "portfolio"
DB_PATH = ROOT / "analysis.db"
PRICE_DB_PATH = Path(r"D:\Quant\data\db\price.db")
AI_FEATURE_DB_PATH = Path(r"D:\Quant\data\db\ai_feature_ext.db")
MARKET_ANALYSIS_DB_PATH = Path(r"D:\QuantMarket\data\db\market_analysis.db")
MARKET_STATUS = Path(r"D:\QuantMarket\reports\market_analysis\market_ai_generation_status_latest.json")
MARKET_CONTEXT = Path(r"D:\QuantMarket\reports\market_analysis\market_context_latest.json")
ETF_ALLOC_DIR = Path(r"D:\Quant\reports\backtest_etf_allocation")
E_SERIES_POLICY = Path(
    r"D:\Quant\service_platform\web\admin_data\current\e_series_etf_operational_policy_hierarchy_current.json"
)
STOCK_SELECTION_CSV = ROOT / "weekly_model_selection_20260301_20260515_full.csv"

KST = timezone(timedelta(hours=9))
KIWOOM_HOST = "https://api.kiwoom.com"
KIWOOM_TOKEN_ENDPOINT = "/oauth2/token"
KIWOOM_STOCK_ENDPOINT = "/api/dostk/stkinfo"
KIWOOM_QUOTE_API_ID = "ka10001"
KIWOOM_INVESTOR_API_ID = "ka10059"
KIWOOM_APPKEY_FILE = Path(r"D:\Quant\config\kiwoom_54810245_appkey.txt")
KIWOOM_SECRETKEY_FILE = Path(r"D:\Quant\config\kiwoom_54810245_secretkey.txt")
NAVER_INVESTOR_URL = "https://finance.naver.com/item/frgn.naver"
GCS_BUCKET = "quantservice-489808-market-analysis"
GCS_CURRENT_TARGET = f"gs://{GCS_BUCKET}/admin/current/investment_portfolio_latest.json"
GCS_HISTORY_PREFIX = f"gs://{GCS_BUCKET}/admin/history"
GCS_PUBLIC_CURRENT_URL = (
    f"https://storage.googleapis.com/{GCS_BUCKET}/admin/current/investment_portfolio_latest.json"
)

STEP1_V2_LOGIC_VERSION = "step1_v2_6grade_20260525"
STEP1_GRADE_LABELS = {
    1: "강한 위험회피",
    2: "위험회피",
    3: "주의 관찰",
    4: "중립",
    5: "우호적 관찰",
    6: "적극 위험선호",
}
STEP1_GRADE_BOUNDS = [
    (1, 0, 24),
    (2, 25, 39),
    (3, 40, 54),
    (4, 55, 69),
    (5, 70, 84),
    (6, 85, 100),
]


TARGET_STOCKS = {
    "005380": {"name": "현대차", "group": "core_candidate", "decision": "보류"},
    "012330": {"name": "현대모비스", "group": "core_candidate", "decision": "보류"},
    "005490": {"name": "POSCO홀딩스", "group": "core_candidate", "decision": "소액분할검토"},
    "017670": {"name": "SK텔레콤", "group": "core_candidate", "decision": "소액/관찰"},
    "047040": {"name": "대우건설", "group": "core_candidate", "decision": "관찰"},
    "000660": {"name": "SK하이닉스", "group": "high_interest_chase_block", "decision": "추격 보류"},
    "005930": {"name": "삼성전자", "group": "high_interest_chase_block", "decision": "추격 보류/관찰"},
    "066570": {"name": "LG전자", "group": "high_interest_chase_block", "decision": "보류"},
    "003550": {"name": "LG", "group": "high_interest_chase_block", "decision": "보류"},
    "402340": {"name": "SK스퀘어", "group": "high_interest_chase_block", "decision": "관찰"},
}

QUALITATIVE_SUMMARIES = {
    "005380": "완성차, 전기차, 하이브리드, SDV 전환 역량은 긍정적이나 글로벌 수요와 경쟁 심화가 부담.",
    "012330": "모듈, 전동화, 자율주행 부품 경쟁력이 있으나 완성차 업황과 투자비 부담에 민감.",
    "005490": "철강과 2차전지 소재 전환을 병행하나 철강 경기와 배터리 소재 가격 변동성이 핵심 리스크.",
    "017670": "통신 방어주 성격과 AI, 데이터센터, 클라우드 확장이 강점. 요금 규제와 경쟁은 부담.",
    "047040": "주택, 토목, 해외 플랜트 회복이 관건. 금리, 원가, 부동산 경기 둔화 리스크가 큼.",
    "000660": "HBM과 AI 서버 메모리 수혜가 크지만 메모리 사이클, 설비투자, 경쟁 리스크가 높음.",
    "005930": "메모리, 파운드리, 모바일, 가전 포트폴리오가 넓으나 반도체 경쟁과 글로벌 수요가 변수.",
    "066570": "가전, TV, 전장, B2B 전환이 강점이나 단기 급등 후 수요 둔화와 차익실현 부담이 큼.",
    "003550": "지주회사로 계열사 가치와 신사업 투자 성과가 핵심. 할인율과 자회사 변동성에 영향.",
    "402340": "SK하이닉스와 ICT 투자자산 가치에 연동. 하이닉스 변동성과 투자자산 재평가가 핵심 변수.",
}

MODEL_ROLE_DESCRIPTIONS = {
    "I-STOCK-STRONG-RSI-V01": {
        "plain_name": "가격 강도/재가속 확인 모델",
        "description": "최근 시장이 약해도 버티거나 다시 강해지는 종목을 찾는다. RSI, 가격 강도, 재가속 흐름을 중심으로 본다.",
        "signal_family": "price_strength",
    },
    "S2": {
        "plain_name": "펀더멘털 기반 안정형 주식 모델",
        "description": "품질, 성장, 재무 개선, 시장 게이트를 함께 보며 대형 우량주와 실적 기반 종목이 많이 남는다.",
        "signal_family": "fundamental_defensive",
    },
    "S2_PIT_V01": {
        "plain_name": "시점 정보 기준 강화형 S2",
        "description": "미래정보 누수를 줄이고 해당 시점에 확인 가능한 펀더멘털과 시장 필터로 종목을 다시 걸러낸다.",
        "signal_family": "pit_fundamental",
    },
    "S3_CORE2": {
        "plain_name": "추세 지속 확인 모델",
        "description": "가격 추세와 상대 강도가 이어지는 종목을 선별한다.",
        "signal_family": "trend",
    },
    "T-STOCK-V01": {
        "plain_name": "테마/전환 후보 탐색 모델",
        "description": "테마 확산, 초기 모멘텀, 상위 그룹 진입 가능성을 보는 탐색형 모델이다.",
        "signal_family": "theme_transition",
    },
}

MODEL_DISPLAY_MAP = {
    "I-STOCK-STRONG-RSI-V01": "I-STOCK",
    "S2": "S2",
    "S2_PIT_V01": "S2_PIT",
    "S3": "S3",
    "S3_CORE2": "S3_CORE2",
    "S3_ACCEL_V01": "S3_ACCEL",
    "S4": "S4",
    "S5": "S5",
    "S6": "S6",
    "T-STOCK-V01": "T-STOCK",
    "T-ETF-V01": "T-ETF",
}

KIWOOM_SNAPSHOT_20260518 = {
    "source": "kiwoom_rest_ka10001+ka10059",
    "asof_date": "2026-05-18",
    "status": "snapshot_confirmed",
    "items": {
        "005380": {"price": 663000, "change_pct": -5.29, "foreign_net_억원": -1355.9, "institution_net_억원": -1113.9, "individual_net_억원": 2480.5, "pension_net_억원": -120.9},
        "012330": {"price": 571000, "change_pct": -9.22, "foreign_net_억원": -1587.8, "institution_net_억원": 293.4, "individual_net_억원": 1000.8, "pension_net_억원": -3.4},
        "005490": {"price": 463000, "change_pct": -0.96, "foreign_net_억원": 166.0, "institution_net_억원": 22.8, "individual_net_억원": -150.2, "pension_net_억원": 8.0},
        "017670": {"price": 100500, "change_pct": -0.79, "foreign_net_억원": -27.4, "institution_net_억원": 47.5, "individual_net_억원": -8.0, "pension_net_억원": -15.8},
        "047040": {"price": 29300, "change_pct": 2.81, "foreign_net_억원": 182.9, "institution_net_억원": -71.0, "individual_net_억원": -81.1, "pension_net_억원": -54.8},
        "000660": {"price": 1840000, "change_pct": 1.15, "foreign_net_억원": -10211.9, "institution_net_억원": 4977.0, "individual_net_억원": 5225.3, "pension_net_억원": -259.1},
        "005930": {"price": 281000, "change_pct": 3.88, "foreign_net_억원": -12401.9, "institution_net_억원": 7862.0, "individual_net_억원": 4583.6, "pension_net_억원": 355.7},
        "066570": {"price": 217000, "change_pct": -9.77, "foreign_net_억원": -1866.7, "institution_net_억원": -347.7, "individual_net_억원": 2213.9, "pension_net_억원": -74.4},
        "003550": {"price": 115400, "change_pct": -8.41, "foreign_net_억원": -317.1, "institution_net_억원": -88.1, "individual_net_억원": 394.2, "pension_net_억원": -1.5},
        "402340": {"price": 1093000, "change_pct": -0.46, "foreign_net_억원": -1003.1, "institution_net_억원": 942.0, "individual_net_억원": 49.0, "pension_net_억원": 56.6},
    },
}


def read_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def latest_s6_file():
    candidates = sorted(ETF_ALLOC_DIR.glob("s6_alloc_weights_*_M_*.csv"), reverse=True)
    if not candidates:
        return None
    return candidates[0]


def load_s6_holdings():
    path = latest_s6_file()
    if not path:
        return {"source_file": None, "holdings": []}
    rows = list(csv.DictReader(path.open("r", encoding="utf-8-sig", newline="")))
    latest_date = max(row["rebalance_date"] for row in rows)
    holdings = []
    for row in rows:
        if row["rebalance_date"] != latest_date:
            continue
        if str(row.get("selected", "")).lower() != "true":
            continue
        holdings.append(
            {
                "ticker": row["ticker"],
                "name": row["name"],
                "market": row["market"],
                "role": row["group_key"],
                "weight_pct": round(float(row["weight"]) * 100, 2),
                "rebalance_date": row["rebalance_date"],
                "trade_date": row["trade_date"],
            }
        )
    return {"source_file": str(path), "rebalance_date": latest_date, "holdings": holdings}


def stock_model_summary():
    if not STOCK_SELECTION_CSV.exists():
        return []
    rows = list(csv.DictReader(STOCK_SELECTION_CSV.open("r", encoding="utf-8-sig", newline="")))
    out = []
    for code, meta in TARGET_STOCKS.items():
        selected = [row for row in rows if row["종목코드"].zfill(6) == code]
        if not selected:
            continue
        latest = max(row["선정일"] for row in selected)
        latest_rows = [row for row in selected if row["선정일"] == latest]
        model_groups = sorted({row["전략군"] for row in latest_rows})
        model_ids = sorted({row["모델"] for row in latest_rows})
        model_display_codes = [MODEL_DISPLAY_MAP.get(model_id, model_id) for model_id in model_ids]
        first_row = latest_rows[0]
        out.append(
            {
                "ticker": code,
                "name": meta["name"],
                "group": meta["group"],
                "decision": meta["decision"],
                "latest_selection_date": latest,
                "model_groups": model_groups,
                "model_ids": model_ids,
                "model_display_codes": model_display_codes,
                "model_display": " / ".join(model_display_codes),
                "model_count": len(model_ids),
                "selection_close": to_number(first_row.get("선정일 종가")),
                "market_cap": to_number(first_row.get("선정일 시가총액")),
                "return_from_selection_pct": to_number(first_row.get("선정일 대비 종가 등락율(%)")),
                "holding_days": to_number(first_row.get("보유기간(일)")),
                "qualitative_summary": QUALITATIVE_SUMMARIES.get(code, ""),
            }
        )
    return out


def to_number(value):
    if value is None or value == "":
        return None
    try:
        value = float(value)
        if value.is_integer():
            return int(value)
        return value
    except ValueError:
        return value


def read_secret(path):
    value = path.read_text(encoding="utf-8-sig").strip()
    if not value:
        raise RuntimeError(f"empty secret file: {path}")
    return value


def normalize_api_date(value):
    text = str(value).strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"invalid date: {value}")
    return text


def parse_kiwoom_number(value):
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "-", "None", "nan"}:
        return None
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    try:
        number = sign * float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def recursive_find(payload, keys):
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                return payload[key]
        for value in payload.values():
            found = recursive_find(value, keys)
            if found is not None:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = recursive_find(item, keys)
            if found is not None:
                return found
    return None


def kiwoom_access_token():
    response = requests.post(
        f"{KIWOOM_HOST}{KIWOOM_TOKEN_ENDPOINT}",
        headers={"Content-Type": "application/json;charset=UTF-8"},
        json={
            "grant_type": "client_credentials",
            "appkey": read_secret(KIWOOM_APPKEY_FILE),
            "secretkey": read_secret(KIWOOM_SECRETKEY_FILE),
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if int(payload.get("return_code", -1)) != 0 or not payload.get("token"):
        raise RuntimeError(
            f"Kiwoom token failed: return_code={payload.get('return_code')}, return_msg={payload.get('return_msg')}"
        )
    return str(payload["token"]), payload.get("expires_dt")


def kiwoom_post(token, api_id, body, retries=3):
    response = None
    for attempt in range(retries + 1):
        response = requests.post(
            f"{KIWOOM_HOST}{KIWOOM_STOCK_ENDPOINT}",
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": f"Bearer {token}",
                "api-id": api_id,
                "cont-yn": "N",
                "next-key": "",
            },
            json=body,
            timeout=60,
        )
        if response.status_code != 429:
            break
        time.sleep(min(6.0, 1.5 * (attempt + 1)))
    if response is None:
        raise RuntimeError("Kiwoom request was not executed")
    response.raise_for_status()
    payload = response.json()
    if int(payload.get("return_code", 0)) != 0:
        raise RuntimeError(
            f"Kiwoom {api_id} failed: return_code={payload.get('return_code')}, return_msg={payload.get('return_msg')}"
        )
    return payload


def request_kiwoom_quote(token, ticker):
    payload = kiwoom_post(token, KIWOOM_QUOTE_API_ID, {"stk_cd": ticker})
    price = parse_kiwoom_number(
        recursive_find(payload, ["cur_prc", "now_prc", "stck_prpr", "price", "현재가", "TDD_CLSPRC"])
    )
    prev_close = parse_kiwoom_number(
        recursive_find(payload, ["base_pric", "pred_close", "prev_close", "전일종가", "SETL_PRC"])
    )
    change_pct = parse_kiwoom_number(
        recursive_find(payload, ["flu_rt", "fluctuation_rate", "change_rate", "chg_rt", "등락률", "전일대비율"])
    )
    if change_pct is None and price is not None and prev_close not in (None, 0):
        change_pct = round(((abs(price) / abs(prev_close)) - 1) * 100, 2)
    return {
        "price": abs(price) if price is not None else None,
        "change_pct": change_pct,
    }


def load_price_db_quotes(stocks, asof_date):
    if not PRICE_DB_PATH.exists():
        return {}
    tickers = [stock["ticker"] for stock in stocks]
    placeholders = ",".join("?" for _ in tickers)
    query = f"""
        SELECT p.ticker, p.close, prev.close
        FROM prices_daily p
        LEFT JOIN prices_daily prev
          ON prev.ticker = p.ticker
         AND prev.date = (
             SELECT MAX(date)
             FROM prices_daily
             WHERE ticker = p.ticker AND date < p.date AND close IS NOT NULL
         )
        WHERE p.date = ?
          AND p.ticker IN ({placeholders})
          AND p.close IS NOT NULL
    """
    out = {}
    with sqlite3.connect(PRICE_DB_PATH) as con:
        for ticker, close, prev_close in con.execute(query, [asof_date, *tickers]):
            change_pct = None
            if prev_close not in (None, 0):
                change_pct = round((float(close) / float(prev_close) - 1) * 100, 2)
            out[ticker] = {
                "price": int(close) if float(close).is_integer() else close,
                "change_pct": change_pct,
                "price_date": asof_date,
                "price_source": "price.db.prices_daily",
            }
    return out


def normalize_ticker(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits.zfill(6) if digits else None


def pick_column(columns, candidates):
    normalized = {str(col).replace(" ", ""): str(col) for col in columns}
    for candidate in candidates:
        key = candidate.replace(" ", "")
        if key in normalized:
            return normalized[key]
    for col in columns:
        compact = str(col).replace(" ", "")
        if any(candidate.replace(" ", "") in compact for candidate in candidates):
            return str(col)
    return None


def pick_column_with_all_tokens(columns, tokens):
    for col in columns:
        compact = str(col).replace(" ", "")
        if all(token in compact for token in tokens):
            return str(col)
    return None


def won_to_eok(value):
    number = parse_kiwoom_number(value)
    return None if number is None else round(float(number) / 100_000_000, 1)


def load_local_investor_flows(stocks, asof_date):
    if not AI_FEATURE_DB_PATH.exists():
        return {}
    tickers = [stock["ticker"] for stock in stocks]
    placeholders = ",".join("?" for _ in tickers)
    investor_map = {
        "외국인": "foreign_net_억원",
        "기관합계": "institution_net_억원",
        "개인": "individual_net_억원",
        "연기금": "pension_net_억원",
    }
    query = f"""
        SELECT ticker, investor, net_value, source
        FROM investor_flows_daily
        WHERE date = ?
          AND ticker IN ({placeholders})
          AND investor IN ('외국인', '기관합계', '개인', '연기금')
    """
    out = {}
    try:
        with sqlite3.connect(AI_FEATURE_DB_PATH) as con:
            rows = con.execute(query, [asof_date, *tickers]).fetchall()
    except sqlite3.Error:
        return {}
    for ticker, investor, net_value, source in rows:
        field = investor_map.get(investor)
        if not field:
            continue
        row = out.setdefault(ticker, {"flow_date": asof_date, "flow_source": source or "ai_feature_ext.investor_flows_daily"})
        row[field] = won_to_eok(net_value)
    return out


def load_krx_investor_flows(stocks, asof_date):
    tickers = {stock["ticker"] for stock in stocks}
    investor_map = {
        "외국인": "foreign_net_억원",
        "기관합계": "institution_net_억원",
        "개인": "individual_net_억원",
        "연기금": "pension_net_억원",
    }
    try:
        from pykrx import stock as krx_stock
    except Exception:
        return {}

    out = {}
    api_date = normalize_api_date(asof_date)
    for investor, field in investor_map.items():
        for market in ("KOSPI", "KOSDAQ"):
            try:
                raw = krx_stock.get_market_net_purchases_of_equities_by_ticker(
                    api_date,
                    api_date,
                    market=market,
                    investor=investor,
                )
            except Exception:
                continue
            if raw is None or raw.empty:
                continue
            frame = raw.reset_index()
            ticker_col = pick_column(list(frame.columns), ["티커", "종목코드", "ticker", "index"])
            net_value_col = pick_column(list(frame.columns), ["순매수거래대금", "순매수대금", "순매수금액"])
            if not ticker_col or not net_value_col:
                continue
            for row in frame.to_dict(orient="records"):
                ticker = normalize_ticker(row.get(ticker_col))
                if ticker not in tickers:
                    continue
                item = out.setdefault(
                    ticker,
                    {"flow_date": asof_date, "flow_source": "pykrx_krx_investor_net_purchase"},
                )
                item[field] = won_to_eok(row.get(net_value_col))
    return out


def load_naver_investor_flow_for_ticker(ticker, asof_date, session):
    try:
        import pandas as pd
    except Exception:
        return {}
    try:
        response = session.get(
            NAVER_INVESTOR_URL,
            params={"code": ticker, "page": 1},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        response.raise_for_status()
        tables = pd.read_html(response.content, encoding="euc-kr", flavor="lxml")
    except Exception:
        return {}

    flow_table = None
    for table in tables:
        df = table.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join(str(x) for x in col if str(x) != "nan").strip("_") for col in df.columns]
        else:
            df.columns = [str(col) for col in df.columns]
        compact_cols = "".join(df.columns)
        if "날짜" in compact_cols and "기관" in compact_cols and "외국인" in compact_cols:
            flow_table = df
            break
    if flow_table is None:
        return {}

    date_col = pick_column(list(flow_table.columns), ["날짜"])
    close_col = pick_column(list(flow_table.columns), ["종가"])
    inst_col = pick_column_with_all_tokens(list(flow_table.columns), ["기관", "순매매량"])
    foreign_col = pick_column_with_all_tokens(list(flow_table.columns), ["외국인", "순매매량"])
    if not date_col or not close_col or not inst_col or not foreign_col:
        return {}
    for row in flow_table.to_dict(orient="records"):
        date_text = str(row.get(date_col) or "").strip()
        try:
            trade_date = datetime.strptime(date_text, "%Y.%m.%d").strftime("%Y-%m-%d")
        except ValueError:
            continue
        if trade_date != asof_date:
            continue
        close = parse_kiwoom_number(row.get(close_col))
        foreign_volume = parse_kiwoom_number(row.get(foreign_col))
        inst_volume = parse_kiwoom_number(row.get(inst_col))
        return {
            "foreign_net_억원": won_to_eok(None if close is None or foreign_volume is None else close * foreign_volume),
            "institution_net_억원": won_to_eok(None if close is None or inst_volume is None else close * inst_volume),
            "flow_date": asof_date,
            "flow_source": "naver_finance_frgn_derived_value",
            "naver_close": abs(close) if close is not None else None,
        }
    return {}


def load_naver_investor_flows(stocks, asof_date):
    out = {}
    with requests.Session() as session:
        for stock in stocks:
            flow = load_naver_investor_flow_for_ticker(stock["ticker"], asof_date, session)
            if flow:
                out[stock["ticker"]] = flow
            time.sleep(0.15)
    return out


def merge_flow_sources(*sources):
    out = {}
    for source in sources:
        for ticker, flow in source.items():
            current = out.setdefault(ticker, {})
            for key, value in flow.items():
                if current.get(key) is None and value is not None:
                    current[key] = value
    return out


def load_backup_investor_flows(stocks, asof_date):
    local = load_local_investor_flows(stocks, asof_date)
    missing = [stock for stock in stocks if stock["ticker"] not in local]
    krx = load_krx_investor_flows(missing, asof_date) if missing else {}
    missing = [stock for stock in stocks if stock["ticker"] not in local and stock["ticker"] not in krx]
    naver = load_naver_investor_flows(missing, asof_date) if missing else {}
    return merge_flow_sources(local, krx, naver)


def attach_backup_live_snapshot(stocks, asof_date, reason, errors=None, historical_quotes=None):
    fetched_at = datetime.now(KST).isoformat(timespec="milliseconds")
    historical_quotes = historical_quotes if historical_quotes is not None else load_price_db_quotes(stocks, asof_date)
    backup_flows = load_backup_investor_flows(stocks, asof_date)
    merged = []
    complete_count = 0
    attached_count = 0
    sources = set()
    for stock in stocks:
        item = dict(stock)
        ticker = stock["ticker"]
        quote = historical_quotes.get(ticker, {})
        flow = backup_flows.get(ticker, {})
        naver_close = flow.get("naver_close")
        price = quote.get("price")
        if price is None and naver_close is not None:
            price = naver_close
        if quote or flow:
            price_source = quote.get("price_source") or ("naver_finance_frgn_close" if naver_close is not None else None)
            flow_source = flow.get("flow_source")
            quote_sources = [source for source in (price_source, flow_source) if source]
            source_text = "+".join(dict.fromkeys(quote_sources)) if quote_sources else "backup_snapshot"
            sources.add(source_text)
            live_quote = {
                "price": price,
                "change_pct": quote.get("change_pct"),
                "foreign_net_억원": flow.get("foreign_net_억원"),
                "institution_net_억원": flow.get("institution_net_억원"),
                "individual_net_억원": flow.get("individual_net_억원"),
                "pension_net_억원": flow.get("pension_net_억원"),
                "source": source_text,
                "asof_date": asof_date,
                "fetched_at": fetched_at,
                "price_date": quote.get("price_date") or asof_date,
                "flow_date": flow.get("flow_date"),
            }
            item["live_quote"] = live_quote
            attached_count += 1
            if (
                live_quote.get("price") is not None
                and live_quote.get("foreign_net_억원") is not None
                and live_quote.get("institution_net_억원") is not None
            ):
                complete_count += 1
        else:
            item["live_quote"] = None
        merged.append(item)

    if complete_count == len(stocks):
        status = "ok"
    elif attached_count:
        status = "partial"
    else:
        status = "not_loaded"
    return {
        "status": status,
        "source": "+".join(sorted(sources)) if sources else None,
        "asof_date": asof_date,
        "fetched_at": fetched_at,
        "reason": reason,
        "success_count": complete_count,
        "error_count": 0 if not errors else len(errors),
        "errors": (errors or [])[:10],
        "items": merged,
    }


def request_kiwoom_investor_amount(token, ticker, asof_date):
    payload = kiwoom_post(
        token,
        KIWOOM_INVESTOR_API_ID,
        {
            "dt": normalize_api_date(asof_date),
            "stk_cd": ticker,
            "amt_qty_tp": "1",
            "trde_tp": "0",
            "unit_tp": "1",
        },
    )
    rows = payload.get("stk_invsr_orgn") or []
    row = rows[0] if isinstance(rows, list) and rows else {}

    def to_eok(field):
        value = parse_kiwoom_number(row.get(field))
        return None if value is None else round(value / 100, 1)

    return {
        "foreign_net_억원": to_eok("frgnr_invsr"),
        "institution_net_억원": to_eok("orgn"),
        "individual_net_억원": to_eok("ind_invsr"),
        "pension_net_억원": to_eok("penfnd_etc"),
        "flow_date": row.get("dt"),
    }


def classify_market_rating(total_score, risk_score):
    if total_score is None:
        return "Neutral Watch"
    if total_score < 0.2 and risk_score is not None and risk_score > 0.5:
        return "Defensive Caution"
    if total_score >= 1.2 and (risk_score is None or risk_score <= 0.3):
        return "Constructive Watch"
    if total_score >= 0.4:
        return "Neutral Watch"
    return "Cautious Watch"


def market_db_uri():
    return f"file:{MARKET_ANALYSIS_DB_PATH.as_posix()}?mode=ro&immutable=1"


def connect_market_db():
    if not MARKET_ANALYSIS_DB_PATH.exists():
        return None
    con = sqlite3.connect(market_db_uri(), uri=True)
    con.row_factory = sqlite3.Row
    return con


def latest_market_date_with_flow(con, asof_date):
    row = con.execute(
        """
        SELECT MAX(session_date) AS session_date
        FROM market_intraday_flow_signal
        WHERE session_date <= ?
        """,
        (asof_date,),
    ).fetchone()
    return row["session_date"] if row and row["session_date"] else asof_date


def latest_row_by_date(con, table, date_col, target_date):
    row = con.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE {date_col} = ?
        ORDER BY asof DESC
        LIMIT 1
        """,
        (target_date,),
    ).fetchone()
    return dict(row) if row else {}


def latest_rows_by_date(con, table, date_col, target_date):
    rows = con.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE {date_col} = ?
          AND asof = (
              SELECT MAX(asof)
              FROM {table}
              WHERE {date_col} = ?
          )
        ORDER BY asof DESC
        """,
        (target_date, target_date),
    ).fetchall()
    return [dict(row) for row in rows]


def load_market_v2_inputs(asof_date):
    try:
        con = connect_market_db()
    except Exception:
        return {}
    if con is None:
        return {}
    with con:
        effective_date = latest_market_date_with_flow(con, asof_date)
        latest_asof_row = con.execute(
            """
            SELECT MAX(asof) AS asof
            FROM market_intraday_state
            WHERE session_date = ?
            """,
            (effective_date,),
        ).fetchone()
        return {
            "requested_asof_date": asof_date,
            "effective_date": effective_date,
            "effective_asof": latest_asof_row["asof"] if latest_asof_row else None,
            "features": latest_row_by_date(con, "market_features_hourly", "asof_date", effective_date),
            "component": latest_row_by_date(con, "market_component_scores", "date(asof)", effective_date),
            "state": latest_row_by_date(con, "market_intraday_state", "session_date", effective_date),
            "breadth": latest_rows_by_date(con, "market_intraday_breadth", "session_date", effective_date),
            "index": latest_rows_by_date(con, "market_intraday_index_snapshot", "session_date", effective_date),
            "futures": latest_row_by_date(con, "market_intraday_futures_snapshot", "session_date", effective_date),
            "fx": latest_row_by_date(con, "market_intraday_fx_snapshot", "session_date", effective_date),
            "flows": latest_rows_by_date(con, "market_intraday_flow_signal", "session_date", effective_date),
        }


def pct(value):
    return None if value is None else value * 100


def index_by_name(rows):
    return {row.get("index_name"): row for row in rows}


def flow_by_code(rows):
    return {row.get("signal_code"): row for row in rows}


def clamp_score(value, maximum):
    return max(0, min(maximum, round(value, 1)))


def score_direction_axis(inputs):
    state = inputs.get("state", {})
    indexes = index_by_name(inputs.get("index", []))
    features = inputs.get("features", {})
    futures = inputs.get("futures", {})
    score = 0
    reasons = []
    direction_score = state.get("direction_score")
    if isinstance(direction_score, (int, float)):
        score += min(12, max(0, direction_score / 3 * 12))
    kospi = pct((indexes.get("KOSPI") or {}).get("change_pct"))
    kosdaq = pct((indexes.get("KOSDAQ") or {}).get("change_pct"))
    if kospi is not None and kospi > 0:
        score += 2
    if kosdaq is not None and kosdaq > 0:
        score += 2
    if features.get("kospi_20d_ret", 0) > 0 and features.get("kospi200_20d_ret", 0) > 0:
        score += 1.5
    if futures.get("change_pct") is not None and futures.get("change_pct") >= 0:
        score += 0.5
    reasons.append(f"KOSPI {fmt(kospi)}%, KOSDAQ {fmt(kosdaq)}%")
    reasons.append(f"KOSPI 20일 {fmt(pct(features.get('kospi_20d_ret')))}%, KOSDAQ 20일 {fmt(pct(features.get('kosdaq_20d_ret')))}%")
    reasons.append(f"선물 {fmt(pct(futures.get('change_pct')))}%")
    return clamp_score(score, 20), reasons


def score_breadth_axis(inputs):
    features = inputs.get("features", {})
    breadth_rows = inputs.get("breadth", [])
    score = 0
    reasons = []
    positive_ratios = [
        row.get("positive_ratio")
        for row in breadth_rows
        if isinstance(row.get("positive_ratio"), (int, float))
    ]
    avg_positive = sum(positive_ratios) / len(positive_ratios) if positive_ratios else None
    if avg_positive is not None:
        if avg_positive >= 0.75:
            score += 8
        elif avg_positive >= 0.6:
            score += 6
        elif avg_positive >= 0.5:
            score += 4
        else:
            score += 2
    adv_dec = features.get("adv_dec_ratio")
    if isinstance(adv_dec, (int, float)):
        if adv_dec >= 5:
            score += 4
        elif adv_dec >= 2:
            score += 3
        elif adv_dec >= 1:
            score += 2
    above20 = features.get("above_20dma_ratio")
    above60 = features.get("above_60dma_ratio")
    if isinstance(above20, (int, float)):
        score += 4 if above20 >= 0.55 else 2 if above20 >= 0.4 else 0
    if isinstance(above60, (int, float)):
        score += 3 if above60 >= 0.55 else 1 if above60 >= 0.4 else 0
    if features.get("new_high_count", 0) > features.get("new_low_count", 0):
        score += 1
    reasons.append(f"상승종목 평균비율 {fmt(pct(avg_positive))}%")
    reasons.append(f"20일선 위 {fmt(pct(above20))}%, 60일선 위 {fmt(pct(above60))}%")
    reasons.append(f"신고가 {fmt(features.get('new_high_count'))}, 신저가 {fmt(features.get('new_low_count'))}")
    return clamp_score(score, 20), reasons


def score_flow_axis(inputs):
    flows = flow_by_code(inputs.get("flows", []))
    score = 10
    reasons = []
    foreign = (flows.get("FOREIGNER_NET") or {}).get("metric_value")
    institution = (flows.get("INSTITUTION_NET") or {}).get("metric_value")
    program = (flows.get("PROGRAM_TOTAL_NET") or {}).get("metric_value")
    if isinstance(foreign, (int, float)):
        score += 3 if foreign > 3000 else 1 if foreign > 0 else -4 if foreign < -10000 else -2
    if isinstance(institution, (int, float)):
        score += 3 if institution > 3000 else 1 if institution > 0 else -2 if institution < -3000 else 0
    if isinstance(program, (int, float)):
        score += 3 if program > 3000 else 1 if program > 0 else -4 if program < -10000 else -2
    if not flows:
        score -= 4
        reasons.append("외국인/기관/프로그램 수급 없음")
    else:
        reasons.append(f"외국인 {fmt(foreign)}억원, 기관 {fmt(institution)}억원")
        reasons.append(f"프로그램 전체 {fmt(program)}억원")
    reasons.append("선물 수급은 가격 방향만 참고하고 투자주체별 수급은 추가 데이터가 필요함")
    return clamp_score(score, 20), reasons


def score_risk_axis(inputs, market_context):
    features = inputs.get("features", {})
    fx = inputs.get("fx", {})
    score = 14
    reasons = []
    fx_day = pct(fx.get("change_pct"))
    fx_20d = pct(features.get("usdkrw_20d_ret"))
    ktb3y = features.get("rate_ktb3y_20d_chg")
    vol = pct(features.get("realized_vol_20d"))
    if fx_day is not None and fx_day > 0.5:
        score -= 2
    if fx_20d is not None and fx_20d > 1:
        score -= 2
    if ktb3y is not None and ktb3y > 0.2:
        score -= 2
    if vol is not None and vol > 3:
        score -= 1
    if market_context.get("caution_bias"):
        score -= 1
    reasons.append(f"원달러 당일 {fmt(fx_day)}%, 20일 {fmt(fx_20d)}%")
    reasons.append(f"국고3년 20일 변화 {fmt(ktb3y)}%p, 20일 변동성 {fmt(vol)}%")
    if market_context.get("risk_headlines"):
        reasons.append("글로벌 이벤트/유가/금리 뉴스 경계 신호 존재")
    return clamp_score(score, 20), reasons


def score_style_axis(inputs):
    indexes = index_by_name(inputs.get("index", []))
    features = inputs.get("features", {})
    kospi = pct((indexes.get("KOSPI") or {}).get("change_pct"))
    kosdaq = pct((indexes.get("KOSDAQ") or {}).get("change_pct"))
    kospi200 = pct((indexes.get("KOSPI200") or {}).get("change_pct"))
    score = 5
    reasons = []
    if kosdaq is not None and kospi is not None and kosdaq > kospi:
        score += 2
    if kospi200 is not None and kospi is not None and kospi >= kospi200:
        score += 1
    if features.get("regime_3m_score") is not None:
        score += 1
    if features.get("kosdaq_60d_ret", 0) > 0 and features.get("kospi_60d_ret", 0) > 0:
        score += 1
    reasons.append(f"KOSDAQ {fmt(kosdaq)}% vs KOSPI {fmt(kospi)}%")
    reasons.append("중소형/성장 위험선호가 회복됐지만 수급 확인이 필요함")
    return clamp_score(score, 10), reasons


def score_data_quality_axis(inputs, asof_date):
    effective_date = inputs.get("effective_date")
    rows = []
    rows.extend(inputs.get("breadth", []))
    rows.extend(inputs.get("index", []))
    if inputs.get("futures"):
        rows.append(inputs["futures"])
    if inputs.get("fx"):
        rows.append(inputs["fx"])
    fallback_count = sum(1 for row in rows if row.get("is_fallback"))
    has_flow = bool(inputs.get("flows"))
    score = 10
    reasons = []
    if fallback_count:
        score -= min(3, fallback_count)
    if not has_flow:
        score -= 3
    if effective_date != asof_date and has_flow:
        reasons.append(f"{asof_date} 휴장/비거래일로 판단해 마지막 거래일 {effective_date} 기준으로 평가")
    if fallback_count:
        reasons.append(f"fallback 데이터 {fallback_count}건")
    if has_flow:
        reasons.append("마지막 거래일 외국인/기관/프로그램 수급 데이터 확인")
    else:
        reasons.append("수급 데이터 미확인")
    return clamp_score(score, 10), reasons


def step1_grade_from_score(score):
    for grade, low, high in STEP1_GRADE_BOUNDS:
        if low <= score <= high:
            return grade
    return 6 if score > 100 else 1


def step1_boundary_info(score, grade):
    for current, low, high in STEP1_GRADE_BOUNDS:
        if current != grade:
            continue
        if grade < 6 and high - score <= 3:
            return True, grade + 1, "상단 경계"
        if grade > 1 and score - low <= 3:
            return True, grade - 1, "하단 경계"
    return False, None, "중앙"


def display_step1_grade(grade, boundary_position=None):
    label = STEP1_GRADE_LABELS.get(grade, "미분류")
    if boundary_position in {"상단 경계", "하단 경계"}:
        suffix = "상단" if boundary_position == "상단 경계" else "하단"
        return f"{grade}등급 {label} {suffix}"
    return f"{grade}등급 {label}"


def build_step1_v2_assessment(market_risk, asof_date, market_context):
    inputs = load_market_v2_inputs(asof_date)
    if not inputs:
        return {}
    axes = []
    direction, direction_reasons = score_direction_axis(inputs)
    breadth, breadth_reasons = score_breadth_axis(inputs)
    flow, flow_reasons = score_flow_axis(inputs)
    risk, risk_reasons = score_risk_axis(inputs, market_context)
    style, style_reasons = score_style_axis(inputs)
    quality, quality_reasons = score_data_quality_axis(inputs, asof_date)
    axes.extend(
        [
            {"axis": "시장 방향성", "score": direction, "max_score": 20, "reasons": direction_reasons},
            {"axis": "시장 확산력", "score": breadth, "max_score": 20, "reasons": breadth_reasons},
            {"axis": "수급", "score": flow, "max_score": 20, "reasons": flow_reasons},
            {"axis": "변동성/리스크", "score": risk, "max_score": 20, "reasons": risk_reasons},
            {"axis": "시장 스타일", "score": style, "max_score": 10, "reasons": style_reasons},
            {"axis": "데이터 신뢰도", "score": quality, "max_score": 10, "reasons": quality_reasons},
        ]
    )
    total = clamp_score(sum(row["score"] for row in axes), 100)
    grade = step1_grade_from_score(total)
    is_boundary, adjacent_grade, boundary_position = step1_boundary_info(total, grade)
    conflict_boundary = (
        grade == 4
        and direction >= 16
        and breadth >= 14
        and (flow <= 8 or risk <= 8)
    )
    if conflict_boundary:
        is_boundary = True
        adjacent_grade = 5
        boundary_position = "상단 경계"
    return {
        "logic_version": STEP1_V2_LOGIC_VERSION,
        "requested_asof_date": asof_date,
        "effective_date": inputs.get("effective_date"),
        "effective_asof": inputs.get("effective_asof"),
        "legacy_rating": market_risk.get("rating"),
        "legacy_total_score": market_risk.get("total_score"),
        "legacy_risk_score": market_risk.get("risk_score"),
        "score": total,
        "grade": grade,
        "label": STEP1_GRADE_LABELS.get(grade),
        "display_rating": display_step1_grade(grade, boundary_position),
        "is_boundary": is_boundary,
        "adjacent_grade": adjacent_grade,
        "adjacent_label": STEP1_GRADE_LABELS.get(adjacent_grade),
        "boundary_position": boundary_position,
        "boundary_reason": (
            "방향성과 확산력은 5등급에 가깝지만 수급 또는 리스크가 약해 4등급 상단으로 분류"
            if conflict_boundary
            else None
        ),
        "axes": axes,
    }


def apply_step1_v2_assessment(market_risk, asof_date, market_context):
    updated = dict(market_risk)
    assessment = build_step1_v2_assessment(updated, asof_date, market_context)
    if not assessment:
        return updated
    updated["legacy_rating"] = updated.get("rating")
    updated["rating"] = assessment["display_rating"]
    updated["step1_v2"] = assessment
    updated["asof"] = assessment.get("effective_asof") or updated.get("asof")
    updated["action"] = build_market_action(updated)
    return updated


def refresh_market_risk_rating(market_risk):
    refreshed = dict(market_risk)
    rating = classify_market_rating(refreshed.get("total_score"), refreshed.get("risk_score"))
    refreshed["rating"] = rating
    refreshed["action"] = build_market_action(refreshed)
    return refreshed


def infer_market_risk(market_status):
    state = market_status.get("intraday_context", {}).get("state", {})
    breadth = market_status.get("intraday_context", {}).get("breadth", [])
    flows = market_status.get("intraday_context", {}).get("flow_signals", [])
    total_score = state.get("total_score")
    risk_score = state.get("risk_score")
    rating = classify_market_rating(total_score, risk_score)
    return {
        "rating": rating,
        "asof": market_status.get("asof"),
        "generated_at": market_status.get("generated_at"),
        "direction_label": state.get("direction_label"),
        "direction_score": state.get("direction_score"),
        "breadth_score": state.get("breadth_score"),
        "risk_score": risk_score,
        "total_score": total_score,
        "summary": state.get("summary_line"),
        "breadth": breadth,
        "flows": flows,
        "action": build_market_action({"rating": rating}),
    }


def market_grade(market_risk):
    step1 = market_risk.get("step1_v2") or {}
    grade = step1.get("grade")
    return grade if isinstance(grade, int) else None


def market_rating_text(market_risk):
    step1 = market_risk.get("step1_v2") or {}
    return step1.get("display_rating") or market_risk.get("rating")


def is_defensive_caution(market_risk):
    grade = market_grade(market_risk)
    if grade is not None:
        return grade <= 2
    return market_risk.get("rating") in {"Defensive Caution", "Cautious Watch"}


def is_constructive_watch(market_risk):
    grade = market_grade(market_risk)
    if grade is not None:
        return grade >= 5
    return market_risk.get("rating") == "Constructive Watch"


def is_neutral_grade(market_risk):
    grade = market_grade(market_risk)
    if grade is not None:
        return grade == 4
    return market_risk.get("rating") == "Neutral Watch"


def is_cautious_grade(market_risk):
    grade = market_grade(market_risk)
    if grade is not None:
        return grade == 3
    return market_risk.get("rating") == "Cautious Watch"


def build_market_action(market_risk):
    grade = market_grade(market_risk)
    if grade == 6:
        return "시장 위험선호가 매우 강하다. 다만 종목별 수급과 과열 여부를 확인해 주식 비중을 확대한다."
    if grade == 5:
        return "시장 흐름은 강세 우위다. 주식 후보는 추격매수보다 수급 확인 후 단계적 편입을 검토한다."
    if grade == 4:
        return "중립 관찰 구간이다. 주식은 선별 관찰과 소액 분할만 검토한다."
    if grade == 3:
        return "약한 경계 구간이다. ETF/현금성 자산을 우선하고 주식 신규 편입은 제한한다."
    rating = market_risk.get("rating") if isinstance(market_risk, dict) else str(market_risk)
    if rating == "Constructive Watch":
        return "시장 흐름은 강세 우위다. 주식 후보는 추격매수보다 수급 확인 후 단계적 편입을 검토한다."
    if rating == "Neutral Watch":
        return "중립 관찰 구간이다. 주식은 선별 관찰과 소액 분할만 검토한다."
    if rating == "Cautious Watch":
        return "약한 경계 구간이다. ETF/현금성 자산을 우선하고 주식 신규 편입은 제한한다."
    return "주식 추격매수보다 ETF/현금/방어자산 우선. 주식은 선별 관찰과 소액 분할만 검토."


def build_etf_strategy_reason(market_risk):
    grade = market_grade(market_risk)
    if grade is not None and (market_risk.get("step1_v2") or {}).get("is_boundary"):
        return "STEP1이 등급 경계 구간이므로 S6 방어 배분을 기본안으로 두고, 수급 개선 시 조건부 주식 편입안을 함께 제시한다."
    if grade is not None and grade <= 2:
        return "시장 위험 신호가 높아 위험자산 노출을 낮추는 S6 방어형 ETF 모델을 우선 적용한다."
    if grade is not None and grade == 3:
        return "시장은 완전한 위험 회피 구간은 아니지만 경계 신호가 있어 S6 방어 배분을 유지한다."
    if is_constructive_watch(market_risk):
        return "시장 강도는 우호적이나 수급 확인과 이벤트 리스크가 남아 있어 S6 방어 배분을 기본축으로 유지하고 주식 편입은 단계적으로 검토한다."
    return (
        "시장판단은 Neutral Watch로 위험 고조 단계는 아니지만, 아직 관찰이 필요한 구간이므로 "
        "주식 비중을 성급히 늘리지 않고 S6 방어 배분을 유지한다."
    )


def build_market_step_summary(market_risk):
    step1 = market_risk.get("step1_v2") or {}
    if step1.get("is_boundary"):
        return f"시장판단은 {market_rating_text(market_risk)}이다. 등급 경계 구간이므로 보수안과 조건부 공격안을 함께 검토한다."
    grade = market_grade(market_risk)
    if grade is not None and grade <= 2:
        return "시장 위험 신호가 높아 방어적 판단을 우선했다."
    if grade is not None and grade == 3:
        return "일부 지표가 약해진 경계 구간으로 판단했다. 공격적 비중 확대보다 방어적 확인이 필요하다."
    if is_constructive_watch(market_risk):
        return "시장 방향과 종목 확산은 강세다. 다만 수급 데이터 공백과 이벤트 리스크가 있어 강세 관찰 구간으로 판단했다."
    return "시장판단은 중립 관찰 구간이다. 위험이 높다고 보지는 않지만, 추격매수보다 확인 후 대응이 필요한 상태로 판단했다."


def build_market_step_conclusion(market_risk):
    step1 = market_risk.get("step1_v2") or {}
    if step1.get("is_boundary"):
        adjacent = step1.get("adjacent_grade")
        adjacent_label = STEP1_GRADE_LABELS.get(adjacent)
        return f"기본은 {market_rating_text(market_risk)} 기준 보수안이며, 수급 개선 시 {adjacent}등급 {adjacent_label} 기준 조건부 포트폴리오로 전환한다."
    grade = market_grade(market_risk)
    if grade is not None and grade <= 2:
        return "오늘은 공격적 주식 매수보다 방어형 자산과 현금성 자산을 우선한다."
    if grade is not None and grade == 3:
        return "오늘은 주식 신규 편입을 제한하고 방어 배분을 유지한다."
    if is_constructive_watch(market_risk):
        return "오늘은 주식 비중 확대를 검토할 수 있지만, 추격매수보다 수급 확인 후 단계적으로 접근한다."
    return "오늘은 주식 비중을 0%로 낮출 상황은 아니지만, 신규 매수는 관찰/소액 분할 중심으로 제한한다."


def build_etf_step_summary(market_risk):
    step1 = market_risk.get("step1_v2") or {}
    if step1.get("is_boundary"):
        return "STEP1이 경계 구간이므로 S6 중심 보수안과 주식 일부 편입 조건부안을 동시에 제시했다."
    grade = market_grade(market_risk)
    if grade is not None and grade <= 2:
        return "시장 위험이 높은 구간이므로 위험자산 편입을 줄이고 방어형 ETF 모델인 S6를 우선 적용했다."
    if grade is not None and grade == 3:
        return "경계 구간이므로 S6 ETF 배분을 방어축으로 유지했다."
    if is_constructive_watch(market_risk):
        return "시장 강도는 우호적이지만 이벤트 리스크와 수급 확인 필요성이 남아 있어 S6 ETF 배분을 기본축으로 유지했다."
    return "시장 위험이 높아서가 아니라 중립 관찰 구간이므로, 포트폴리오의 기본 방어축으로 S6 ETF 배분을 유지했다."


def build_etf_step_conclusion(market_risk):
    step1 = market_risk.get("step1_v2") or {}
    if step1.get("is_boundary"):
        return "S6를 기본축으로 유지하되 수급 개선 여부에 따라 주식 편입안을 병행 검토한다."
    grade = market_grade(market_risk)
    if grade is not None and grade <= 2:
        return "포트폴리오의 중심은 S6 방어 배분으로 두는 것이 합리적이다."
    if grade is not None and grade == 3:
        return "S6는 경계 구간에서 변동성을 낮추는 기준 배분으로 해석한다."
    if is_constructive_watch(market_risk):
        return "S6는 강세를 부정하는 신호가 아니라, 주식 편입을 단계적으로 늘리기 전 유지하는 기준 배분이다."
    return "S6는 위험 회피 신호가 아니라, 중립 구간에서 현금성/방어자산 비중을 유지하는 기준 배분으로 해석한다."


def build_final_step_summary(market_risk):
    if (market_risk.get("step1_v2") or {}).get("is_boundary"):
        return "시장 방향성과 확산력은 우호적이나 수급과 리스크가 엇갈려 보수안과 조건부 공격안을 함께 제시하는 것이 결론이다."
    if is_constructive_watch(market_risk):
        return "시장 강도는 우호적이지만 ETF 모델, 주식 후보, 수급 확인을 종합하면 단계적 주식 편입과 S6 기준 배분 병행이 결론이다."
    if is_neutral_grade(market_risk):
        return "시장 위험, ETF 모델, 주식 후보, 수급 확인을 종합하면 오늘은 S6 기준 배분을 유지하며 주식은 제한적으로 검토하는 결론이다."
    return "시장 위험, ETF 모델, 주식 후보, 수급 확인을 종합하면 오늘은 방어형 ETF 중심 포트폴리오가 결론이다."


def build_final_step_conclusion(market_risk):
    if (market_risk.get("step1_v2") or {}).get("is_boundary"):
        return "최종 결론은 보수안을 기본 포트폴리오로 채택하고, 외국인/프로그램 수급 개선 시 조건부 공격안으로 전환하는 것이다."
    if is_constructive_watch(market_risk):
        return "최종 결론은 S6 기준 배분을 유지하되, 주식은 수급 개선 종목부터 단계적 편입을 검토하는 것이다."
    if is_neutral_grade(market_risk):
        return "최종 결론은 S6 기준 배분 유지, 주식은 관찰/소액 분할 검토이다."
    return "최종 결론은 ETF 방어 배분 우선, 주식은 관찰/소액 분할 검토이다."


def build_step6_first_detail(market_risk):
    if (market_risk.get("step1_v2") or {}).get("is_boundary"):
        return "ETF는 S6 기준 배분을 기본안으로 두고, 주식은 조건부 편입안으로 별도 관리한다."
    if is_constructive_watch(market_risk):
        return "ETF는 S6 기준 배분을 유지하되, 주식 편입 가능성을 함께 검토한다."
    return "ETF는 S6 방어 배분을 중심으로 한다."


def build_stock_exposure_guidance(market_risk):
    if (market_risk.get("step1_v2") or {}).get("is_boundary"):
        return "기본안은 주식 10~20% 이내 제한, 조건부안은 수급 개선 확인 시 20~35%까지 단계적 편입 검토."
    if is_constructive_watch(market_risk):
        return "오늘 주식 비중은 0% 고정이 아니라 수급이 확인되는 종목부터 단계적 편입을 검토."
    if is_neutral_grade(market_risk):
        return "오늘 주식 비중은 0% 고정이 아니라 최대 10~20% 이내 관찰/소액 분할 검토."
    return "오늘 주식 신규 편입은 제한하고 방어 배분을 우선."


def build_final_process_result(market_risk):
    if (market_risk.get("step1_v2") or {}).get("is_boundary"):
        return "보수안 기본 + 조건부 공격안 병행"
    if is_constructive_watch(market_risk):
        return "S6 기준 배분 유지 + 주식 단계적 편입 검토"
    if is_neutral_grade(market_risk):
        return "S6 기준 배분 유지, 주식은 제한 비중"
    return "ETF 방어 배분 중심, 주식은 제한 비중"


def build_stock_candidate_step_conclusion(market_risk):
    if (market_risk.get("step1_v2") or {}).get("is_boundary"):
        return "주식 후보는 유지하되 기본안에서는 제한 비중, 조건부안에서는 수급 개선 종목부터 단계적 편입한다."
    if is_constructive_watch(market_risk):
        return "주식 후보는 유지하고, 수급과 가격 조건이 개선되는 종목부터 단계적 편입을 검토한다."
    if is_neutral_grade(market_risk):
        return "주식 후보는 유지하되 오늘 전체 주식 비중은 최대 10~20% 이내로 제한한다."
    return "주식 후보는 유지하되 신규 편입은 제한하고 관찰 중심으로 관리한다."


def build_step2_portfolio_scenarios(market_risk):
    step1 = market_risk.get("step1_v2") or {}
    grade = step1.get("grade") or market_grade(market_risk)
    scenarios = []
    if step1.get("is_boundary") and grade == 4 and step1.get("adjacent_grade") == 5:
        scenarios.append(
            {
                "scenario": "A",
                "name": "보수안",
                "basis": "4등급 중립 상단",
                "etf_policy": "S6_DEFENSIVE_V1 중심 유지",
                "stock_policy": "주식 후보는 관찰/소액분할 중심",
                "stock_weight_range_pct": "10~20",
                "cash_or_defensive_weight": "높게 유지",
                "activation_condition": "기본 적용",
            }
        )
        scenarios.append(
            {
                "scenario": "B",
                "name": "조건부 공격안",
                "basis": "5등급 우호적 관찰 하단",
                "etf_policy": "S6 유지 + 성장/모멘텀 노출 일부 허용",
                "stock_policy": "수급 개선 종목부터 단계적 편입",
                "stock_weight_range_pct": "20~35",
                "cash_or_defensive_weight": "일부 축소",
                "activation_condition": "외국인/프로그램 매도 완화 또는 기관·외국인 동시 개선 확인",
            }
        )
        return scenarios
    if grade and grade <= 2:
        return [
            {
                "scenario": "A",
                "name": "방어안",
                "basis": f"{grade}등급 {STEP1_GRADE_LABELS.get(grade)}",
                "etf_policy": "S6_DEFENSIVE_V1 방어 배분 우선",
                "stock_policy": "신규 주식 편입 제한",
                "stock_weight_range_pct": "0~10",
                "cash_or_defensive_weight": "최대화",
                "activation_condition": "기본 적용",
            }
        ]
    if grade == 3:
        return [
            {
                "scenario": "A",
                "name": "주의 관찰안",
                "basis": "3등급 주의 관찰",
                "etf_policy": "S6_DEFENSIVE_V1 중심",
                "stock_policy": "관찰 중심, 소액 편입만 예외 허용",
                "stock_weight_range_pct": "0~15",
                "cash_or_defensive_weight": "높게 유지",
                "activation_condition": "기본 적용",
            }
        ]
    if grade == 5:
        return [
            {
                "scenario": "A",
                "name": "우호적 관찰안",
                "basis": "5등급 우호적 관찰",
                "etf_policy": "S6 기준 배분 유지",
                "stock_policy": "수급과 가격 안정 종목부터 단계적 편입",
                "stock_weight_range_pct": "20~40",
                "cash_or_defensive_weight": "중립 이하로 축소",
                "activation_condition": "기본 적용",
            }
        ]
    if grade == 6:
        return [
            {
                "scenario": "A",
                "name": "적극 위험선호안",
                "basis": "6등급 적극 위험선호",
                "etf_policy": "방어 ETF 비중 축소",
                "stock_policy": "주식 전략 모델 비중 확대",
                "stock_weight_range_pct": "35~60",
                "cash_or_defensive_weight": "낮게 유지",
                "activation_condition": "과열/수급 훼손이 없을 때 적용",
            }
        ]
    return [
        {
            "scenario": "A",
            "name": "중립안",
            "basis": "4등급 중립",
            "etf_policy": "S6_DEFENSIVE_V1 기준 배분 유지",
            "stock_policy": "주식 후보 관찰/소액분할 검토",
            "stock_weight_range_pct": "10~20",
            "cash_or_defensive_weight": "중립 이상 유지",
            "activation_condition": "기본 적용",
        }
    ]


def attach_live_snapshot(stocks, asof_date):
    if os.getenv("QUANTANALYSIS_DISABLE_KIWOOM_LIVE") != "1":
        return attach_kiwoom_live_snapshot(stocks, asof_date)
    return attach_backup_live_snapshot(stocks, asof_date, "kiwoom_disabled")


def attach_kiwoom_live_snapshot(stocks, asof_date):
    fetched_at = datetime.now(KST).isoformat(timespec="milliseconds")
    historical_quotes = load_price_db_quotes(stocks, asof_date)
    try:
        token, expires_dt = kiwoom_access_token()
    except Exception as exc:
        return attach_backup_live_snapshot(
            stocks,
            asof_date,
            "kiwoom_token_failed",
            [str(exc)],
            historical_quotes=historical_quotes,
        )

    merged = []
    errors = []
    success_count = 0
    for stock in stocks:
        item = dict(stock)
        ticker = stock["ticker"]
        try:
            quote = historical_quotes.get(ticker)
            quote_source = "price.db.prices_daily"
            if quote is None:
                quote = request_kiwoom_quote(token, ticker)
                quote_source = f"kiwoom_rest_{KIWOOM_QUOTE_API_ID}"
                time.sleep(0.2)
            flows = request_kiwoom_investor_amount(token, ticker, asof_date)
            item["live_quote"] = {
                **quote,
                **flows,
                "source": f"{quote_source}+kiwoom_rest_{KIWOOM_INVESTOR_API_ID}",
                "asof_date": asof_date,
                "fetched_at": fetched_at,
            }
            success_count += 1
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
            item["live_quote"] = None
        merged.append(item)
        time.sleep(0.2)

    if success_count < len(stocks):
        backup = attach_backup_live_snapshot(
            stocks,
            asof_date,
            "kiwoom_partial_failed",
            errors,
            historical_quotes=historical_quotes,
        )
        backup_by_ticker = {
            item.get("ticker"): item.get("live_quote")
            for item in backup.get("items", [])
            if item.get("live_quote")
        }
        for item in merged:
            if item.get("live_quote") is None and backup_by_ticker.get(item.get("ticker")):
                item["live_quote"] = backup_by_ticker[item["ticker"]]

    complete_count = sum(
        1
        for item in merged
        if item.get("live_quote")
        and item["live_quote"].get("price") is not None
        and item["live_quote"].get("foreign_net_억원") is not None
        and item["live_quote"].get("institution_net_억원") is not None
    )
    attached_count = sum(1 for item in merged if item.get("live_quote"))

    if complete_count == len(stocks):
        status = "ok"
    elif attached_count:
        status = "partial"
    else:
        fallback = attach_backup_live_snapshot(
            stocks,
            asof_date,
            "kiwoom_request_failed",
            errors,
            historical_quotes=historical_quotes,
        )
        fallback["token_expires_dt"] = expires_dt
        return fallback

    sources = sorted(
        {
            item["live_quote"].get("source")
            for item in merged
            if item.get("live_quote") and item["live_quote"].get("source")
        }
    )

    return {
        "status": status,
        "source": "+".join(sources)
        if sources
        else (
            "price.db.prices_daily+kiwoom_rest_ka10059"
            if historical_quotes
            else f"kiwoom_rest_{KIWOOM_QUOTE_API_ID}+{KIWOOM_INVESTOR_API_ID}"
        ),
        "asof_date": asof_date,
        "fetched_at": fetched_at,
        "token_expires_dt": expires_dt,
        "success_count": complete_count,
        "error_count": len(errors),
        "errors": errors[:10],
        "items": merged,
    }


def attach_static_snapshot(stocks, asof_date, reason):
    if asof_date != "2026-05-18":
        return {
            "status": "not_loaded",
            "source": None,
            "asof_date": asof_date,
            "reason": reason,
            "items": stocks,
        }
    snapshot = KIWOOM_SNAPSHOT_20260518
    by_code = snapshot["items"]
    merged = []
    for stock in stocks:
        item = dict(stock)
        item["live_quote"] = by_code.get(stock["ticker"])
        merged.append(item)
    return {
        "status": snapshot["status"],
        "source": snapshot["source"],
        "asof_date": snapshot["asof_date"],
        "reason": reason,
        "items": merged,
    }


def load_historical_portfolio_snapshot(asof_date):
    ymd = re.sub(r"[^0-9]", "", asof_date)
    paths = sorted(OUTPUT_DIR.glob(f"investment_portfolio_{ymd}_*.json"), reverse=True)
    for path in paths:
        try:
            report = read_json(path)
        except Exception:
            continue
        market_asof = str(report.get("market_risk", {}).get("asof") or "")
        if report.get("as_of_date") == asof_date and market_asof.startswith(asof_date):
            return report
    return None


def build_report(asof_date):
    market_status = read_json(MARKET_STATUS)
    market_context = read_json(MARKET_CONTEXT)
    e_policy = read_json(E_SERIES_POLICY)
    s6 = load_s6_holdings()
    stocks = stock_model_summary()
    live = attach_live_snapshot(stocks, asof_date)
    historical_snapshot = load_historical_portfolio_snapshot(asof_date)
    market_risk = (
        refresh_market_risk_rating(historical_snapshot.get("market_risk", {}))
        if historical_snapshot
        else infer_market_risk(market_status)
    )
    market_context_for_report = historical_snapshot.get("market_news_context", {}) if historical_snapshot else market_context
    market_risk = apply_step1_v2_assessment(market_risk, asof_date, market_context_for_report)
    step_details = build_step_details(market_risk, market_context_for_report, s6, e_policy, live)
    previous_context = load_previous_model_explanation_context()
    model_concentration = build_model_concentration_explanation(
        live,
        market_risk,
        previous_context,
        market_context_for_report,
    )

    return {
        "page": "투자 포트폴리오",
        "as_of_date": asof_date,
        "generated_at": datetime.now(KST).isoformat(timespec="milliseconds"),
        "run_session": classify_session(datetime.now(KST)),
        "source_thread": "QuantAnalysis",
        "publishing_rule": "redbot.co.kr 반영은 QuantService 작업요청서를 통해서만 수행",
        "market_risk": market_risk,
        "market_news_context": {
            "fetched_at": market_context_for_report.get("fetched_at"),
            "caution_bias": market_context_for_report.get("caution_bias"),
            "risk_headlines": market_context_for_report.get("risk_headlines", [])[:5],
            "snapshot_source": "historical_portfolio_snapshot" if historical_snapshot else "latest_market_context",
        },
        "etf_strategy": {
            "selected_model": "S6_DEFENSIVE_V1",
            "reason": build_etf_strategy_reason(market_risk),
            "portfolio_scenarios": build_step2_portfolio_scenarios(market_risk),
            "s6_allocation": s6,
            "e_series_reference": {
                "as_of_date": e_policy.get("as_of_date"),
                "strategy_model_code": e_policy.get("strategy_model_code"),
                "active_primary_shadow_policy": e_policy.get("active_primary_shadow_policy"),
                "public_recommendation_allowed": e_policy.get("governance", {}).get("public_recommendation_allowed"),
                "admin_display_allowed": e_policy.get("governance", {}).get("admin_display_allowed"),
                "use_policy": "공개 추천이 아닌 ETF 전략 참고 정보로만 사용.",
            },
        },
        "stock_strategy": {
            "exposure_guidance": build_stock_exposure_guidance(market_risk),
            "execution_rule": "외국인 매도와 당일 급락/급등 종목은 추격 금지. 기관/외국인 수급이 동시 개선되는 종목만 후보 유지.",
            "live_data": {
                "status": live.get("status"),
                "source": live.get("source"),
                "asof_date": live.get("asof_date"),
                "fetched_at": live.get("fetched_at"),
                "success_count": live.get("success_count"),
                "error_count": live.get("error_count"),
                "errors": live.get("errors", []),
            },
            "candidates": live["items"],
        },
        "process_steps": [
            {"step": 1, "name": "시장 위험 판단", "result": market_rating_text(market_risk)},
            {"step": 2, "name": "ETF 전략 선택", "result": build_final_process_result(market_risk)},
            {"step": 3, "name": "E-series ETF 참고", "result": "shadow/admin reference, 공개 추천 제외"},
            {"step": 4, "name": "주식 모델 후보 점검", "result": "S2/S3/T/I 중복 선정 종목 중심"},
            {"step": 5, "name": "정성 분석과 최신 수급 확인", "result": "Kiwoom 조회 기준으로 추격매수 제한"},
            {"step": 6, "name": "최종 포트폴리오 판단", "result": build_final_process_result(market_risk)},
        ],
        "step_details": step_details,
        "model_concentration_explanation": model_concentration,
        "disclaimer": "본 자료는 Quant 모델 기반 투자정보 정리이며 매수/매도 권유가 아니다.",
    }


def load_previous_model_explanation_context():
    if not DB_PATH.exists():
        return {}
    try:
        with sqlite3.connect(DB_PATH) as con:
            row = con.execute(
                """
                SELECT r.market_rating, e.model_id_counts_json, e.decision_counts_json,
                       e.top_models_json, e.explanation_fingerprint, e.narrative_focus
                FROM portfolio_model_explanations e
                JOIN portfolio_runs r ON r.run_id = e.run_id
                ORDER BY e.run_id DESC
                LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    return {
        "market_rating": row[0],
        "model_id_counts": safe_json(row[1], {}),
        "decision_counts": safe_json(row[2], {}),
        "top_models": safe_json(row[3], []),
        "explanation_fingerprint": row[4],
        "narrative_focus": row[5],
    }


def safe_json(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def build_model_concentration_explanation(live, market_risk, previous_context=None, market_context=None):
    previous_context = previous_context or {}
    market_context = market_context or {}
    candidates = live.get("items", [])
    model_counts = Counter()
    family_counts = Counter()
    decision_counts = Counter()
    overlap_rows = []
    negative_flow_count = 0
    large_move_count = 0
    for row in candidates:
        model_ids = row.get("model_ids") or row.get("model_groups", [])
        model_groups = row.get("model_groups", [])
        model_counts.update(model_ids)
        family_counts.update(model_groups)
        decision_counts.update([row.get("decision", "미정")])
        live_quote = row.get("live_quote") or {}
        if (live_quote.get("foreign_net_억원") or 0) < 0:
            negative_flow_count += 1
        if abs(live_quote.get("change_pct") or 0) >= 3:
            large_move_count += 1
        if len(model_ids) >= 2:
            overlap_rows.append(
                {
                    "ticker": row.get("ticker"),
                    "name": row.get("name"),
                    "model_ids": model_ids,
                    "model_groups": model_groups,
                    "decision": row.get("decision"),
                }
            )

    total = len(candidates)
    top_models = model_counts.most_common(4)
    top_model_names = [name for name, _count in top_models]
    top_model_text = ", ".join(top_model_names) if top_model_names else "특정 모델 없음"
    concentration_ratio = round(top_models[0][1] / total * 100, 1) if total and top_models else 0
    signal_families = Counter(
        MODEL_ROLE_DESCRIPTIONS.get(model, {}).get("signal_family", "other")
        for model in model_counts
    )

    if {"I-STOCK-STRONG-RSI-V01", "S2", "S2_PIT_V01"} & set(top_model_names):
        section_title = f"왜 {top_model_text} 후보가 많이 나왔나"
    elif top_model_names:
        section_title = f"오늘 후보가 많이 몰린 모델: {top_model_text}"
    else:
        section_title = "오늘 후보 모델 분포 해석"

    if not top_models:
        summary = "오늘 후보 데이터가 충분하지 않아 특정 모델 쏠림을 판단하기 어렵다."
    elif concentration_ratio >= 50:
        summary = f"오늘 후보 {total}개 중 가장 많이 등장한 모델은 {top_models[0][0]}이며, 후보의 {concentration_ratio}%에 포함됐다. 이는 해당 모델의 신호가 오늘 후보군 형성에 큰 영향을 줬다는 뜻이다."
    else:
        summary = f"오늘 후보 {total}개는 {top_model_text} 등 여러 모델에 분산되어 있다. 특정 모델 하나의 신호보다 복수 모델의 교차 확인이 더 중요한 날이다."

    model_roles = []
    for model, count in top_models:
        meta = MODEL_ROLE_DESCRIPTIONS.get(
            model,
            {
                "plain_name": "기타 후보 선별 모델",
                "description": "해당 모델의 세부 성격은 현재 설명 사전에 없으므로 후보 분포와 실제 수급으로 보조 해석한다.",
            },
        )
        model_roles.append(
            {
                "model": model,
                "plain_name": meta["plain_name"],
                "description": meta["description"],
                "candidate_count": count,
                "candidate_ratio_pct": round(count / total * 100, 1) if total else 0,
            }
        )

    explanation_fingerprint = make_explanation_fingerprint(
        market_risk=market_risk,
        top_models=top_models,
        decision_counts=decision_counts,
        negative_flow_count=negative_flow_count,
        large_move_count=large_move_count,
        total=total,
    )
    narrative_focus = choose_narrative_focus(
        market_risk=market_risk,
        top_models=top_model_names,
        decision_counts=decision_counts,
        negative_flow_count=negative_flow_count,
        large_move_count=large_move_count,
        total=total,
        previous_context=previous_context,
        current_fingerprint=explanation_fingerprint,
    )
    summary = build_dynamic_summary(
        total=total,
        top_models=top_models,
        concentration_ratio=concentration_ratio,
        narrative_focus=narrative_focus,
        market_risk=market_risk,
        negative_flow_count=negative_flow_count,
        large_move_count=large_move_count,
    )
    why_now = build_dynamic_why_now(
        market_risk=market_risk,
        top_models=top_model_names,
        signal_families=signal_families,
        negative_flow_count=negative_flow_count,
        large_move_count=large_move_count,
        total=total,
        narrative_focus=narrative_focus,
    )
    interpretation = build_dynamic_interpretation(
        market_risk=market_risk,
        top_models=top_model_names,
        decision_counts=decision_counts,
        total=total,
    )
    conclusion = build_dynamic_model_conclusion(market_risk, top_model_names, decision_counts, narrative_focus)

    base = {
        "section_title": section_title,
        "placement": "단계별 상세 설명 다음, ETF 전략 섹션 이전",
        "summary": summary,
        "model_roles": model_roles,
        "why_now": why_now,
        "interpretation": interpretation,
        "model_group_counts": dict(family_counts),
        "model_id_counts": dict(model_counts),
        "decision_counts": dict(decision_counts),
        "top_models": [{"model": model, "count": count} for model, count in top_models],
        "concentration_ratio_pct": concentration_ratio,
        "narrative_focus": narrative_focus,
        "explanation_fingerprint": explanation_fingerprint,
        "previous_context": previous_context,
        "overlap_candidates": overlap_rows,
        "conclusion": conclusion,
        "generation_method": "rule_based_dynamic",
        "generation_model": None,
        "generation_status": "fallback_not_needed",
    }
    return apply_gemini_model_explanation(
        base_explanation=base,
        live=live,
        market_risk=market_risk,
        market_context=market_context,
        previous_context=previous_context,
    )


def apply_gemini_model_explanation(*, base_explanation, live, market_risk, market_context, previous_context):
    if os.getenv("QUANTANALYSIS_DISABLE_GEMINI", "").lower() in {"1", "true", "yes"}:
        base_explanation["generation_status"] = "disabled"
        return base_explanation
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        base_explanation["generation_status"] = "missing_api_key"
        return base_explanation

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = build_gemini_explanation_prompt(
        base_explanation=base_explanation,
        live=live,
        market_risk=market_risk,
        market_context=market_context,
        previous_context=previous_context,
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.65,
            "responseMimeType": "application/json",
        },
    }
    try:
        response = requests.post(
            url,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        generated = json.loads(text)
        merged = dict(base_explanation)
        for key in ["section_title", "summary", "why_now", "interpretation", "conclusion", "narrative_focus"]:
            if generated.get(key):
                merged[key] = generated[key]
        merged["generation_method"] = "gemini"
        merged["generation_model"] = model
        merged["generation_status"] = "ok"
        merged["gemini_raw"] = generated
        return merged
    except Exception as exc:
        fallback = dict(base_explanation)
        fallback["generation_status"] = f"fallback:{type(exc).__name__}:{str(exc)[:160]}"
        return fallback


def build_gemini_explanation_prompt(*, base_explanation, live, market_risk, market_context, previous_context):
    candidates = []
    for row in live.get("items", []):
        candidates.append(
            {
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "model_ids": row.get("model_ids", []),
                "model_groups": row.get("model_groups", []),
                "decision": row.get("decision"),
                "return_from_selection_pct": row.get("return_from_selection_pct"),
                "qualitative_summary": row.get("qualitative_summary"),
                "live_quote": row.get("live_quote"),
            }
        )
    source = {
        "market_risk": {
            "rating": market_risk.get("rating"),
            "direction_label": market_risk.get("direction_label"),
            "breadth_score": market_risk.get("breadth_score"),
            "risk_score": market_risk.get("risk_score"),
            "total_score": market_risk.get("total_score"),
            "summary": market_risk.get("summary"),
            "flows": market_risk.get("flows", []),
            "breadth": market_risk.get("breadth", []),
        },
        "market_news_context": {
            "caution_bias": market_context.get("caution_bias"),
            "risk_headlines": market_context.get("risk_headlines", [])[:5],
        },
        "model_distribution": {
            "top_models": base_explanation.get("top_models"),
            "model_id_counts": base_explanation.get("model_id_counts"),
            "decision_counts": base_explanation.get("decision_counts"),
            "concentration_ratio_pct": base_explanation.get("concentration_ratio_pct"),
            "overlap_candidates": base_explanation.get("overlap_candidates"),
        },
        "model_roles": base_explanation.get("model_roles"),
        "candidates": candidates,
        "previous_explanation_context": previous_context,
    }
    return (
        "너는 REDBOT Quant 투자분석 해설 작성자다.\n"
        "아래 원천 데이터를 바탕으로 이번 실행에서 왜 이런 모델 분포와 종목 후보가 나왔는지 한국어로 새롭게 설명하라.\n"
        "중요 원칙:\n"
        "- 매수/매도 권유처럼 쓰지 말 것.\n"
        "- 고정 템플릿처럼 반복하지 말 것. 직전 설명과 같은 초점이면 다른 관점으로 쓸 것.\n"
        "- 시장상황, 모델 성격, 후보 종목의 가격/수급/판단 분포를 함께 엮어서 설명할 것.\n"
        "- 과장하지 말고, 입력 데이터에 없는 사실을 만들지 말 것.\n"
        "- 투자 초보자도 이해할 수 있게 쓰되, 너무 일반론으로 흐르지 말 것.\n"
        "- section_title은 실제 많이 나온 모델과 오늘 핵심 이슈가 드러나게 작성할 것.\n"
        "- why_now는 3~5개 문장 배열, interpretation은 3~5개 문장 배열로 작성할 것.\n"
        "반드시 아래 JSON 형식만 반환하라.\n"
        "{\n"
        '  "section_title": "...",\n'
        '  "summary": "...",\n'
        '  "why_now": ["...", "..."],\n'
        '  "interpretation": ["...", "..."],\n'
        '  "conclusion": "...",\n'
        '  "narrative_focus": "market_shift|model_shift|supply_risk|price_volatility|execution_filter|candidate_quality|other"\n'
        "}\n\n"
        "원천 데이터:\n"
        f"{json.dumps(source, ensure_ascii=False, indent=2)}"
    )


def make_explanation_fingerprint(*, market_risk, top_models, decision_counts, negative_flow_count, large_move_count, total):
    payload = {
        "market_rating": market_risk.get("rating"),
        "direction_label": market_risk.get("direction_label"),
        "top_models": top_models[:3],
        "decision_counts": dict(decision_counts),
        "negative_flow_count": negative_flow_count,
        "large_move_count": large_move_count,
        "total": total,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def choose_narrative_focus(*, market_risk, top_models, decision_counts, negative_flow_count, large_move_count, total, previous_context, current_fingerprint):
    previous_fingerprint = previous_context.get("explanation_fingerprint")
    previous_focus = previous_context.get("narrative_focus")
    current_top = top_models[:3]
    previous_top = [row.get("model") for row in previous_context.get("top_models", [])[:3] if isinstance(row, dict)]
    changed_models = current_top != previous_top
    changed_market = market_risk.get("rating") != previous_context.get("market_rating")
    if changed_market:
        return "market_shift"
    if changed_models:
        return "model_shift"
    if total and negative_flow_count / total >= 0.7:
        return "supply_risk"
    if total and large_move_count / total >= 0.4:
        return "price_volatility"
    if current_fingerprint == previous_fingerprint:
        order = ["model_concentration", "execution_filter", "risk_control", "candidate_quality"]
        if previous_focus in order:
            return order[(order.index(previous_focus) + 1) % len(order)]
        return "execution_filter"
    return "candidate_quality"


def build_dynamic_summary(*, total, top_models, concentration_ratio, narrative_focus, market_risk, negative_flow_count, large_move_count):
    if not top_models:
        return "오늘 후보 데이터가 충분하지 않아 특정 모델 쏠림을 판단하기 어렵다."
    top_name, top_count = top_models[0]
    if narrative_focus == "market_shift":
        return f"오늘 설명의 핵심은 시장판단 변화다. 시장이 {market_risk.get('rating')}로 분류되면서 후보 {total}개 중 {top_name} 신호가 {top_count}개로 가장 많이 남았다."
    if narrative_focus == "model_shift":
        return f"오늘은 후보를 이끈 모델 조합이 달라졌다. 후보 {total}개 중 {top_name}이 {top_count}개로 가장 많아, 이 모델의 조건이 현재 후보군을 주도했다."
    if narrative_focus == "supply_risk":
        return f"오늘 후보 {total}개 중 외국인 순매도 종목이 {negative_flow_count}개라 모델 선정 이후에도 수급 리스크를 우선 해석해야 한다."
    if narrative_focus == "price_volatility":
        return f"오늘 후보 {total}개 중 당일 3% 이상 움직인 종목이 {large_move_count}개라, 모델 신호보다 진입 가격과 추격매수 위험이 핵심 변수다."
    if narrative_focus == "execution_filter":
        return f"오늘 후보 {total}개는 모델 신호보다 실행 필터가 더 중요하다. 가장 많이 등장한 {top_name}도 최종 매수 신호가 아니라 후보 검증 출발점이다."
    if concentration_ratio >= 50:
        return f"오늘 후보 {total}개 중 가장 많이 등장한 모델은 {top_name}이며, 후보의 {concentration_ratio}%에 포함됐다. 이는 해당 모델의 신호가 오늘 후보군 형성에 큰 영향을 줬다는 뜻이다."
    return f"오늘 후보 {total}개는 여러 모델에 분산되어 있다. 특정 모델 하나의 신호보다 복수 모델의 교차 확인이 더 중요한 날이다."


def build_dynamic_why_now(*, market_risk, top_models, signal_families, negative_flow_count, large_move_count, total, narrative_focus):
    rating = market_risk.get("rating")
    breadth_score = market_risk.get("breadth_score")
    why = []
    if narrative_focus == "model_shift":
        why.append("직전 실행과 비교해 상위 모델 조합이 달라졌기 때문에, 오늘 설명은 어떤 모델이 새로 후보를 주도했는지에 초점을 둔다.")
    if narrative_focus == "market_shift":
        why.append("직전 실행과 비교해 시장판단이 달라졌기 때문에, 같은 종목이라도 포트폴리오 해석이 달라질 수 있다.")
    if rating == "Defensive Caution":
        why.append("시장판단이 Defensive Caution이므로 공격적 모멘텀보다 방어력, 실적, 가격 버팀 신호가 있는 종목이 후보에 남기 쉽다.")
    elif rating:
        why.append(f"시장판단이 {rating}이므로 모델 분포는 위험자산 선호와 방어 신호를 함께 확인하는 방식으로 해석한다.")
    if isinstance(breadth_score, (int, float)) and breadth_score < -1:
        why.append(f"시장 확산력 점수({breadth_score})가 낮아 전체 종목이 함께 오르는 장이 아니며, 일부 강한 종목만 모델을 통과했다.")
    if signal_families.get("price_strength") and (signal_families.get("fundamental_defensive") or signal_families.get("pit_fundamental")):
        why.append("가격 강도 모델과 펀더멘털 모델이 동시에 많이 등장해, 단순 급등주보다 가격 버팀과 실적 기반이 함께 확인된 종목이 많다.")
    elif signal_families.get("trend") or signal_families.get("theme_transition"):
        why.append("추세 또는 테마 전환형 모델 비중이 있어, 일부 종목은 방어력보다 추세 지속 가능성 때문에 후보에 포함됐다.")
    if total and narrative_focus == "supply_risk":
        why.append(f"후보 {total}개 중 외국인 순매도 종목이 {negative_flow_count}개로 많아, 모델 점수보다 수급 확인이 우선되는 구간이다.")
    elif total and narrative_focus == "price_volatility":
        why.append(f"후보 {total}개 중 당일 3% 이상 움직인 종목이 {large_move_count}개로 많아, 매수 타이밍을 보수적으로 잡아야 한다.")
    elif total:
        why.append(f"후보 {total}개 중 외국인 순매도가 확인된 종목은 {negative_flow_count}개, 당일 3% 이상 움직인 종목은 {large_move_count}개라 실행 판단은 보수적으로 제한했다.")
    if top_models:
        why.append(f"이번 설명은 실제 후보에 많이 등장한 모델({', '.join(top_models[:3])})을 기준으로 자동 생성됐다.")
    return why


def build_dynamic_interpretation(*, market_risk, top_models, decision_counts, total):
    interpretation = []
    if top_models:
        interpretation.append("많이 등장한 모델은 오늘 후보군을 만든 주된 필터로 해석한다.")
    interpretation.append("여러 모델에 동시에 선정된 종목은 관심 우선순위가 높지만, 그 자체가 즉시 매수 신호는 아니다.")
    if decision_counts:
        parts = [f"{key} {value}개" for key, value in decision_counts.items()]
        interpretation.append(f"현재 실행 판단은 {', '.join(parts)}로 나뉘며, 모델 선정 이후에도 가격/수급 조건으로 한 번 더 걸렀다.")
    if market_risk.get("rating") == "Defensive Caution":
        interpretation.append("시장판단이 Defensive Caution이면 중복 선정 종목도 추격매수보다 관찰, 보류, 소액 분할 검토로 해석한다.")
    elif total:
        interpretation.append("시장판단이 개선되면 중복 선정 종목의 편입 우선순위를 다시 높일 수 있다.")
    return interpretation


def build_dynamic_model_conclusion(market_risk, top_models, decision_counts, narrative_focus):
    model_text = ", ".join(top_models[:3]) if top_models else "특정 모델"
    if narrative_focus == "supply_risk":
        return f"{model_text} 신호가 확인되더라도 외국인 수급 부담이 크므로 최종 실행은 보류/관찰 중심으로 제한한다."
    if narrative_focus == "price_volatility":
        return f"{model_text} 후보라도 당일 변동성이 큰 종목은 추격하지 않고 가격 안정 확인 후 판단한다."
    if narrative_focus == "model_shift":
        return f"오늘은 {model_text} 조합이 후보군을 주도했으므로, 직전 실행 대비 모델 분포 변화 자체를 관찰 포인트로 둔다."
    if market_risk.get("rating") == "Defensive Caution":
        return f"현재 {model_text} 중심의 후보 분포는 약한 시장에서 강한 후보만 남긴 결과로 해석한다. 최종 실행은 시장위험과 당일 수급 때문에 보수적으로 제한한다."
    if decision_counts.get("소액분할검토") or decision_counts.get("소액/관찰"):
        return f"{model_text} 중심 후보 중 일부는 소액 검토가 가능하지만, 실제 편입은 수급 개선과 가격 안정 확인 뒤 판단한다."
    return f"{model_text} 중심 후보 분포를 참고하되, 최종 포트폴리오는 시장위험, ETF 전략, 종목별 수급을 함께 반영해 결정한다."


def build_step_details(market_risk, market_context, s6, e_policy, live):
    breadth = market_risk.get("breadth", [])
    flows = market_risk.get("flows", [])
    step1 = market_risk.get("step1_v2") or {}
    axis_text = []
    for axis in step1.get("axes", []):
        axis_text.append(f"{axis.get('axis')}: {axis.get('score')}/{axis.get('max_score')}점")
        for reason in axis.get("reasons", [])[:2]:
            axis_text.append(f"{axis.get('axis')} 근거: {reason}")
    flow_text = []
    for row in flows:
        flow_text.append(f"{row.get('signal_name')}: {fmt(row.get('metric_value'))}{row.get('metric_unit', '')}({row.get('direction_label')})")
    breadth_text = []
    for row in breadth:
        positive = row.get("positive_ratio")
        positive_pct = round(positive * 100, 1) if isinstance(positive, (int, float)) else None
        breadth_text.append(f"{row.get('universe_code')}: 상승 {row.get('advancers')} / 하락 {row.get('decliners')} / 상승비율 {positive_pct}%")

    holdings = s6.get("holdings", [])
    cash_like = sum(row.get("weight_pct", 0) for row in holdings if row.get("role") in {"bond_short", "CASH"})
    hedge_like = sum(row.get("weight_pct", 0) for row in holdings if row.get("role") in {"fx_usd", "commodity_gold", "hedge_inverse_kr", "bond_long"})
    candidates = live.get("items", [])
    hold_count = sum(1 for row in candidates if "보류" in row.get("decision", ""))
    watch_count = sum(1 for row in candidates if "관찰" in row.get("decision", ""))
    small_count = sum(1 for row in candidates if "소액" in row.get("decision", ""))

    return [
        {
            "step": 1,
            "title": "시장 위험 판단",
            "summary": build_market_step_summary(market_risk),
            "details": [
                f"시장판단은 {market_rating_text(market_risk)}이다.",
                f"STEP1 v2 점수는 {step1.get('score')}점, 기준 시점은 {step1.get('effective_asof') or market_risk.get('asof')}이다.",
                f"기존 판단은 {market_risk.get('legacy_rating') or step1.get('legacy_rating')}였다.",
                *axis_text,
                *breadth_text,
                *flow_text,
                "중동, 유가, 금리, 반도체 변동성 관련 뉴스가 리스크 요인으로 반영됐다.",
            ],
            "conclusion": build_market_step_conclusion(market_risk),
        },
        {
            "step": 2,
            "title": "ETF 전략 선택",
            "summary": build_etf_step_summary(market_risk),
            "details": [
                f"S6 최신 리밸런싱 기준일은 {s6.get('rebalance_date')}이다.",
                f"현금성/단기채 성격 비중은 약 {round(cash_like, 1)}%, 달러/금/인버스/장기채 방어 비중은 약 {round(hedge_like, 1)}%이다.",
                *[
                    f"{row.get('scenario')}안 {row.get('name')}: {row.get('basis')} / 주식 {row.get('stock_weight_range_pct')}% / {row.get('activation_condition')}"
                    for row in build_step2_portfolio_scenarios(market_risk)
                ],
                "구성은 단기금리, 달러채권, 금, 인버스, 장기채, 현금으로 분산되어 있다.",
            ],
            "conclusion": build_etf_step_conclusion(market_risk),
        },
        {
            "step": 3,
            "title": "E-series ETF 참고",
            "summary": "E-series는 ETF 전용 AI 전략이지만 현재 공개 추천 단계가 아니라 참고용으로만 반영했다.",
            "details": [
                f"E-series 기준일은 {e_policy.get('as_of_date')}이다.",
                f"운영 후보 정책은 {e_policy.get('active_primary_shadow_policy')}이다.",
                f"공개 추천 허용 여부는 {e_policy.get('governance', {}).get('public_recommendation_allowed')}이다.",
                "따라서 S6 실행 판단을 대체하지 않고 ETF 전략 검증 참고자료로만 사용한다.",
            ],
            "conclusion": "현재 페이지에서는 E-series를 보조 판단 근거로만 표시한다.",
        },
        {
            "step": 4,
            "title": "주식 모델 후보 점검",
            "summary": "주식은 모델 중복 선정 종목을 중심으로 보되, 오늘 시장 상황에서는 적극 매수보다 후보 관리에 초점을 둔다.",
            "details": [
                "S2/S3/T/I 계열 중복 선정 종목을 우선 점검했다.",
                "현대차, 현대모비스, POSCO홀딩스, SK텔레콤, 대우건설은 핵심 후보군으로 분류했다.",
                "SK하이닉스, 삼성전자, LG전자, LG, SK스퀘어는 관심은 높지만 추격매수 제한 그룹으로 분류했다.",
            ],
            "conclusion": build_stock_candidate_step_conclusion(market_risk),
        },
        {
            "step": 5,
            "title": "정성 분석과 최신 수급 확인",
            "summary": "정성적 사업 전망과 최신 가격/수급을 함께 확인해 단기 매수 가능성과 위험을 분리했다.",
            "details": [
                f"최신 수급 데이터 상태는 {live.get('status')}, 원천은 {live.get('source')}이다.",
                f"보류 판단 종목은 {hold_count}개, 관찰 판단 종목은 {watch_count}개, 소액 검토 종목은 {small_count}개이다.",
                "외국인 매도가 큰 대형주는 모델 선정 여부와 무관하게 추격매수를 제한했다.",
                "POSCO홀딩스와 SK텔레콤처럼 가격 변동이 작고 수급 부담이 낮은 종목만 소액/관찰 후보로 남겼다.",
            ],
            "conclusion": "정성적으로 좋아도 당일 수급과 가격이 불리하면 매수 판단을 보류한다.",
        },
        {
            "step": 6,
            "title": "최종 포트폴리오 판단",
            "summary": build_final_step_summary(market_risk),
            "details": [
                build_step6_first_detail(market_risk),
                "주식은 0% 고정은 아니지만 신규 편입은 제한적으로만 검토한다.",
                "추격매수 보류 종목은 관심 목록에 남기되 매수 실행 종목으로 표시하지 않는다.",
                "시장 확산력과 외국인 수급이 개선되면 주식 비중 확대 여부를 다시 판단한다.",
            ],
            "conclusion": build_final_step_conclusion(market_risk),
        },
    ]


def write_markdown(report, path):
    lines = []
    lines.append("# 투자 포트폴리오")
    lines.append("")
    lines.append(f"- 기준일: {report['as_of_date']}")
    lines.append(f"- 생성시각: {report['generated_at']}")
    lines.append(f"- 실행구분: {report.get('run_session')}")
    lines.append(f"- 시장판단: {report['market_risk']['rating']}")
    step1 = report["market_risk"].get("step1_v2") or {}
    if step1:
        lines.append(f"- STEP1 v2: {step1.get('score')}점 / {step1.get('display_rating')} / 기준시점 {step1.get('effective_asof')}")
        lines.append(f"- 기존 판단: {step1.get('legacy_rating')}")
    lines.append("")
    lines.append("## 단계별 판단")
    for step in report["process_steps"]:
        lines.append(f"{step['step']}. {step['name']}: {step['result']}")
    lines.append("")
    lines.append("## 단계별 상세 설명")
    for detail in report.get("step_details", []):
        lines.append(f"### {detail['step']}. {detail['title']}")
        lines.append(detail["summary"])
        lines.append("")
        for item in detail.get("details", []):
            lines.append(f"- {item}")
        lines.append(f"- 결론: {detail.get('conclusion')}")
        lines.append("")
    concentration = report.get("model_concentration_explanation")
    if concentration:
        lines.append(f"## {concentration['section_title']}")
        lines.append(concentration["summary"])
        lines.append("")
        lines.append("### 모델별 역할")
        for role in concentration.get("model_roles", []):
            count_txt = ""
            if role.get("candidate_count") is not None:
                count_txt = f" / 후보 {role.get('candidate_count')}개({role.get('candidate_ratio_pct')}%)"
            lines.append(f"- {role['model']}({role['plain_name']}{count_txt}): {role['description']}")
        lines.append("")
        lines.append("### 지금 이런 결과가 나온 이유")
        for item in concentration.get("why_now", []):
            lines.append(f"- {item}")
        lines.append("")
        lines.append("### 투자 해석")
        for item in concentration.get("interpretation", []):
            lines.append(f"- {item}")
        lines.append(f"- 결론: {concentration.get('conclusion')}")
        lines.append("")
    lines.append("## 시장 위험")
    mr = report["market_risk"]
    lines.append(f"- 방향: {mr.get('direction_label')} / 총점 {mr.get('total_score')} / 위험점수 {mr.get('risk_score')}")
    lines.append(f"- 실행: {mr.get('action')}")
    if step1:
        for axis in step1.get("axes", []):
            lines.append(f"- {axis.get('axis')}: {axis.get('score')}/{axis.get('max_score')}점")
    lines.append("")
    lines.append("## ETF 전략")
    lines.append(f"- 선택 모델: {report['etf_strategy']['selected_model']}")
    lines.append(f"- 판단: {report['etf_strategy']['reason']}")
    for scenario in report["etf_strategy"].get("portfolio_scenarios", []):
        lines.append(
            f"- {scenario.get('scenario')}안 {scenario.get('name')}: {scenario.get('basis')}, "
            f"주식 {scenario.get('stock_weight_range_pct')}%, {scenario.get('activation_condition')}"
        )
    lines.append("")
    lines.append("| 코드 | 종목 | 역할 | 비중 |")
    lines.append("|---|---:|---:|---:|".replace("---:", "---"))
    for row in report["etf_strategy"]["s6_allocation"]["holdings"]:
        lines.append(f"| {row['ticker']} | {row['name']} | {row['role']} | {row['weight_pct']}% |")
    lines.append("")
    lines.append("## 주식 후보")
    lines.append(report["stock_strategy"]["exposure_guidance"])
    live_data = report["stock_strategy"].get("live_data", {})
    if live_data.get("fetched_at"):
        lines.append(f"- 최신가/당일등락/외국인/기관 거래금액 조회시점: {live_data.get('fetched_at')} ({live_data.get('source')})")
    lines.append("")
    lines.append("| 코드 | 종목 | 모델군 | 선정일 | 최신가 | 당일등락 | 외국인 | 기관 | 판단 |")
    lines.append("|---|---|---|---|---:|---:|---:|---:|---|")
    for row in report["stock_strategy"]["candidates"]:
        live = row.get("live_quote") or {}
        models = row.get("model_display") or " / ".join(row.get("model_display_codes") or row.get("model_ids") or row.get("model_groups", []))
        lines.append(
            f"| {row['ticker']} | {row['name']} | {models} | {row.get('latest_selection_date')} | "
            f"{fmt(live.get('price'))} | {fmt(live.get('change_pct'))}% | "
            f"{fmt(live.get('foreign_net_억원'))}억 | {fmt(live.get('institution_net_억원'))}억 | {row['decision']} |"
        )
    lines.append("")
    lines.append(f"> {report['disclaimer']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def init_portfolio_schema(con):
    migrate_portfolio_schema(con)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS portfolio_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_key TEXT NOT NULL UNIQUE,
            as_of_date TEXT NOT NULL,
            run_time TEXT NOT NULL,
            run_session TEXT,
            generated_at TEXT NOT NULL,
            page TEXT NOT NULL,
            market_rating TEXT,
            market_total_score REAL,
            market_risk_score REAL,
            selected_etf_model TEXT,
            stock_exposure_guidance TEXT,
            live_data_status TEXT,
            live_data_source TEXT,
            json_path TEXT,
            md_path TEXT,
            report_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolio_process_steps (
            run_id INTEGER NOT NULL,
            step_no INTEGER NOT NULL,
            name TEXT,
            result TEXT,
            PRIMARY KEY (run_id, step_no),
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS portfolio_etf_holdings (
            run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT,
            role TEXT,
            weight_pct REAL,
            rebalance_date TEXT,
            trade_date TEXT,
            PRIMARY KEY (run_id, ticker, role),
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS portfolio_stock_candidates (
            run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            candidate_group TEXT,
            decision TEXT,
            latest_selection_date TEXT,
            model_groups TEXT,
            model_ids TEXT,
            model_display_codes TEXT,
            model_display TEXT,
            model_count INTEGER,
            selection_close REAL,
            market_cap REAL,
            return_from_selection_pct REAL,
            holding_days REAL,
            qualitative_summary TEXT,
            live_price REAL,
            live_change_pct REAL,
            foreign_net_억원 REAL,
            institution_net_억원 REAL,
            individual_net_억원 REAL,
            pension_net_억원 REAL,
            PRIMARY KEY (run_id, ticker),
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_portfolio_runs_asof ON portfolio_runs(as_of_date, run_time);
        CREATE INDEX IF NOT EXISTS idx_portfolio_stock_ticker ON portfolio_stock_candidates(ticker);

        CREATE TABLE IF NOT EXISTS portfolio_step_details (
            run_id INTEGER NOT NULL,
            step_no INTEGER NOT NULL,
            title TEXT,
            summary TEXT,
            details_json TEXT,
            conclusion TEXT,
            PRIMARY KEY (run_id, step_no),
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS portfolio_model_explanations (
            run_id INTEGER PRIMARY KEY,
            section_title TEXT,
            placement TEXT,
            summary TEXT,
            model_roles_json TEXT,
            why_now_json TEXT,
            interpretation_json TEXT,
            model_group_counts_json TEXT,
            model_id_counts_json TEXT,
            decision_counts_json TEXT,
            top_models_json TEXT,
            concentration_ratio_pct REAL,
            narrative_focus TEXT,
            explanation_fingerprint TEXT,
            generation_method TEXT,
            generation_model TEXT,
            generation_status TEXT,
            overlap_candidates_json TEXT,
            conclusion TEXT,
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );
        """
    )
    ensure_column(con, "portfolio_stock_candidates", "model_ids", "TEXT")
    ensure_column(con, "portfolio_stock_candidates", "model_display_codes", "TEXT")
    ensure_column(con, "portfolio_stock_candidates", "model_display", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "model_id_counts_json", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "decision_counts_json", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "top_models_json", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "concentration_ratio_pct", "REAL")
    ensure_column(con, "portfolio_model_explanations", "narrative_focus", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "explanation_fingerprint", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "generation_method", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "generation_model", "TEXT")
    ensure_column(con, "portfolio_model_explanations", "generation_status", "TEXT")
    ensure_column(con, "portfolio_runs", "market_legacy_rating", "TEXT")
    ensure_column(con, "portfolio_runs", "market_step1_v2_grade", "INTEGER")
    ensure_column(con, "portfolio_runs", "market_step1_v2_label", "TEXT")
    ensure_column(con, "portfolio_runs", "market_step1_v2_score", "REAL")
    ensure_column(con, "portfolio_runs", "market_step1_v2_is_boundary", "INTEGER")
    ensure_column(con, "portfolio_runs", "market_effective_asof", "TEXT")
    ensure_column(con, "portfolio_runs", "market_logic_version", "TEXT")


def migrate_portfolio_schema(con):
    con.execute("DROP VIEW IF EXISTS v_portfolio_latest_run")
    cols = table_columns(con, "portfolio_runs")
    if not cols or "run_key" in cols:
        return

    legacy_tables = [
        "portfolio_runs",
        "portfolio_process_steps",
        "portfolio_etf_holdings",
        "portfolio_stock_candidates",
    ]
    suffix = datetime.now(KST).strftime("%Y%m%d%H%M%S")
    for table in legacy_tables:
        if table_exists(con, table):
            con.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy_{suffix}")

    con.executescript(
        """
        CREATE TABLE portfolio_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_key TEXT NOT NULL UNIQUE,
            as_of_date TEXT NOT NULL,
            run_time TEXT NOT NULL,
            run_session TEXT,
            generated_at TEXT NOT NULL,
            page TEXT NOT NULL,
            market_rating TEXT,
            market_total_score REAL,
            market_risk_score REAL,
            selected_etf_model TEXT,
            stock_exposure_guidance TEXT,
            live_data_status TEXT,
            live_data_source TEXT,
            json_path TEXT,
            md_path TEXT,
            report_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE portfolio_process_steps (
            run_id INTEGER NOT NULL,
            step_no INTEGER NOT NULL,
            name TEXT,
            result TEXT,
            PRIMARY KEY (run_id, step_no),
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE portfolio_etf_holdings (
            run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT,
            role TEXT,
            weight_pct REAL,
            rebalance_date TEXT,
            trade_date TEXT,
            PRIMARY KEY (run_id, ticker, role),
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE portfolio_stock_candidates (
            run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            candidate_group TEXT,
            decision TEXT,
            latest_selection_date TEXT,
            model_groups TEXT,
            model_count INTEGER,
            selection_close REAL,
            market_cap REAL,
            return_from_selection_pct REAL,
            holding_days REAL,
            qualitative_summary TEXT,
            live_price REAL,
            live_change_pct REAL,
            foreign_net_억원 REAL,
            institution_net_억원 REAL,
            individual_net_억원 REAL,
            pension_net_억원 REAL,
            PRIMARY KEY (run_id, ticker),
            FOREIGN KEY (run_id) REFERENCES portfolio_runs(run_id) ON DELETE CASCADE
        );
        """
    )

    old_runs = f"portfolio_runs_legacy_{suffix}"
    if not table_exists(con, old_runs):
        return
    id_map = {}
    for row in con.execute(f"SELECT * FROM {old_runs} ORDER BY run_id"):
        old_cols = table_columns(con, old_runs)
        data = dict(zip(old_cols, row))
        generated_at = data["generated_at"]
        run_dt = parse_dt(generated_at)
        run_time = run_dt.isoformat(timespec="milliseconds") if run_dt else generated_at
        run_key = build_run_key(data["as_of_date"], run_time)
        cur = con.execute(
            """
            INSERT INTO portfolio_runs (
                run_key, as_of_date, run_time, run_session, generated_at, page,
                market_rating, market_total_score, market_risk_score,
                selected_etf_model, stock_exposure_guidance, live_data_status,
                live_data_source, json_path, md_path, report_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_key,
                data["as_of_date"],
                run_time,
                classify_session(run_dt) if run_dt else None,
                generated_at,
                data["page"],
                data.get("market_rating"),
                data.get("market_total_score"),
                data.get("market_risk_score"),
                data.get("selected_etf_model"),
                data.get("stock_exposure_guidance"),
                data.get("live_data_status"),
                data.get("live_data_source"),
                data.get("json_path"),
                data.get("md_path"),
                data["report_json"],
                data.get("created_at"),
            ),
        )
        id_map[data["run_id"]] = cur.lastrowid

    copy_child_table(con, f"portfolio_process_steps_legacy_{suffix}", "portfolio_process_steps", id_map)
    copy_child_table(con, f"portfolio_etf_holdings_legacy_{suffix}", "portfolio_etf_holdings", id_map)
    copy_child_table(con, f"portfolio_stock_candidates_legacy_{suffix}", "portfolio_stock_candidates", id_map)


def table_exists(con, table):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone() is not None


def table_columns(con, table):
    return [row[1] for row in con.execute(f"PRAGMA table_info({table})")]


def ensure_column(con, table, column, column_type):
    if table_exists(con, table) and column not in table_columns(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def copy_child_table(con, source, target, id_map):
    if not table_exists(con, source):
        return
    cols = table_columns(con, source)
    target_cols = table_columns(con, target)
    common = [col for col in cols if col in target_cols]
    placeholders = ",".join("?" for _ in common)
    col_sql = ",".join(common)
    for row in con.execute(f"SELECT {col_sql} FROM {source}"):
        data = dict(zip(common, row))
        old_run_id = data.get("run_id")
        if old_run_id not in id_map:
            continue
        data["run_id"] = id_map[old_run_id]
        con.execute(
            f"INSERT INTO {target}({col_sql}) VALUES ({placeholders})",
            tuple(data[col] for col in common),
        )


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def classify_session(dt):
    if dt is None:
        return None
    hour = dt.hour
    if hour < 12:
        return "morning"
    if hour < 15:
        return "afternoon"
    if hour < 16:
        return "close"
    return "after_close"


def build_run_key(asof_date, run_time):
    return f"{asof_date}_{re.sub(r'[^0-9]', '', run_time)}"


def save_report_to_db(report, json_path, md_path):
    with sqlite3.connect(DB_PATH) as con:
        con.execute("PRAGMA foreign_keys = ON")
        init_portfolio_schema(con)

        market = report["market_risk"]
        step1 = market.get("step1_v2") or {}
        stock_strategy = report["stock_strategy"]
        run_time = report["generated_at"]
        run_key = build_run_key(report["as_of_date"], run_time)
        cur = con.execute(
            """
            INSERT INTO portfolio_runs (
                run_key, as_of_date, run_time, run_session, generated_at, page,
                market_rating, market_total_score, market_risk_score,
                selected_etf_model, stock_exposure_guidance, live_data_status,
                live_data_source, json_path, md_path, report_json,
                market_legacy_rating, market_step1_v2_grade, market_step1_v2_label,
                market_step1_v2_score, market_step1_v2_is_boundary,
                market_effective_asof, market_logic_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_key,
                report["as_of_date"],
                run_time,
                report.get("run_session"),
                run_time,
                report["page"],
                market.get("rating"),
                market.get("total_score"),
                market.get("risk_score"),
                report["etf_strategy"].get("selected_model"),
                stock_strategy.get("exposure_guidance"),
                stock_strategy.get("live_data", {}).get("status"),
                stock_strategy.get("live_data", {}).get("source"),
                str(json_path),
                str(md_path),
                json.dumps(report, ensure_ascii=False),
                market.get("legacy_rating") or step1.get("legacy_rating"),
                step1.get("grade"),
                step1.get("label"),
                step1.get("score"),
                1 if step1.get("is_boundary") else 0,
                step1.get("effective_asof") or market.get("asof"),
                step1.get("logic_version"),
            ),
        )
        run_id = cur.lastrowid

        con.executemany(
            "INSERT INTO portfolio_process_steps(run_id, step_no, name, result) VALUES (?, ?, ?, ?)",
            [
                (run_id, row["step"], row.get("name"), row.get("result"))
                for row in report["process_steps"]
            ],
        )
        con.executemany(
            """
            INSERT INTO portfolio_step_details(
                run_id, step_no, title, summary, details_json, conclusion
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row["step"],
                    row.get("title"),
                    row.get("summary"),
                    json.dumps(row.get("details", []), ensure_ascii=False),
                    row.get("conclusion"),
                )
                for row in report.get("step_details", [])
            ],
        )
        con.executemany(
            """
            INSERT INTO portfolio_etf_holdings(
                run_id, ticker, name, market, role, weight_pct, rebalance_date, trade_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row.get("ticker"),
                    row.get("name"),
                    row.get("market"),
                    row.get("role"),
                    row.get("weight_pct"),
                    row.get("rebalance_date"),
                    row.get("trade_date"),
                )
                for row in report["etf_strategy"]["s6_allocation"]["holdings"]
            ],
        )
        con.executemany(
            """
            INSERT INTO portfolio_stock_candidates(
                run_id, ticker, name, candidate_group, decision, latest_selection_date,
                model_groups, model_ids, model_display_codes, model_display, model_count, selection_close, market_cap,
                return_from_selection_pct, holding_days, qualitative_summary, live_price,
                live_change_pct, foreign_net_억원, institution_net_억원,
                individual_net_억원, pension_net_억원
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [stock_row(run_id, row) for row in report["stock_strategy"]["candidates"]],
        )
        explanation = report.get("model_concentration_explanation")
        if explanation:
            con.execute(
                """
                INSERT INTO portfolio_model_explanations(
                    run_id, section_title, placement, summary, model_roles_json,
                    why_now_json, interpretation_json, model_group_counts_json,
                    model_id_counts_json, decision_counts_json, top_models_json,
                    concentration_ratio_pct, narrative_focus, explanation_fingerprint,
                    generation_method, generation_model, generation_status,
                    overlap_candidates_json, conclusion
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    explanation.get("section_title"),
                    explanation.get("placement"),
                    explanation.get("summary"),
                    json.dumps(explanation.get("model_roles", []), ensure_ascii=False),
                    json.dumps(explanation.get("why_now", []), ensure_ascii=False),
                    json.dumps(explanation.get("interpretation", []), ensure_ascii=False),
                    json.dumps(explanation.get("model_group_counts", {}), ensure_ascii=False),
                    json.dumps(explanation.get("model_id_counts", {}), ensure_ascii=False),
                    json.dumps(explanation.get("decision_counts", {}), ensure_ascii=False),
                    json.dumps(explanation.get("top_models", []), ensure_ascii=False),
                    explanation.get("concentration_ratio_pct"),
                    explanation.get("narrative_focus"),
                    explanation.get("explanation_fingerprint"),
                    explanation.get("generation_method"),
                    explanation.get("generation_model"),
                    explanation.get("generation_status"),
                    json.dumps(explanation.get("overlap_candidates", []), ensure_ascii=False),
                    explanation.get("conclusion"),
                ),
            )
        con.execute(
            """
            CREATE VIEW IF NOT EXISTS v_portfolio_latest_run AS
            SELECT *
            FROM portfolio_runs
            WHERE run_id = (SELECT MAX(run_id) FROM portfolio_runs)
            """
        )
        return run_id


def stock_row(run_id, row):
    live = row.get("live_quote") or {}
    return (
        run_id,
        row.get("ticker"),
        row.get("name"),
        row.get("group"),
        row.get("decision"),
        row.get("latest_selection_date"),
        ",".join(row.get("model_groups", [])),
        ",".join(row.get("model_ids", [])),
        ",".join(row.get("model_display_codes", [])),
        row.get("model_display"),
        row.get("model_count"),
        row.get("selection_close"),
        row.get("market_cap"),
        row.get("return_from_selection_pct"),
        row.get("holding_days"),
        row.get("qualitative_summary"),
        live.get("price"),
        live.get("change_pct"),
        live.get("foreign_net_억원"),
        live.get("institution_net_억원"),
        live.get("individual_net_억원"),
        live.get("pension_net_억원"),
    )


def fmt(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def resolve_gcloud():
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        bundled = Path(local_appdata) / "GoogleCloudSDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd"
        try:
            if bundled.exists():
                return bundled
        except OSError:
            pass
    found = shutil.which("gcloud")
    if found:
        return Path(found)
    raise RuntimeError("gcloud not found")


def validate_portfolio_json(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid portfolio json: {path}") from exc
    required = ["as_of_date", "generated_at", "source_thread"]
    missing = [key for key in required if not payload.get(key)]
    candidates = payload.get("stock_strategy", {}).get("candidates")
    if not isinstance(candidates, list) or not candidates:
        missing.append("stock_strategy.candidates")
    if missing:
        raise RuntimeError(f"portfolio json missing required fields: {', '.join(missing)}")
    return payload


def run_gcloud(gcloud, *args):
    completed = subprocess.run(
        [str(gcloud), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"gcloud {' '.join(args)} failed: {stderr}")


def publish_portfolio_to_gcs(latest_json_path, archive_json_path):
    payload = validate_portfolio_json(latest_json_path)
    gcloud = resolve_gcloud()
    run_gcloud(gcloud, "config", "configurations", "activate", "quantservice")
    run_gcloud(gcloud, "storage", "cp", str(latest_json_path), GCS_CURRENT_TARGET, "--quiet")
    run_gcloud(
        gcloud,
        "storage",
        "cp",
        str(archive_json_path),
        f"{GCS_HISTORY_PREFIX}/{archive_json_path.name}",
        "--quiet",
    )

    verify_url = f"{GCS_PUBLIC_CURRENT_URL}?ts={int(time.time())}"
    response = requests.get(
        verify_url,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        timeout=30,
    )
    response.raise_for_status()
    remote_payload = response.json()
    if remote_payload.get("generated_at") != payload.get("generated_at"):
        raise RuntimeError(
            "GCS publish verification failed: "
            f"local generated_at={payload.get('generated_at')}, "
            f"remote generated_at={remote_payload.get('generated_at')}"
        )
    return {
        "target": GCS_CURRENT_TARGET,
        "history": f"{GCS_HISTORY_PREFIX}/{archive_json_path.name}",
        "generated_at": payload.get("generated_at"),
        "verify_url": verify_url,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default=datetime.now(KST).strftime("%Y-%m-%d"))
    parser.add_argument("--skip-gcs-publish", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report(args.asof)
    run_dt = parse_dt(report["generated_at"]) or datetime.now(KST)
    run_stamp = run_dt.strftime("%H%M%S%f")[:9]
    ymd = re.sub(r"[^0-9]", "", args.asof)
    json_path = OUTPUT_DIR / f"investment_portfolio_{ymd}_{run_stamp}.json"
    md_path = PORTFOLIO_DOCS_DIR / f"investment_portfolio_{ymd}_{run_stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    run_id = save_report_to_db(report, json_path, md_path)
    latest_json_path = OUTPUT_DIR / "investment_portfolio_latest.json"
    shutil.copyfile(json_path, latest_json_path)
    shutil.copyfile(md_path, PORTFOLIO_DOCS_DIR / "investment_portfolio_latest.md")
    publish_result = None
    if not args.skip_gcs_publish and os.getenv("QUANTANALYSIS_SKIP_GCS_PUBLISH") != "1":
        publish_result = publish_portfolio_to_gcs(latest_json_path, json_path)
    print(str(json_path))
    print(str(md_path))
    print(f"db={DB_PATH}")
    print(f"run_id={run_id}")
    if publish_result:
        print(f"gcs_current={publish_result['target']}")
        print(f"gcs_history={publish_result['history']}")
        print(f"gcs_generated_at={publish_result['generated_at']}")


if __name__ == "__main__":
    main()
