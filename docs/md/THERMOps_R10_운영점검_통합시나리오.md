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
6. 미매핑 ND_ID 수집 확인
7. secret 미노출 확인

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

## 7) 배포 전 체크리스트
1. R10-S7 통합 테스트 PASS
2. model/quick regression PASS
3. frontend build/check-pages PASS
4. 운영 seed 업무 샘플 없음 확인
5. 마스킹 정책 검증(serviceKey/API Key 원문 미노출)
6. 배포 시 migration 실행 및 backend/frontend 재기동

