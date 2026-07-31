import { useEffect, useState } from "react";
import {
  getVisualPipelineOpsStuckRuns,
  getVisualPipelineOpsSummary,
} from "@/api/visualPipelineOps";
import { useRole } from "@/hooks/useRole";
import {
  buildOpsActionBadgeSummary,
  type OpsActionBadgeSummary,
} from "@/utils/opsActionRequired";

export type UseOpsActionBadgeResult = {
  badge: OpsActionBadgeSummary | null;
  loading: boolean;
  error: boolean;
  enabled: boolean;
  refresh: () => void;
};

/**
 * R11-S8-9-21 / B5: load derived Ops action badge from existing summary + stuck APIs.
 * No polling by default. No notification table / read-unread.
 */
export function useOpsActionBadge(options?: {
  /** Override mock-role gate (default: ADMIN / canViewVpOps). */
  enabled?: boolean;
}): UseOpsActionBadgeResult {
  const { canViewVpOps } = useRole();
  const enabled = options?.enabled ?? canViewVpOps;
  const [badge, setBadge] = useState<OpsActionBadgeSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setBadge(null);
      setLoading(false);
      setError(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(false);

    void (async () => {
      try {
        const [summary, stuck] = await Promise.all([
          getVisualPipelineOpsSummary(),
          getVisualPipelineOpsStuckRuns({ pending_age_seconds: 600, limit: 50 }),
        ]);
        if (cancelled) return;
        setBadge(
          buildOpsActionBadgeSummary({
            summary,
            stuckItems: stuck.items ?? [],
          }),
        );
        setError(false);
      } catch {
        if (cancelled) return;
        setBadge(null);
        setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled, tick]);

  return {
    badge,
    loading,
    error,
    enabled,
    refresh: () => setTick((n) => n + 1),
  };
}
