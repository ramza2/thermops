-- R9-S2-2 Standard Dataset metadata classification (business_domain, tags)

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS business_domain VARCHAR(100);

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS tags_json JSONB;

-- Preserve legacy domain codes as optional business metadata (no seed inserts).
UPDATE tb_standard_dataset_type
SET business_domain = domain
WHERE business_domain IS NULL
  AND domain IS NOT NULL
  AND TRIM(domain) <> '';

-- Normalize legacy category codes
UPDATE tb_standard_dataset_type
SET category = 'TIMESERIES'
WHERE category = 'TIME_SERIES';

UPDATE tb_standard_dataset_type
SET category = 'CUSTOM'
WHERE category IS NULL OR TRIM(category) = '';

CREATE INDEX IF NOT EXISTS ix_standard_dataset_type_business_domain
    ON tb_standard_dataset_type(business_domain)
    WHERE active_yn = 'Y' AND business_domain IS NOT NULL;
