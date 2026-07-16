-- R10-S11 CRON schedule support
-- Existing columns (cron_expression, timezone, next_run_at) are reused.
-- Widen cron_expression for longer expressions.

ALTER TABLE tb_data_load_schedule
    ALTER COLUMN cron_expression TYPE VARCHAR(120);
