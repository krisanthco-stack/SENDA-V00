import unittest
from pathlib import Path

class UiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.html=(Path(__file__).parents[1]/'ui'/'index.html').read_text('utf-8')
    def test_exactly_four_primary_modules(self):
        self.assertEqual(self.html.count('data-module='),4)
        for name in ('INICIO','CONTROL','EXPEDIENTES','CONFIGURACIÓN'): self.assertIn(name,self.html)
    def test_horizontal_filters_include_period_district_alarm(self):
        for control in ('filterYear','filterQuarter','filterMonth','filterDistrict','filterAlarm'): self.assertIn(f'id="{control}"',self.html)
        for district in ('PUERTO VIEJO','LA VIRGEN','HORQUETAS','LLANURAS DEL GASPAR','CUREÑA'): self.assertIn(district,self.html)
    def test_real_source_formats_are_visible(self):
        for ext in ('.xls','.xlsx','.csv','.json','.txt','.zip','.rar'): self.assertIn(ext,self.html.lower())
    def test_previous_alarm_rules_are_visible(self):
        self.assertIn('90 días',self.html); self.assertIn('60 días',self.html)
    def test_right_context_panel_preserves_requested_sections(self):
        for label in ('INFORMACIÓN SENDA','FOLIOS / FINCAS PENDIENTES','ALARMAS','CÓDIGOS','LEYENDA DE ESTADO'):self.assertIn(label,self.html)

if __name__=='__main__':unittest.main()
