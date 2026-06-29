# THERMOps P1-4 모델 고도화 정리

P1-4 단계에서 CatBoost 단일 모델과 2-Stage CatBoost 모델을 MLOps 파이프라인에 통합했습니다.

## 추가된 model_type

| algorithm (설정값) | 내부 model_type | Registry 모델명 |
|--------------------|-----------------|-----------------|
| `catboost` | `catboost` | `heat_demand_catboost` |
| `two_stage_catboost` | `two_stage_catboost` | `heat_demand_two_stage_catboost` |

기존 `lightgbm`, `baseline`, `sklearn_gbdt`(fallback)는 그대로 유지됩니다.

## CatBoost 단일 모델

- `ml/models/catboost_model.py` — `CatBoostRegressor` 기반 회귀
- 기본 하이퍼파라미터: `iterations=300`, `learning_rate=0.05`, `depth=6`, `loss_function=RMSE`
- 학습 설정 템플릿: `TRC-TPL-CATBOOST` (Feature Set: `FS-TPL-LAG-ROLL`)
- MLflow: `mlflow.catboost.log_model` (실패 시 sklearn fallback)

## 2-Stage CatBoost

논문 반영 메모의 잔차 보정 구조를 CPU 기반으로 구현했습니다.

```
Stage 1: CatBoostRegressor → target_heat_demand 예측
residual = actual - stage1_pred (train set 기준)
Stage 2: CatBoostRegressor → residual 예측
final_pred = clip(stage1_pred + stage2_residual_pred, min=0)
```

- 구현: `ml/models/two_stage_catboost.py` — `TwoStageCatBoostRegressor`
- 학습 설정 템플릿: `TRC-TPL-TWO-STAGE-CATBOOST` (Feature Set: `FS-TPL-TWO-STAGE`)
- MLflow: wrapper 객체를 `mlflow.sklearn.log_model`로 저장 (Stage1·Stage2 CatBoost 포함)
- 추가 검증 metric: `stage1_validation_mape`, `final_validation_mape`, `residual_mae`

### LightGBM과의 차이

| 항목 | LightGBM (기존) | CatBoost / 2-Stage |
|------|-----------------|---------------------|
| 알고리즘 | GBDT (LightGBM) | CatBoost (ordered boosting) |
| 구조 | 단일 모델 | 2-Stage는 잔차 보정 2단계 |
| 미설치 시 | sklearn_gbdt 자동 fallback | 명시적 오류 (fallback 없음) |
| MLflow flavor | lightgbm / sklearn | catboost / sklearn(wrapper) |

## 학습·예측 연동

- Training: `POST /api/v1/training-jobs` + `config_id` (`TRC-TPL-CATBOOST` 등)
- Prediction: 기존 `prediction_service`와 동일 — `model_loader`가 pyfunc/sklearn/catboost 순으로 로드
- 재학습 후보: source `model_name`에 따라 선호 config 자동 선택 (`heat_demand_catboost` → `TRC-TPL-CATBOOST`)

## 테스트

```powershell
python scripts/test_catboost_training.py
python scripts/test_two_stage_catboost.py
```

테스트는 파이프라인 동작(학습·MLflow·Registry·예측 저장)을 검증하며, 성능 수치는 보장하지 않습니다.

## 제한사항

- GPU 학습 최적화 없음 (CPU 기준)
- 하이퍼파라미터 자동 튜닝(Optuna 등) 없음
- Stage 2 잔차는 **train set prediction 기준** (validation OOF 잔차 미사용)
- categorical feature(`site_id` 등) 자동 처리는 TODO — 현재 numeric 중심
- 예측값은 `max(pred, 0)`으로 clip
- 모델 성능은 데이터·Feature 품질에 따라 달라지며 보장하지 않음
