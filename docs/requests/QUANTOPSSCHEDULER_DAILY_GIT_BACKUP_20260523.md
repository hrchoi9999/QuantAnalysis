# QuantOpsScheduler 작업요청서: QuantAnalysis 일일 git 백업

## 목적

`D:\QuantAnalysis`의 코드, 문서, 요청서 변경사항을 매일 1회 GitHub 저장소로 백업한다.

## 대상 저장소

- 로컬 저장소: `D:\QuantAnalysis`
- 원격 저장소: `https://github.com/hrchoi9999/QuantAnalysis.git`
- 브랜치: `main`

## 실행 명령

```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantAnalysis\backup_quantanalysis_git.ps1
```

## 권장 실행 주기

- 매일 1회
- 권장 시각: KST `23:30`
- 장중 분석/자동수집 작업과 겹치지 않게 장마감 이후 실행

## 정상 완료 기준

- 변경사항이 없으면:
  - `status=no_changes`
- 변경사항이 있으면:
  - git commit 생성
  - `git push origin main` 성공
  - `status=ok`

## 실패 판단 기준

- git commit 실패
- git push 실패
- 원격 인증 실패
- 저장소 lock 상태
- merge conflict 또는 non-fast-forward 발생

## 알림 기준

사용자 알림 필요:

- push 실패
- 인증 실패
- merge conflict
- 2일 연속 백업 실패

사용자 알림 불필요:

- 변경사항 없음
- 정상 commit/push 완료

## 주의사항

- `analysis.db`, `outputs/`, `_tmp/`, `__pycache__/`는 `.gitignore`로 제외되어야 한다.
- Scheduler는 백업 스크립트 실행만 수행한다.
- Scheduler가 임의로 파일을 수정하거나 git reset/rebase를 수행하면 안 된다.
- non-fast-forward가 발생하면 자동 해결하지 말고 QuantAnalysis 쓰레드에 작업요청서를 보낸다.

## 현재 검증 상태

- 백업 스크립트: `D:\QuantAnalysis\backup_quantanalysis_git.ps1`
- 검증 실행 완료
- 커밋: `3616ce9 Daily QuantAnalysis backup 2026-05-23 10:26`
- GitHub push 완료
