import type { Edge, Node } from "@xyflow/react";
import type { StandardDatasetColumnInput } from "@/types/standardDatasets";
import { ensureNodeConfig } from "@/utils/visualPipelineNodeConfig";
import { findUpstreamTransformForUpsert, parsePortHandleId } from "@/utils/visualPipelineGraph";

/** Align with StandardDatasetWizard DATA_TYPE_OPTIONS. */
export const STANDARD_DATASET_DATA_TYPE_OPTIONS = [
  "VARCHAR",
  "TEXT",
  "INTEGER",
  "BIGINT",
  "NUMERIC",
  "BOOLEAN",
  "DATE",
  "TIMESTAMP",
  "TIMESTAMPTZ",
  "JSONB",
] as const;

export type StandardDatasetDataType = (typeof STANDARD_DATASET_DATA_TYPE_OPTIONS)[number];

export const TRANSFORM_COLUMN_PROPOSAL_HINT =
  "현재 연결된 Transform 노드의 출력 구조를 기준으로 컬럼 초안을 제안합니다. 생성 전 컬럼명과 타입을 확인해 주세요.";

export const TRANSFORM_COLUMN_PROPOSAL_UNAVAILABLE =
  "현재 Upsert 노드에 연결된 Transform 출력 정보를 찾을 수 없습니다. 컬럼을 수동으로 입력하거나, Transform 노드를 연결한 뒤 다시 시도해 주세요.";

export type ProposedColumnDraft = {
  column_name: string;
  data_type: StandardDatasetDataType;
  required: boolean;
  description?: string;
  sort_order?: number;
};

export type TransformColumnProposalResult =
  | {
      ok: true;
      source: "target_schema_preview" | "mapping_config" | "transform_type_fallback";
      transform_type: string;
      transform_node_id: string;
      columns: ProposedColumnDraft[];
    }
  | {
      ok: false;
      reason: string;
    };

function normalizeDataType(value: string | undefined, columnName: string): StandardDatasetDataType {
  const raw = String(value || "").trim().toUpperCase();
  if ((STANDARD_DATASET_DATA_TYPE_OPTIONS as readonly string[]).includes(raw)) {
    return raw as StandardDatasetDataType;
  }
  const name = columnName.toLowerCase();
  if (name.endsWith("_at") || name.includes("timestamp") || name === "observed_at" || name === "measured_at") {
    return "TIMESTAMPTZ";
  }
  if (name.startsWith("is_") || name.endsWith("_yn")) return "BOOLEAN";
  if (name === "raw_json" || name.endsWith("_json")) return "JSONB";
  if (name.includes("hour") && !name.includes("holiday")) return "INTEGER";
  if (
    name.includes("demand") ||
    name.includes("value") ||
    name.includes("temperature") ||
    name.includes("humidity") ||
    name.includes("precipitation") ||
    name.includes("pressure") ||
    name.includes("radiation") ||
    name.includes("speed")
  ) {
    return "NUMERIC";
  }
  if (name.endsWith("_id") || name.endsWith("_code") || name.includes("name")) return "VARCHAR";
  return "VARCHAR";
}

function dedupeColumns(columns: ProposedColumnDraft[]): ProposedColumnDraft[] {
  const seen = new Set<string>();
  const out: ProposedColumnDraft[] = [];
  for (const col of columns) {
    const key = col.column_name.trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push({ ...col, column_name: col.column_name.trim(), sort_order: out.length });
  }
  return out;
}

function resolveOutputField(config: Record<string, unknown>, key: string, fallback: string): string {
  const v = config[key];
  return typeof v === "string" && v.trim() ? v.trim() : fallback;
}

function col(
  column_name: string,
  data_type: StandardDatasetDataType,
  description: string,
  required = false,
): ProposedColumnDraft {
  return {
    column_name,
    data_type: normalizeDataType(data_type, column_name),
    required,
    description,
  };
}

function parseSchemaPreviewColumns(preview: unknown): ProposedColumnDraft[] | null {
  if (!preview || typeof preview !== "object" || Array.isArray(preview)) return null;
  const obj = preview as Record<string, unknown>;
  const raw = obj.columns ?? obj.fields ?? obj.schema;
  if (!Array.isArray(raw)) return null;
  const columns: ProposedColumnDraft[] = [];
  for (const item of raw) {
    if (typeof item === "string" && item.trim()) {
      columns.push(col(item.trim(), "VARCHAR", "target_schema_preview"));
      continue;
    }
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const name = String(row.column_name ?? row.name ?? row.field ?? "").trim();
    if (!name) continue;
    const type = normalizeDataType(
      typeof row.data_type === "string" ? row.data_type : typeof row.type === "string" ? row.type : undefined,
      name,
    );
    columns.push({
      column_name: name,
      data_type: type,
      required: Boolean(row.required),
      description: typeof row.description === "string" ? row.description : "target_schema_preview",
    });
  }
  return columns.length ? dedupeColumns(columns) : null;
}

function wideHourToLongColumns(mappingConfig: Record<string, unknown>): ProposedColumnDraft[] {
  const cfg = mappingConfig;
  return dedupeColumns([
    col(resolveOutputField(cfg, "value_output_field", "heat_demand"), "NUMERIC", "WIDE_HOUR_TO_LONG value output", true),
    col(resolveOutputField(cfg, "measured_at_output_field", "measured_at"), "TIMESTAMPTZ", "WIDE_HOUR_TO_LONG measured_at", true),
    col(resolveOutputField(cfg, "entity_id_output_field", "entity_id"), "VARCHAR", "WIDE_HOUR_TO_LONG entity_id", true),
    col(resolveOutputField(cfg, "entity_code_output_field", "site_id"), "VARCHAR", "WIDE_HOUR_TO_LONG site_id"),
    col(resolveOutputField(cfg, "external_code_output_field", "external_node_id"), "VARCHAR", "WIDE_HOUR_TO_LONG external_node_id"),
    col(resolveOutputField(cfg, "external_name_output_field", "external_node_name"), "VARCHAR", "WIDE_HOUR_TO_LONG external_node_name"),
    col("source_system", "VARCHAR", "WIDE_HOUR_TO_LONG source_system"),
    col("source_operation_id", "VARCHAR", "WIDE_HOUR_TO_LONG source_operation_id"),
    col("raw_date", "VARCHAR", "WIDE_HOUR_TO_LONG raw_date"),
    col("raw_hour", "INTEGER", "WIDE_HOUR_TO_LONG raw_hour"),
    col("raw_json", "JSONB", "WIDE_HOUR_TO_LONG raw_json"),
  ]);
}

function asosHourlyColumns(): ProposedColumnDraft[] {
  return dedupeColumns([
    col("station_code", "VARCHAR", "ASOS_HOURLY_TO_CANONICAL station_code", true),
    col("observed_at", "TIMESTAMPTZ", "ASOS_HOURLY_TO_CANONICAL observed_at", true),
    col("temperature", "NUMERIC", "ASOS_HOURLY_TO_CANONICAL temperature"),
    col("humidity", "NUMERIC", "ASOS_HOURLY_TO_CANONICAL humidity"),
    col("wind_speed", "NUMERIC", "ASOS_HOURLY_TO_CANONICAL wind_speed"),
    col("precipitation", "NUMERIC", "ASOS_HOURLY_TO_CANONICAL precipitation"),
    col("pressure", "NUMERIC", "ASOS_HOURLY_TO_CANONICAL pressure"),
    col("sunshine_duration", "NUMERIC", "ASOS_HOURLY_TO_CANONICAL sunshine_duration"),
    col("solar_radiation", "NUMERIC", "ASOS_HOURLY_TO_CANONICAL solar_radiation"),
    col("weather_condition", "VARCHAR", "ASOS_HOURLY_TO_CANONICAL weather_condition"),
    col("source_system", "VARCHAR", "ASOS_HOURLY_TO_CANONICAL source_system"),
    col("source_operation_id", "VARCHAR", "ASOS_HOURLY_TO_CANONICAL source_operation_id"),
    col("raw_json", "JSONB", "ASOS_HOURLY_TO_CANONICAL raw_json"),
  ]);
}

function calendarSpecialDayColumns(): ProposedColumnDraft[] {
  return dedupeColumns([
    col("calendar_date", "DATE", "CALENDAR_SPECIAL_DAY_TO_DATE calendar_date", true),
    col("holiday_name", "VARCHAR", "CALENDAR_SPECIAL_DAY_TO_DATE holiday_name"),
    col("special_day_type", "VARCHAR", "CALENDAR_SPECIAL_DAY_TO_DATE special_day_type"),
    col("special_day_name", "VARCHAR", "CALENDAR_SPECIAL_DAY_TO_DATE special_day_name"),
    col("is_public_holiday", "BOOLEAN", "CALENDAR_SPECIAL_DAY_TO_DATE is_public_holiday"),
    col("is_holiday", "BOOLEAN", "CALENDAR_SPECIAL_DAY_TO_DATE is_holiday"),
    col("raw_json", "JSONB", "CALENDAR_SPECIAL_DAY_TO_DATE raw_json"),
  ]);
}

function calendarDateToHourColumns(): ProposedColumnDraft[] {
  return dedupeColumns([
    col("measured_at", "TIMESTAMPTZ", "CALENDAR_DATE_TO_HOUR measured_at", true),
    col("calendar_date", "DATE", "CALENDAR_DATE_TO_HOUR calendar_date", true),
    col("hour", "INTEGER", "CALENDAR_DATE_TO_HOUR hour", true),
    col("year", "INTEGER", "CALENDAR_DATE_TO_HOUR year"),
    col("month", "INTEGER", "CALENDAR_DATE_TO_HOUR month"),
    col("day", "INTEGER", "CALENDAR_DATE_TO_HOUR day"),
    col("day_of_week", "INTEGER", "CALENDAR_DATE_TO_HOUR day_of_week"),
    col("is_weekend", "BOOLEAN", "CALENDAR_DATE_TO_HOUR is_weekend"),
    col("is_holiday", "BOOLEAN", "CALENDAR_DATE_TO_HOUR is_holiday"),
    col("is_public_holiday", "BOOLEAN", "CALENDAR_DATE_TO_HOUR is_public_holiday"),
    col("is_workday", "BOOLEAN", "CALENDAR_DATE_TO_HOUR is_workday"),
    col("season", "VARCHAR", "CALENDAR_DATE_TO_HOUR season"),
    col("holiday_name", "VARCHAR", "CALENDAR_DATE_TO_HOUR holiday_name"),
    col("special_day_type", "VARCHAR", "CALENDAR_DATE_TO_HOUR special_day_type"),
    col("special_day_name", "VARCHAR", "CALENDAR_DATE_TO_HOUR special_day_name"),
  ]);
}

function fallbackColumnsForTransformType(
  transformType: string,
  mappingConfig: Record<string, unknown>,
): ProposedColumnDraft[] | null {
  switch (transformType) {
    case "WIDE_HOUR_TO_LONG":
      return wideHourToLongColumns(mappingConfig);
    case "ASOS_HOURLY_TO_CANONICAL":
      return asosHourlyColumns();
    case "CALENDAR_SPECIAL_DAY_TO_DATE":
      return calendarSpecialDayColumns();
    case "CALENDAR_DATE_TO_HOUR":
      return calendarDateToHourColumns();
    default:
      return null;
  }
}

function getTransformValues(transformNode: Node): Record<string, unknown> {
  const componentType = String(transformNode.type ?? transformNode.data?.component_type ?? "VP_TRANSFORM");
  return ensureNodeConfig(transformNode, componentType).values;
}

export function proposeTransformOutputColumns(
  upsertNodeId: string,
  nodes: Node[],
  edges: Edge[],
): TransformColumnProposalResult {
  const upstream = findUpstreamTransformForUpsert(upsertNodeId, nodes, edges);
  if (!upstream) {
    return { ok: false, reason: TRANSFORM_COLUMN_PROPOSAL_UNAVAILABLE };
  }

  const { transformNode } = upstream;
  const values = getTransformValues(transformNode);
  const transformType = String(values.transform_type || "").trim().toUpperCase();
  if (!transformType || transformType === "NONE") {
    return { ok: false, reason: TRANSFORM_COLUMN_PROPOSAL_UNAVAILABLE };
  }

  const mappingConfig =
    values.mapping_config && typeof values.mapping_config === "object" && !Array.isArray(values.mapping_config)
      ? (values.mapping_config as Record<string, unknown>)
      : {};

  const previewCols = parseSchemaPreviewColumns(values.target_schema_preview);
  if (previewCols?.length) {
    return {
      ok: true,
      source: "target_schema_preview",
      transform_type: transformType,
      transform_node_id: transformNode.id,
      columns: previewCols,
    };
  }

  if (
    transformType === "WIDE_HOUR_TO_LONG" &&
    Object.keys(mappingConfig).some((k) => k.endsWith("_output_field"))
  ) {
    return {
      ok: true,
      source: "mapping_config",
      transform_type: transformType,
      transform_node_id: transformNode.id,
      columns: wideHourToLongColumns(mappingConfig),
    };
  }

  const fallback = fallbackColumnsForTransformType(transformType, mappingConfig);
  if (fallback?.length) {
    return {
      ok: true,
      source: "transform_type_fallback",
      transform_type: transformType,
      transform_node_id: transformNode.id,
      columns: fallback,
    };
  }

  return { ok: false, reason: TRANSFORM_COLUMN_PROPOSAL_UNAVAILABLE };
}

export function proposedColumnsToCreatePayload(columns: ProposedColumnDraft[]): StandardDatasetColumnInput[] {
  return columns
    .filter((c) => c.column_name.trim())
    .map((c, idx) => ({
      column_name: c.column_name.trim(),
      data_type: c.data_type,
      required: c.required,
      description: c.description?.trim() || undefined,
      sort_order: idx,
      primary_key: false,
    }));
}

/** For tests: detect REST raw_rows direct connection (no proposal). */
export function isRestDirectUpsertInput(upsertNodeId: string, nodes: Node[], edges: Edge[]): boolean {
  const inbound = edges.filter((e) => e.target === upsertNodeId);
  for (const edge of inbound) {
    const data = (edge.data ?? {}) as Record<string, unknown>;
    const dataType = String(data.data_type || "").toUpperCase();
    const sourcePort =
      typeof data.source_port === "string"
        ? data.source_port
        : parsePortHandleId(edge.sourceHandle).portName;
    const sourceNode = nodes.find((n) => n.id === edge.source);
    if (!sourceNode) continue;
    const componentType = String(sourceNode.type ?? sourceNode.data?.component_type ?? "");
    if (componentType === "VP_REST_API_SOURCE" && (sourcePort === "raw_rows" || dataType === "RAW_ROWS")) {
      return true;
    }
  }
  return false;
}
