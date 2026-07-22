/**
 * R11-S5-1 Visual Pipeline node.data.config normalize helpers.
 */
import type { Node } from "@xyflow/react";
import type {
  VisualPipelineConfigValidationStatus,
  VisualPipelineNodeConfig,
  VisualPipelineNodeConfigValidation,
  VisualPipelineNodeConfigValues,
  VisualPipelineNodeData,
} from "@/types/visualPipeline";
import {
  VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
  getDefaultConfigValues,
  getPlaceholderConfigValues,
  isSecretConfigField,
} from "@/utils/visualPipelineConfigRegistry";

const CONFIG_META_KEYS = new Set(["schema_version", "values", "validation"]);

const SECRET_INLINE_KEY_PATTERN =
  /^(api[_-]?key|apikey|token|password|secret|authorization|auth[_-]?token|bearer)$/i;

export function defaultConfigValidation(): VisualPipelineNodeConfigValidation {
  return {
    status: "NOT_VALIDATED",
    last_validated_at: null,
    issue_count: 0,
  };
}

function normalizeValidationStatus(
  status: string | undefined,
): VisualPipelineConfigValidationStatus {
  if (status === "VALID") return "OK";
  if (status === "INVALID") return "ERROR";
  if (
    status === "NOT_VALIDATED" ||
    status === "OK" ||
    status === "WARNING" ||
    status === "ERROR" ||
    status === "STALE"
  ) {
    return status;
  }
  return "NOT_VALIDATED";
}

function mergeValidation(raw: unknown): VisualPipelineNodeConfigValidation {
  const base = defaultConfigValidation();
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return base;
  const v = raw as Record<string, unknown>;
  return {
    status: normalizeValidationStatus(v.status as string | undefined),
    last_validated_at: (v.last_validated_at as string | null | undefined) ?? base.last_validated_at,
    issue_count: typeof v.issue_count === "number" ? v.issue_count : base.issue_count,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasStructuredValues(obj: Record<string, unknown>): boolean {
  return "values" in obj && obj.values !== undefined && isRecord(obj.values);
}

function isLegacyFlatConfig(raw: unknown): boolean {
  if (!isRecord(raw)) return false;
  if (hasStructuredValues(raw)) return false;
  if (Object.keys(raw).length === 0) return true;
  if ("schema_version" in raw || "validation" in raw) return !("values" in raw);
  return true;
}

export function isNormalizedNodeConfig(value: unknown): value is VisualPipelineNodeConfig {
  if (!isRecord(value)) return false;
  if (!("values" in value) || !isRecord(value.values)) return false;
  return true;
}

export function normalizeNodeConfig(
  raw: unknown,
  componentType?: string,
): VisualPipelineNodeConfig {
  const validation = defaultConfigValidation();

  if (raw == null) {
    return {
      schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
      values: componentType ? getDefaultConfigValues(componentType) : {},
      validation,
    };
  }

  if (!isRecord(raw)) {
    return {
      schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
      values: {},
      validation,
    };
  }

  if (hasStructuredValues(raw)) {
    return {
      schema_version:
        typeof raw.schema_version === "string"
          ? raw.schema_version
          : raw.schema_version == null
            ? null
            : VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
      values: { ...(raw.values as Record<string, unknown>) },
      validation: mergeValidation(raw.validation),
    };
  }

  if ("schema_version" in raw || "validation" in raw) {
    const values: VisualPipelineNodeConfigValues = {};
    for (const [key, val] of Object.entries(raw)) {
      if (!CONFIG_META_KEYS.has(key)) values[key] = val;
    }
    return {
      schema_version: typeof raw.schema_version === "string" ? raw.schema_version : null,
      values,
      validation: mergeValidation(raw.validation),
    };
  }

  if (isLegacyFlatConfig(raw)) {
    return {
      schema_version: null,
      values: { ...raw },
      validation,
    };
  }

  return {
    schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
    values: {},
    validation,
  };
}

export function normalizeNodeDataConfig(
  nodeData: Record<string, unknown> | undefined | null,
  componentType?: string,
): VisualPipelineNodeConfig {
  const raw = nodeData?.config;
  return normalizeNodeConfig(raw, componentType ?? String(nodeData?.component_type ?? ""));
}

export function createDefaultNodeConfig(
  componentType: string,
  options?: { includeSchemaVersion?: boolean },
): VisualPipelineNodeConfig {
  const includeSchemaVersion = options?.includeSchemaVersion ?? true;
  return {
    ...(includeSchemaVersion ? { schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION } : { schema_version: null }),
    values: getDefaultConfigValues(componentType),
    validation: defaultConfigValidation(),
  };
}

export function ensureNodeConfig(node: Node, componentType?: string): VisualPipelineNodeConfig {
  const ctype = componentType ?? String(node.type ?? node.data?.component_type ?? "");
  return normalizeNodeConfig(node.data?.config, ctype);
}

export function withUpdatedNodeConfig(
  node: Node,
  valuesOrPatch: VisualPipelineNodeConfigValues | ((prev: VisualPipelineNodeConfigValues) => VisualPipelineNodeConfigValues),
): Node {
  const ctype = String(node.type ?? node.data?.component_type ?? "");
  const current = normalizeNodeConfig(node.data?.config, ctype);
  const nextValues =
    typeof valuesOrPatch === "function" ? valuesOrPatch(current.values) : { ...current.values, ...valuesOrPatch };
  return {
    ...node,
    data: {
      ...node.data,
      config: {
        ...current,
        values: nextValues,
      },
    },
  };
}

/** Apply values patch and reset validation cache (R11-S5-2+). */
export function applyNodeConfigPatch(node: Node, patch: Record<string, unknown>): Node {
  const ctype = String(node.type ?? node.data?.component_type ?? "");
  const updated = withUpdatedNodeConfig(node, (prev) => {
    const next = { ...prev, ...patch };
    for (const [key, val] of Object.entries(patch)) {
      if (val === undefined) delete next[key];
    }
    return next;
  });
  const config = normalizeNodeConfig(updated.data?.config, ctype);
  return {
    ...updated,
    data: {
      ...updated.data,
      config: {
        ...config,
        schema_version: config.schema_version ?? VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
        validation: defaultConfigValidation(),
      },
    },
  };
}

/** Detect secret-like keys/values. S5-1: prepare only — does not mutate unless caller applies. */
export function sanitizeConfigValuesForGraph(
  componentType: string,
  values: VisualPipelineNodeConfigValues,
): { values: VisualPipelineNodeConfigValues; warnings: string[] } {
  const warnings: string[] = [];
  const out: VisualPipelineNodeConfigValues = { ...values };

  for (const [key, val] of Object.entries(out)) {
    if (isSecretConfigField(componentType, key)) {
      if (typeof val === "string" && val.length > 0 && !key.endsWith("_ref") && key !== "credential_ref") {
        warnings.push(`Field "${key}" looks like a secret reference field with inline value`);
      }
      continue;
    }
    if (SECRET_INLINE_KEY_PATTERN.test(key)) {
      warnings.push(`Field "${key}" matches secret-like key pattern (inline storage discouraged)`);
    }
    if (typeof val === "string" && /^(Bearer\s|Basic\s)/i.test(val)) {
      warnings.push(`Field "${key}" contains auth header-like value`);
    }
  }

  return { values: out, warnings };
}

export function hasConfigValues(config: VisualPipelineNodeConfig): boolean {
  return Object.keys(config.values ?? {}).length > 0;
}

export function formatNodeConfigPreviewJson(node: Node, componentType?: string): string {
  const ctype = componentType ?? String(node.type ?? node.data?.component_type ?? "");
  const normalized = normalizeNodeConfig(node.data?.config, ctype);
  const payload = hasConfigValues(normalized)
    ? normalized
    : createDefaultNodeConfig(ctype, { includeSchemaVersion: true });
  return JSON.stringify(payload, null, 2);
}

export function formatPlaceholderConfigJson(componentType: string): string {
  const values = getPlaceholderConfigValues(componentType);
  return JSON.stringify(
    {
      schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
      values,
      validation: defaultConfigValidation(),
    },
    null,
    2,
  );
}

/** Sample S5-0 config for E2E / fixtures (4-node MVP). */
export function buildMvpSampleNodeConfigs(): Record<string, VisualPipelineNodeConfig> {
  return {
    "e2e-cron": createDefaultNodeConfig("VP_CRON_SCHEDULE"),
    "e2e-rest": createDefaultNodeConfig("VP_REST_API_SOURCE"),
    "e2e-transform": createDefaultNodeConfig("VP_TRANSFORM"),
    "e2e-load": createDefaultNodeConfig("VP_UPSERT_LOAD"),
  };
}

export type { VisualPipelineNodeData };

/** Aggregate CONFIG-phase issues into node.data.config.validation cache (R11-S5-5). */
export function applyConfigValidationCache(
  nodes: Node[],
  issues: Array<{
    phase?: string;
    node_id?: string;
    severity?: string;
  }>,
  validatedAt: string = new Date().toISOString(),
): Node[] {
  const byNode = new Map<string, Array<{ severity?: string }>>();
  for (const issue of issues) {
    if (issue.phase !== "CONFIG" || !issue.node_id) continue;
    const list = byNode.get(issue.node_id) ?? [];
    list.push(issue);
    byNode.set(issue.node_id, list);
  }

  return nodes.map((node) => {
    const ctype = String(node.type ?? node.data?.component_type ?? "");
    const config = normalizeNodeConfig(node.data?.config, ctype);
    const nodeIssues = byNode.get(node.id) ?? [];
    let status: VisualPipelineConfigValidationStatus = "OK";
    if (nodeIssues.some((i) => i.severity === "ERROR")) status = "ERROR";
    else if (nodeIssues.some((i) => i.severity === "WARNING")) status = "WARNING";

    return {
      ...node,
      data: {
        ...node.data,
        config: {
          ...config,
          validation: {
            status,
            issue_count: nodeIssues.length,
            last_validated_at: validatedAt,
          },
        },
      },
    };
  });
}

/** Map CONFIG field_key → warning message for the selected node (R11-S5-5). */
export function fieldWarningsFromConfigIssues(
  issues: Array<{
    phase?: string;
    node_id?: string;
    field_key?: string;
    severity?: string;
    message?: string;
  }>,
  nodeId: string | null | undefined,
): Record<string, string> {
  if (!nodeId) return {};
  const ranked: Record<string, { message: string; rank: number }> = {};
  const rank = (s?: string) => (s === "ERROR" ? 3 : s === "WARNING" ? 2 : 1);
  for (const issue of issues) {
    if (issue.phase !== "CONFIG" || issue.node_id !== nodeId || !issue.field_key || !issue.message) {
      continue;
    }
    const nextRank = rank(issue.severity);
    const prev = ranked[issue.field_key];
    if (!prev || nextRank >= prev.rank) {
      ranked[issue.field_key] = { message: issue.message, rank: nextRank };
    }
  }
  const out: Record<string, string> = {};
  for (const [key, val] of Object.entries(ranked)) {
    out[key] = val.message;
  }
  return out;
}
