BEGIN;
ALTER TABLE research.research_case_model_runs
  DROP CONSTRAINT IF EXISTS research_case_model_runs_attempt_check;
ALTER TABLE research.research_case_model_runs
  ADD CONSTRAINT research_case_model_runs_attempt_check
  CHECK (attempt >= 1 AND attempt <= 4);
COMMIT;
