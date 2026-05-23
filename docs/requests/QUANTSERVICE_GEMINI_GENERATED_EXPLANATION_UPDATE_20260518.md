# QuantService 수정 작업요청서: Gemini 생성형 포트폴리오 해설 반영

## 목적
`투자 포트폴리오` 페이지의 모델 분포/선정 이유 설명을 고정 문구가 아닌 Gemini 생성형 해설로 표시한다.

## 배경
QuantAnalysis 파이프라인이 최신 투자분석 실행 시 Gemini API를 호출해 시장상황, 모델 분포, 종목 후보, 수급 정보를 기반으로 설명을 생성하도록 개선되었다.

## 데이터 원천
우선 DB를 사용한다.

- DB: `D:\QuantAnalysis\analysis.db`
- 최신 실행: `portfolio_runs.run_id = max(run_id)`
- 테이블: `portfolio_model_explanations`

주요 필드:
- `section_title`
- `summary`
- `model_roles_json`
- `why_now_json`
- `interpretation_json`
- `conclusion`
- `generation_method`
- `generation_model`
- `generation_status`
- `narrative_focus`

주식 후보 모델 표시 필드:
- 테이블: `portfolio_stock_candidates`
- `model_display`: 사용자 화면 표시용 모델명. 예: `I-STOCK / S2 / S2_PIT`
- `model_display_codes`: 표시용 모델 코드 CSV. 예: `I-STOCK,S2,S2_PIT`
- `model_ids`: 내부 원천 모델 ID. 예: `I-STOCK-STRONG-RSI-V01,S2,S2_PIT_V01`

Fallback:
- `D:\QuantAnalysis\outputs\investment_portfolio_latest.json`
- 필드: `model_concentration_explanation`

## 페이지 반영 위치
기존 `단계별 상세 설명` 아래, `시장 위험` 또는 `ETF 전략` 위에 배치한다.

섹션 제목은 고정하지 말고 `section_title` 값을 그대로 사용한다.

## 렌더링 규칙
1. `generation_method = gemini` 및 `generation_status = ok`
   - Gemini 생성형 해설로 표시한다.
   - 관리자 화면에는 `generation_model`, `narrative_focus`를 확인 가능하게 표시한다.
   - 일반 사용자 화면에는 생성 메타정보를 노출하지 않는다.
2. `generation_method != gemini` 또는 `generation_status != ok`
   - fallback 해설로 표시한다.
   - 관리자 화면에는 fallback 상태를 표시한다.
3. `model_roles_json`
   - 모델명, 쉬운 이름, 후보 개수/비율, 설명을 표시한다.
4. `why_now_json`
   - “지금 이런 결과가 나온 이유” 목록으로 표시한다.
5. `interpretation_json`
   - “투자 해석” 목록으로 표시한다.
6. `conclusion`
   - 섹션 하단 결론으로 표시한다.
7. 주식 후보 표의 모델 컬럼
   - `model_display`를 우선 표시한다.
   - `model_display`가 없을 때만 `model_ids` 또는 기존 모델군 필드로 fallback한다.
   - `I`, `S` 같은 전략군만 표시하지 않는다.

## 주의 문구
해설이 생성형이더라도 다음 의미가 유지되어야 한다.

- 모델 선정은 매수 추천이 아니다.
- 포트폴리오 판단은 시장위험, ETF 전략, 종목별 수급을 함께 반영한다.
- 사용자 화면에서는 투자 권유처럼 보이는 문구를 추가하지 않는다.

## 최신 검증 상태
QuantAnalysis 최신 실행 기준:

- run_id: `13`
- `generation_method`: `gemini`
- `generation_model`: `gemini-2.5-flash`
- `generation_status`: `ok`
- 생성형 섹션 제목: `약세장 속 펀더멘털 우량주의 변동성 관리`

## 완료 기준
- redbot.co.kr `투자 포트폴리오` 페이지에 Gemini 생성형 해설이 표시된다.
- 섹션 제목과 문장은 DB/JSON에서 받은 값을 그대로 사용한다.
- 고정된 `I-stock/S2/S2_PIT` 설명 문구를 하드코딩하지 않는다.
- 관리자 화면에서 생성 방식과 상태를 확인할 수 있다.
