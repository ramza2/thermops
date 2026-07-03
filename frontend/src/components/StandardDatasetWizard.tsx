import { useState } from "react";
import {
  createPhysicalTable,
  createStandardDatasetType,
  previewCreateTable,
  suggestTableName,
  updateStandardDatasetType,
  validateDatasetDefinition,
} from "@/api/standardDatasets";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import type { StandardDatasetColumnInput } from "@/types/standardDatasets";

const CATEGORY_OPTIONS = [
  { value: "FACT", label: "FACT" },
  { value: "MASTER", label: "MASTER" },
  { value: "MAPPING", label: "MAPPING" },
  { value: "TRANSACTION", label: "TRANSACTION" },
  { value: "TIME_SERIES", label: "TIME_SERIES" },
  { value: "EVENT", label: "EVENT" },
  { value: "CUSTOM", label: "CUSTOM" },
];

const DATA_TYPE_OPTIONS = [
  { value: "VARCHAR", label: "VARCHAR" },
  { value: "TEXT", label: "TEXT" },
  { value: "INTEGER", label: "INTEGER" },
  { value: "BIGINT", label: "BIGINT" },
  { value: "NUMERIC", label: "NUMERIC" },
  { value: "DOUBLE", label: "DOUBLE" },
  { value: "BOOLEAN", label: "BOOLEAN" },
  { value: "DATE", label: "DATE" },
  { value: "TIMESTAMP", label: "TIMESTAMP" },
  { value: "TIMESTAMPTZ", label: "TIMESTAMPTZ" },
  { value: "JSONB", label: "JSONB" },
];

const ROLE_OPTIONS = [
  { value: "", label: "(없음)" },
  { value: "ENTITY_KEY", label: "ENTITY_KEY" },
  { value: "TIME_KEY", label: "TIME_KEY" },
  { value: "TARGET", label: "TARGET" },
  { value: "NUMERIC_INPUT", label: "NUMERIC_INPUT" },
  { value: "CATEGORICAL_INPUT", label: "CATEGORICAL_INPUT" },
  { value: "JOIN_KEY", label: "JOIN_KEY" },
];

const EMPTY_COL: StandardDatasetColumnInput = {
  column_name: "",
  data_type: "VARCHAR",
  data_length: 100,
  required: false,
  primary_key: false,
  unique: false,
  default_column_role: "",
};

interface WizardProps {
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
}

export function StandardDatasetWizard({ open, onClose, onCompleted }: WizardProps) {
  const { showToast } = useToast();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [datasetId, setDatasetId] = useState("");
  const [basic, setBasic] = useState({
    dataset_type_code: "",
    dataset_type_name: "",
    description: "",
    category: "FACT",
    target_table: "",
  });
  const [columns, setColumns] = useState<StandardDatasetColumnInput[]>([{ ...EMPTY_COL }]);
  const [validation, setValidation] = useState<{ valid?: boolean; errors?: { code: string; message: string }[]; warnings?: { code: string; message: string }[] } | null>(null);
  const [sqlPreview, setSqlPreview] = useState("");
  const [confirmCreate, setConfirmCreate] = useState(false);

  const reset = () => {
    setStep(0);
    setDatasetId("");
    setBasic({ dataset_type_code: "", dataset_type_name: "", description: "", category: "FACT", target_table: "" });
    setColumns([{ ...EMPTY_COL }]);
    setValidation(null);
    setSqlPreview("");
    setConfirmCreate(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const suggestName = async (code: string) => {
    if (!code.trim()) return;
    try {
      const res = await suggestTableName(code);
      setBasic((b) => ({ ...b, target_table: res.physical_table_name }));
    } catch {
      setBasic((b) => ({ ...b, target_table: `std_${code.toLowerCase().replace(/[^a-z0-9_]+/g, "_")}` }));
    }
  };

  const saveDraft = async (): Promise<string | null> => {
    if (!basic.dataset_type_code.trim() || !basic.dataset_type_name.trim() || !basic.target_table.trim()) {
      showToast("warning", "코드, 이름, 물리 테이블명을 입력하세요.");
      return null;
    }
    setSaving(true);
    try {
      const payloadCols = columns.filter((c) => c.column_name.trim());
      if (datasetId) {
        await updateStandardDatasetType(datasetId, { ...basic, columns: payloadCols });
        return datasetId;
      }
      const created = await createStandardDatasetType({
        ...basic,
        dataset_type_code: basic.dataset_type_code.toUpperCase(),
        status: "DRAFT",
        managed_table: true,
        mapping_supported: false,
        columns: payloadCols,
      });
      setDatasetId(created.dataset_type_id);
      return created.dataset_type_id;
    } catch {
      showToast("error", "DRAFT 저장에 실패했습니다.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const runValidate = async () => {
    const id = await saveDraft();
    if (!id) return;
    setSaving(true);
    try {
      const res = await validateDatasetDefinition(id);
      setValidation(res);
      if (res.valid) {
        showToast("success", "검증을 통과했습니다.");
        setStep(3);
      } else {
        showToast("warning", "검증 오류가 있습니다.");
      }
    } catch {
      showToast("error", "검증 요청에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const runPreview = async () => {
    const id = datasetId || (await saveDraft());
    if (!id) return;
    setSaving(true);
    try {
      const res = await previewCreateTable(id);
      setSqlPreview(res.sql_preview || "");
      setValidation(res);
      if (res.valid) setStep(4);
      else showToast("warning", "SQL Preview 생성 전 검증 오류가 있습니다.");
    } catch {
      showToast("error", "SQL Preview 생성에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const runCreate = async () => {
    if (!confirmCreate) {
      showToast("warning", "생성 확인에 체크하세요.");
      return;
    }
    const id = datasetId || (await saveDraft());
    if (!id) return;
    setSaving(true);
    try {
      await createPhysicalTable(id, true);
      showToast("success", "물리 테이블이 생성되었습니다.");
      handleClose();
      onCompleted();
    } catch {
      showToast("error", "물리 테이블 생성에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const stepTitle = ["1. 기본 정보", "2. 컬럼 정의", "3. 검증", "4. SQL Preview", "5. 생성 확인"][step];

  return (
    <Modal
      open={open}
      title={`표준 데이터셋 생성 Wizard — ${stepTitle}`}
      onClose={handleClose}
      size="xl"
      footer={
        <>
          {step > 0 && step < 5 && (
            <Button variant="secondary" onClick={() => setStep((s) => Math.max(0, s - 1))}>이전</Button>
          )}
          {step === 0 && (
            <Button onClick={async () => { if (await saveDraft()) setStep(1); }} disabled={saving}>
              다음: 컬럼 정의
            </Button>
          )}
          {step === 1 && (
            <Button onClick={() => setStep(2)} disabled={saving}>다음: 검증</Button>
          )}
          {step === 2 && (
            <Button onClick={() => void runValidate()} disabled={saving}>{saving ? "검증 중..." : "검증 실행"}</Button>
          )}
          {step === 3 && (
            <Button onClick={() => void runPreview()} disabled={saving}>{saving ? "생성 중..." : "SQL Preview"}</Button>
          )}
          {step === 4 && (
            <Button onClick={() => void runCreate()} disabled={saving || !confirmCreate}>
              {saving ? "생성 중..." : "물리 테이블 생성"}
            </Button>
          )}
          <Button variant="secondary" onClick={handleClose}>닫기</Button>
        </>
      }
    >
      <div className="space-y-4 text-sm">
        <p className="text-xs text-slate-500">
          SQL은 시스템이 안전하게 생성하며 직접 수정·실행할 수 없습니다. Wizard 생성 테이블은 <code>std_</code> prefix를 사용합니다.
        </p>

        {step === 0 && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">dataset_code</label>
              <TextInput
                value={basic.dataset_type_code}
                onChange={(v) => {
                  setBasic({ ...basic, dataset_type_code: v });
                  void suggestName(v);
                }}
                placeholder="customer_transaction"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">dataset_name</label>
              <TextInput value={basic.dataset_type_name} onChange={(v) => setBasic({ ...basic, dataset_type_name: v })} />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-slate-500 mb-1">physical_table_name (std_ prefix)</label>
              <TextInput value={basic.target_table} onChange={(v) => setBasic({ ...basic, target_table: v.toLowerCase() })} />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">category</label>
              <SelectInput value={basic.category} onChange={(v) => setBasic({ ...basic, category: v })} options={CATEGORY_OPTIONS} />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">description</label>
              <TextInput value={basic.description} onChange={(v) => setBasic({ ...basic, description: v })} />
            </div>
          </div>
        )}

        {step === 1 && (
          <div>
            <div className="flex justify-between mb-2">
              <span className="text-xs text-slate-500">컬럼 정의</span>
              <Button variant="ghost" onClick={() => setColumns([...columns, { ...EMPTY_COL }])}>컬럼 추가</Button>
            </div>
            {columns.map((col, idx) => (
              <div key={idx} className="grid grid-cols-6 gap-2 mb-2 items-end">
                <TextInput value={col.column_name} onChange={(v) => { const c = [...columns]; c[idx] = { ...c[idx], column_name: v }; setColumns(c); }} placeholder="column_name" />
                <SelectInput value={col.data_type || "VARCHAR"} onChange={(v) => { const c = [...columns]; c[idx] = { ...c[idx], data_type: v }; setColumns(c); }} options={DATA_TYPE_OPTIONS} />
                <TextInput value={String(col.data_length ?? "")} onChange={(v) => { const c = [...columns]; c[idx] = { ...c[idx], data_length: v ? Number(v) : undefined }; setColumns(c); }} placeholder="length" />
                <SelectInput value={col.default_column_role || ""} onChange={(v) => { const c = [...columns]; c[idx] = { ...c[idx], default_column_role: v }; setColumns(c); }} options={ROLE_OPTIONS} />
                <label className="text-xs flex items-center gap-2">
                  <input type="checkbox" checked={!!col.primary_key} onChange={(e) => { const c = [...columns]; c[idx] = { ...c[idx], primary_key: e.target.checked }; setColumns(c); }} />
                  PK
                </label>
                <label className="text-xs flex items-center gap-2">
                  <input type="checkbox" checked={!!col.required} onChange={(e) => { const c = [...columns]; c[idx] = { ...c[idx], required: e.target.checked }; setColumns(c); }} />
                  NOT NULL
                </label>
              </div>
            ))}
          </div>
        )}

        {step === 2 && (
          <div className="text-xs text-slate-600">
            <p>Backend 검증을 실행하면 테이블명·컬럼명·데이터 타입·중복 여부를 확인합니다.</p>
            {validation?.errors?.length ? (
              <ul className="mt-2 text-red-700 list-disc pl-4">
                {validation.errors.map((e) => <li key={e.code}>{e.message}</li>)}
              </ul>
            ) : null}
          </div>
        )}

        {step >= 3 && (
          <div>
            {validation?.warnings?.length ? (
              <ul className="text-xs text-amber-700 list-disc pl-4 mb-2">
                {validation.warnings.map((w) => <li key={w.code}>{w.message}</li>)}
              </ul>
            ) : null}
            <pre className="text-xs bg-slate-900 text-slate-100 p-3 rounded overflow-x-auto whitespace-pre-wrap">{sqlPreview || "SQL Preview를 생성하세요."}</pre>
            {step === 4 && (
              <label className="mt-3 flex items-center gap-2 text-xs">
                <input type="checkbox" checked={confirmCreate} onChange={(e) => setConfirmCreate(e.target.checked)} />
                위 SQL로 물리 테이블을 생성합니다.
              </label>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}