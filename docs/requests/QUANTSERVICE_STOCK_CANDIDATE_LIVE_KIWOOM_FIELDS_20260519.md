# QuantService 작업요청서: 주식 후보 점검 최신 시세/수급 필드 반영

## 목적

`투자 포트폴리오 > 주식 후보 점검` 섹션의 `최신가`, `당일등락`, `외인거래`, `기관 거래금액`은 QuantAnalysis 파이프라인 생성 시점의 Kiwoom REST 조회값으로 표시한다.

## 데이터 기준

- 최신 산출물: `D:\QuantAnalysis\outputs\investment_portfolio_latest.json`
- DB: `D:\QuantAnalysis\analysis.db`
- 실행 단위: `portfolio_runs.run_id`
- 조회 상태: `portfolio_runs.live_data_status`, `portfolio_runs.live_data_source`
- 조회시점: JSON `stock_strategy.live_data.fetched_at`

## 표시 필드

`portfolio_stock_candidates`에서 최신 실행 `run_id` 기준으로 아래 필드를 사용한다.

| 화면 컬럼 | DB 필드 | JSON 필드 |
|---|---|---|
| 최신가 | `live_price` | `stock_strategy.candidates[].live_quote.price` |
| 당일등락 | `live_change_pct` | `stock_strategy.candidates[].live_quote.change_pct` |
| 외인거래 | `foreign_net_억원` | `stock_strategy.candidates[].live_quote.foreign_net_억원` |
| 기관 거래금액 | `institution_net_억원` | `stock_strategy.candidates[].live_quote.institution_net_억원` |
| 모델 | `model_display` | `stock_strategy.candidates[].model_display` |

## 화면 반영 요청

1. `live_data_status = 'ok'`이면 주식 후보 점검 표에 위 필드를 그대로 표시한다.
2. `live_data_status = 'partial'`이면 값이 있는 종목은 표시하고, 누락 종목은 `-`로 표시한다.
3. `live_data_status = 'not_loaded'`이면 최신 시세/수급 미조회 상태임을 섹션 상단에 표시한다.
4. 표 상단 또는 하단에 `조회시점: {stock_strategy.live_data.fetched_at}`을 표시한다.
5. 거래금액 단위는 `억원`으로 표시한다.

## QuantAnalysis 변경사항

- `portfolio_pipeline.py`가 Kiwoom `ka10001`로 최신가/등락률을 조회한다.
- `portfolio_pipeline.py`가 Kiwoom `ka10059`로 외국인/기관/개인/연기금 순거래금액을 조회한다.
- API 429 응답에 대비해 재시도와 짧은 호출 간격을 적용했다.
- 최신 검증 실행: `run_id=21`, `live_data_status='ok'`, 후보 10개 전부 최신값 저장 완료.
