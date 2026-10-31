# OpsRadar · Observabilidad y análisis inteligente de operaciones TI

**Facilitar la detección temprana de señales operativas relevantes, separando errores de telemetría de posibles anomalías de infraestructura.**

## Qué resuelve
Procesar registros operativos, detectar inconsistencias, generar alertas priorizadas, conservar evidencia técnica y facilitar el análisis de incidentes por especialistas.

Pipeline de calidad de telemetría TI: valida esquema, tiempos y trazas, redacta mensajes sensibles, agrega ventanas y propone señales de triaje para el operador.

## Hacia dónde va
Convertirse en una capa inteligente de observabilidad que permita a los equipos de operaciones tomar decisiones rápidas y explicables basadas en datos confiables.

**Objetivo:** Validar un pipeline de logs con controles de calidad temporal, detección exploratoria de anomalías y evaluación objetiva de la utilidad de sus alertas.

**Valor que persigue:** Reducir ruido de alertas y tiempo de revisión de registros de infraestructura.

## Resultados de la demo
Sobre un conjunto de datos sintéticos diseñado con errores y casos difíciles: **2 400 eventos de log: 2 359 candidatos, 21 a revisión, 20 en cuarentena; 200 ventanas y 11 señales de triaje; mensajes sensibles redactados**.

## Pruébalo en 2 minutos
```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py test     # 35 tests automatizados
python run.py demo     # demo de punta a punta → demo_output/
python run.py api      # API REST → http://127.0.0.1:8000/docs
```

## Diseñado para decisiones responsables
- **Siempre con una persona al mando:** no reinicia ni reconfigura sistemas; una alerta no es un incidente confirmado.
- **Trazable:** cada registro conserva su motivo de aceptación, revisión o cuarentena.
- **Probado:** 35 tests automatizados en Linux y Windows en cada cambio.
- **Contenedor:** la imagen Docker se construye en cada cambio.
- **Windows:** la suite tiene un caso conocido pendiente de corrección; en Linux pasa completa.

## Estado
Prototipo funcional demostrado con datos sintéticos. El siguiente paso es un **piloto con datos reales** de su organización, bajo acuerdo de uso y confidencialidad.

**¿Le interesa un piloto?** Contacte a **Kriter Systems**.

---
I23 · Kriter Systems · Los datos incluidos son sintéticos y no representan a personas ni empresas reales.
