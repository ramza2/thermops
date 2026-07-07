import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Link2 } from "lucide-react";
import {
  archiveExternalCodeMapping,
  assignUnmappedCode,
  createExternalCodeMapping,
  getExternalCodeMappingOptions,
  ignoreUnmappedCode,
  listExternalCodeMappings,
  listUnmappedExternalCodes,
  resolveExternalCode,
  searchTargetCandidates,
} from "@/api/externalCodeMappings";
import { extractApiErrorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import {
  EMPTY_MESSAGES,
  HELP_TEXTS,
  PAGE_DESCRIPTIONS,
  PAGE_TITLES,
} from "@/constants/displayLabels";
import type { ExternalCodeMapping, ResolveResult, TargetCandidate, UnmappedExternalCode } from "@/types/externalCodeMappings";
import {
  MAPPING_STATUS_OPTIONS,
  TARGET_TYPE_OPTIONS,
  mappingStatusLabel,
  reviewStatusLabel,
  targetTypeLabel,
} from "@/types/externalCodeMappings";

type Tab = "mappings" | "unmapped" | "resolve" | "help";

const EMPTY_FORM = {
  source_system: "",
  source_operation_id: "",
  external_code_group: "",
  external_code: "",
  external_code_name: "",
  target_type: "PREDICTION_ENTITY",
  target_id: "",
  target_display_name: "",
  mapping_status: "ACTIVE",
  mapping_method: "MANUAL",
  priority: "1",
  valid_from: "",
  valid_to: "",
};

export default function ExternalCodeMappingsPage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("mappings");
  const [mappings, setMappings] = useState<ExternalCodeMapping[]>([]);
  const [unmapped, setUnmapped] = useState<UnmappedExternalCode[]>([]);
  const [options, setOptions] = useState<{ source_systems: string[]; external_code_groups: string[] }>({
    source_systems: [],
    external_code_groups: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [candidates, setCandidates] = useState<TargetCandidate[]>([]);
  const [candidateKeyword, setCandidateKeyword] = useState("");
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignTarget, setAssignTarget] = useState<UnmappedExternalCode | null>(null);
  const [assignForm, setAssignForm] = useState({ target_type: "PREDICTION_ENTITY", target_id: "", target_display_name: "" });
  const [resolveForm, setResolveForm] = useState({
    source_system: "",
    external_code_group: "",
    external_code: "",
    target_type: "",
    at_date: "",
  });
  const [resolveResult, setResolveResult] = useState<ResolveResult | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [m, u, o] = await Promise.all([
        listExternalCodeMappings(),
        listUnmappedExternalCodes(),
        getExternalCodeMappingOptions(),
      ]);
      setMappings(m);
      setUnmapped(u);
      setOptions(o);
    } catch {
      setError("외부 코드 매핑 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const loadCandidates = async (targetType: string, keyword?: string) => {
    try {
      const rows = await searchTargetCandidates(targetType, keyword);
      setCandidates(rows);
    } catch {
      setCandidates([]);
    }
  };

  const handleCreate = async () => {
    setBusy(true);
    try {
      await createExternalCodeMapping({
        ...form,
        source_operation_id: form.source_operation_id || null,
        priority: Number(form.priority) || 1,
        valid_from: form.valid_from || null,
        valid_to: form.valid_to || null,
      });
      showToast("success", "외부 코드 매핑이 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      await load();
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "등록에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleAssign = async () => {
    if (!assignTarget) return;
    setBusy(true);
    try {
      await assignUnmappedCode(assignTarget.unmapped_id, assignForm);
      showToast("success", "미매핑 코드가 내부 대상과 연결되었습니다.");
      setAssignOpen(false);
      setAssignTarget(null);
      await load();
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "연결에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleIgnore = async (row: UnmappedExternalCode) => {
    setBusy(true);
    try {
      await ignoreUnmappedCode(row.unmapped_id, "사용자 무시 처리");
      showToast("success", "미매핑 코드를 무시 처리했습니다.");
      await load();
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "무시 처리에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleResolveTest = async () => {
    setBusy(true);
    try {
      const result = await resolveExternalCode({
        ...resolveForm,
        target_type: resolveForm.target_type || null,
        at_date: resolveForm.at_date || null,
      });
      setResolveResult(result);
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "코드 변환 테스트에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  if (loading && !mappings.length && !unmapped.length) return <LoadingState />;
  if (error && !mappings.length) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader title={PAGE_TITLES.externalCodeMappings} description={PAGE_DESCRIPTIONS.externalCodeMappings} />

      <div className="bg-blue-50 border border-blue-100 rounded p-3 mb-4 text-xs text-blue-900 space-y-1">
        <p>{HELP_TEXTS.externalCodeMappingIntro}</p>
        <p>{HELP_TEXTS.externalCodeNoAutoCreate}</p>
        <p>{HELP_TEXTS.externalCodeNdIdExample}</p>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {[
          ["mappings", "매핑 목록"],
          ["unmapped", "미매핑 코드"],
          ["resolve", "코드 변환 테스트"],
          ["help", "도움말"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id as Tab)}
            className={`px-3 py-1.5 text-sm rounded border ${tab === id ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white text-slate-600"}`}
          >
            {label}
          </button>
        ))}
        {tab === "mappings" && (
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>외부 코드 매핑 등록</Button>
        )}
      </div>

      {tab === "mappings" && (
        mappings.length === 0 ? (
          <div className="text-center py-12 text-slate-500 bg-slate-50 rounded border border-dashed text-sm">
            {EMPTY_MESSAGES.externalCodeMappings}
          </div>
        ) : (
          <DataTable
            columns={[
              { key: "source_system", header: "외부 시스템" },
              { key: "external_code_group", header: "외부 코드 그룹" },
              { key: "external_code", header: "외부 코드" },
              { key: "external_code_name", header: "외부 코드명", render: (r) => String(r.external_code_name || "-") },
              { key: "target_type", header: "내부 연결 대상", render: (r) => targetTypeLabel(String(r.target_type)) },
              { key: "target_display_name", header: "내부 대상명", render: (r) => String(r.target_display_name || r.target_id || "-") },
              { key: "mapping_status", header: "상태", render: (r) => mappingStatusLabel(String(r.mapping_status)) },
              {
                key: "validity",
                header: "유효기간",
                render: (r) => {
                  const from = r.valid_from ? String(r.valid_from) : "";
                  const to = r.valid_to ? String(r.valid_to) : "";
                  return from || to ? `${from || "∞"} ~ ${to || "∞"}` : "-";
                },
              },
              { key: "priority", header: "우선순위" },
              {
                key: "actions",
                header: "작업",
                render: (r) => (
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={() => void archiveExternalCodeMapping(String(r.mapping_id)).then(() => load())}
                  >
                    보관
                  </Button>
                ),
              },
            ]}
            data={mappings as unknown as Record<string, unknown>[]}
          />
        )
      )}

      {tab === "unmapped" && (
        unmapped.length === 0 ? (
          <div className="text-center py-12 text-slate-500 bg-slate-50 rounded border border-dashed text-sm">
            {EMPTY_MESSAGES.unmappedExternalCodes}
          </div>
        ) : (
          <DataTable
            columns={[
              { key: "source_system", header: "외부 시스템" },
              { key: "external_code_group", header: "외부 코드 그룹" },
              { key: "external_code", header: "외부 코드" },
              { key: "external_code_name", header: "외부 코드명", render: (r) => String(r.external_code_name || "-") },
              { key: "seen_count", header: "발견 횟수" },
              { key: "last_seen_at", header: "최근 발견", render: (r) => String(r.last_seen_at || "-").slice(0, 19).replace("T", " ") },
              { key: "review_status", header: "검토 상태", render: (r) => reviewStatusLabel(String(r.review_status)) },
              {
                key: "actions",
                header: "작업",
                render: (r) => {
                  const row = r as unknown as UnmappedExternalCode;
                  return (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        icon={<Link2 className="w-3 h-3" />}
                        onClick={() => {
                          setAssignTarget(row);
                          setAssignForm({
                            target_type: "PREDICTION_ENTITY",
                            target_id: "",
                            target_display_name: "",
                          });
                          void loadCandidates("PREDICTION_ENTITY");
                          setAssignOpen(true);
                        }}
                      >
                        연결
                      </Button>
                      <Button variant="ghost" disabled={busy} onClick={() => void handleIgnore(row)}>무시</Button>
                    </div>
                  );
                },
              },
            ]}
            data={unmapped as unknown as Record<string, unknown>[]}
          />
        )
      )}

      {tab === "resolve" && (
        <div className="bg-white border rounded-lg p-4 max-w-2xl space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-slate-500">외부 시스템</label>
              <TextInput value={resolveForm.source_system} onChange={(v) => setResolveForm({ ...resolveForm, source_system: v })} />
            </div>
            <div>
              <label className="text-xs text-slate-500">외부 코드 그룹</label>
              <TextInput value={resolveForm.external_code_group} onChange={(v) => setResolveForm({ ...resolveForm, external_code_group: v })} />
            </div>
            <div>
              <label className="text-xs text-slate-500">외부 코드</label>
              <TextInput value={resolveForm.external_code} onChange={(v) => setResolveForm({ ...resolveForm, external_code: v })} />
            </div>
            <div>
              <label className="text-xs text-slate-500">내부 연결 대상 (선택)</label>
              <SelectInput
                value={resolveForm.target_type}
                onChange={(v) => setResolveForm({ ...resolveForm, target_type: v })}
                options={[{ value: "", label: "전체" }, ...TARGET_TYPE_OPTIONS]}
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">기준일 (선택)</label>
              <TextInput value={resolveForm.at_date} onChange={(v) => setResolveForm({ ...resolveForm, at_date: v })} placeholder="YYYY-MM-DD" />
            </div>
          </div>
          <Button variant="secondary" onClick={() => void handleResolveTest()} disabled={busy}>코드 변환 테스트</Button>
          {resolveResult && (
            <div className={`border rounded p-3 text-xs ${resolveResult.resolved ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}`}>
              <p><strong>결과:</strong> {resolveResult.resolved ? "변환 성공" : "미매핑"}</p>
              {resolveResult.target_display_name && <p>내부 대상: {resolveResult.target_display_name} ({resolveResult.target_type})</p>}
              {resolveResult.warnings?.map((w) => <p key={w} className="text-amber-800">{w}</p>)}
            </div>
          )}
        </div>
      )}

      {tab === "help" && (
        <div className="bg-slate-50 border rounded-lg p-4 text-sm text-slate-700 space-y-2">
          <p>{HELP_TEXTS.externalCodeMappingIntro}</p>
          <p>{HELP_TEXTS.externalCodeNoAutoCreate}</p>
          <p>{HELP_TEXTS.externalCodeNdIdExample}</p>
          <p>{HELP_TEXTS.externalCodeStableId}</p>
          <p>{HELP_TEXTS.restApiConnectorExternalCodeLink}</p>
          <p>{HELP_TEXTS.externalCodeStationHint}</p>
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="외부 코드 매핑 등록" size="lg">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <label className="text-xs text-slate-500">외부 시스템</label>
            <TextInput value={form.source_system} onChange={(v) => setForm({ ...form, source_system: v })} />
          </div>
          <div>
            <label className="text-xs text-slate-500">API 작업 ID (선택)</label>
            <TextInput value={form.source_operation_id} onChange={(v) => setForm({ ...form, source_operation_id: v })} />
          </div>
          <div>
            <label className="text-xs text-slate-500">외부 코드 그룹</label>
            <TextInput value={form.external_code_group} onChange={(v) => setForm({ ...form, external_code_group: v })} />
          </div>
          <div>
            <label className="text-xs text-slate-500">외부 코드</label>
            <TextInput value={form.external_code} onChange={(v) => setForm({ ...form, external_code: v })} />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-slate-500">외부 코드명</label>
            <TextInput value={form.external_code_name} onChange={(v) => setForm({ ...form, external_code_name: v })} />
          </div>
          <div>
            <label className="text-xs text-slate-500">내부 연결 대상</label>
            <SelectInput
              value={form.target_type}
              onChange={(v) => {
                setForm({ ...form, target_type: v, target_id: "", target_display_name: "" });
                void loadCandidates(v);
              }}
              options={TARGET_TYPE_OPTIONS}
            />
          </div>
          <div>
            <label className="text-xs text-slate-500">내부 대상 검색</label>
            <div className="flex gap-1">
              <TextInput value={candidateKeyword} onChange={setCandidateKeyword} />
              <Button variant="ghost" icon={<Search className="w-4 h-4" />} onClick={() => void loadCandidates(form.target_type, candidateKeyword)} />
            </div>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-slate-500">내부 대상 선택</label>
            <SelectInput
              value={form.target_id}
              onChange={(v) => {
                const c = candidates.find((x) => x.target_id === v);
                setForm({
                  ...form,
                  target_id: v,
                  target_display_name: c?.target_display_name || "",
                });
              }}
              options={[
                { value: "", label: "선택하세요" },
                ...candidates.map((c) => ({
                  value: c.target_id,
                  label: `${c.target_display_name}${c.subtitle ? ` (${c.subtitle})` : ""}`,
                })),
              ]}
            />
          </div>
          <div>
            <label className="text-xs text-slate-500">우선순위</label>
            <TextInput value={form.priority} onChange={(v) => setForm({ ...form, priority: v })} />
          </div>
          <div>
            <label className="text-xs text-slate-500">상태</label>
            <SelectInput value={form.mapping_status} onChange={(v) => setForm({ ...form, mapping_status: v })} options={MAPPING_STATUS_OPTIONS} />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={() => setCreateOpen(false)}>취소</Button>
          <Button onClick={() => void handleCreate()} disabled={busy}>저장</Button>
        </div>
      </Modal>

      <Modal open={assignOpen} onClose={() => setAssignOpen(false)} title="미매핑 코드 연결" size="md">
        {assignTarget && (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-slate-600">
              {assignTarget.source_system} / {assignTarget.external_code_group} / <strong>{assignTarget.external_code}</strong>
            </p>
            <SelectInput
              value={assignForm.target_type}
              onChange={(v) => {
                setAssignForm({ ...assignForm, target_type: v, target_id: "", target_display_name: "" });
                void loadCandidates(v);
              }}
              options={TARGET_TYPE_OPTIONS}
            />
            <SelectInput
              value={assignForm.target_id}
              onChange={(v) => {
                const c = candidates.find((x) => x.target_id === v);
                setAssignForm({
                  ...assignForm,
                  target_id: v,
                  target_display_name: c?.target_display_name || "",
                });
              }}
              options={[
                { value: "", label: "내부 대상 선택" },
                ...candidates.map((c) => ({
                  value: c.target_id,
                  label: `${c.target_display_name}${c.subtitle ? ` (${c.subtitle})` : ""}`,
                })),
              ]}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setAssignOpen(false)}>취소</Button>
              <Button onClick={() => void handleAssign()} disabled={busy || !assignForm.target_id}>연결 저장</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
