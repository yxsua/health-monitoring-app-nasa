"""Ejecutar:  python -m unittest -v test_mantenimiento"""
import unittest
from pathlib import Path

import mantenimiento as m

PANTALLA = {"fc (lpm)": 72.78, "pa_sis (mmHg)": 114.34, "pa_dia (mmHg)": 77.86, "spo2 (%)": 97.19, "temp (°C)": 39.03,
            "glucosa (mg/dL)": 95.98, "hrv (ms)": 67.93}
CABINA = {"co2 (ppm)": 1000, "presión (kPa)": 101, "temp_cabina (°C)": 22.4, "humedad (%)": 45, "ruido (dBA)": 40, "radiación (mSv/día)": 0.5}
SANO = {**PANTALLA, "temp (°C)": 36.7, **CABINA}
EXCEL = Path("/mnt/user-data/uploads/Historial_medico_sintetico_IA_ampliado__1_.xlsx")
ids = lambda lst: [r["id"] for r in lst]


class MantenimientoTest(unittest.TestCase):
    def test_catalogo_y_logica_coinciden(self):
        for cat, log in ((m.ESC_CUERPO, m.LOGICA_CUERPO), (m.ESC_CABINA, m.LOGICA_CABINA),
                         (m.ESC_PRED_CUERPO, m.LOGICA_PRED_CUERPO), (m.ESC_PRED_CABINA, m.LOGICA_PRED_CABINA)):
            self.assertEqual(sorted(e["id"] for e in cat), sorted(log))

    def test_pantalla_del_usuario_fiebre_con_if_normal(self):
        r = m.Evaluador().evaluar({**PANTALLA, **CABINA}, {"anomaly": False, "score": 0.0278})
        self.assertEqual(ids(r["cuerpo"]["correctivo"]), ["B08"])
        self.assertEqual(r["cuerpo"]["correctivo"][0]["nivel_nombre"], "ALERTA")  # 39,03 < 39,5 (Excel)
        self.assertEqual(r["if"]["clave"], "B")
        self.assertEqual(r["if"]["contribuyentes"][0]["variable"], "temp (°C)")
        self.assertEqual(ids(r["cabina"]["correctivo"]), ["K12"])

    def test_sano(self):
        r = m.Evaluador().evaluar(SANO, {"anomaly": False})
        self.assertEqual(ids(r["cuerpo"]["correctivo"]), ["B23"])

    def test_if_anomalo_sin_umbral(self):
        r = m.Evaluador().evaluar(SANO, {"anomaly": True, "score": -0.2})
        self.assertEqual(ids(r["cuerpo"]["correctivo"]), ["B22"])
        self.assertEqual(r["if"]["clave"], "C")

    def test_hipercapnia_no_es_hipoxia(self):
        r = m.Evaluador().evaluar({**SANO, "co2 (ppm)": 8000, "fc (lpm)": 112}, {"anomaly": True})
        self.assertIn("K02", ids(r["cabina"]["correctivo"]))
        self.assertIn("B15", ids(r["cuerpo"]["correctivo"]))
        self.assertNotIn("B10", ids(r["cuerpo"]["correctivo"]))

    def test_ejercicio_es_contexto(self):
        r = m.Evaluador().evaluar({**SANO, "fc (lpm)": 135}, {"anomaly": False}, actividad="exercise")
        self.assertEqual(ids(r["cuerpo"]["correctivo"]), ["B18"])
        r = m.Evaluador().evaluar({**SANO, "fc (lpm)": 135}, {"anomaly": False}, actividad="rest")
        self.assertEqual(ids(r["cuerpo"]["correctivo"]), ["B06"])

    def test_persistencia(self):
        ev = m.Evaluador(); v = {**SANO, "fc (lpm)": 105}
        self.assertTrue(ev.evaluar(v)["cuerpo"]["correctivo"][0]["pendiente"])
        self.assertTrue(ev.evaluar(v)["cuerpo"]["correctivo"][0]["confirmado"])
        self.assertTrue(m.Evaluador().evaluar({**SANO, "fc (lpm)": 160})["cuerpo"]["correctivo"][0]["confirmado"])  # crítico: sin espera

    def test_inestabilidad(self):
        r = m.Evaluador().evaluar({**SANO, "pa_sis (mmHg)": 85, "fc (lpm)": 125})
        self.assertEqual(r["cuerpo"]["correctivo"][0]["id"], "B19")
        self.assertEqual(r["cuerpo"]["correctivo"][0]["nivel"], 3)

    def test_predictivo_se_acerca_con_eta(self):
        r = m.Evaluador().evaluar(SANO, {"anomaly": False}, pron={**SANO, "fc (lpm)": 96.0}, paso_s=3)
        p = r["cuerpo"]["predictivo"]
        self.assertIn("P05", ids(p))
        self.assertIsNotNone(next(x for x in p if x["id"] == "P05")["eta_s"])

    def test_predictivo_recuperacion_y_estable(self):
        r = m.Evaluador().evaluar({**PANTALLA, **CABINA}, pron={**PANTALLA, **CABINA, "temp (°C)": 38.2})
        self.assertIn("P15", ids(r["cuerpo"]["predictivo"]))
        r = m.Evaluador().evaluar(SANO, pron=SANO)
        self.assertEqual(ids(r["cuerpo"]["predictivo"]), ["P16"]); self.assertEqual(ids(r["cabina"]["predictivo"]), ["Q10"])

    def test_predictivo_cabina_y_cruzado(self):
        r = m.Evaluador().evaluar(SANO, pron={**SANO, "co2 (ppm)": 5100, "fc (lpm)": 97})
        self.assertIn("Q01", ids(r["cabina"]["predictivo"])) if "Q08" not in ids(r["cabina"]["predictivo"]) else None
        self.assertTrue({"Q01", "Q08"} & set(ids(r["cabina"]["predictivo"])))

    def test_sin_pronostico_calentando(self):
        self.assertEqual(m.Evaluador().evaluar(SANO)["cuerpo"]["predictivo"], {"estado": "calentando"})

    @unittest.skipUnless(EXCEL.exists(), "falta el Excel del usuario")
    def test_umbrales_del_excel_del_usuario(self):
        u = m.cargar_umbrales(str(EXCEL))
        for k in ("fc", "sis", "dia", "spo2", "temp", "glu"):
            self.assertEqual(u[k]["lo"], m.UMBRALES[k]["lo"], k)
            self.assertEqual(u[k]["hi"], m.UMBRALES[k]["hi"], k)


if __name__ == "__main__":
    unittest.main()
