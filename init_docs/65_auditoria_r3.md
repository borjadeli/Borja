# 65 — Auditoría externa r3 (rama destete-v2-fase3 hasta 5128532)

> Verificado: repros de r1/r2 pasan, P1 bien encarado. Hallazgos reproducidos. Prioridad en orden. Captura fiel.

## 1. FRESCURA — ningún agente sabe la fecha (PRIORIDAD MÁXIMA)
RKLB usa el 8-K del 3T25 y no sabe si Neutron voló; OKLO llega al 4T25 y no explica una caída de 58%.
- **a.** Todos los agentes (Analista/Bear/Macro/PM/Auditor/OpusSolo) reciben "Fecha de hoy: YYYY-MM-DD".
- **b.** `_render_pack` muestra el `known_at` de cada DataPoint + la fecha del último filing periódico.
- **c.** Prompt del Analista, protocolo de frescura: buscar primero el último 10-Q/10-K/8-K + noticias de los
  últimos 90d; si la evidencia central tiene >120 días, decirlo y bajar convicción; explicar todo movimiento
  de precio >30% en 6m o declararlo no-explicado → red flag `brecha_informativa`.
- **d.** Verificador: `dato_vigente` deja de ser fijo True. Un claim central con `source_date` anterior al
  último filing periódico del pack → REVIEW con motivo.
- **e.** Falsadores: si `fecha_limite` ya pasó o el hecho ya se resolvió, el dossier no es válido.
- **Test:** central de hace 12 meses + 10-Q más nuevo en el pack → REVIEW.

## 2. CLASE EPISTÉMICA — press releases en sec.gov
`clase_por_url` da "primaria_regulatoria" a cualquier URL de sec.gov, incluidos anexos EX-99.x (comunicados).
- En sec.gov: anexos `ex99` y `press`/`pressr`/`pr` → **company_statement**. Solo el cuerpo de 10-K/10-Q/8-K
  y el XBRL cuentan como primaria.
- Central cualitativo desde company_statement → REVIEW, salvo corroboración primaria/independiente.
- **Test:** el mismo comunicado de Archer en investors.archer.com y en sec.gov → misma clase.

## 3. BASELINE "OPUS SOLO" A IGUAL GASTO
Hoy 6 búsquedas para TODA la cartera vs 6/nombre + Bear del comité. Darle el mismo presupuesto USD/ciclo que
gastó el comité (búsquedas/turnos proporcionales) y registrar el gasto de ambos. Sin paridad, el duelo no mide.

## 4. HASH DE REUTILIZACIÓN
Derivadas cuyos insumos incluyen volátiles (dilucion_12m_pct con shares de Yahoo) → excluir del hash, o
calcular solo con insumos XBRL. **Test:** mismo pack sin XBRL de acciones, dos días → mismo hash.

## 5. CONTEXTO DEL MAPA
`contexto_fn` arma el contexto del cuello desde `nx_*` (nodo, dependencias, criticidad) para el Analista. Hoy "".

## 6. EXPORTS Y SMOKE #3
Exportar dossiers del smoke #2 (OKLO/ACHR/RKLB) al doc 56; correr smoke #3 (mismos 3) y exportar, para
comparar frescura y veredictos.

## 7. PENDIENTES
Cablear `candidatos_del_universo` en `ops.correr_semana_v2` con flag `--universo` · limpiar `/static/` (solo
app.css), borrar `solo`, `nohup.out`, `uvicorn_manual.log` · CLAUDE.md §04 "Flask"→FastAPI · doc 53 al día.
