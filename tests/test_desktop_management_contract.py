from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_management_tab_has_chart_and_portable_export_actions():
    text = (ROOT / 'app' / 'desktop.py').read_text(encoding='utf-8')
    assert 'Trámites realizados por mes' in text
    assert 'EXPORTAR BASE EXCEL' in text
    assert 'EXPORTAR BASE JSON' in text
    assert '_export_sync_database' in text
    assert 'management_chart' in text
