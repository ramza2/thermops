import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import {
  acknowledgeIncident,
  createAlertRule,
  createNotificationChannel,
  createNotificationRecipient,
  getNotificationSummary,
  listAlertRules,
  listIncidents,
  listNotificationChannels,
  listNotificationDeliveries,
  listNotificationEvents,
  listNotificationRecipients,
  resolveIncident,
  retryNotificationDelivery,
  testNotificationChannel,
} from "@/api/notifications";
import { Button } from "@/components/Button";
import { Column, DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { EMPTY_MESSAGES, HELP_TEXTS, PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import type { AlertRule, Incident, NotificationChannel, NotificationDelivery, NotificationEvent, NotificationRecipient } from "@/types/notification";

type Tab = "incidents" | "events" | "rules" | "channels" | "recipients" | "deliveries" | "help";

export default function NotificationsPage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("incidents");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [recipients, setRecipients] = useState<NotificationRecipient[]>([]);
  const [deliveries, setDeliveries] = useState<NotificationDelivery[]>([]);
  const [detail, setDetail] = useState<Incident | null>(null);
  const [channelModal, setChannelModal] = useState(false);
  const [ruleModal, setRuleModal] = useState(false);
  const [channelForm, setChannelForm] = useState({ channel_name: "", channel_type: "MOCK" });
  const [ruleForm, setRuleForm] = useState({
    rule_name: "",
    event_source: "SYSTEM",
    event_type: "SCHEDULE_RUN_FAILED",
    min_severity: "WARNING",
    dedup_window_minutes: 30,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, inc, ev, ru, ch, rc, dl] = await Promise.all([
        getNotificationSummary(),
        listIncidents(),
        listNotificationEvents(),
        listAlertRules(),
        listNotificationChannels(),
        listNotificationRecipients(),
        listNotificationDeliveries(),
      ]);
      setSummary(s as unknown as Record<string, unknown>);
      setIncidents(inc);
      setEvents(ev);
      setRules(ru);
      setChannels(ch);
      setRecipients(rc);
      setDeliveries(dl);
    } catch (e) {
      setError(e instanceof Error ? e.message : "조회에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const incidentColumns: Column<Incident & Record<string, unknown>>[] = [
    { key: "title", header: "제목" },
    { key: "severity", header: "심각도", render: (r) => <StatusBadge status={r.severity} /> },
    { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status} /> },
    { key: "occurrence_count", header: "발생 횟수" },
    { key: "last_occurred_at", header: "최근 발생", render: (r) => r.last_occurred_at?.slice(0, 19) || "-" },
    {
      key: "actions",
      header: "처리",
      render: (r) => (
        <div className="flex gap-1">
          <Button variant="secondary" onClick={() => setDetail(r)}>상세</Button>
          {r.status === "OPEN" && (
            <Button variant="secondary" onClick={() => void acknowledgeIncident(r.incident_id).then(() => load())}>장애 확인</Button>
          )}
          {r.status !== "RESOLVED" && (
            <Button variant="secondary" onClick={() => void resolveIncident(r.incident_id, { resolution_note: "운영자 해결" }).then(() => load())}>장애 해결</Button>
          )}
        </div>
      ),
    },
  ];

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader title={PAGE_TITLES.notifications} description={PAGE_DESCRIPTIONS.notifications} />
      <p className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded p-2 mb-4">{HELP_TEXTS.notificationIntro}</p>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="border rounded p-3 bg-white"><p className="text-xs text-slate-500">미해결 장애</p><p className="text-xl font-semibold">{String(summary.open_incident_count ?? 0)}</p></div>
          <div className="border rounded p-3 bg-white"><p className="text-xs text-slate-500">긴급/오류</p><p className="text-xl font-semibold">{String((summary.severity_counts as Record<string, number> | undefined)?.CRITICAL ?? 0)} / {String((summary.severity_counts as Record<string, number> | undefined)?.ERROR ?? 0)}</p></div>
          <div className="border rounded p-3 bg-white"><p className="text-xs text-slate-500">알림 이벤트</p><p className="text-xl font-semibold">{String(summary.total_event_count ?? 0)}</p></div>
          <div className="border rounded p-3 bg-white"><p className="text-xs text-slate-500">발송 실패</p><p className="text-xl font-semibold">{String(summary.failed_delivery_count ?? 0)}</p></div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        {[
          ["incidents", "장애 현황"],
          ["events", "알림 이벤트"],
          ["rules", "알림 규칙"],
          ["channels", "알림 채널"],
          ["recipients", "수신 대상"],
          ["deliveries", "발송 이력"],
          ["help", "도움말"],
        ].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id as Tab)} className={`px-3 py-1.5 text-sm rounded border ${tab === id ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white text-slate-600"}`}>{label}</button>
        ))}
        <Button variant="secondary" icon={<RefreshCw className="w-4 h-4" />} onClick={() => void load()}>새로고침</Button>
        {tab === "channels" && <Button icon={<Plus className="w-4 h-4" />} onClick={() => setChannelModal(true)}>채널 등록</Button>}
        {tab === "rules" && <Button icon={<Plus className="w-4 h-4" />} onClick={() => setRuleModal(true)}>규칙 등록</Button>}
      </div>

      {tab === "incidents" && (
        incidents.length ? <DataTable columns={incidentColumns} data={incidents as (Incident & Record<string, unknown>)[]} /> : (
          <div className="border border-dashed rounded p-6 text-sm text-slate-500">{EMPTY_MESSAGES.notificationsIncidents}</div>
        )
      )}
      {tab === "events" && (
        events.length ? <DataTable columns={[
          { key: "event_source", header: "발생 위치" },
          { key: "event_type", header: "유형" },
          { key: "severity", header: "심각도" },
          { key: "title", header: "제목" },
          { key: "occurred_at", header: "발생 시각", render: (r) => r.occurred_at?.slice(0, 19) || "-" },
        ]} data={events as (NotificationEvent & Record<string, unknown>)[]} /> : (
          <div className="border border-dashed rounded p-6 text-sm text-slate-500">{EMPTY_MESSAGES.notificationsEvents}</div>
        )
      )}
      {tab === "rules" && (
        rules.length ? <DataTable columns={[
          { key: "rule_name", header: "규칙명" },
          { key: "event_source", header: "발생 위치" },
          { key: "event_type", header: "유형" },
          { key: "min_severity", header: "최소 심각도" },
          { key: "dedup_window_minutes", header: "중복 알림 억제(분)" },
          { key: "enabled_yn", header: "사용", render: (r) => (r.enabled_yn ? "사용" : "중지") },
        ]} data={rules as (AlertRule & Record<string, unknown>)[]} /> : (
          <div className="border border-dashed rounded p-6 text-sm text-slate-500">{EMPTY_MESSAGES.notificationsRules}</div>
        )
      )}
      {tab === "channels" && (
        channels.length ? <DataTable columns={[
          { key: "channel_name", header: "채널명" },
          { key: "channel_type", header: "유형" },
          { key: "enabled_yn", header: "사용", render: (r) => (r.enabled_yn ? "사용" : "중지") },
          { key: "actions", header: "테스트", render: (r) => <Button variant="secondary" onClick={() => void testNotificationChannel(r.channel_id).then(() => showToast("success", "채널 테스트 완료"))}>테스트</Button> },
        ]} data={channels as (NotificationChannel & Record<string, unknown>)[]} /> : (
          <div className="border border-dashed rounded p-6 text-sm text-slate-500">{EMPTY_MESSAGES.notificationsChannels}</div>
        )
      )}
      {tab === "recipients" && (
        recipients.length ? <DataTable columns={[
          { key: "recipient_name", header: "수신자" },
          { key: "recipient_type", header: "유형" },
          { key: "address_masked", header: "주소(마스킹)" },
          { key: "enabled_yn", header: "사용", render: (r) => (r.enabled_yn ? "사용" : "중지") },
        ]} data={recipients as (NotificationRecipient & Record<string, unknown>)[]} /> : (
          <div className="border border-dashed rounded p-6 text-sm text-slate-500">{EMPTY_MESSAGES.notificationsRecipients}</div>
        )
      )}
      {tab === "deliveries" && (
        deliveries.length ? <DataTable columns={[
          { key: "delivery_status", header: "상태" },
          { key: "severity", header: "심각도" },
          { key: "title", header: "제목" },
          { key: "destination_masked", header: "대상" },
          { key: "sent_at", header: "발송 시각", render: (r) => r.sent_at?.slice(0, 19) || "-" },
          { key: "actions", header: "재시도", render: (r) => r.delivery_status === "FAILED" ? <Button variant="secondary" onClick={() => void retryNotificationDelivery(r.delivery_id).then(() => load())}>재시도</Button> : "-" },
        ]} data={deliveries as (NotificationDelivery & Record<string, unknown>)[]} /> : (
          <div className="border border-dashed rounded p-6 text-sm text-slate-500">{EMPTY_MESSAGES.notificationsDeliveries}</div>
        )
      )}
      {tab === "help" && (
        <div className="text-sm text-slate-600 space-y-2 border rounded p-4 bg-slate-50">
          <p>{HELP_TEXTS.notificationHelp1}</p>
          <p>{HELP_TEXTS.notificationHelp2}</p>
          <p>{HELP_TEXTS.notificationHelp3}</p>
          <p>{HELP_TEXTS.notificationHelp4}</p>
        </div>
      )}

      <Modal open={!!detail} onClose={() => setDetail(null)} title="장애 상세" footer={<Button onClick={() => setDetail(null)}>닫기</Button>}>
        {detail && (
          <div className="text-sm space-y-2">
            <p><strong>제목:</strong> {detail.title}</p>
            <p><strong>상태:</strong> {detail.status}</p>
            <p><strong>심각도:</strong> {detail.severity}</p>
            <p><strong>발생 횟수:</strong> {detail.occurrence_count}</p>
            <p><strong>요약:</strong> {detail.summary || "-"}</p>
          </div>
        )}
      </Modal>

      <Modal open={channelModal} onClose={() => setChannelModal(false)} title="알림 채널 등록" footer={
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={() => setChannelModal(false)}>취소</Button>
          <Button onClick={() => void createNotificationChannel(channelForm).then(() => {
            setChannelModal(false);
            void load();
            showToast("success", "알림 채널이 등록되었습니다.");
          })}>저장</Button>
        </div>
      }>
        <div className="space-y-2">
          <label className="text-xs text-slate-500">채널명</label>
          <TextInput value={channelForm.channel_name} onChange={(v) => setChannelForm({ ...channelForm, channel_name: v })} />
          <label className="text-xs text-slate-500">채널 유형</label>
          <SelectInput value={channelForm.channel_type} onChange={(v) => setChannelForm({ ...channelForm, channel_type: v })} options={[
            { value: "MOCK", label: "MOCK (테스트)" },
            { value: "WEBHOOK", label: "WEBHOOK" },
            { value: "EMAIL", label: "EMAIL" },
          ]} />
        </div>
      </Modal>

      <Modal open={ruleModal} onClose={() => setRuleModal(false)} title="알림 규칙 등록" footer={
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={() => setRuleModal(false)}>취소</Button>
          <Button onClick={() => void createAlertRule({
            ...ruleForm,
            channel_ids_json: channels.slice(0, 1).map((c) => c.channel_id),
            recipient_ids_json: recipients.slice(0, 1).map((r) => r.recipient_id),
          }).then(() => { setRuleModal(false); void load(); showToast("success", "알림 규칙이 등록되었습니다."); })}>저장</Button>
        </div>
      }>
        <div className="space-y-2">
          <label className="text-xs text-slate-500">규칙명</label>
          <TextInput value={ruleForm.rule_name} onChange={(v) => setRuleForm({ ...ruleForm, rule_name: v })} />
          <label className="text-xs text-slate-500">발생 위치</label>
          <TextInput value={ruleForm.event_source} onChange={(v) => setRuleForm({ ...ruleForm, event_source: v })} />
          <label className="text-xs text-slate-500">이벤트 유형</label>
          <TextInput value={ruleForm.event_type} onChange={(v) => setRuleForm({ ...ruleForm, event_type: v })} />
        </div>
      </Modal>
    </div>
  );
}
