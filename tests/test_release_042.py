from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_release_contract_is_042_and_keeps_updater_and_sync_dependencies():
    desktop = (ROOT / 'app' / 'desktop.py').read_text(encoding='utf-8')
    with (ROOT / 'pyproject.toml').open('rb') as fh:
        version = tomllib.load(fh)['project']['version']
    workflow = (ROOT / '.github' / 'workflows' / 'build-windows-desktop.yml').read_text(encoding='utf-8').lower()
    assert version == '0.4.2'
    assert f'SENDA.V0 {version}' in desktop
    assert 'tomllib' in workflow and 'pyproject.toml' in workflow
    # The version is resolved once; package and artifact names are then composed from it.
    assert 'asset = "senda.v0_${version}_windows_desktop.zip"' in workflow
    assert 'artifact = "senda.v0-${version}-windows-desktop"' in workflow
    assert workflow.count('0.4.2') == 0
    assert 'install_from_github.ps1' in workflow
    assert 'openpyxl==3.1.5' in workflow and 'xlsxwriter==3.2.9' in workflow
