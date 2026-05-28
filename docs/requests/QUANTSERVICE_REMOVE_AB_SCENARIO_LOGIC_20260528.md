# QuantService 작업요청서: 투자 포트폴리오 A/B 시나리오 표시 제거

## 목적

QuantAnalysis 투자 포트폴리오 로직에서 A안/B안 시나리오를 삭제했다. redbot.co.kr `투자 포트폴리오` 페이지에서도 A안/B안 컬럼과 문구를 제거하고, 포트폴리오 전체 비중 정책만 표시해야 한다.

## 변경된 투자 원칙

1. 종목 선정은 시장등급과 무관하게 전체 Quant 후보 중 일간 반응성 점수 상위 10개를 유지한다.
2. 시장등급은 종목 제외나 A/B 분기 판단에 사용하지 않는다.
3. 시장등급은 주식/ETF/현금 비중 조절에만 사용한다.

## QuantAnalysis 최신 데이터

- 최신 JSON: `D:\QuantAnalysis\outputs\investment_portfolio_latest.json`
- 최신 실행: `2026-05-28T23:43:42.982+09:00`
- 최신 DB 실행: `run_id=54`
- GCS current: `gs://quantservice-489808-market-analysis/admin/current/investment_portfolio_latest.json`
- GCS history: `gs://quantservice-489808-market-analysis/admin/history/investment_portfolio_20260528_234342982.json`

## JSON 변경사항

### 신규/사용 필드

`final_portfolio_strategy`:

- `stock_weight_range_pct`
- `etf_policy`
- `cash_or_defensive_policy`
- `weight_policy.logic_version`
- `weight_policy.stock_selection_policy`
- `weight_policy.adjustment_rule`

`etf_strategy.portfolio_weight_policy`:

- `stock_weight_range_pct`
- `etf_policy`
- `cash_or_defensive_policy`
- `stock_selection_policy`
- `adjustment_rule`

### 더 이상 사용하지 않을 필드

아래 필드는 빈 배열로 제공되며 화면에서 사용하지 않는다.

- `etf_strategy.portfolio_scenarios`
- `etf_strategy.e_series_scenario_reference`
- `stock_strategy.scenario_summary`
- `stock_strategy.validation_scenarios`
- `stock_strategy.candidates[].scenario_decisions`

## 화면 수정 요청

1. `주식 후보 점검` 표에서 `A안`, `B안` 컬럼을 제거한다.
2. 종목별 A/B 판단 문구를 표시하지 않는다.
3. `ETF 전략` 또는 `최종 포트폴리오` 영역에 아래 항목을 표시한다.
   - 주식 비중: `final_portfolio_strategy.stock_weight_range_pct`
   - ETF 정책: `final_portfolio_strategy.etf_policy`
   - 현금/방어 정책: `final_portfolio_strategy.cash_or_defensive_policy`
4. 설명 문구는 다음 기준으로 변경한다.
   - 기존: A안/B안 중 선택 또는 조건부 전환
   - 변경: 종목은 상위 10개 유지, 시장등급은 주식/ETF/현금 비중 조절에만 반영
5. 캐시 무효화 후 최신 current JSON을 다시 읽어 화면을 갱신한다.

## 검증 기준

1. 페이지 어디에도 `A안`, `B안`, `조건부안`, `기본안` 문구가 나오지 않아야 한다.
2. `주식 후보 점검` 표에 A/B 컬럼이 없어야 한다.
3. 최종 포트폴리오 영역에 `주식 비중 0~15%`, `ETF 정책 S6_DEFENSIVE_V1 중심`, `현금성/방어 ETF 높게 유지`가 표시되어야 한다.
4. 주식 후보 10개 종목은 그대로 표시되어야 한다.
