import json
import unittest
from pathlib import Path

from . import alert_engine as ae

EJEMPLO = Path(__file__).resolve().parents[2] / "Docs" / "Challenge" / "simulated-astronaut-inputs.example.json"
OK = {"fc (lpm)": 70, "spo2 (%)": 98, "temp (°C)": 36.7, "co2 (ppm)": 1000, "presión (kPa)": 101,
      "radiación (mSv/día)": 0.5, "sueño (h)": 7, "hrv (ms)": 65, "ánimo (1-5)": 4}


def sistemas(m, **kw):
    return {a["sistema"] for a in ae.generar_alertas_actuales(m, **kw)[1]}


class AlertEngineTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(ae.generar_alertas_actuales(OK)[0], "NORMAL")

    def test_hipercapnia_es_ambiental_y_no_hipoxia(self):
        estado, alertas = ae.generar_alertas_actuales({**OK, "co2 (ppm)": 8000, "fc (lpm)": 112})
        self.assertEqual(estado, "ADVERTENCIA")
        textos = " ".join(a["mensaje"] for a in alertas)
        self.assertIn("hipercapnia", textos)
        self.assertNotIn("hipoxia", textos)

    def test_hipoxia_por_fuga(self):
        estado, _ = ae.generar_alertas_actuales({**OK, "presión (kPa)": 78, "spo2 (%)": 90})
        self.assertEqual(estado, "CRITICO")

    def test_fc_depende_de_la_fase(self):
        self.assertEqual(ae.generar_alertas_actuales({**OK, "fc (lpm)": 140}, ae.MissionPhase.EJERCICIO)[0], "NORMAL")
        self.assertEqual(ae.generar_alertas_actuales({**OK, "fc (lpm)": 110})[0], "PRECAUCION")

    def test_dato_faltante_no_se_oculta(self):
        self.assertIn("SENSOR", sistemas(OK, faltantes=["co2 (ppm)"]))

    def test_contrato_real(self):
        res = ae.triage_payload(json.loads(EJEMPLO.read_text(encoding="utf-8")))
        self.assertEqual(res["astronaut_id"], "A01")
        self.assertEqual(res["estado_global"], "PRECAUCION" if res["alertas"] else "NORMAL")

    def test_compatibilidad_con_main_py(self):
        self.assertIsInstance(ae.generar_alertas_preventivas({**OK, "co2 (ppm)": 9000, "fc (lpm)": 115}), list)


if __name__ == "__main__":
    unittest.main()
