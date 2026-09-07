from _ai_os_runtime.scripts.project_company_routine_note import project_company_note
from _ai_os_runtime.tests.test_company_routine_projection import setup


def test_storage_root_and_notes_root_share_one_destination(monkeypatch, tmp_path):
    row, destination = setup(monkeypatch, tmp_path)
    first = project_company_note(row)
    assert destination.exists()
    assert not (tmp_path / '00 AI OS').exists()
    monkeypatch.setenv('AI_OS_VAULT_ROOT', str(tmp_path / 'ai memory'))
    second = project_company_note(row)
    assert first == second
    assert len(list(tmp_path.rglob('*.md'))) == 1
