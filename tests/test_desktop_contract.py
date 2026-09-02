from pathlib import Path
import subprocess, sys

from app.desktop_model import create_context, filters_from_values

ROOT=Path(__file__).resolve().parents[1]


def test_desktop_check_uses_local_database_without_server(tmp_path):
    cp=subprocess.run([sys.executable,'-m','app.desktop','--check','--data-dir',str(tmp_path)],cwd=ROOT,capture_output=True,text=True)
    assert cp.returncode==0, cp.stderr
    assert 'SENDA.V0 Desktop OK' in cp.stdout
    assert (tmp_path/'database'/'senda_v0.sqlite').exists()


def test_windows_launcher_opens_exe_not_browser_or_localhost():
    text=(ROOT/'INICIAR_SENDA_V0.bat').read_text(encoding='utf-8',errors='ignore').lower()
    assert 'senda.v0.exe' in text
    assert '127.0.0.1' not in text
    assert 'chrome' not in text
    assert 'edge' not in text
    assert 'http://' not in text and 'https://' not in text


def test_desktop_module_has_no_http_or_browser_dependency():
    text=(ROOT/'app'/'desktop.py').read_text(encoding='utf-8').lower()
    assert 'webbrowser' not in text
    assert 'requests' not in text
    assert 'urllib' not in text
    assert '127.0.0.1' not in text
    assert 'app.server' not in text


def test_desktop_filters_keep_quarter_month_district_alarm_and_movement():
    f=filters_from_values(year='2026',quarter='T1',month='3',district='HORQUETAS',alarm='red',movement='HIPOTECAS',search='4-123')
    assert f=={'search':'4-123','year':2026,'quarter':'T1','month':3,'district':'HORQUETAS','alarm':'red','movement_type':'HIPOTECAS'}


def test_update_script_never_deletes_data_root():
    text=(ROOT/'scripts'/'update_desktop.ps1').read_text(encoding='utf-8').lower()
    assert "'senda.v0'" in text
    assert 'datos protegidos' in text
    assert 'remove-item $dataroot' not in text


def test_desktop_context_reuses_existing_database(tmp_path):
    c1=create_context(tmp_path)
    cid=c1.repo.create_case('4-999-001','HORQUETAS','persistente')
    c2=create_context(tmp_path)
    assert c2.repo.get_case(cid)['note']=='persistente'
