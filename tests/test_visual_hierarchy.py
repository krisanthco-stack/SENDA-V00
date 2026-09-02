from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_typography_is_twenty_percent_larger():
    text = (ROOT / 'app' / 'desktop.py').read_text(encoding='utf-8')
    for token in (
        'BODY_FONT_SIZE = 12',
        'PANEL_TITLE_SIZE = 14',
        'SECTION_TITLE_SIZE = 23',
        'NAV_FONT_SIZE = 13',
        'KPI_VALUE_SIZE = 24',
        'KPI_LABEL_SIZE = 12',
        'SMALL_FONT_SIZE = 11',
        "rowheight=37",
    ):
        assert token in text
