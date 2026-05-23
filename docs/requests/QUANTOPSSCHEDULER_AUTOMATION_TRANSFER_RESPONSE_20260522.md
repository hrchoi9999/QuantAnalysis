# QuantOpsScheduler 자동실행 이관 응답서 - QuantAnalysis

## 1. 기본 정보

- 대상 쓰레드/프로젝트명: QuantAnalysis
- 작업 폴더: `D:\QuantAnalysis`
- 담당 목적: Quant 모델 기반 투자 포트폴리오 분석, 주식 후보 점검, 최신가/등락률/외국인·기관 수급 확인
- 현재 자동실행 여부: PAUSED
- 기존 자동실행 ID: `quantanalysis`
- 기존 자동실행 종류: Codex cron
- 기존 자동실행 상태: 실패 알림 쓰레드가 생성되어 `PAUSED` 처리됨

## 2. 자동실행 작업 목록

### 작업 A

- 작업 이름: QuantAnalysis 장중 주식 후보 최신값 갱신
- 작업 ID 또는 기존 자동실행 ID: `quantanalysis`
- 실행 주기: 장중 10분 간격
- 실행 시간대: 평일 KST `09:00~15:40`
- 실행 조건:
  - 한국 주식시장 장중
  - 주말 제외
  - 휴장일은 별도 캘린더 적용 필요
- 기존 실행 명령:
  - `D:\Quant\venv64\Scripts\python.exe D:\QuantAnalysis\intraday_live_stock_refresh.py`
- 작업 디렉터리:
  - `D:\QuantAnalysis`
- 사용하는 Python/venv/도구:
  - `D:\Quant\venv64\Scripts\python.exe`
  - Kiwoom REST API
  - SQLite
- 필요한 입력 파일:
  - `D:\QuantAnalysis\portfolio_pipeline.py`
  - `D:\QuantAnalysis\intraday_live_stock_refresh.py`
  - `D:\QuantAnalysis\weekly_model_selection_20260301_20260515_full.csv`
  - `D:\Quant\config\kiwoom_54810245_appkey.txt`
  - `D:\Quant\config\kiwoom_54810245_secretkey.txt`
- 읽는 DB/테이블:
  - `D:\QuantAnalysis\analysis.db`
  - `portfolio_runs`
  - `portfolio_stock_candidates`
- 쓰는 DB/테이블:
  - 기존 방식:
    - `D:\QuantAnalysis\analysis.db`
    - `portfolio_stock_live_refresh_runs`
    - `portfolio_stock_live_snapshots`
    - `v_portfolio_stock_live_latest`
    - 최신 `portfolio_stock_candidates`의 live 필드
  - 이관 후 권장 방식:
    - QuantOpsScheduler는 `D:\QuantAnalysis` DB에 직접 write하지 않음
    - Scheduler는 자체 공유 저장소에만 write
- 수정/생성하는 파일:
  - 기존 방식은 파일 생성 없음, DB만 갱신
  - 이관 후 권장 산출물은 아래 3장 참조
- 외부 API/네트워크 의존성:
  - Kiwoom REST `ka10001`: 최신가/등락률
  - Kiwoom REST `ka10059`: 외국인/기관/개인/연기금 거래금액
  - 네트워크 권한 필요
  - Codex cron 환경에서는 `WinError 10013`으로 실패 발생
- 정상 완료 판단 기준:
  - `status = ok`
  - `source = kiwoom_rest_ka10001+ka10059`
  - `snapshot_rows = 10`
  - `updated_candidates = 10`
  - `errors = []`
- 실패 판단 기준:
  - `status != ok`
  - `source is null`
  - `errors`에 Kiwoom token/API/network 오류 존재
  - `snapshot_rows < 대상 종목 수`
- 실패 시 사용자에게 알려야 하는 조건:
  - 장중 실행 시간대에 2회 연속 실패
  - Kiwoom token 실패
  - 대상 종목 일부 누락
  - 최신 스냅샷이 30분 이상 갱신되지 않음
- 알림이 불필요한 조건:
  - 장외 시간 `outside_market_refresh_window`
  - 휴장일 정상 스킵
- 평균 실행 시간:
  - 약 6~10초
- 중복 실행 허용 여부:
  - 비허용 권장
  - 동일 작업은 lock 파일 또는 실행 상태 플래그로 동시 실행 방지 필요

## 3. 최종 산출물 요구사항

### 산출물 A

- 산출물 이름: QuantAnalysis 주식 후보 장중 최신 스냅샷
- 산출물 형식: JSON + SQLite 또는 JSONL
- 산출물 현재 위치:
  - 기존: `D:\QuantAnalysis\analysis.db`
  - 기존 최신 뷰: `v_portfolio_stock_live_latest`
- 허브에 공유해야 할 위치:
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-latest.json`
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-history.jsonl`
  - `D:\QuantOpsScheduler\state\run-status\quantanalysis-stock-live-refresh-latest.json`
- 최신 상태 판정 기준:
  - 장중에는 `fetched_at`이 현재 시각 기준 15분 이내
  - `status = ok`
  - 후보 10개 모두 가격/등락률/외국인/기관 수급 존재
- 보존 기간:
  - 장중 history: 90일
  - latest: 항상 최신 1건
  - 실패 로그: 180일
- 후속 소비 쓰레드:
  - QuantAnalysis
  - QuantService
  - QA/검증 쓰레드가 별도 존재할 경우 해당 쓰레드
- 후속 소비 방식:
  - QuantAnalysis는 Scheduler 공유 산출물을 read-only로 읽어 투자 포트폴리오 판단에 반영
  - QuantService는 QuantAnalysis 최종 산출물을 우선 사용
  - Scheduler 원천 스냅샷은 보조/검증용으로 사용

### 권장 JSON 구조

```json
{
  "job_id": "quantanalysis-stock-live-refresh",
  "as_of_date": "YYYY-MM-DD",
  "fetched_at": "YYYY-MM-DDTHH:mm:ss+09:00",
  "status": "ok",
  "source": "kiwoom_rest_ka10001+ka10059",
  "candidate_count": 10,
  "success_count": 10,
  "error_count": 0,
  "items": [
    {
      "ticker": "005930",
      "name": "삼성전자",
      "model_display": "I-STOCK / S2_PIT",
      "price": 0,
      "change_pct": 0.0,
      "foreign_net_억원": 0.0,
      "institution_net_억원": 0.0,
      "individual_net_억원": 0.0,
      "pension_net_억원": 0.0,
      "source": "kiwoom_rest_ka10001+ka10059"
    }
  ],
  "errors": []
}
```

## 4. 허브 이관 가능 범위

- 선택: 허브가 최종 산출물만 수집
- 선택: 허브가 읽기만 하고 결과 요약만 저장

권장 방식:

1. QuantOpsScheduler가 Kiwoom API를 직접 호출해 Scheduler 공유 저장소에 최신 스냅샷 저장
2. QuantOpsScheduler는 `D:\QuantAnalysis` 내부 DB/파일을 직접 수정하지 않음
3. QuantAnalysis는 필요 시 Scheduler 공유 산출물을 읽어 자체 DB/포트폴리오 산출물에 반영
4. QuantAnalysis 내부 DB 갱신이 필요하면 QuantAnalysis 쓰레드에 별도 작업요청서를 보냄

## 5. 제약 및 주의사항

- 장중/장마감 등 시간 제약:
  - 평일 KST `09:00~15:40`
  - 장마감 후에는 종가 확정 파이프라인과 분리
- 휴장일 처리:
  - 한국거래소 휴장일 캘린더 필요
  - 휴장일은 정상 스킵으로 처리하고 사용자 알림 불필요
- 데이터 무결성 조건:
  - 실패 실행이 최신 정상값을 null로 덮으면 안 됨
  - `status != ok`인 스냅샷은 latest로 승격하지 않음
  - 종목 수가 기준 후보 수보다 적으면 partial로 관리
- 재실행 시 주의사항:
  - 동일 시간대 중복 실행 방지
  - Kiwoom rate limit 대비 0.2초 이상 호출 간격 및 429 재시도 필요
- 잠금 파일 또는 동시 실행 방지 장치:
  - 권장 lock 파일: `D:\QuantOpsScheduler\state\locks\quantanalysis-stock-live-refresh.lock`
  - lock TTL: 5분
- 수동 확인이 필요한 케이스:
  - Kiwoom token 실패
  - 2회 연속 network/API 실패
  - 후보 종목 수 불일치
  - 30분 이상 latest 미갱신

## 6. 요청하는 통합 자동실행 결과

- 필요한 통합 결과 파일:
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-latest.json`
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-history.jsonl`
  - `D:\QuantOpsScheduler\state\run-status\quantanalysis-stock-live-refresh-latest.json`
- 필요한 대시보드/요약:
  - 최신 실행시각
  - status
  - 대상 종목 수
  - 성공/실패 종목 수
  - 마지막 정상 갱신 후 경과시간
  - 최근 10회 실패율
- 다른 쓰레드가 읽을 표준 파일명:
  - `stock-live-latest.json`
- 알림이 필요한 실패 유형:
  - 장중 2회 연속 실패
  - latest 정상 스냅샷 30분 이상 미갱신
  - Kiwoom 인증 실패
  - 대상 종목 누락
- 알림이 불필요한 정상 스킵 조건:
  - 장외 시간
  - 주말
  - 휴장일

## 7. 현재 QuantAnalysis 자동화 처리 상태

- 기존 Codex cron 자동화 `quantanalysis`는 현재 `PAUSED`
- 실패 원인:
  - Codex cron 실행 환경에서 Kiwoom API 네트워크 접근 실패
  - 오류: `WinError 10013`
- 임시 조치:
  - 실패 실행이 최신 후보값을 null로 덮지 않도록 `intraday_live_stock_refresh.py` 수정 완료
  - 실패 스냅샷 null 데이터 제거 완료
  - 마지막 정상 스냅샷 기준으로 최신 후보값 복구 완료
- 마지막 확인된 정상 스냅샷:
  - `refresh_id = 21`
  - `fetched_at = 2026-05-22T13:24:28.738+09:00`
  - `status = ok`
  - `snapshot_rows = 10`

## 8. QuantOpsScheduler에 요청

1. 위 작업을 통합 자동실행 레지스트리에 등록해 주세요.
2. Scheduler가 자체 공유 저장소에만 write하도록 구성해 주세요.
3. QuantAnalysis 내부 DB/파일 직접 수정은 하지 말아 주세요.
4. 통합 자동실행이 완성되면 QuantAnalysis 쓰레드에 완료 고지를 보내 주세요.
5. 완료 고지를 받은 뒤 QuantAnalysis 쪽 기존 자동실행은 최종 중지/삭제하겠습니다.
