import unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]

class LifecycleScriptTests(unittest.TestCase):
    def test_batch_entrypoints_exist_and_pause_on_error(self):
        for name,ps in (
            ('INSTALAR_SENDA_V0.bat','install.ps1'),
            ('ACTUALIZAR_SENDA_V0.bat','update.ps1'),
            ('DESINSTALAR_SENDA_V0.bat','uninstall.ps1'),
        ):
            p=ROOT/name
            self.assertTrue(p.is_file(), name)
            text=p.read_text('utf-8',errors='replace').lower()
            self.assertIn(ps.lower(),text)
            self.assertIn('errorlevel',text)
            self.assertIn('pause',text)

    def test_install_and_update_keep_user_data_outside_application(self):
        install=(ROOT/'scripts'/'install.ps1').read_text('utf-8',errors='replace')
        update=(ROOT/'scripts'/'update.ps1').read_text('utf-8',errors='replace')
        for text in (install,update):
            self.assertIn('LOCALAPPDATA',text)
            self.assertIn('Programs',text)
            self.assertNotIn('SENDA_DATA',text)
            self.assertIn('app',text)
            self.assertIn('ui',text)
            self.assertIn('vendor',text)
        self.assertIn('preserva',update.lower())

    def test_uninstall_defaults_to_preserve_data_and_requires_explicit_delete(self):
        text=(ROOT/'scripts'/'uninstall.ps1').read_text('utf-8',errors='replace')
        lower=text.lower()
        self.assertIn('conservar',lower)
        self.assertIn('eliminar',lower)
        self.assertIn('localappdata',lower)
        self.assertIn('remove-item',lower)
        self.assertIn("$choice -eq '2'",lower)

if __name__=='__main__':
    unittest.main()
