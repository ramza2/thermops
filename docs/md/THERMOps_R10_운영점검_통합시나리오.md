# THERMOps R10 운영점검 / 통합 시나리오 (R10-S7)

## 1) 목적
- R10 계열 기능(REST API Connector, 표준 데이터셋, 예측 대상/기상 매핑, 외부 코드 매핑, Transform, Forecast Provider, 데이터 적재 일정)이 실제 운영 흐름에서 함께 동작하는지 검증한다.
- 신규 기능 대규모 개발이 아니라 운영 점검, 통합 테스트, 회귀 방지, UI/문서 정합성 점검을 수행한다.
- clean seed 0건 정책과 secret masking 정책 준수를 확인한다.

## 2) 사전 조건
- backend/frontend 실행 중
- PostgreSQL 접근 가능
- `python scripts/apply_dev_migrations.py` 완료
- 외부 공공 API 호출 없이 `sample_external` endpoint만 사용

## 3) 통합 시나리오 A~F

### A. Clean 설치 / 빈 화면
1. migration 적용
2. 운영 seed에 업무 샘플 INSERT 없음 확인
3. 주요 R10 테이블 0건 확인
4. 주요 화면 empty state 확인
5. 메뉴 순서/안내 문구 확인

### B. 표준 데이터셋 / 물리 테이블 준비
1. 표준 데이터셋 4종(열수요 long, ASOS, Calendar date/hour) 생성
2. SQL preview 확인
3. 물리 테이블 생성 및 ACTIVE 전환
4. target_table 검증
5. 매핑/동일 컬럼명 준비

### C. 열수요 wide-hour 변환 적재
1. 예측 대상 생성
2. `HEAT_DEMAND_API/NODE` 외부 코드 매핑
3. REST API 작업 + `WIDE_HOUR_TO_LONG` 설정
4. load-preview 변환 건수 확인
5. load-run INSERT 확인
6. 동일 조건 재실행 시 UPSERT/DEDUPLICATE 정책으로 중복 누적 방지 확인(신규 0 또는 갱신/제외 증가)
7. 미매핑 ND_ID 수집 확인
8. secret 미노출 확인

### D. ASOS / Calendar 적재
1. ASOS 관측소 생성
2. ASOS 작업 + `ASOS_HOURLY_TO_CANONICAL` 실행
3. Calendar date 작업 + `CALENDAR_SPECIAL_DAY_TO_DATE` 실행
4. Calendar hour 작업 + `CALENDAR_DATE_TO_HOUR` 실행
5. 월 단위 row count 및 warnings 확인

### E. 데이터 적재 일정
1. schedule 생성 및 `next_run_at` 확인
2. runtime params 템플릿 렌더링/마스킹 확인
3. run-now, run-due 실행
4. `schedule_run.api_load_run_id` 연결 확인
5. event 기록/실패 재시도 확인
6. run-due 재실행 시 적재 방식(write_mode)에 따라 inserted/updated/skipped 변화 확인

### F. Forecast on-demand
1. forecast_ready entity(nx/ny) 생성
2. Provider config 설정
3. preview-input + cache 재사용 확인
4. prediction job(`forecast_provider_enabled=true`) 실행
5. `result_summary.forecast_input_summary`/weather-inputs 확인
6. secret 미노출 확인

## 4) 검증 명령
```bash
python scripts/apply_dev_migrations.py
python scripts/test_r10_operational_integration.py
python scripts/run_regression_tests.py --group model --timeout-scale 2
python scripts/run_regression_tests.py --group quick --timeout-scale 2
cd frontend
npm run build
node scripts/check-pages.mjs
```

## 5) Clean reset 확인 항목
- `tb_data_source` 0건
- `tb_standard_dataset_type` 0건
- `tb_api_connector_operation` 0건
- `tb_api_connector_transform_config` 0건
- `tb_prediction_entity` 0건
- `tb_external_code_mapping` 0건
- `tb_unmapped_external_code` 0건
- `tb_forecast_provider_config` / `tb_forecast_input_snapshot` / `tb_prediction_weather_input` 0건
- `tb_data_load_schedule` / `tb_data_load_schedule_run` / `tb_data_load_schedule_event` 0건

## 6) 실패 시 점검 포인트
- `sample_external` endpoint path/파라미터 오타
- target table ACTIVE/물리 테이블 생성 여부
- 외부 코드 매핑 누락(ND_ID, station_code)
- schedule `next_run_at`/active 상태
- forecast entity readiness(nx/ny) 누락
- 마스킹 검증 시 secret 문자열 직접 포함 여부
- 알림 규칙/채널 등록 여부 (운영 seed 기본값 없음)
- `/notifications` 화면 및 MOCK 채널 테스트 발송

## 7) 배포 전 체크리스트
1. R10-S7 통합 테스트 PASS
2. `python scripts/test_notification_alerting.py` PASS
3. model/quick regression PASS
4. frontend build/check-pages PASS
5. 운영 seed 업무 샘플 없음 확인 (notification 테이블 0건)
6. 마스킹 정책 검증(serviceKey/API Key/notification secret 원문 미노출)
7. 배포 시 migration 실행 및 backend/frontend 재기동
8. write policy/중복 요약 조회 API 동작 확인
9. 알림 / 장애 통보 화면(`/notifications`) clean 상태 확인

## 부록. 시나리오 G — 알림 / 장애 통보 (R10-S9)
1. MOCK 알림 채널·수신 대상·알림 규칙 등록 (`SCHEDULE_RUN_FAILED` 등)
2. `POST /notifications/events/test` 또는 스케줄/API 실패로 이벤트 생성
3. 장애 현황에서 OPEN incident 확인 → 장애 확인 처리 → 장애 해결 처리
4. 발송 이력에서 MOCK `SENT` 또는 `SUPPRESSED` 확인
5. secret probe 문자열이 API 응답/발송 이력에 노출되지 않음 확인

## 부록. 시나리오 H — Run Due Worker 운영 구성 (R10-S10)
1. `python scripts/apply_dev_migrations.py` 로 worker 테이블 적용 확인
2. Traefik: `docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build run-due-worker`
3. `docker compose ... logs run-due-worker` 에서 loop tick·heartbeat 로그 확인
4. 데이터 적재 일정 → **Worker 상태** 탭에서 instance/run/lock 조회 (clean 0건 또는 실행 후 등록)
5. `POST /api/v1/run-due-worker/run-once` (또는 UI **1회 실행**) — fixture 일정만 사용
6. `GET /api/v1/run-due-worker/locks` 로 중복 실행 방지 잠금 확인
7. 연속 실패·STALE 시 `/notifications` 에 RUN_DUE_WORKER 이벤트 확인 (규칙 등록 시)
8. `./scripts/run_due_once.sh` cron 예시 스크립트 존재 확인 (OS cron 자동 등록 없음)

## 부록. 시나리오 I — CRON schedule due / Worker (R10-S11)
1. `python scripts/test_cron_schedule_parser.py` 로 parser/next-run 단위 검증
2. CRON 일정 생성 (`*/5 * * * *`) — next_run_at 자동 계산 확인
3. `POST /data-load-schedules/cron/validate` · `preview-next-run` 으로 다음 실행 예정 미리보기
4. invalid 표현식(`0 0 L * *`, 6-field) 저장 차단 확인
5. `next_run_at`을 과거로 조정 후 `GET /due`에 CRON 포함 확인
6. `run-due` 또는 Worker **1회 실행** 후 schedule_run 생성·next_run_at 미래로 갱신 확인
7. MANUAL은 계속 due 제외, HOURLY/DAILY regression 유지
8. 운영 seed에 CRON 샘플 일정 없음 확인

