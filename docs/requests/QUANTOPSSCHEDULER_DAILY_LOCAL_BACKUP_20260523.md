# QuantOpsScheduler 작업요청서: QuantAnalysis 일일 로컬 백업

## 목적

`D:\QuantAnalysis`의 코드, 문서, DB, 산출물을 매일 1회 로컬 백업한다.

## 실행 명령

```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantAnalysis\backup_quantanalysis_local.ps1
```

## 백업 위치

- 기본 위치: `D:\QuantBackup\QuantAnalysis`
- 백업 폴더명: `QuantAnalysis-yyyyMMdd-HHmmss`
- manifest: 각 백업 폴더의 `backup_manifest.json`

## 포함 대상

- 코드/스크립트
- `docs`
- `requests`
- `outputs`
- `analysis.db`
- CSV 등 로컬 분석 입력/산출물

## 제외 대상

- `.git`
- `__pycache__`
- `_tmp`
- `backups`

## 실행 주기

- 매일 1회
- 권장 시각: KST `23:40`
- QuantOpsScheduler에서 실행

## 보존 정책

- 기본 보존 기간: 30일
- 30일 초과 `QuantAnalysis-*` 백업 폴더는 자동 삭제

## 정상 완료 기준

- stdout에 `status=ok`
- `destination=...` 출력
- `backup_manifest.json` 생성

## 실패 알림 기준

- robocopy exit code `8` 이상
- 백업 폴더 생성 실패
- manifest 생성 실패
- 2일 연속 백업 실패

## 주의사항

- 이 요청은 git push 백업이 아니라 로컬 파일 백업이다.
- 기존 `QUANTOPSSCHEDULER_DAILY_GIT_BACKUP_20260523.md` 요청은 사용하지 않는다.
