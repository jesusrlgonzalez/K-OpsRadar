# Fixture contaminado — simulación I23

Archivo `logs_dirty.csv`: 2.400 eventos completamente ficticios (cuatro servicios × 600 eventos). `INJECTION_TRUTH_NOT_FOR_TRAINING.csv`: manifiesto con 41 defectos inyectados y etiquetas separadas. Es inaceptable usar dicho manifiesto como feature, regla de predicción o ground truth de incidentes.

Error de evento, tiempo observado, servicio faltante, duración negativa, id duplicado conflictivo, severity inválida, trazas, schema desconocido, lecturas tardías/futuras, PII ficticia, status fuera de rango. El prototipo no representa datos reales ni PII verdadero. Regenerar con `python -m i23.fixture --out DATOS_FUENTES/04_SINTETICOS`.
