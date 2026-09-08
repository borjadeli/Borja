# 23 — "Demanda confirmada": estándar de evidencia + el límite hecho→PM (caso AAOI/Amazon)

> ⚠️ **DIDÁCTICO / SUPERADO — ver `00_MAPA_DOCUMENTOS.md`.** Resolvió un crux; formalizado en los
> gates de demanda G1-G4 de **doc 33**. Lectura de contexto, no referencia operativa.

> Para triangular. La ÚNICA decisión de fondo que quedó abierta del motor de evidencia:
> qué cuenta como *demanda confirmada* (toca el gate), ilustrada con un caso **real** con
> todos los hechos citados. Incluye el límite hecho→decisión (el norte del sistema).

## ⚠️ Corrección (verificada contra la fuente primaria, post-IA 1)
La primera versión de este doc **sobre-caracterizó** el deal — el error exacto que el sistema
existe para prevenir, cometido en el propio diseño. Verificado contra el 8-K y el 10-Q:
- **8-K:** *"the balance vesting over time based on **discretionary purchases** by or on behalf
  of Amazon… **up to a total of $4 billion**."* → los USD 4.000M son un **techo de vesting sobre
  compras DISCRECIONALES**, NO un compromiso de compra.
- **10-Q:** *"We **do not have any long-term purchase commitments** (in excess of one year) with
  any of our customers, most of whom purchase our products on a **purchase order basis**."*
- Por lo tanto: donde abajo dice "compromiso de compra" y "exclusividad", la fuente dice
  **compras discrecionales** y **sin compromiso de largo plazo**. Lo correcto: **relación
  comercial VALIDADA**, no demanda COMPROMETIDA.

**Estándar adoptado (IA 1), tres estados:**
- **VALIDATED** — contraparte nombrada + acuerdo operativo real. *Solo SOSTIENE el nodo.*
- **COMMITTED** — obligación de compra ejecutable / backlog no cancelable / mínimo contractual /
  take-or-pay, con plazo. *Pasa el gate.* (Un monto redactado abre COMMITTED **solo** si el filing
  dice inequívocamente que existe una obligación mínima material, aunque oculte el número; si se
  redacta el monto **y** la naturaleza vinculante → no alcanza.)
- **REALIZED** — compras/shipments/revenue observados y **repetidos**. *Pasa el gate.*
- El warrant atado a volumen **cuantifica el incentivo y la dilución, NO la demanda** (y la
  dirección es AAOI pagando a Amazon, no al revés). AAOI = **VALIDATED**, no COMMITTED.

## Contexto (para una IA externa)
Sistema quant de small/mid caps de "industrias del futuro" (cuellos de botella). Principio
rector: **datos y límites duros deterministas; el LLM trae hechos citados y NUNCA inventa un
número de decisión; un PM-LLM decide DENTRO de caps deterministas.** Acabamos de construir el
motor de evidencia (recuperar filing real → extraer citando → verificar → cachear) y el
full-text search de EDGAR para encontrar la evidencia de forma productiva (consultar, no
crawlear). Todo lo de abajo es info dura: hechos fechados, citados, verificables.

## El caso real — AAOI (Applied Optoelectronics), óptica para datacenters de IA
Todo con FUENTE A (filing/exhibit), fechado y citado:
- **DEMANDA:** *"Transaction Agreement, by and between Applied Optoelectronics, Inc. and
  Amazon.com, Inc."* (EX-10.1 del 8-K, 2025-03-13) — compromiso de compra + exclusividad +
  forecast. Cliente Microsoft también (EX-10.1, 2023-05-03).
- **PERO términos REDACTADOS:** *"certain identified information has been excluded"* → el
  **volumen y el precio NO son públicos**.
- **DILUCIÓN (mismo deal):** warrants a Amazon (EX-4.01, misma accession) atados a **tramos de
  volumen de compra**. Es decir: el mismo hecho confirma demanda **y** diluye.
- **CAPACIDAD:** contrato design-build de **FAB4 / OMD3** (EX-10.1/10.2 del 8-K, 2026-07-01) —
  expansión de manufactura.
- **FUNDAMENTALS:** revenue Q $151.1M (+51% YoY), gross margin 29.1% (verificado contra XBRL).

## La cadena de decisión (el norte, ilustrado con este caso)
1. **HECHOS** (deterministas, citados) — los de arriba. Cero opinión del LLM.
2. **LÍMITES DUROS** (deterministas, **antes** del PM): arquetipo (Growth) · gate (G1 orgánico
   DERIVED ok; G2 continuidad **ahora sí** con el Transaction Agreement de Amazon) · fragility
   (dilución del warrant + capex de FAB4 → CRR) · **HARD CAP** (máx % de cartera).
3. **PM-LLM** (juicio **dentro** de la caja): *"demanda confirmada + dilución + parada en un
   cuello + expandiendo capacidad → potencial enorme → la elijo para mi cartera"* — pero **solo**
   entre las que pasan el gate, **dentro** del hard cap, razonando sobre los hechos (sin inventar
   ninguno), y con los **triggers de salida** escritos al entrar.

## Las preguntas a triangular
1. **Redacción:** ¿un Transaction Agreement con **contraparte nombrada** (Amazon) + exclusividad
   + warrants atados a volumen cuenta como **demanda confirmada** (abre/pasa el nodo), aunque el
   número esté **redactado**? ¿O sin *número + unidad + fecha* público NO abre (regla estricta del
   doc 22) y solo *sostiene*? ¿Dónde ponés la línea?
2. **Proxy cuantificado:** si el volumen está redactado, ¿la **estructura del warrant** (acciones
   por tramo de volumen de compra) sirve como la **señal costosa cuantificada**? Es disclosure de
   la contraparte **pagando con equity** para asegurar suministro → ¿es señal costosa fuerte?
3. **Dilución simultánea:** el mismo hecho abre demanda **y** levanta CRR/dilución. ¿Cómo se marca
   sin matar la tesis ni ignorar el riesgo? ¿El hard cap por CRR es suficiente?
4. **Doble filo de la capacidad:** expandir capacidad **alivia** el cuello. ¿Es señal alcista de la
   **empresa** o **falsificador del nodo**? ¿Ambos? ¿Cómo debería ponderarlo el sistema (bullish
   para el nombre, bearish para la durabilidad del cuello)?
5. **El límite hecho→juicio:** *"potencial enorme"* es una **inferencia** del PM. ¿Está bien que el
   PM la haga —mientras no invente hechos y respete el cap— o hay que acotarla más? ¿Qué NO debería
   poder hacer el PM con estos hechos?

## Qué NO estamos preguntando
Si AAOI es buena inversión (eso lo decide el PM dentro de caps, y no es el punto). Preguntamos por
el **estándar de evidencia de "demanda confirmada"** y por el **límite hecho→decisión**.

Devolvé crítica concreta y priorizada; donde discrepes, tu alternativa. Sin sobreingeniería.
