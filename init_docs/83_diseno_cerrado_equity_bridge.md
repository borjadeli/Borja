# Doc 83 — Diseño CERRADO: integridad del equity bridge + verificación independiente

> **Canónico.** Sucesor del doc 82 (brief). Convergido por **IA1 + IA2** (2026-11-16, convergencia casi total) +
> decisiones del operador. Cierra los 4 cambios estructurales que surgieron de validar 4 nombres contra un
> LLM+web externo. **A IMPLEMENTAR por fases (F1→F4).** No codear fuera de este doc.
>
> Relacionado: [[82]] (brief), doc 80 (ficha viva), doc 53 (estado).

## 0. El diagnóstico en una línea

Validamos VST/MP/IESC/OKLO contra un LLM+web independiente: **coincidió en ranking/zona 3/4 pero cazó cosas que
el comité no** (una adquisición, instrumentos de capital, el balance congelado). Hay **dos fallas distintas**:

1. **Errores de información** — el comité razona bien sobre datos incompletos. Los resuelve la **verificación
   independiente (#4)**.
2. **Errores de modelización** — con datos correctos, el equity bridge asigna al común valor que pertenece a
   acreedores / financiadores futuros / inversiones no ejecutadas. Los resuelven el **cash bridge (#1)** + el
   **resolver de instrumentos (#2)**.

El **#3 (factor)** evita que decisiones individualmente razonables produzcan una cartera sobre-concentrada.

**El edge permanente de BORJA no es *encontrar* un instrumento (un LLM+web también lo encuentra) — es que, una
vez encontrado, calcula exacto qué cambia en cada escenario y en el retorno implícito, de forma reproducible.**

## 1. El marco que unifica todo: 3 objetos en la ficha viva

La ficha deja de mezclar hechos, supuestos y decisiones. **Tres secciones estructuradas** (no 3 agentes, no 3
docs):

| Objeto | Quién lo produce | Qué representa |
|---|---|---|
| **Evidence ledger** | determinismo + Verificador ciego | qué hechos están comprobados y bajo qué condiciones (con cita + fecha) |
| **Scenario economics** | comité **propone hipótesis**; el **código reconcilia** | cómo evolucionan caja, deuda, financiamiento, instrumentos y acciones por escenario |
| **Investment judgment** | PM bajo IPS; Auditor cuestiona | qué hacer con el activo al precio de hoy |

Principio rector: **el LLM aporta hipótesis (FCF, CAPEX, financiamiento, resolución de instrumentos); el código
hace la contabilidad.** El LLM nunca escribe la deuda neta terminal ni el valor por acción directo.

Trazabilidad del reloj lento: cada cambio registra *qué hecho cambió → qué hipótesis cambió → cuánto se movió
cada escenario → por qué el PM mantuvo/cambió su juicio.*

## 2. La pieza central: inventario de instrumentos + cash bridge por escenario (#1 + #2)

**#1 y #2 NO son dos cambios: son un inventario de instrumentos por nombre + un puente que lo lee por escenario.**

### 2.1 Inventario de instrumentos (registro por nombre, con cita al filing)
Un registro por instrumento material (converts, preferidas, warrants, capped calls, deuda con vencimiento < T):

```
instrument_id: MP_CONVERT_2030
type: convertible              # convertible | convertible_preferred | warrant | term_debt
principal_usd_m: 862.8
book_value_usd_m: 842.4        # para no doble-contar: si YA está en la deuda XBRL, flag en_deuda_xbrl=true
en_deuda_xbrl: true
maturity: 2030-03-01           # OJO si < T del escenario → se resuelve en el cash bridge, no como dilución terminal
conversion_price: 21.74
potential_shares_m: 39.68
settlement_options: [cash, shares, mixed]
seniority: unsecured_senior
hedge: capped_call             # capped call cubre dilución de 21.74 a 31.06
liq_preference_usd_m: null     # solo preferidas
accession: "0001193125-..."    # procedencia obligatoria
```

Detector determinista de inventario incompleto: el tag XBRL
`AntidilutiveSecuritiesExcludedFromComputationOfEarningsPerShareAmount` (en empresas con pérdidas, la dilución
potencial *solo* aparece ahí). Si supera un umbral y el inventario está vacío → flag CONFLICTED. **+ sumar el
ítem 8-K 3.02 a la guarda de frescura ya existente.**

### 2.2 Cash bridge por escenario (sources & uses — NO un DCF)
Para cada escenario `i`, el comité provee hipótesis económicas (no un modelo de capital markets):

```
fcf_cumulative_i          # FCF operativo acumulado a T (incluye CAPEX de mantenimiento)
new_equity_net_proceeds_i # caja levantada por emisión primaria
new_equity_shares_i       # acciones nuevas emitidas
new_debt_i / debt_repaid_i
distributions_i           # dividendos/recompras
```

El **código** reconcilia:
```
EV_{i,T} = métrica_terminal_i × múltiplo_i
C_{i,T}  = C_0 + Σ FCF_i + Σ EquityRaised_i + Σ DebtDrawn_i − Σ DebtRepaid_i − Σ Distributions_i
D_{i,T}  = D_0 + Σ DebtDrawn_i − Σ DebtRepaid_i − Σ DebtConverted_i
N_{i,T}  = acciones_0 × (1 + dilución_SBC_i) + new_equity_shares_i + shares_por_conversión_i
V_{i,T}  = max(0, EV_{i,T} + C_{i,T} − D_{i,T} − K_{i,T}) / N_{i,T}
```
donde `K_{i,T}` = claims senior al común que NO están en la deuda (preferidas vigentes según su derecho).

**Assert de cierre de caja (auditoría anti-doble-conteo):**
`C_0 + Σ FCF + Σ EquityRaised + Σ DebtDrawn − … = C_{i,T} ≥ caja_mínima_operativa`.

### 2.3 Las reglas que eliminan el doble conteo (determinismo, no juicio)
- **Emisión de equity:** sube caja **Y** acciones, las dos cosas juntas. Doble conteo aparece si se diluye sin
  reconocer los fondos, o si se suma caja **ya gastada** para construir los activos cuyo EBITDA se valora (OKLO:
  la caja de hoy es el presupuesto de obra → se consume en `fcf_cumulative`, no se agrega al EV).
- **Instrumento ya en la deuda XBRL** (`en_deuda_xbrl=true`): si convierte, se **resta** de la deuda **y** se
  suman acciones (no se cuenta dos veces). Si no convierte, queda en la deuda (no se re-suma como senior).
- **Recompras — convención de retención total:** si el FCF baja deuda, el Analista **no puede además** bajar
  acciones por recompras (el doble conteo de VST). Dividendos intermedios se reconocen en el retorno, sin
  contarlos como caja retenida al terminal.
- **Dilución = OUTPUT, no input.** Se **deriva** de los movimientos (SBC + emisión + conversión), es
  **scenario-dependent** (bull levanta poco; bear emite más a menor precio). Se conserva `dilución_total` como
  campo de análisis, pero no sustituye a los movimientos que la originan.

### 2.4 Resolver de instrumentos (#2) — por términos, no por etiqueta de escenario
**NO** `if scenario==bear: convertible=debt`. La resolución es por **términos contractuales + valor del común en
el escenario**:
- **Convertible:** convierte si `V_i ≥ conversion_price` (if-converted). Respeta settlement (cash/acciones/mix) y
  capped call. Si vence antes de T → se resuelve en el cash bridge (repago/refinanciación/conversión).
- **Preferida convertible:** NO es automáticamente deuda exigible porque la acción cayó. En **bear de
  liquidación** → aplica la preferencia (`max(piso contractual, valor as-converted)`) antes del común. En **bear
  going-concern** → valora el derecho vigente, sin asumir rescate inmediato. En **bull con conversión** → cuenta
  acciones y NO vuelve a restar la preferencia.
- **Warrant:** fuera del dinero → no se ejerce. Ejercicio con pago → entra caja; net-share-settlement → menos
  acciones, sin caja.

Modo de falla #1 (prohibido): **contar dos derechos incompatibles** — restar el principal del convertible *y*
sumar todas sus acciones; o restar la preferencia *y* sumar las acciones de conversión. Un **bear de distress**
puede requerir **valor de recuperación**, no un múltiplo de empresa en marcha.

Implementación: 3 tipos (convertible, convertible_preferred, warrant) + 2-3 resoluciones por instrumento. **No**
una cascada universal de tramos de deuda ni pricing estocástico de convertibles. **No se publica un valor por
acción de un nombre con instrumentos materiales sin resolverlos explícitamente.**

### 2.5 Pre-revenue (OKLO class, ~70% del universo)
No inventar 5 años de flujos. `FundingGap = max(0, necesidad de caja futura + caja_mínima − caja_disponible −
financiamiento_comprometido)`. Si > 0, el Analista debe explicar con qué instrumento se cubre y qué pasa con las
acciones. Si no puede → marcar **`funding_unresolved`** (NO fabricar una dilución arbitraria). Si un escenario
implica insolvencia sin rescate → **el común puede valer cero**. Default cuando falta el dato: para la que quema,
la caja de hoy vale **cero** en el terminal + bridge incompleto; para la generadora, congelado. **El default
siempre perjudica al nombre** (al revés que hoy).

## 3. #3 — Concentración por factor (config del IPS, P1, en paralelo)

Tercera dimensión de concentración, independiente de sector y cuello. **No** porque 4 acciones caigan juntas sean
la misma apuesta — el IPS debe captar **dependencia económica compartida**, no correlación de precios reciente.

- **Vocabulario cerrado ~8 drivers** (propiedad del operador), 3 intensidades: **1.0** (central para la tesis) /
  **0.5** (material no dominante) / **0** (incidental). Máx 1 primario + 2 secundarios por nombre. El Analista
  propone cargas citando ingresos/backlog por mercado final; el Bear cuestiona; el reloj lento versiona.
- **Cap duro:** `Exposure_f = Σ wⱼ · sⱼ_f ≤ 30%` del NAV (rango de calibración 25-35%, derivado de la pérdida
  tolerable del IPS). Para posiciones con opcionalidad/apalancamiento, usar exposición económica, no capital
  invertido.
- **Complemento — 3 shocks predefinidos** con pérdida por nombre estimada por el PM (contracción capex IA /
  retiro de política industrial US / shock de tasas-liquidez): `PortfolioLoss_f = Σ wⱼ · Loss_{j,f}`. Tags para el
  cap duro; shocks para informar al PM de la **magnitud** (dos nombres con el mismo tag pueden perder 20% vs 65%).
- **Tag derivado determinista:** todo nombre con `FundingGap > 0` recibe "depende de mercado de capitales abierto".
- **Estadística = alarma, no fuente:** correlación móvil de retornos residuales entre pares SIN tag común; si
  > ~0.6 → revisar tags. Nada de PCA / multifactor / Monte Carlo todavía. No tratar la sensibilidad genérica a
  tasas como un cuello específico de la tesis.

## 4. #4 — Verificación independiente (desdoblar el Verificador, NO el Auditor)

Tres trabajos distintos, no mezclar: **Verificador** (¿los hechos que alimentan la valuación son correctos y
completos?) · **Bear** (¿la tesis puede fallar aunque los hechos sean ciertos?) · **Auditor** (¿la decisión del
PM está justificada y cumple el IPS?).

La **independencia es de EVIDENCIA, no de modelo**: un 2º agente con otro prompt sobre el **mismo data pack** NO
es independiente. Dos canales:
- **Canal principal (research):** Analista → Dossier → Bear (sobre el data pack). Como hoy.
- **Canal independiente (hechos materiales):** ticker + fecha de corte + **protocolo fijo** → consulta fresca a
  filings/exhibits → **extracción CIEGA** (no ve la respuesta numérica del Analista; nada de "el Analista dijo
  196M, verificá" → eso ancla) → reconciliación determinista con tolerancias → PASS / REVIEW / FAIL.

**Qué verifica — 3 paquetes de evidencia** (no 3 números sueltos):
1. **Liquidez y deuda** (caja, deuda, vencimientos, cambios económicos materiales).
2. **Capitalización** (acciones, converts, preferidas, warrants, derechos materiales) — el caso MP prueba que un
   share count sin sus instrumentos es engañoso.
3. **Premisa de la tesis** (contrato clave / capacidad / financiamiento / permiso que sostiene la valuación).

Paquetes 1-2 estructurales; el 3 se adapta al negocio. La **guarda determinista de 8-K ya existe** y no se
duplica; la verificación independiente busca además **instrumentos omitidos o interpretaciones erradas** dentro de
información que SÍ está disponible.

- **Triggers:** compra inicial / aumento material propuesto por el PM · conflicto de una guarda determinista ·
  cambio sustancial de tesis. **No** diario, **no** en cada recálculo del reloj rápido. La ficha registra el set
  de fuentes + fecha de verificación; si cambió un filing relevante se invalida ESE chequeo, no todos.
- **Resolución:** si cambia un dato del bridge → recálculo determinista + se devuelve el impacto al PM. Ausencia
  de verificación (presupuesto agotado / fuente no verificable) → **"revisión pendiente", NUNCA PASS**.
- **Presupuesto:** NO un 2º Opus. Recuperación determinista de fuentes + extracción con modelo barato + escalada
  a modelo fuerte solo ante término contractual ambiguo. Techo de diseño **$8-12/mes** para el canal, costo
  medido por corrida.
- **Métrica de valor (la que dice si cerramos la brecha):** **errores materiales NUEVOS detectados**, no
  afirmaciones confirmadas. + **muestra aleatoria ~5%** de nombres no disparados para medir la tasa de error del
  data pack. Cada clase de discrepancia recurrente → **nueva guarda determinista**.

## 5. Los 5 tests de aceptación (se exigen antes de dar por válido el bridge)

| Test | Resultado obligatorio |
|---|---|
| Caja usada para construir plantas | baja la caja terminal; el activo NO se suma dos veces |
| Emisión de acciones para cubrir CAPEX | suben caja **y** acciones; se reconcilian |
| Convertible que se transforma en acciones | desaparece la obligación convertida; aparece la dilución |
| Bear con valor residual insuficiente | el común puede valer **cero**; preferencias respetadas por contrato |
| Dossier deliberadamente incompleto | el verificador ciego **encuentra solo** el instrumento/hecho omitido |

Los 4 primeros, deterministas. El 5º mide el canal ciego. **Más informativos que comparar rankings.** Los 4
nombres (VST/MP/IESC/OKLO) quedan como set de evaluación — **sin asumir que el LLM externo es la verdad**: se
comparan los claims recuperados de fuente primaria, los errores económicos, el impacto en el bridge y el costo.

## 6. Plan por fases (F1-F3 = P0; F4 en paralelo)

- **F1 — Integridad del equity bridge:** cash bridge, sources & uses, acciones por escenario, reglas anti-doble-
  conteo + los 4 asserts. Corrige OKLO y buena parte de VST. *(toca `backend/agentes/ficha.py` `valor_accion`/
  `calcular_puente`; el comité pasa a emitir las hipótesis del cash bridge por escenario.)*
- **F2 — Instrumentos de capital materiales:** inventario + resolver (convertible/preferida/warrant), MP como caso
  de prueba. Detector `AntidilutiveSecurities…` + ítem 3.02 en la guarda.
- **F3 — Verificación independiente:** canal ciego, 3 paquetes, PASS/REVIEW/FAIL en el flujo de decisión de
  capital, modelo barato + escalada.
- **F4 — Concentración por factor (paralelo):** vocabulario de drivers, cargas 0/0.5/1, cap 30%, 3 shocks. No
  cambia las otras reglas del IPS.

**Validación post-build:** re-correr el LLM+web externo sobre los 4 nombres y medir cierre de brecha por **líneas
del puente** (no ranking). Ese es el único uso que vale de un tercer par de ojos.

## 7. Qué queda EXPLÍCITAMENTE afuera (para no sobre-construir)
- **No** un DCF completo por nombre (duplica supuestos: trayectorias anuales, WACC, valor terminal).
- **No** pricing estocástico de convertibles ni cascada universal de tramos de deuda.
- **No** PCA / multifactor / correlaciones dinámicas / Monte Carlo de cartera.
- **No** permitir que el LLM escriba la deuda neta terminal o el valor por acción sin reconciliación del código.
- **No** validar por magnitud del bear ("el externo es más extremo") — validar por la identidad económica: *cada
  dólar de valor, cada obligación y cada acción nueva aparece exactamente una vez, en el escenario correcto.*

## 8. Decisiones del operador (defaults elegidos, ajustables)
- Taxonomía de factores: **arrancar con ~8**, el operador la cierra.
- Cap por factor: **30%** inicial (25-35% calibrable).
- Presupuesto del canal independiente: **$8-12/mes** (tope mensual global ya subido a $100 en fase build).
- Orden: **F1 → F2 → F3**, **F4 en paralelo**.
