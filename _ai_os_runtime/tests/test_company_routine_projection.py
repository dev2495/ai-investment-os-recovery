from pathlib import Path
import pytest
from _ai_os_runtime.scripts.project_company_routine_note import project_company_note, START, END


def setup(monkeypatch, tmp_path):
    monkeypatch.setenv('AI_OS_SSD_ROOT', str(tmp_path))
    monkeypatch.setenv('AI_OS_VAULT_ROOT', str(tmp_path))
    monkeypatch.setattr(Path, 'is_mount', lambda self: self == tmp_path)
    row = {'managed_note_path': '00 AI OS/Managed/Company Updates/'+'a'*64+'.md',
           'artifact': {'symbol': 'WIPRO', 'model_calls': 0}}
    return row, tmp_path / row['managed_note_path']


def test_projection_preserves_human_text_and_replays_identically(monkeypatch, tmp_path):
    row, path = setup(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('My private notes\n'+START+'\nold\n'+END+'\nMy conclusion\n')
    first = project_company_note(row)
    content = path.read_text()
    second = project_company_note(row)
    assert first == second
    assert content.startswith('My private notes\n')
    assert content.endswith('\nMy conclusion\n')
    assert content.count(START) == 1


def test_projection_refuses_escape_symlink_and_bad_markers(monkeypatch, tmp_path):
    row, path = setup(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        project_company_note({**row, 'managed_note_path': '../private.md'})
    path.parent.mkdir(parents=True)
    target = tmp_path / 'human.md'
    target.write_text('do not touch')
    path.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        project_company_note(row)
    assert target.read_text() == 'do not touch'
    path.unlink()
    path.write_text(START+'\nbroken')
    with pytest.raises(ValueError, match='markers'):
        project_company_note(row)
    assert path.read_text() == START+'\nbroken'
