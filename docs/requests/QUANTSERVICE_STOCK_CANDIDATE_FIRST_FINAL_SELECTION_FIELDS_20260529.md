# QuantService 작업요청서: 주식 후보 점검 최초/최종 포트폴리오 선정 정보 표시

## 목적

`투자 포트폴리오 > 주식 후보 점검` 섹션에서 단일 `선정일` 표시를 제거하고, 포트폴리오 기준 최초 선정과 현재 선정 정보를 분리해 표시한다.

## 데이터 기준

- 최신 JSON: `D:\QuantAnalysis\outputs\investment_portfolio_latest.json`
- DB: `D:\QuantAnalysis\analysis.db`
- 대상 배열: `stock_strategy.candidates[]`
- 대상 테이블: `portfolio_stock_candidates`

## 신규 표시 필드

| 화면 컬럼 | JSON 필드 | DB 필드 |
|---|---|---|
| 최초 포트 선정일 | `first_portfolio_selection_date` | `first_portfolio_selection_date` |
| 최초 선정가 | `first_portfolio_selection_price` | `first_portfolio_selection_price` |
| 최종 포트 선정일 | `final_portfolio_selection_date` | `final_portfolio_selection_date` |
| 최종일 주가 | `final_portfolio_selection_price` | `final_portfolio_selection_price` |
| 등락율 | `return_from_first_portfolio_selection_pct` | `return_from_first_portfolio_selection_pct` |

## 계산 기준

1. `최초 포트 선정일`은 2026-05-13 이후 일별 포트폴리오 상위 10개 이력에서 해당 종목이 처음 등장한 날짜다.
2. `최초 선정가`는 최초 포트 선정일의 종가다.
3. `최종 포트 선정일`은 현재 투자 포트폴리오 파이프라인 실행일이다.
4. `최종일 주가`는 현재 실행일의 포트폴리오 선정가, 즉 후보 점검 최신가다.
5. `등락율`은 `(최종일 주가 / 최초 선정가 - 1) * 100`이다.

## 화면 반영 요청

1. 기존 단일 `선정일` 컬럼은 제거하거나 `최종 포트 선정일`로 이름을 변경한다.
2. 주식 후보 점검 표에는 아래 컬럼을 추가한다.
   - 최초 포트 선정일
   - 최초 선정가
   - 최종 포트 선정일
   - 최종일 주가
   - 등락율
3. 등락율은 `%` 단위로 표시하고, 소수점 둘째 자리까지 표시한다.
4. 가격은 원 단위 천 단위 콤마로 표시한다.
5. `model_selection_date`는 모델 원천 후보 편입일이므로 이 표의 `선정일`로 사용하지 않는다.

## 검증 예시

최신 검증 실행 기준 일부 기대값:

| 코드 | 종목 | 최초 포트 선정일 | 최초순위 |
|---|---|---|---:|
| 066570 | LG전자 | 2026-05-13 | 3 |
| 319400 | 현대무벡스 | 2026-05-13 | 5 |
| 034730 | SK | 2026-05-20 | 10 |
| 086520 | 에코프로 | 2026-05-26 | 2 |
| 000660 | SK하이닉스 | 2026-05-28 | 6 |

## 참고

일별 포트폴리오 선정 이력 원천:

- `D:\QuantAnalysis\outputs\daily_portfolio_selection_history_20260513_20260528.csv`
- `D:\QuantAnalysis\outputs\daily_portfolio_selection_history_20260513_20260528.json`
- `D:\QuantAnalysis\docs\portfolio\daily_portfolio_selection_history_20260513_20260528.md`
