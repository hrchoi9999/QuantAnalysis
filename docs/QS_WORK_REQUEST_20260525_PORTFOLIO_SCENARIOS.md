# QuantService 작업요청서: 투자 포트폴리오 STEP1~STEP6 시나리오 표시 반영

- 요청일: 2026-05-25
- 요청 쓰레드: QuantAnalysis
- 대상 쓰레드: QuantService
- 대상 페이지: redbot.co.kr 투자 포트폴리오
- 데이터 원천: `gs://quantservice-489808-market-analysis/admin/current/investment_portfolio_latest.json`
- 최신 생성시각 예시: `2026-05-25T19:53:26.069+09:00`

## 1. 요청 배경

QuantAnalysis 투자분석 파이프라인의 STEP1~STEP6 구조가 변경되었습니다.

기존에는 시장판단과 최종 포트폴리오가 단일 결론 중심이었으나, 이제는 아래 구조로 제공됩니다.

- STEP1: 6등급 시장 위험 평가
- STEP2: 등급 경계 구간에서 A안/B안 포트폴리오 시나리오 제공
- STEP3: E-series ETF 참고 해석을 시나리오별로 분리
- STEP4: 주식 후보를 시나리오별로 재분류
- STEP5: 시나리오별 검증 조건 제공
- STEP6: 기본안, 조건부안, 전환조건을 최종 포트폴리오 전략으로 제공

따라서 QuantService 투자 포트폴리오 페이지도 신규 JSON 필드를 읽어 표시하도록 수정이 필요합니다.

## 2. 필수 반영 데이터

### 2.1 STEP1 시장 위험 판단

신규 필드:

```json
market_risk.step1_v2
```

표시 요청:

- `score`: STEP1 총점
- `display_rating`: 예: `4등급 중립 상단`
- `effective_asof`: 실제 판단 기준 시각
- `legacy_rating`: 기존 판단
- `is_boundary`: 등급 경계 여부
- `boundary_reason`: 경계 판단 사유
- `axes`: 6개 축별 점수와 근거

표시 예:

- 시장판단: `4등급 중립 상단`
- STEP1 점수: `63.0점`
- 기준시점: `2026-05-22T18:00:00+09:00`
- 기존판단: `Constructive Watch`
- 경계사유: 방향성과 확산력은 5등급에 가깝지만 수급 또는 리스크가 약해 4등급 상단으로 분류

6개 축은 표로 표시해 주십시오.

| 축 | 점수 | 주요 근거 |
|---|---:|---|
| 시장 방향성 | 18.0/20 | `reasons` |
| 시장 확산력 | 14/20 | `reasons` |
| 수급 | 5/20 | `reasons` |
| 변동성/리스크 | 6/20 | `reasons` |
| 시장 스타일 | 10/10 | `reasons` |
| 데이터 신뢰도 | 10/10 | `reasons` |

## 3. STEP2 포트폴리오 시나리오 표시

신규 필드:

```json
etf_strategy.portfolio_scenarios
```

표시 요청:

| 항목 | 표시 내용 |
|---|---|
| `scenario` | A/B 구분 |
| `name` | 보수안/조건부 공격안 |
| `basis` | 적용 등급 기준 |
| `etf_policy` | ETF 운용 정책 |
| `stock_policy` | 주식 운용 정책 |
| `stock_weight_range_pct` | 주식 비중 범위 |
| `activation_condition` | 적용 조건 |

현재 예시:

- A안: 보수안, 4등급 중립 상단, 주식 10~20%
- B안: 조건부 공격안, 5등급 우호적 관찰 하단, 주식 20~35%

## 4. STEP3 E-series ETF 시나리오별 해석

신규 필드:

```json
etf_strategy.e_series_scenario_reference
```

표시 요청:

- A안에서는 E-series를 S6 방어 배분 대체 근거로 쓰지 않음
- B안에서는 위험선호 회복 확인 시 ETF 노출 조정 참고자료로 사용
- `public_recommendation_allowed`가 `false`이면 공개 추천이 아니라 참고 정보로 표시

## 5. STEP4 주식 후보 시나리오별 판단

신규 필드:

```json
stock_strategy.scenario_summary
stock_strategy.candidates[].scenario_decisions
```

표시 요청:

### 5.1 요약 영역

`stock_strategy.scenario_summary`를 사용해 A/B안별 후보 분포를 표시해 주십시오.

예:

- A안 보수안: 보류/관찰 8개, 소액/관찰 2개
- B안 조건부 공격안: 조건부 소액검토 5개, 조건부 관찰 3개, 추격 보류 2개

### 5.2 종목 테이블

기존 주식 후보 테이블에 아래 컬럼을 추가해 주십시오.

| 신규 컬럼 | 원천 |
|---|---|
| A안 판단 | `scenario_decisions` 중 `scenario=A`의 `decision` |
| A안 비중 | `scenario_decisions` 중 `scenario=A`의 `max_weight_hint` |
| A안 조건 | `scenario_decisions` 중 `scenario=A`의 `activation_condition` |
| B안 판단 | `scenario_decisions` 중 `scenario=B`의 `decision` |
| B안 비중 | `scenario_decisions` 중 `scenario=B`의 `max_weight_hint` |
| B안 조건 | `scenario_decisions` 중 `scenario=B`의 `activation_condition` |

모바일 화면에서는 A/B 판단을 접이식 상세 영역으로 표시해도 됩니다.

## 6. STEP5 시나리오별 검증 조건

신규 필드:

```json
stock_strategy.validation_scenarios
```

표시 요청:

- A안 검증 조건
- B안 검증 조건

각 `checks` 배열을 bullet 목록으로 표시해 주십시오.

## 7. STEP6 최종 포트폴리오 전략

신규 필드:

```json
final_portfolio_strategy
```

표시 요청:

- `step1_rating`
- `step1_score`
- `default_scenario`
- `conditional_scenario`
- `transition_conditions`
- `conclusion`

표시 방식:

- 기본안: A안 보수안
- 조건부안: B안 조건부 공격안
- 전환조건: 외국인/프로그램 매도 완화, 기관 매수 유지, 후보 종목 가격 과열 완화, 환율/금리 리스크 완화
- 최종 결론 문구 표시

## 8. 후방 호환성

아래 필드가 없을 경우 기존 화면 방식으로 fallback 처리해 주십시오.

- `market_risk.step1_v2`
- `etf_strategy.portfolio_scenarios`
- `stock_strategy.candidates[].scenario_decisions`
- `final_portfolio_strategy`

즉, 신규 데이터가 없는 과거 JSON은 기존 단일 판단 화면으로 표시되어야 합니다.

## 9. QA 확인 항목

- 투자 포트폴리오 페이지에서 STEP1 6개 축 점수가 표시되는지 확인
- A안/B안 포트폴리오 시나리오가 표시되는지 확인
- E-series가 공개 추천이 아닌 참고 정보로 표시되는지 확인
- 주식 후보 테이블에 A안/B안 판단이 표시되는지 확인
- STEP6 최종 포트폴리오에 기본안, 조건부안, 전환조건이 표시되는지 확인
- 기존 JSON 구조에서도 페이지가 깨지지 않는지 확인

## 10. 완료 기준

- redbot.co.kr 투자 포트폴리오 페이지에서 최신 JSON의 신규 시나리오 구조가 정상 표시됨
- 모바일/데스크톱에서 종목 테이블이 깨지지 않음
- 기존 단일 판단 구조 JSON에 대한 fallback 동작 확인
- QS 작업 완료 후 QuantAnalysis 쓰레드에 반영 완료 사실 공유
