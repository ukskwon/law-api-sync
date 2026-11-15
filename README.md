# law-api-sync

국가법령정보센터 Open API로 산업안전 관련 법령·고시(regs.json, 95개)의 현행 원문을 매일 받아 두는 개인 학습용 저장소입니다.

- 매일 04:17(KST)에 GitHub Actions가 실행됩니다. Actions 탭에서 "Run workflow"로 바로 돌릴 수도 있습니다.
- 인증값은 저장소 Secrets 의 `LAW_OC` 에만 둡니다. 파일에 적지 않습니다.
- `manifest.json`: 규정별 일련번호·공포일·시행일 / `data/*.json`: 원문 응답 / `report.json`: 이번 실행에서 바뀐 규정과 실패 목록
- 「산업안전 법령 학습 대시보드」의 동기화 작업이 이 저장소를 읽어 개정 여부를 대조합니다.
