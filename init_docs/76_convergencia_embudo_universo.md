# 76 — Convergencia: embudo + universo + Discovery (2 IAs sobre el doc 75)

> Triangulación del doc 75 por 2 IAs independientes de alta calidad. **Convergieron fuerte.** Este doc fija lo
> FIRME, el reencuadre clave (parte de esto cabe en el congelamiento), las decisiones del operador y el plan
> priorizado. Secuela del doc 75 (hallazgo del dry-run: 30 deeps, 21 forzados por evento, ~$20).

## 0. El reencuadre que cambia todo (ambas IAs)

El embudo **confunde dos obligaciones distintas con presupuestos opuestos**:
- **DETECTAR un cambio** (alerta): barata; para capital en riesgo (posiciones) y riesgo crítico, **sin tope**.
- **INVESTIGAR a fondo** (deep): cara ($0,68); para oportunidad; **se rankea y se capea**.

"Monitorear ≠ investigar. Ningún filing debe consumir presupuesto automáticamente por su código SEC" (IA1).
Y **estos fixes caben en el congelamiento**: el código hoy **viola reglas ya escritas** — la regla de earnings
del operador (doc 64) y el filtro de market cap del IPS. Arreglarlo es honrar reglas existentes, no método nuevo.

## 1. FIRME — embudo (convergen las 2)

- **Ruteo por DOS ejes: estado del nombre × clase de evento** (no un booleano `es_evento_fuerte`):
  - **Posición en cartera:** deep SIEMPRE (capital en riesgo), desde una **reserva de emergencia fuera del tope**.
  - **No-posición:** se **rankea y capea** (perder un evento = oportunidad postergada una corrida).
  - El estado "candidato vivo / descartado" lo informa el **veredicto previo del PM** (el PM informa la
    prioridad; el código no decide).
- **Idempotencia** (la que más ahorra): un evento fuerza deep **solo si `fecha_evento > fecha_ultimo_deep`**.
  Sin esto, con ventana de 30 días + corridas semanales, el mismo earnings dispara 4 veces.
- **Earnings 2.02 fuera de "evento fuerte" para no-posiciones** (respeta la regla del operador). Pero NO se
  ignora: un 2.02 con **reacción de precio anómala** promueve. "El evento dice cuándo mirar; el precio, cuánto
  importa." (IA1 agrega un **earnings-preflight**: refrescar métricas y comparar vs supuestos previos antes de
  decidir promover.)
- **Carril de precio normalizado por volatilidad** (z-score del exceso sobre el sector, **no % crudo** — una
  small cap se mueve 10% por nada; en earnings season el % crudo también inunda).
- **Tope del carril forzado (no-posiciones) con OVERFLOW VISIBLE**: score = severidad × prioridad cuello ×
  peso del estado; lo que sobra se arrastra con decaimiento y **aparece en el reporte** (nada se pierde en
  silencio).
- **Transparencia + override** (mitiga que el embudo decida qué ve el PM): el reporte lista qué quedó afuera y
  por qué; el operador puede pedir el deep de **cualquier** excluido dentro del presupuesto.
- **Clases de evento** (refinar, post-corrida): red flags 4.02/4.01/3.01 **+ 1.03 (quiebra), 2.04 (aceleración
  deuda), 2.06 (impairment)**; estructurales 2.01 (M&A), 1.01/**1.02 (contrato material / su terminación)**,
  13D, **5.01 (cambio de control)**; **5.02 ruidoso → filtrar a salida de CEO/CFO**; **dilución = TAKEDOWN
  (424B5/3.02 PIPEs) y su TAMAÑO** (monto/market cap o Δacciones XBRL >~10%), NO "hubo un S-3" (los shelves son
  rutina).
- **Punto ciego de emisores extranjeros (FPI)**: no presentan 8-K sino 6-K/20-F/40-F sin códigos de ítem → en
  un universo con uranio/minería/nuclear CA/AU el carril de eventos es CIEGO. No scrapear SEDAR+ ahora; dejarlo
  explícito en el reporte y que el carril de precio los cubra.
- **Clasificador LLM del 8-K**: NO (rompe el embudo determinista) salvo que el replay muestre que los proxies
  pierden cambios reales.

## 2. FIRME — market cap antes del deep (convergen las 2)

- **SÍ, filtro de admisibilidad del IPS en el embudo, antes del deep** (no pagar análisis cuyo resultado ya
  está determinado = "el determinismo limita").
- **$60B es tope de ENTRADA, no de TENENCIA.** Los ganadores power-law crecen fuera del rango; recortar un
  ganador grande es sizing del PM bajo el peso máx, **no** un filtro de market cap. **→ ACCIÓN: verificar que
  el gate actual no fuerce vender / deje de monitorear posiciones que superan $60B.**
- **Posiciones: se monitorean SIEMPRE, a cualquier tamaño.** Excepciones al filtro: posiciones, info de un
  gigante que cambia la tesis de un elegible, y **datos faltantes = pendiente de verificación, no inelegible**.
- **Una sola función de admisibilidad** llamada por el embudo Y el gate (no dos que divergen) + **liquidez en
  el mismo paso** (ADV mín vs ticket) + **banda de histéresis ±15%** (que no entre/salga con cada movimiento).
- Exclusiones **contadas en el reporte** (por tamaño / liquidez / falta de dato) — nada desaparece en silencio.

## 3. FIRME — tope $60B y gigantes (convergen las 2)

- **Mantener $60B** durante la validación. La pregunta correcta no es "¿puede multiplicar un $80B?" sino
  **"¿este sistema lo ve antes que el consenso?"** — el edge está donde la cobertura es baja, y la cobertura
  crece con el tamaño. NO rangos por arquetipo (gameable). NO subir sin datos.
- **Gigantes = contexto / SENSORES del mapa** (opción i): su capex/contratos/guías (XBRL, sin LLM) alimentan
  el mapa y el Discovery, **no disparan análisis propios**. Descartar (ii) analizables-no-comprables (es pagar
  por nada) y (iii) sleeve dentro del sistema (diluye la identidad; no hay edge en NVDA).
- **Si el operador quiere exposición a enablers → core-satellite**: core pasivo (ETF temático/semis) que el
  humano ejecuta FUERA del sistema; el sistema maneja el satélite power-law (y se mide contra un benchmark de
  small/mid temáticas).
- **MEDIR antes de cambiar el mandato**: seguimiento determinista (solo precios, costo cero) de una **banda de
  observación** ($60–150B) vs el rango; registrar **oportunidades excluidas solo por tamaño**; revisar el tope
  en **6–12 meses con evidencia**. *(Única diferencia menor entre IAs: banda $60–100B vs $60–150B — a elección
  del operador.)*

## 4. FIRME — Discovery / Map Curator (convergen las 2)

- **Después de la primera corrida real** (un Discovery que alimenta un embudo mal calibrado multiplica el
  defecto; sin corrida real no hay línea de base; un mapa quieto unas semanas cuesta poco).
- **Antes, sin LLM:** construir la **cola `propuestas_empresa`** (esquema + flujo de aprobación) + el estado
  **"observación"**, alimentada a mano por el operador. El agente, cuando llegue, es solo otro productor.
- **Proponer-y-aprobar, NO auto** para todo lo que toque el universo analizable (la web de small caps está
  llena de research pago/promocional → un agente que lee y agrega solo es más vulnerable JUSTO en este
  segmento; un alta mala puede terminar en una compra). **3 capas de autonomía:** anotaciones descriptivas del
  mapa (auto, versionadas, revertibles) · cambios de severidad de nodo (cola) · **altas → estado "observación"**
  (datos/eventos deterministas, NO elegible para deep ni compra hasta que el humano promueve).
- **Validadores duros + vencimiento** antes del humano: ticker/bolsa existen, banda IPS, liquidez, no duplicado,
  ≥1 fuente primaria para el "por qué ahora". **Nunca se acepta por silencio.**
- **Qué busca:** cambios en la ESTRUCTURA de los cuellos — candidatos nuevos, cambios de relaciones
  industriales, y **falsadores del mapa** (se resolvió la escasez / se comoditizó / la empresa dejó de capturar
  el valor). *Clave: exposición a una industria que crece ≠ el accionista captura el valor → buscar quién
  RETIENE el valor económico.*
- **Agrega Y retira** (asimétrico): bajas por hecho corporativo (adquirida/quiebra/deslistada) automáticas → a
  histórico, sin borrar; bajas por juicio ("dejó de ser cuello") → cola con evidencia → contexto del mapa.
  **Ninguna baja toca una posición.**
- **Frecuencia/presupuesto:** quincenal (~$1) + corridas por señales deterministas baratas (8-K 1.01 con
  contraparte fuera del mapa, capex de gigantes, IPOs S-1/F-1 en SIC relevantes, contratos defensa/DOE,
  licencias NRC). Sobre fijo con **tope duro en código ~$3–4/mes (<10%)** + tope de **5–10 propuestas/ciclo**
  (el recurso escaso también es la atención del que aprueba).

## 5. Transversal — medir lo que se deja afuera (la clave power-law)

Dos errores simétricos; para power-law el **falso negativo** (perder una oportunidad extraordinaria) es mucho
más caro que el falso positivo ($0,68). → **Registro de candidatos descartados + razón** (eventos no
promovidos, fuera de IPS, propuestas rechazadas) + **auditorías por muestreo**. No para predecir ganadores,
sino para verificar que la selección no ignora sistemáticamente clases de oportunidad.

- **Tamaño objetivo del universo analizable atado a la capacidad** (~$30/mes deep ≈ 44 análisis/mes; si la
  mitad va a monitoreo, ~20 para cobertura → 135 nombres se recorren 1 vez cada 6-7 meses). Un universo que
  crece sin bajas **no amplía la cobertura: la envejece.** Operar **uno-entra-uno-sale** por encima del target.
- **Delta-deep** (la palanca que más cobertura compra): re-analizar nombres ya vistos dándole al LLM la **tesis
  previa + el evento**, a una fracción de $0,68. (Post-congelamiento.)
- **Versionar el universo point-in-time, sin borrados duros** (si no, toda evaluación futura tiene sesgo de
  supervivencia). **Auditar por qué 135 activas de ~245** (puede haber curación implícita del código).

## 6. Plan priorizado (síntesis de ambas)

**A — Antes de la primera corrida real (DENTRO del congelamiento: el código viola reglas ya escritas; con tests):**
1. **Idempotencia** de eventos (`fecha_evento > fecha_ultimo_deep`).
2. **Sacar 2.02 de "evento fuerte"** para no-posiciones (candidatos vivos → carril earnings top-N; posiciones
   siempre entran).
3. **Filtro de admisibilidad del IPS en el embudo** (una sola función; NUNCA a posiciones; exclusiones en el
   reporte) + verificar que el gate no trate $60B como tope de tenencia.
4. **Tope duro del carril forzado** (no-posiciones) con overflow visible y arrastrado + **reserva de emergencia**
   para red flags en cartera.
5. **Replay del dry-run de 30 nombres como test de regresión**, que verifique: GOOG excluido · no-posiciones
   con solo earnings afuera · una posición con 2.02 entra · una posición >$60B sigue monitoreada · un evento ya
   analizado no re-dispara.

**B — Después de la primera corrida (medir primero):** refinar clases de evento + normalizar precio por vol ·
auditar 135/245 + documentar FPI + versionar universo · cola de propuestas + estado "observación" (sin LLM) ·
registro de descartados + auditoría por muestreo.

**C — Más adelante:** agente Discovery (sobre fijo + validadores) · **delta-deep** · gigantes como sensores
(capex XBRL → mapa) · revisar $60B con la banda de observación a los 6-12 meses.

## 7. Decisiones del operador (lo único abierto)

- Banda de observación: **$60–100B** (IA1) o **$60–150B** (IA2).
- ¿Querés el **core-satellite** para exposición a enablers (core pasivo fuera del sistema), o el sistema se
  queda 100% en el satélite power-law?

## 8. Principio rector

Todo esto es determinismo que **informa/limita** (rutea, filtra por IPS, capea presupuesto); ninguna regla
elige nombres ni tamaños. Salvedad honesta de ambas IAs: **el embudo ES una decisión implícita de qué ve el
PM** → mitigación = transparencia (reporte de exclusiones) + override del operador. El código ordena la fila,
no es la única puerta de entrada.
