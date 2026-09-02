from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_has_visible_update_from_github_button():
    text = (ROOT / 'app' / 'desktop.py').read_text(encoding='utf-8')
    assert 'ACTUALIZAR DESDE GITHUB' in text
    assert '_update_from_github' in text
    assert 'install_from_github.ps1' in text


def test_release_bundle_contains_github_updater_files():
    workflow = (ROOT / '.github' / 'workflows' / 'build-windows-desktop.yml').read_text(encoding='utf-8').lower()
    assert 'scripts/install_from_github.ps1' in workflow
    assert 'instalar_desde_github.bat' in workflow


def test_github_updater_stops_running_desktop_before_install_and_preserves_data():
    script = (ROOT / 'scripts' / 'install_from_github.ps1').read_text(encoding='utf-8').lower()
    assert "get-process -name 'senda.v0'" in script
    assert 'stop-process' in script
    assert "join-path $env:localappdata 'senda.v0'" in script
    assert 'remove-item $dataroot' not in script
