-- SmartWell migration: OLD UUID motor_logs/device_id schema -> CURRENT schema.
-- Run ONLY after the diagnostic confirms the old UUID schema.
-- BACK UP smartwell_db first.

BEGIN;

-- Temporary map from old UUID motor log IDs to new integer IDs.
CREATE TEMP TABLE motor_log_id_map (
    old_id uuid PRIMARY KEY,
    new_id integer UNIQUE NOT NULL
);

INSERT INTO motor_log_id_map(old_id, new_id)
SELECT id, row_number() OVER (ORDER BY start_time, id)::integer
FROM motor_logs;

-- Remove old foreign keys that point to UUID columns.
ALTER TABLE khata_entries DROP CONSTRAINT IF EXISTS khata_entries_motor_log_id_fkey;
ALTER TABLE khata_entries DROP CONSTRAINT IF EXISTS khata_entries_device_id_fkey;
ALTER TABLE motor_logs DROP CONSTRAINT IF EXISTS motor_logs_device_id_fkey;

-- Convert Khata's motor_log_id UUID -> integer using the mapping.
ALTER TABLE khata_entries ADD COLUMN motor_log_id_new integer;
UPDATE khata_entries ke
SET motor_log_id_new = m.new_id
FROM motor_log_id_map m
WHERE ke.motor_log_id = m.old_id;
ALTER TABLE khata_entries DROP COLUMN motor_log_id;
ALTER TABLE khata_entries RENAME COLUMN motor_log_id_new TO motor_log_id;

-- Convert device_id UUID -> public device_uid string.
ALTER TABLE motor_logs ALTER COLUMN device_id TYPE varchar(100) USING device_id::text;
ALTER TABLE khata_entries ALTER COLUMN device_id TYPE varchar(100) USING device_id::text;

UPDATE motor_logs ml
SET device_id = d.device_uid
FROM devices d
WHERE ml.device_id = d.id::text;

UPDATE khata_entries ke
SET device_id = d.device_uid
FROM devices d
WHERE ke.device_id = d.id::text;

-- Replace motor_logs.id UUID PK with integer PK.
ALTER TABLE motor_logs ADD COLUMN id_new integer;
UPDATE motor_logs ml
SET id_new = m.new_id
FROM motor_log_id_map m
WHERE ml.id = m.old_id;

ALTER TABLE motor_logs DROP CONSTRAINT IF EXISTS motor_logs_pkey;
ALTER TABLE motor_logs DROP COLUMN id;
ALTER TABLE motor_logs RENAME COLUMN id_new TO id;
ALTER TABLE motor_logs ADD PRIMARY KEY (id);
ALTER TABLE motor_logs ALTER COLUMN id SET NOT NULL;

-- Auto-increment for new motor logs.
CREATE SEQUENCE IF NOT EXISTS motor_logs_id_seq;
ALTER SEQUENCE motor_logs_id_seq OWNED BY motor_logs.id;
SELECT setval('motor_logs_id_seq', COALESCE((SELECT MAX(id) FROM motor_logs), 0) + 1, false);
ALTER TABLE motor_logs ALTER COLUMN id SET DEFAULT nextval('motor_logs_id_seq');

-- Current schema intentionally uses public device_uid strings and no physical
-- FK from child device_id columns, so devices can be registered independently.
ALTER TABLE khata_entries
    ADD CONSTRAINT khata_entries_motor_log_id_fkey
    FOREIGN KEY (motor_log_id) REFERENCES motor_logs(id) ON DELETE SET NULL;

COMMIT;
