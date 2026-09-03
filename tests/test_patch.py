from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / 'senda_ui_patch.css'
JS = ROOT / 'senda_selection_patch.js'


def test_css_exists():
    assert CSS.exists(), 'Falta senda_ui_patch.css'


def test_js_exists():
    assert JS.exists(), 'Falta senda_selection_patch.js'


def test_status_is_text_only():
    css = CSS.read_text(encoding='utf-8')
    for name in ['red', 'yellow', 'green']:
        block = re.search(rf"\.senda-status--{name}\s*\{{([^}}]+)\}}", css, re.S)
        assert block, f'Falta clase de estado {name}'
        body = block.group(1).lower()
        assert 'color:' in body, f'Estado {name} debe colorear texto'
        assert 'background-color:' not in body, f'Estado {name} no debe pintar fondo'
        assert not re.search(r'(?<!-)background\s*:', body), f'Estado {name} no debe pintar fondo'


def test_legacy_status_backgrounds_are_neutralized():
    css = CSS.read_text(encoding='utf-8').lower()
    assert 'background: transparent' in css or 'background-color: transparent' in css


def test_content_is_mouse_selectable():
    css = CSS.read_text(encoding='utf-8').lower()
    assert 'user-select: text' in css
    assert '-webkit-user-select: text' in css


def test_interactive_controls_keep_normal_interaction():
    css = CSS.read_text(encoding='utf-8').lower()
    for selector in ['button', 'input', 'select', 'textarea']:
        assert selector in css
    assert 'user-select: none' in css


def test_js_targets_senda_sections_without_blocking_copy():
    js = JS.read_text(encoding='utf-8').lower()
    for token in ['senda', 'expediente', 'movimiento', 'control', 'folio', 'finca']:
        assert token in js
    assert 'preventdefault' not in js, 'El parche no debe bloquear selección/copia mediante preventDefault'


if __name__ == '__main__':
    tests = [v for k, v in globals().items() if k.startswith('test_') and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print('PASS', test.__name__)
        except Exception as exc:
            failed += 1
            print('FAIL', test.__name__, '-', exc)
    raise SystemExit(1 if failed else 0)
