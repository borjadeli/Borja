# 68 — Auditoría del brief 67 (análisis presente+futuro) — IA 1

> Devolución de **IA 1**. **Pendiente converger con IA 2.** Dictamen: los defaults van bien, pero D2 tiene un
> agujero conceptual y D4 una trampa de implementación; y el brief no ve que **gran parte de la tesis de
> futuro se apoya en hechos presentes verificables** (contratos, financiación, fechas regulatorias) → cambia
> D3. ⚠️ El pegado del operador se cortó al final de D6 (Analista, punto 5 "asimetría"). Captura fiel.

## D1 · Balance presente/futuro — correcto en el fondo, mal especificada la combinación
- **NO compensatorias (no promedio/score sumado).** `convicción = min(calidad de tesis, solvencia para
  llegar a ella)`. Tesis 9/10 con runway que no llega al hito → convicción baja, no 6.
- **Salud presente depende de la ETAPA:** a una pre-revenue no se le piden márgenes; "salud" = runway vs
  camino crítico, eficiencia de capital (caja quemada por hito logrado), estructura de capital. Mismo
  checklist para madura y pre-revenue = penaliza mal a la segunda.
- **Runway ajustado por dilución:** ATM no ejercido / equity line / "acceso a capital" NO son runway. Solo
  caja + inversiones líquidas + facilidades comprometidas sin condiciones. Warrants/convertibles/ATM =
  **overhang de dilución** (otro dato).
- **Falta el HISTORIAL DE EJECUCIÓN (el mejor predictor):** tasa de cumplimiento de hitos guiados por el
  management en 2-3 años (qué prometieron, para cuándo, qué entregaron, con cuánto atraso). Hecho presente
  verificable (transcripts/filings viejos); dice más sobre hitos futuros que cualquier análisis de la tesis.
  Va en la pata presente Y como descuento en D2.
- **"Tracción" aparece en D1 y D2** → definir en UN solo lugar (sugiere D2) para no contarla dos veces.

## D2 · Invertibilidad temporal — los 3 ejes son correctos pero INSUFICIENTES
- **Falta el eje que separa la cuántica: TIPO DE RIESGO REMANENTE** (qué falta demostrar). Escalera:
  | Riesgo | Pregunta abierta | Ejemplo | Elegibilidad máx |
  |---|---|---|---|
  | Científico | ¿es posible? | cómputo cuántico tolerante a fallas a escala útil | carril especulativo |
  | Ingeniería | es posible, ¿funciona a escala a costo razonable? | primer reactor de un diseño nuevo | satélite |
  | Comercial | funciona, ¿alguien paga lo suficiente? | tecnología validada buscando offtakers | core si hay financiación |
  | Escala/ejecución | hay clientes, ¿crecen sin romperse? | fabricante con backlog creciente | core |
  La cuántica queda afuera **por la razón correcta**: el hito que valida la tesis depende de una pregunta
  **científica abierta**, y nadie puede fecharla (no es solo "no genera ingresos").
- **Matiz sobre "ingresos":** algunas cuánticas listadas SÍ facturan (contratos de investigación/gobierno/
  acceso a hardware) → un gate "revenue>0" las deja pasar. La regla correcta: **tracción en el MERCADO DE LA
  TESIS** — ingresos/contratos que validan el caso de negocio que el precio descuenta. Un ingreso que no
  valida la tesis cuenta para salud presente (D1), no para invertibilidad.
- **Eje 3 reescrito — escalera de evidencia de tracción (mata el "MOU como contrato"):**
  `0` PR/"conversaciones"/MOU/LOI no vinculante (cuenta CERO) · `1` piloto pago / subsidio obligado (no solo
  anunciado) / selección en programa · `2` contrato vinculante con condiciones precedentes (préstamo
  condicional, PPA sujeto a permisos/FID) · `3` vinculante sin condiciones materiales, take-or-pay, backlog
  con depósitos · `4` revenue recurrente en el mercado de la tesis. **La contraparte pondera:** take-or-pay
  con un hyperscaler/utility IG vale más que con una startup.
- **Eje 2 — horizonte RELATIVO, no absoluto.** Separar dos hitos: **próximo hito que re-ratea** (debe caer
  dentro del runway financiado = supervivencia) y **hito de autosuficiencia (T\*)** (el horizonte depende del
  sector: nuclear/infra 7 años con fechas regulatorias públicas pueden ser más invertibles que 3 años de
  software con hitos autodeclarados). **Lo que importa: que la fecha la fije un TERCERO** (regulador,
  contraparte, cronograma de obra financiado), no el management. Cada fecha se **descuenta por el historial
  de cumplimiento** (D1): si el mgmt llega 50% tarde, un hito a 24m se trata como a 36m.
- **Tiers (gate determinista):**
  | Tier | Requisitos (todos) | Uso |
  |---|---|---|
  | A·Core | riesgo comercial o de escala · runway ajustado ≥ meses al hito + 6 de colchón · próximo hito ≤24m · tracción ≥3 · T* ≤ horizonte del sector | posición grande |
  | B·Satélite | riesgo de ingeniería+ · runway ≥ hito (sin colchón) · tracción ≥2 · T* ≤ horizonte +2a | posición media |
  | C·Especulativo | camino plausible pero sin financiar, o riesgo científico | carril, cap chico |
  | D·No elegible | runway <12m sin financiación comprometida, o hitos sin fecha | nada |
- **Override del PM ASIMÉTRICO:** puede BAJAR de tier libremente; **subir solo UN tier** con justificación
  escrita + falsador fechado + log que revisa el Auditor. Sin fricción, el gate es decorativo.
- **Decaimiento por atraso:** cada hito que se corre >2 trimestres baja el tier un escalón hasta que se cumpla.

## D3 · Quién cuestiona la tesis — AMPLIAR EL VERIFICADOR (el insight que el brief no vio)
El brief asume que el Verificador no puede tocar el futuro. Pero **los insumos del gate D2 son hechos
PRESENTES verificables:** si el contrato es vinculante o un MOU, si el préstamo está cerrado o es condicional,
si la fecha la puso un regulador o es aspiración del CEO, si el subsidio está obligado o solo anunciado →
todo se verifica contra 8-Ks, exhibits, dockets regulatorios, documentos de agencias. **El Verificador
verifica la EVIDENCIA de la tesis, no juzga la tesis.** Es su mismo trabajo con perímetro más amplio, y es
donde más se equivoca un LLM entusiasmado. Reparto:
- **Verificador:** verifica los insumos del gate (grado de tracción, estado de la financiación, origen de las
  fechas). No opina.
- **Bear:** ataca la tesis con mandato EXPLÍCITO de madurez (por qué el riesgo remanente está mal
  clasificado, por qué el hito se va a correr).
- **Gate:** determinista, asigna el tier.
- **Auditor:** sigue a NIVEL CARTERA — exposición agregada a tiers B/C, concentración de hitos en el mismo
  trimestre o en la misma fuente de financiación, y **calibración: qué % de falsadores se resolvió a favor y
  si los overrides del PM terminan mejor o peor que el gate** (dice si el juicio del PM agrega valor o ruido).
  Si el Auditor evalúa cada tesis individual, duplica al Bear.

## D4 · Calculadoras deterministas — sí, pero el default solo MUEVE la improvisación de lugar
Si la calculadora es determinista pero los supuestos los pone el LLM a mano, hay apariencia de rigor sin
rigor. 4 condiciones: (1) **insumos con procedencia** (XBRL/guidance/consenso/supuesto; los supuestos con
RANGO, no punto, marcados en el dossier); (2) salida como **grilla de sensibilidad**, no un T* único (revenue
requerido en el año T bajo distintos márgenes terminales y costos de capital); (3) **por acción, con
dilución** (el gap de financiamiento → acciones nuevas al precio actual/descuento, burden por acción; a menudo
cambia la conclusión); (4) **BASE RATES** (lo más anti-especulación y lo que falta): contrastar "el precio
exige pasar de X a Y de revenue en N años" contra la clase de referencia (tablas de Mauboussin) —
*"requiere 60% CAGR por 7 años"* suena posible; *"lo logró <1% de las empresas de ese tamaño"* es la frase
que el PM necesita. + chequeo de **TAM** (qué market share implica el burden).

## D5 · PM + macro — de acuerdo, con una excepción fundamental
- **La VENTANA DE FINANCIAMIENTO NO es macro de fondo: es parte del camino crítico** de una pre-revenue.
  Tasas, estado de las emisiones de equity del sector, spreads de crédito determinan si el hito sin financiar
  se podrá financiar y a qué dilución. Va al memo macro como indicador explícito (**"ventana abierta /
  cerrándose / cerrada"**), conectado al eje 1 de D2.
- **Datos que parecen flujos pero son estructura de capital del NOMBRE → al dossier, no al memo:** short
  interest + costo de préstamo, overhang de warrants/convertibles, ATM vigente, lockups por vencer (afectan
  dilución y riesgo de la posición).
- **Afuera (como el default):** posicionamiento agregado, flujos de ETFs, sentimiento.
- **Dosis:** memo de **una página, idéntico para todos, sin tickers**, y el PM lo recibe **antes** de los
  dossiers (marco), no al lado de cada uno.

## D6 · Prompts
**Analista — imponer un ORDEN de razonamiento** (el orden evita que la narrativa se coma el análisis):
1. **Cuello de botella y captura de valor:** por qué ESTA empresa captura el valor y no sus clientes/
   proveedores/un competidor que resuelva el cuello por otro camino. Un cuello que se libera o lo capturan
   otros = falsador ESTRUCTURAL.
2. **Tipo de riesgo remanente** (escalera D2) con justificación.
3. **Camino crítico:** hitos, fecha, quién la fija, financiación de cada uno (citar el pack).
4. **Qué exige el precio:** citar la calculadora D4 + el base rate. Prohibido improvisar números.
5. **Asimetría real:** el downside de una empresa que quema caja NO está acotado por la caja actual —
   estimar el valor si falla el próximo hito, con la caja que QUEDE tras la quema hasta ahí + la dilución.
   Si el prompt no lo dice, el LLM escribe "downside protegido por la caja".
6. **Falsadores ESTRUCTURALES fechados:** además de "si el dato X no se confirma", falsadores sobre la
   TESIS: "si al Q2-2027 no hay contrato vinculante con contraparte investment grade", "si un competidor
   alcanza costo/unidad menor que Y", "si el hito regulatorio Z se corre más de dos trimestres".

**Instrucción explícita de cómo ponderar futuro/precio/tiempo (al Analista):**
> *El futuro solo cuenta en la medida en que tenga FECHA, FINANCIACIÓN y EVIDENCIA. Lo que no cumple eso vale
> como opción → carril especulativo, aunque la tesis sea brillante. El TIEMPO es el precio de la tesis: cada
> año de atraso cuesta el retorno requerido compuesto + la dilución de financiar ese año. Una tesis correcta
> con 3 años de atraso puede ser perdedora.*

**★ TEST DE ATRASO (campo OBLIGATORIO del dossier, la herramienta más simple para separar invertible de
especulativo):** *"¿qué pasa con esta inversión si todo sale bien pero dos años más tarde?"*

**PM — separar CONVICCIÓN (qué tan seguro de la tesis) de MADUREZ (el tier):** el **tamaño lo define el
TIER**; la convicción solo lo **modula dentro del tier**. "Convicción altísima en tesis tier C" = tamaño máx
de carril especulativo, sin excepción salvo el override de un escalón documentado. Para que el PM sea experto
en tesis (no solo sizer): en cada decisión debe decir **qué hito, si se cumple, lo subiría de tier, y qué
hito, si falla, lo haría salir** → convierte su experiencia en predicciones auditables.

## Resumen de cambios (IA 1)
D1: presente = TECHO (min, no promedio) + runway ajustado por dilución + historial de cumplimiento de hitos.
D2: + eje tipo de riesgo remanente · tracción en el mercado de la tesis con escalera de evidencia · horizontes
relativos al sector · tiers con override asimétrico + decaimiento por atraso. D3: Verificador verifica la
EVIDENCIA de la tesis · Auditor mide calibración (overrides del PM vs gate). D4: inputs con procedencia +
grilla de sensibilidad + burden por acción + base rates. D5: incluir ventana de financiamiento + estructura
de capital del nombre; excluir flujos. D6: orden de razonamiento impuesto + downside real + test de atraso.
