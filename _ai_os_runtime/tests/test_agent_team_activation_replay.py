from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "activate_agent_team.py"


def test_activation_replay_requeues_only_incomplete_activation_tasks() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "task.source_kind='employee_activation'" in source
    assert "task.source_ref=" in source
    assert "task.status IN ('in_progress','needs_review','blocked','failed')" in source
    assert "run.status='completed'" in source
    assert "SET status='queued'" in source


def test_activation_contract_remains_deterministic_and_non_executing() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Do not invoke a model" in source
    assert "recommend live execution" in source
    assert "'live_execution_allowed',false" in source
