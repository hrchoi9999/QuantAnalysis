# QuantService 작업요청서: 주식 후보 장중 최신 스냅샷 반영

## 목적

투자 포트폴리오 페이지의 `주식 후보 점검` 섹션은 장중 10분 간격으로 갱신되는 QuantAnalysis 최신 스냅샷을 우선 사용한다.

## 신규 데이터

- DB: `D:\QuantAnalysis\analysis.db`
- 누적 테이블: `portfolio_stock_live_snapshots`
- 갱신 실행 테이블: `portfolio_stock_live_refresh_runs`
- 최신 뷰: `v_portfolio_stock_live_latest`

## 표시 우선순위

1. `v_portfolio_stock_live_latest`에 해당 종목 값이 있으면 이를 우선 표시한다.
2. 값이 없으면 기존 `portfolio_stock_candidates`의 최신 `run_id` 값을 fallback으로 표시한다.

## 표시 필드

| 화면 컬럼 | 최신 뷰 필드 |
|---|---|
| 최신가 | `live_price` |
| 당일등락 | `live_change_pct` |
| 외인거래 | `foreign_net_억원` |
| 기관 거래금액 | `institution_net_억원` |
| 조회시점 | `fetched_at` |
| 원천 | `source` |

## 운영 방식

- QuantAnalysis가 장중 10분 간격으로 `intraday_live_stock_refresh.py`를 실행한다.
- 실행 시간대는 평일 `09:00~15:40`이다.
- 장외 시간에는 스크립트가 자동으로 `skipped` 처리한다.
- 최신 검증 실행: `refresh_id=1`, `status='ok'`, 후보 10개 전부 저장 완료.

## 주의

QS는 이 데이터를 계산하거나 외부 API로 다시 조회하지 않는다.  
QS는 QuantAnalysis DB/JSON 산출물을 읽어 웹에 표시만 한다.
