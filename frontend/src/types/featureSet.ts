export interface FeatureSet {
  feature_set_id: string;
  feature_set_name: string;
  target_domain: string;
  features: string[];
  apply_site_scope: string;
  description: string | null;
}

export interface FeatureSetMeta {
  text: string;
  missingHandling: string;
  normalize: boolean;
}

const META_SEP = "---META---";

export function parseFeatureSetDescription(desc: string | null): FeatureSetMeta {
  if (!desc) return { text: "", missingHandling: "PREV", normalize: false };
  const idx = desc.indexOf(META_SEP);
  if (idx < 0) return { text: desc, missingHandling: "PREV", normalize: false };
  try {
    const parsed = JSON.parse(desc.slice(idx + META_SEP.length)) as Partial<FeatureSetMeta>;
    return {
      text: desc.slice(0, idx),
      missingHandling: parsed.missingHandling ?? "PREV",
      normalize: parsed.normalize ?? false,
    };
  } catch {
    return { text: desc, missingHandling: "PREV", normalize: false };
  }
}

export function serializeFeatureSetDescription(text: string, missingHandling: string, normalize: boolean): string {
  return `${text}${META_SEP}${JSON.stringify({ missingHandling, normalize })}`;
}

export function toFeatureSetPayload(
  form: Pick<FeatureSet, "feature_set_name" | "target_domain" | "features" | "apply_site_scope"> & FeatureSetMeta,
) {
  return {
    feature_set_name: form.feature_set_name,
    target_domain: form.target_domain,
    features: form.features,
    apply_site_scope: form.apply_site_scope,
    description: serializeFeatureSetDescription(form.text, form.missingHandling, form.normalize),
  };
}
