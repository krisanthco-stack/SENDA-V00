import socket
import tempfile
import unittest
from pathlib import Path

class StartupRegressionTests(unittest.TestCase):
    def test_occupied_default_port_falls_back_instead_of_crashing(self):
        from app.launcher import create_resilient_server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.bind(('127.0.0.1', 0))
            blocker.listen(1)
            occupied = blocker.getsockname()[1]
            with tempfile.TemporaryDirectory() as td:
                server, used_port = create_resilient_server(
                    '127.0.0.1', occupied,
                    data_dir=Path(td) / 'data',
                    ui_dir=Path(__file__).parents[1] / 'ui',
                )
                try:
                    self.assertNotEqual(used_port, occupied)
                    self.assertGreater(used_port, 0)
                finally:
                    server.server_close()


    def test_invalid_data_directory_returns_error_instead_of_crashing(self):
        from app.launcher import run
        with tempfile.TemporaryDirectory() as td:
            blocked = Path(td) / 'not_a_directory'
            blocked.write_text('x', encoding='utf-8')
            self.assertEqual(run('127.0.0.1', 0, data_dir=blocked, no_browser=True), 1)

    def test_windows_launcher_cannot_close_silently_on_error(self):
        root = Path(__file__).parents[1]
        bat = (root / 'INICIAR_SENDA_V0.bat').read_text('utf-8', errors='replace').lower()
        self.assertIn('app.launcher', bat)
        self.assertIn('errorlevel', bat)
        self.assertIn('pause', bat)
        self.assertTrue('where py' in bat or 'where python' in bat)

    def test_launcher_source_contains_health_gate_and_log(self):
        text = (Path(__file__).parents[1] / 'app' / 'launcher.py').read_text('utf-8')
        self.assertIn('/api/health', text)
        self.assertIn('senda_v0.log', text)
        self.assertIn('webbrowser.open', text)

if __name__ == '__main__':
    unittest.main()
