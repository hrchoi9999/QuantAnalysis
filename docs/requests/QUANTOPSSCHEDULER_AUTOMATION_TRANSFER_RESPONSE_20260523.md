# QuantOpsScheduler 자동실행 이관 응답서 - QuantAnalysis

## 1. 기본 정보

- 대상 쓰레드/프로젝트명: QuantAnalysis
- 작업 폴더: `D:\QuantAnalysis`
- 담당 목적:
  - Quant 모델 기반 투자 포트폴리오 분석
  - 주식 후보 점검
  - 주식 후보 최신가/등락률/외국인·기관 수급 확인
  - QuantAnalysis 로컬 산출물 백업
- 현재 자동실행 여부: PAUSED / 일부 수동 실행 중
- 기존 자동실행 ID:
  - `quantanalysis`
- 기존 자동실행 상태:
  - Codex cron으로 등록됐으나 Kiwoom API 네트워크 권한 문제로 실패 알림 쓰레드가 생성되어 현재 `PAUSED`
- 중요 운영 원칙:
  - QuantOpsScheduler는 `D:\QuantAnalysis` 내부 파일/DB를 직접 수정하지 않는다.
  - QuantOpsScheduler는 자체 공유 저장소에 자동실행 결과를 저장한다.
  - QuantAnalysis 내부 DB/파일 갱신이 필요하면 QuantAnalysis 쓰레드에 별도 작업요청서를 보낸다.

## 2. 자동실행 작업 목록

### 작업 A

- 작업 이름: QuantAnalysis 장중 주식 후보 최신값 갱신
- 작업 ID 또는 기존 자동실행 ID: `quantanalysis`
- 실행 주기: 10분 간격
- 실행 시간대: 평일 KST `09:00~15:40`
- 실행 조건:
  - 한국 주식시장 장중
  - 주말 제외
  - 휴장일은 한국거래소 캘린더 기준 정상 스킵
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
  - 기존 스크립트 기준:
    - `D:\QuantAnalysis\analysis.db`
    - `portfolio_runs`
    - `portfolio_stock_candidates`
- 쓰는 DB/테이블:
  - 기존 스크립트 기준:
    - `portfolio_stock_live_refresh_runs`
    - `portfolio_stock_live_snapshots`
    - `v_portfolio_stock_live_latest`
    - 최신 `portfolio_stock_candidates` live 필드
  - 이관 후 권장:
    - QuantOpsScheduler는 `D:\QuantAnalysis\analysis.db`에 직접 쓰지 않음
    - Scheduler 공유 저장소에 JSON/JSONL로 저장
- 수정/생성하는 파일:
  - 기존 스크립트는 파일 생성 없음, DB 갱신 중심
  - 이관 후 Scheduler 산출물은 3장 참조
- 외부 API/네트워크 의존성:
  - Kiwoom REST `ka10001`: 최신가/등락률
  - Kiwoom REST `ka10059`: 외국인/기관/개인/연기금 거래금액
  - 네트워크 권한 필요
  - Codex cron 환경에서는 `WinError 10013` 발생
- 정상 완료 판단 기준:
  - `status = ok`
  - `source = kiwoom_rest_ka10001+ka10059`
  - 후보 10개 전부 수집
  - 가격/등락률/외국인/기관 거래금액 null 없음
  - `errors = []`
- 실패 판단 기준:
  - `status != ok`
  - Kiwoom token/API/network 오류
  - 대상 종목 일부 누락
  - 최신 정상 스냅샷이 장중 30분 이상 갱신되지 않음
- 실패 시 사용자에게 알려야 하는 조건:
  - 장중 2회 연속 실패
  - Kiwoom 인증 실패
  - 후보 종목 수 불일치
  - 최신 정상 스냅샷 30분 이상 미갱신
- 평균 실행 시간:
  - 약 6~10초
- 중복 실행 허용 여부:
  - 비허용
  - lock 파일 또는 실행 상태 플래그 필요

### 작업 B

- 작업 이름: QuantAnalysis 일일 로컬 백업
- 작업 ID 또는 기존 자동실행 ID: 신규 등록 요청
- 실행 주기: 매일 1회
- 실행 시간대: KST `23:40` 권장
- 실행 조건:
  - 장중 분석/수집 작업과 겹치지 않는 시간
  - 백업 대상 폴더 접근 가능
- 실행 명령:
  - `powershell -ExecutionPolicy Bypass -File D:\QuantAnalysis\backup_quantanalysis_local.ps1`
- 작업 디렉터리:
  - `D:\QuantAnalysis`
- 사용하는 Python/venv/도구:
  - PowerShell
  - robocopy
- 필요한 입력 파일:
  - `D:\QuantAnalysis\backup_quantanalysis_local.ps1`
- 읽는 DB/테이블:
  - 파일 백업 방식이므로 DB 쿼리 없음
  - `D:\QuantAnalysis\analysis.db` 파일 자체를 백업 대상에 포함
- 쓰는 DB/테이블:
  - 없음
- 수정/생성하는 파일:
  - `D:\QunatBackup\QuantAnalysis-yyyyMMdd-HHmmss`
  - `D:\QunatBackup\QuantAnalysis-yyyyMMdd-HHmmss\backup_manifest.json`
- 외부 API/네트워크 의존성:
  - 없음
- 정상 완료 판단 기준:
  - stdout `status=ok`
  - `destination=...`
  - `backup_manifest.json` 생성
  - robocopy exit code `0~7`
- 실패 판단 기준:
  - robocopy exit code `8` 이상
  - 백업 폴더 생성 실패
  - manifest 생성 실패
- 실패 시 사용자에게 알려야 하는 조건:
  - 백업 실패
  - 2일 연속 백업 실패
  - `D:\QunatBackup` 쓰기 권한 오류
- 평균 실행 시간:
  - 현재 기준 수 초 내외
  - `outputs` 증가에 따라 늘어날 수 있음
- 중복 실행 허용 여부:
  - 비허용
  - 동일 날짜/시간 중복 백업은 가능하지만 불필요

## 3. 최종 산출물 요구사항

### 산출물 A: 주식 후보 장중 최신 스냅샷

- 산출물 이름: QuantAnalysis 주식 후보 장중 최신 스냅샷
- 산출물 형식: JSON + JSONL
- 산출물 현재 위치:
  - 기존: `D:\QuantAnalysis\analysis.db`
  - 기존 최신 뷰: `v_portfolio_stock_live_latest`
- 허브에 공유해야 할 위치:
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-latest.json`
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-history.jsonl`
  - `D:\QuantOpsScheduler\state\run-status\quantanalysis-stock-live-refresh-latest.json`
- 최신 상태 판정 기준:
  - 장중 `fetched_at`이 현재 시각 기준 15분 이내
  - `status = ok`
  - 후보 10개 전부 가격/등락률/외국인/기관 수급 존재
- 보존 기간:
  - history: 90일
  - latest: 최신 1건 유지
  - 실패 로그: 180일
- 후속 소비 쓰레드:
  - QuantAnalysis
  - QuantService
  - 검증/QA 쓰레드
- 후속 소비 방식:
  - QuantAnalysis는 Scheduler 공유 산출물을 read-only로 참조
  - QuantService는 QuantAnalysis 최종 포트폴리오 산출물을 우선 사용
  - Scheduler 원천 스냅샷은 웹 표시 검증 및 장중 최신값 보조 원천으로 사용

### 산출물 B: 일일 로컬 백업

- 산출물 이름: QuantAnalysis 일일 로컬 백업
- 산출물 형식: 폴더 + JSON manifest
- 산출물 현재 위치:
  - `D:\QunatBackup\QuantAnalysis-yyyyMMdd-HHmmss`
- 허브에 공유해야 할 위치:
  - `D:\QuantOpsScheduler\state\run-status\quantanalysis-local-backup-latest.json`
- 최신 상태 판정 기준:
  - 당일 백업 폴더 존재
  - `backup_manifest.json` 존재
  - `robocopy_exit_code < 8`
- 보존 기간:
  - 30일
- 후속 소비 쓰레드:
  - QuantAnalysis
  - 운영자
- 후속 소비 방식:
  - 장애 시 수동 복구용

## 4. 허브 이관 가능 범위

- 장중 주식 후보 최신값 갱신:
  - 선택: 허브가 최종 산출물만 수집
  - 선택: 허브가 읽기만 하고 결과 요약만 저장
  - 권장: Scheduler가 Kiwoom 조회 결과를 자체 공유 저장소에 저장하고, QuantAnalysis는 read-only로 참조
- 일일 로컬 백업:
  - 선택: 허브가 실행 로그만 수집
  - 선택: 허브가 최종 산출물만 수집
  - 권장: Scheduler가 `backup_quantanalysis_local.ps1` 실행만 담당

## 5. 제약 및 주의사항

- 장중/장마감 등 시간 제약:
  - 작업 A: 평일 KST `09:00~15:40`
  - 작업 B: 매일 KST `23:40` 권장
- 휴장일 처리:
  - 작업 A는 휴장일 정상 스킵
  - 작업 B는 휴장일과 무관하게 실행 가능
- 데이터 무결성 조건:
  - 실패한 장중 스냅샷이 최신 정상값을 null로 덮으면 안 됨
  - `status != ok` 스냅샷은 latest로 승격하지 않음
  - 백업은 `.git`, `_tmp`, `__pycache__`, `backups` 제외
- 재실행 시 주의사항:
  - 작업 A는 중복 실행 금지
  - 작업 B는 중복 실행 가능하지만 불필요
- 잠금 파일 또는 동시 실행 방지 장치:
  - 작업 A 권장 lock:
    - `D:\QuantOpsScheduler\state\locks\quantanalysis-stock-live-refresh.lock`
  - 작업 B 권장 lock:
    - `D:\QuantOpsScheduler\state\locks\quantanalysis-local-backup.lock`
- 수동 확인이 필요한 케이스:
  - Kiwoom 인증 실패
  - 2회 연속 API/network 실패
  - 후보 종목 수 불일치
  - 백업 실패
  - `D:\QunatBackup` 쓰기 권한 오류

## 6. 요청하는 통합 자동실행 결과

- 필요한 통합 결과 파일:
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-latest.json`
  - `D:\QuantOpsScheduler\state\shared-data\quantanalysis\stock-live-history.jsonl`
  - `D:\QuantOpsScheduler\state\run-status\quantanalysis-stock-live-refresh-latest.json`
  - `D:\QuantOpsScheduler\state\run-status\quantanalysis-local-backup-latest.json`
- 필요한 대시보드/요약:
  - 작업별 최신 실행시각
  - 작업별 status
  - 최근 10회 성공/실패
  - 장중 최신 스냅샷 지연 여부
  - 마지막 로컬 백업 시각
- 다른 쓰레드가 읽을 표준 파일명:
  - `stock-live-latest.json`
  - `quantanalysis-local-backup-latest.json`
- 알림이 필요한 실패 유형:
  - 장중 최신값 갱신 2회 연속 실패
  - 장중 latest 30분 이상 미갱신
  - Kiwoom 인증 실패
  - 후보 종목 누락
  - 로컬 백업 실패
  - 2일 연속 백업 실패
- 알림이 불필요한 정상 스킵 조건:
  - 작업 A 장외 시간
  - 작업 A 주말/휴장일
  - 작업 B 정상 완료

## 7. 현재 QuantAnalysis 자동화 처리 상태

- 기존 Codex cron 자동화 `quantanalysis`:
  - 현재 `PAUSED`
  - 통합 자동실행 완료 전까지 유지
  - QuantOpsScheduler 완료 고지 후 최종 삭제/중지 예정
- 기존 실패 원인:
  - Codex cron 실행 환경에서 Kiwoom API 네트워크 접근 실패
  - 오류: `WinError 10013`
- 임시 조치:
  - 실패 실행이 최신 후보값을 null로 덮지 않도록 `intraday_live_stock_refresh.py` 수정 완료
  - 실패 스냅샷 null 데이터 제거 완료
  - 마지막 정상 스냅샷 기준으로 최신 후보값 복구 완료
- 마지막 확인된 정상 장중 스냅샷:
  - `refresh_id = 21`
  - `fetched_at = 2026-05-22T13:24:28.738+09:00`
  - `status = ok`
  - `snapshot_rows = 10`
- 마지막 확인된 로컬 백업:
  - `D:\QunatBackup\QuantAnalysis-20260523-105551`

## 8. 명시적으로 자동실행에서 제외할 작업

- `D:\QuantAnalysis\portfolio_pipeline.py`
  - 현재는 사용자가 "투자분석 실행"을 요청할 때 실행하는 수동 분석 파이프라인
  - Scheduler 자동 반복 실행 대상으로 등록하지 않음
  - 향후 종가 후 자동 분석이 필요하면 별도 요청서로 분리

## 9. QuantOpsScheduler에 요청

1. 이 문서를 기준으로 QuantAnalysis 자동실행 작업을 통합 레지스트리에 등록해 주세요.
2. Scheduler는 자체 공유 저장소와 `D:\QunatBackup`에만 write해 주세요.
3. `D:\QuantAnalysis` 내부 DB/파일을 직접 수정하지 말아 주세요.
4. 통합 자동실행이 완성되면 QuantAnalysis 쓰레드에 완료 고지를 보내 주세요.
5. 완료 고지를 받은 뒤 QuantAnalysis 쪽 기존 Codex 자동실행 `quantanalysis`는 최종 중지/삭제하겠습니다.
