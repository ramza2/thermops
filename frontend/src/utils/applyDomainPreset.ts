/**
 * R11-S8-9-24 / B2: Apply safe Type A Domain Preset patches to a starter flow.
 * Never fills Type B ids. No persist/compile/run.
 */

import type { Node } from "@xyflow/react";
import type { DomainPreset } from "@/utils/domainPresetCatalog";
import { applyNodeConfigPatch } from "@/utils/visualPipelineNodeConfig";
import { getNodeComponentType } from "@/utils/visualPipelineGraph";

/**
 * Apply Domain Preset Type A defaults onto starter template nodes.
 * Currently only recommendedTransformType on VP_TRANSFORM when present.
 */
export function applyDomainPresetToFlow(nodes: Node[], preset: DomainPreset | null | undefined): Node[] {
  if (!preset?.recommendedTransformType) return nodes;
  const transformType = String(preset.recommendedTransformType).trim();
  if (!transformType) return nodes;

  return nodes.map((n) => {
    if (getNodeComponentType(n) !== "VP_TRANSFORM") return n;
    return applyNodeConfigPatch(n, { transform_type: transformType });
  });
}
