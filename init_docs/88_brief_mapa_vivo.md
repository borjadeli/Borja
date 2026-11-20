# 88 — Brief para triangular: el mapa vivo (que el PM entienda el futuro) (2026-11-20)

> Brief para que 1-2 IAs externas critiquen el diseño ANTES de construir. Objetivo: que el mapa de cuellos deje
> de ser un esqueleto estático y se vuelva un **radar económico vivo** que el PM usa para entender el futuro.

## 1. La visión (qué queremos)
La tesis de BORJA es **industrias del futuro** (power-law en cuellos / picks-and-shovels). Queremos que el PM
**entienda cómo viene el futuro con DATOS, no con narrativa**:
- Si una empresa está en un **cuello clave, real, creciendo** (demanda > capacidad, márgenes buenos, revenue
  creciendo) y **todavía barata** → el PM debería valorarla **más**. *Ej (ilustrativo): fotónica — margen alto,
  solución a la escasez de cobre, clave para IA, demanda gigante, empresas que no dan abasto y aún baratas.*
- Si un cuello es **pura promesa/especulación** (empresas que pierden plata, sin revenue) → **NO interesa**,
  salvo que aparezca algo concreto (que **empiece a generar revenue**). *Ej: computación cuántica.*
- El PM debería tener una noción **forward-looking**: qué tan grande es la empresa, qué tan grande el sector,
  qué tanto va a crecer.
- El mapa tiene que estar **muy bien actualizado, vivo** (refresco ~semanal), con **datos VERIFICADOS (no
  inventados)**. El **discovery es el experto y el dueño** de mantenerlo dentro de este marco.
- Empresas **fuera del mapa**: las agrega el operador a mano (`ops.solicitar`). El discovery sigue cuello-first.
  (Decisión tomada, no se discute acá.)

## 2. El estado real HOY (grounded, verificado en código/datos)
- El mapa son **142 nodos de cuello** (`nx_nodo`), bien estructurados por `cluster` (28: photonic_components=8,
  optical_modules=5, minor_metals=10, nuclear_gen=4, dc_power=6…) y `factor_macro` (12: networking_optical=21,
  generation=18, datacenter=16…). **La fotónica YA está mapeada** (13 nodos ópticos/fotónicos).
- **CLAVE: los 142 cuellos están TODOS en estado `promesa`. CERO `confirmado`. Y hay 0 hechos (`nx_hecho=0`).**
  El mapa tiene la distinción promesa/confirmado (confirmado = "primer hecho de monetización REAL: revenue
  contratado") pero **nunca se alimentó con hechos → ningún cuello transicionó jamás**. ⇒ **hoy el mapa NO puede
  distinguir fotónica (real) de quantum (especulación): los dos son "promesa".** Es el problema, hecho dato.
- El **tablero** (`mapa_vivo.py`, determinista, $0): agrega XBRL por cuello (ventas, margen bruto ponderado,
  capex/ventas, inventario/ventas, RPO, crecimiento YoY). **Está construido, FUNCIONA (lo corrimos), pero NADIE
  lo llama** — desconectado. Compara dos períodos → señal de disolución.
- **El PM hoy recibe el cuello como NARRATIVA** (el texto `negocio_y_posicion_cuello` del dossier + el memo
  macro), NO el estado económico cuantitativo ni el confirmado/promesa. El `contexto_mapa` (cuello + empresas
  vinculadas) va al **Analista**, no al PM directamente.
- Defensas de integridad que YA existen: tabla de transiciones **determinista** (observable + umbral; el LLM
  trae el observable, nunca emite el juicio compuesto), `archivo.py` (lápida + anti-reingreso), curador (un
  cuello nuevo exige **≥2 fuentes primarias**), principio "NO inventa" (tablero=XBRL, fuentes clase A-F).

## 3. El diseño a construir (converger/criticar)
1. **Correr el tablero** (`mapa_vivo`) sobre los cuellos del universo → **persistir point-in-time** (para que la
   disolución, que es un delta, tenga contra qué comparar). Cadencia semanal.
2. **Disparar las transiciones**: promesa→confirmado cuando el tablero muestra revenue real/creciente;
   →disolución cuando capex se dispara + inventario acumula + margen cede.
3. **Feed al PM** (y al factor C del score de oportunidad): estado del cuello (confirmado/promesa/disolviéndose)
   + economía (ventas, crecimiento, margen, demanda vs capacidad) → el PM valora más un nombre barato sobre un
   cuello confirmado y creciente; trata quantum como especulativo salvo revenue.
4. **Discovery dueño**: mantiene el mapa fresco y verificado dentro del marco de la brújula.

## 4. Las preguntas a ATACAR (en orden de importancia)
1. **Forward-looking sin caer en el hueco del doc 72 (futuro narrativo).** El tablero da el estado ECONÓMICO
   ACTUAL del cuello (crecimiento, margen, capex, RPO). ¿Qué tanto de "qué tan grande será el sector / cuánto
   crecerá" puede/debe ser determinista (extrapolar la tendencia del tablero) vs juicio LLM? ¿Cómo evitamos que
   "cuánto crecerá" vuelva a ser narrativa optimista en vez de economía?
2. **¿Cómo debe PESAR el cuello en la decisión del PM sin DOBLE CONTEO?** El nombre ya se valúa por su propia
   economía (futuro.py: qué exige el precio). Si además subimos por "buen cuello", ¿no contamos dos veces el
   mismo tailwind? ¿El cuello es un modulador, un desempate, un gate de calidad, o solo contexto?
3. **¿Qué dispara promesa→confirmado de forma HONESTA y automática?** ¿Alcanza "revenue agregado del cuello
   creciendo" del tablero, o necesita revenue CONTRATADO (RPO/8-K 1.01)? ¿Umbral? ¿Quién trae el observable —
   el tablero determinista, o el discovery/LLM (con el riesgo de inventar)?
4. **¿Cómo mantener el mapa HONESTO / no mandarse cagadas?** Un cuello mal asignado, o uno que se disolvió pero
   sigue "caliente", infla el score de un value-trap. Más allá del tablero + archivo + curador, ¿qué falta para
   que un mapa semanal no se pudra? ¿Cómo validamos la SEMILLA (¿son los 142 cuellos correctos? ¿falta alguno?)?
5. **Cadencia y costo:** semanal, determinista ($0 el tablero). ¿Es suficiente? ¿El discovery como dueño cómo
   evita inventar (solo confirma observables verificados)?

## 5. Qué NO estamos preguntando
- No "¿cuello-first o value-first?" (decidido: cuello-first; el valor fuera del mapa lo inyecta el operador).
- No reabrir que la tesis es industrias del futuro (es el mandato).
- El tablero ya existe y funciona; la pregunta es cómo CABLEARLO y USARLO bien, no si construirlo.
