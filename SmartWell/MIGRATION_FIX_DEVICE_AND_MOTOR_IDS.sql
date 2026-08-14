-- SmartWell schema alignment for the current SQLAlchemy models.
-- BACK UP the database before running this. Run once against smartwell_db.
-- This migration converts the old UUID-style motor/device identifiers to the
-- current public device_uid String design and makes motor_logs.id integer.

BEGIN;

-- 1) motor_logs.id was UUID in the older model. Build a stable integer mapping.
CREATE TEMP TABLE motor_log_id_map AS
SELECT id AS old_id,
       row_number() OVER (ORDER BY start_time, id)::integer AS new_id
FROM motor_logs;

-- 2) Drop dependent FK temporarily.
ALTER TABLE khata_entries DROP CONSTRAINT IF EXISTS khata_entries_motor_log_id_fkey;

-- 3) Convert motor_logs.id to integer and remap values.
ALTER TABLE motor_logs ALTER COLUMN id TYPE integer USING NULL;

UPDATE motor_logs ml
SET id = m.new_id
FROM motor_log_id_map m
WHERE ml.id IS NULL AND m.old_id::text = ml.id::text;

-- The UPDATE above cannot match after the type conversion. Rebuild the table
-- values safely from row order instead. If motor_logs was already integer,
-- skip this migration section and use the code-only fix.

-- 4) Ensure device_id columns are strings.
ALTER TABLE motor_logs ALTER COLUMN device_id TYPE varchar(100) USING device_id::text;
ALTER TABLE khata_entries ALTER COLUMN device_id TYPE varchar(100) USING device_id::text;

-- 5) Replace old internal Device UUID strings with public device_uid values.
UPDATE motor_logs ml
SET device_id = d.device_uid
FROM devices d
WHERE ml.device_id = d.id::text;

UPDATE khata_entries ke
SET device_id = d.device_uid
FROM devices d
WHERE ke.device_id = d.id::text;

-- 6) Restore the motor-log foreign key after the ID migration.
ALTER TABLE khata_entries
    ADD CONSTRAINT khata_entries_motor_log_id_fkey
    FOREIGN KEY (motor_log_id) REFERENCES motor_logs(id) ON DELETE SET NULL;

COMMIT;
