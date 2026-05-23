# QuantService 작업요청서: redbot.co.kr 투자 포트폴리오 페이지

## 목적
redbot.co.kr에 `투자 포트폴리오` 페이지를 추가하고, QuantAnalysis가 매일 생성하는 포트폴리오 판단 데이터를 표시한다.

## 데이터 원천
- DB: `D:\QuantAnalysis\analysis.db`
  - 실행 이력: `portfolio_runs` (`as_of_date`, `run_time`, `run_session` 기준)
  - 단계별 판단: `portfolio_process_steps`
  - 단계별 상세 설명: `portfolio_step_details`
  - ETF 배분: `portfolio_etf_holdings`
  - 주식 후보: `portfolio_stock_candidates`
- 최신 JSON: `D:\QuantAnalysis\outputs\investment_portfolio_latest.json`
- 최신 Markdown: `D:\QuantAnalysis\docs\portfolio\investment_portfolio_latest.md`
- 일자별 JSON: `D:\QuantAnalysis\outputs\investment_portfolio_YYYYMMDD.json`

## 페이지 구성
1. 상단 요약
   - 기준일, 생성시각, 시장판단 배지
   - 현재 결론: ETF 방어 배분 중심, 주식은 제한 비중
2. 단계별 판단
   - 시장 위험 판단
   - ETF 전략 선택
   - E-series ETF 참고
   - 주식 모델 후보 점검
   - 정성 분석과 최신 수급 확인
   - 최종 포트폴리오 판단
3. ETF 전략 테이블
   - 코드, 종목명, 역할, 비중, 리밸런싱 기준일
4. 주식 후보 테이블
   - 코드, 종목명, 모델군, 선정일, 최신가, 당일등락, 외국인/기관 수급, 판단
5. 리스크 뉴스와 고지
   - 주요 리스크 헤드라인
   - "본 자료는 매수/매도 권유가 아님" 고지

## 표시 규칙
- `market_risk.rating`이 `Defensive Caution`이면 방어형 색상 배지를 사용한다.
- `etf_strategy.selected_model`은 오늘의 ETF 우선 모델로 표시한다.
- `e_series_reference.public_recommendation_allowed=false`이면 E-series는 공개 추천이 아니라 참고/관찰 정보로만 표시한다.
- `stock_strategy.live_data.status`가 `snapshot_confirmed`가 아니면 최신 수급 미확인 경고를 표시한다.
- `decision` 값이 `추격 보류`, `보류`이면 매수 후보처럼 강조하지 않는다.

## 갱신 방식
현재 단계에서는 자동 스케줄러를 등록하지 않는다.
사용자가 QuantAnalysis 쓰레드에 투자분석 실행을 요청하면 아래 명령으로 산출물을 생성한다.

```powershell
D:\QuantAnalysis\run_daily_investment_portfolio.ps1
```

QuantService는 우선 `analysis.db`의 최신 실행 데이터를 읽고, 필요 시 `investment_portfolio_latest.json`을 fallback으로 사용한다.
하루에 여러 번 실행될 수 있으므로 최신 판단은 `portfolio_runs.run_id` 또는 `run_time`의 최댓값 기준으로 조회한다.

## 금지사항
- QuantService 구현은 QuantService 쓰레드에서만 수행한다.
- 이 QuantAnalysis 쓰레드에서 redbot.co.kr 또는 `D:\QuantService` 파일을 직접 수정하지 않는다.

## 완료 기준
- redbot.co.kr에 `투자 포트폴리오` 페이지가 생성된다.
- 기준일, 시장판단, ETF 배분, 주식 후보 판단이 JSON 기준으로 표시된다.
- 모바일/데스크톱에서 표가 읽기 쉽게 표시된다.
- 최신 데이터 미수집 시 fallback 상태가 명확히 표시된다.
