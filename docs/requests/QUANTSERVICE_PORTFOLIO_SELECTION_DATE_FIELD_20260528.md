# QuantService 작업요청서: 주식 후보 점검 선정일 표시 기준 수정

## 목적

`투자 포트폴리오 > 주식 후보 점검` 섹션의 `선정일`은 Quant 전략모델 원천 후보 선정일이 아니라, QuantAnalysis 포트폴리오 점수로 해당 종목이 공식 후보 상위 10개에 선정된 날짜로 표시해야 한다.

## 현재 문제

- 화면의 `선정일`이 계속 `2026-05-13`으로 보인다.
- 이 값은 Quant 전략모델 원천 후보군의 `모델선정일`이다.
- 사용자가 기대하는 `선정일`은 해당 날짜 포트폴리오 후보로 재선정된 날짜다.

## QuantAnalysis 데이터 변경

최신 JSON/DB에는 아래 필드가 분리되어 제공된다.

| 의미 | JSON 필드 | DB 필드 |
|---|---|---|
| 포트폴리오 선정일 | `stock_strategy.candidates[].portfolio_selection_date` | `portfolio_stock_candidates.portfolio_selection_date` |
| 모델 선정일 | `stock_strategy.candidates[].model_selection_date` | `portfolio_stock_candidates.model_selection_date` |
| 기존 호환 필드 | `stock_strategy.candidates[].latest_selection_date` | `portfolio_stock_candidates.latest_selection_date` |

현재 QuantAnalysis는 웹 호환을 위해 `latest_selection_date`도 `portfolio_selection_date`와 같은 값으로 채운다.

## 화면 반영 요청

1. `주식 후보 점검` 표의 `선정일` 컬럼은 반드시 `portfolio_selection_date`를 사용한다.
2. `portfolio_selection_date`가 없을 때만 하위 호환으로 `latest_selection_date`를 사용한다.
3. `model_selection_date`는 `선정일` 컬럼에 사용하지 않는다.
4. 필요하면 별도 컬럼 또는 툴팁으로 `모델선정일`을 표시할 수 있다.
5. 기존 캐시 때문에 이전 값이 보이지 않도록 current JSON 재조회/캐시 무효화를 적용한다.

## 최신 검증 기준

- QuantAnalysis 최신 산출물: `D:\QuantAnalysis\outputs\investment_portfolio_latest.json`
- 최신 실행 시각: `2026-05-28T23:29:18.274+09:00`
- 최신 DB 실행: `run_id=52`
- 예시:
  - `066570 LG전자`
    - `portfolio_selection_date`: `2026-05-28`
    - `model_selection_date`: `2026-05-13`
  - `319400 현대무벡스`
    - `portfolio_selection_date`: `2026-05-28`
    - `model_selection_date`: `2026-05-13`

## 검증 방법

1. redbot.co.kr 투자 포트폴리오 페이지를 새로고침한다.
2. `주식 후보 점검` 섹션의 `선정일`이 `2026-05-28`로 표시되는지 확인한다.
3. 같은 종목의 `모델선정일`이 필요 시에만 `2026-05-13`으로 별도 표시되는지 확인한다.

## 참고

일별 포트폴리오 선정 이력은 아래 파일로 제공된다.

- `D:\QuantAnalysis\docs\portfolio\daily_portfolio_selection_history_20260513_20260528.md`
- `D:\QuantAnalysis\outputs\daily_portfolio_selection_history_20260513_20260528.csv`
- `D:\QuantAnalysis\outputs\daily_portfolio_selection_history_20260513_20260528.json`
