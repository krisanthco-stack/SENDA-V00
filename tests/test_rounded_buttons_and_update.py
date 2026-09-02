from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_uses_rounded_button_for_primary_actions_and_github_update():
    text = (ROOT / 'app' / 'desktop.py').read_text(encoding='utf-8')
    assert 'class RoundedButton(tk.Canvas)' in text
    assert "text='↻ ACTUALIZAR DESDE GITHUB'" in text
    assert 'RoundedButton(' in text
    assert "text='FINALIZAR'" in text
    assert "text='PASAR A CONTROL'" in text
