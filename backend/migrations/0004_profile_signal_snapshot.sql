ALTER TABLE generated_evaluations
  ADD COLUMN IF NOT EXISTS profile_signal_snapshot JSON;
