# QuantService 추가 작업요청서: 모델 쏠림 설명 영역 추가

## 요청 배경
투자 포트폴리오 페이지에서 현재 주식 후보가 `I-STOCK`, `S2`, `S2_PIT`에 많이 몰려 보인다.
사용자가 "왜 이 모델 종목이 많은가"라는 의문을 갖지 않도록, 모델 쏠림의 이유와 투자 해석을 페이지 안에 설명해야 한다.

## 추가할 영역
영역명은 고정하지 않는다.
QuantAnalysis 파이프라인이 최신 실행 결과를 기준으로 `section_title`을 생성하므로 그 값을 그대로 표시한다.

표시 위치:
- `단계별 상세 설명` 아래
- `시장 위험` 또는 `ETF 전략` 섹션 위

## 데이터 원천
우선 DB를 사용한다.

- DB: `D:\QuantAnalysis\analysis.db`
- 최신 실행 조회 기준: `portfolio_runs.run_id = max(run_id)`
- 테이블: `portfolio_model_explanations`
  - `section_title`
  - `placement`
  - `summary`
  - `model_roles_json`
  - `why_now_json`
  - `interpretation_json`
  - `model_group_counts_json`
  - `model_id_counts_json`
  - `decision_counts_json`
  - `top_models_json`
  - `concentration_ratio_pct`
  - `narrative_focus`
  - `generation_method`
  - `generation_model`
  - `generation_status`
  - `overlap_candidates_json`
  - `conclusion`

Fallback JSON:
- `D:\QuantAnalysis\outputs\investment_portfolio_latest.json`
- 필드: `model_concentration_explanation`

## 렌더링 구성
1. 섹션 제목
2. 요약 문장
3. 모델별 역할
   - 모델명
   - 쉬운 이름
   - 후보 포함 개수/비율
   - 설명
4. 지금 이런 결과가 나온 이유
5. 투자 해석
6. 결론

## 표시 원칙
- 내부 모델명을 숨기지 않는다. 이번 영역은 설명 목적이므로 모델명을 직접 표시한다.
- `I-STOCK/S2/S2_PIT` 문구를 하드코딩하지 않는다.
- 실제 많이 나온 모델 조합은 `top_models_json`과 `model_id_counts_json` 기준으로 표시한다.
- 특정 모델 쏠림이 없으면 파이프라인이 생성한 분산형 설명을 그대로 표시한다.
- `generation_method=gemini`이면 생성형 AI 해설로 표시한다.
- `generation_method=rule_based_dynamic`이면 Gemini 실패/비활성화 fallback으로 표시한다.
- `generation_status`가 `ok`가 아니면 관리자 화면에는 상태를 노출하되, 일반 사용자 화면에는 노출하지 않는다.
- 다만 `선정 = 매수 추천`으로 보이지 않게 한다.
- 문구에는 반드시 다음 의미가 포함되어야 한다.
  - 모델 쏠림 또는 모델 분포는 오류가 아니다.
  - 시장상황, 모델 신호, 수급/가격 조건에 따라 후보 구성이 달라진다.
  - 중복 선정은 관심 우선순위 상승이지 즉시 매수 신호가 아니다.
  - 최종 실행은 시장위험과 당일 수급으로 다시 제한한다.

## 완료 기준
- 투자 포트폴리오 페이지에 모델 분포 설명 영역이 표시된다.
- 실제 많이 나온 모델의 역할 차이가 일반 투자자도 이해 가능하게 표시된다.
- 사용자가 현재 후보 구성이 왜 그렇게 나왔는지 페이지 안에서 이해할 수 있다.
