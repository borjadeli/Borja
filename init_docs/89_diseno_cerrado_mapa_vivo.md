# 89 — Diseño cerrado: mapa vivo, VERSIÓN MÍNIMA (2026-11-20)

> Converge el brief doc 88 con DOS críticas externas (IA 1 + IA 2, ambas con auto-corrección) + un test de $0.
> **Consenso fuerte, no hizo falta IA 3.** La lección: construir la versión MÍNIMA y MEDIR si cambia alguna
> decisión antes de construir más. El valor probable es **defensivo** (evitar 2-3 value-traps/año), no ofensivo.

## 1. Lo que el test de $0 PROBÓ (economía cruda, hoy)
```
FOTÓNICA/ÓPTICA (LITE/COHR/AAOI/FN):  ventas $15,229M · op/ventas  +7%   → CONFIRMADO
QUANTUM (IONQ/QBTS/RGTI):             ventas   $162M · op/ventas −506%   → PROMESA
```
Un número determinista separa lo real de la especulación. El núcleo funciona. (+ confirma que la **pureza**
importa —Fabrinet/EMS hunde el margen del grupo— y que **dentro** de un cuello confirmado los nombres varían
—AAOI −12%— ⇒ el cuello es gate/contexto, no sizer; `futuro.py` decide el nombre.)

## 2. El principio converjido (las 3 devoluciones)
**El cuello NUNCA suma valor.** El tailwind de un cuello bueno YA está en las ventas/márgenes que ve `futuro.py`
— sumarlo es doble conteo. El cuello entra solo como **FILTRO** (y, a mediano plazo, como **calibrador de
credibilidad** vía tasa base — diferido, §4). Test de doble conteo (IA 2): si el factor C correlaciona fuerte con
el crecimiento propio de la empresa, está duplicando → sacarlo.

## 3. IMPRESCINDIBLE — construir ahora (sin esto el mapa MIENTE)
1. **"Confirmado" exige ECONOMÍA REAL, no solo revenue.** Materialidad (ventas atribuibles TTM ≥ ~$100M y ≥2
   empresas ≥$25M) + margen bruto positivo + **pérdida operativa ≤ ~50% de ventas** + crecimiento YoY > 0 dos
   trimestres. (Sin el gate de pérdidas, quantum pasa como confirmado — lo probamos: −506%.)
2. **Panel SAME-STORE.** El crecimiento se calcula solo con las empresas presentes en los DOS períodos — si no,
   agregar un nombre con `ops.solicitar` se lee como "crecimiento". Lápida, no borrado (anti supervivencia).
3. **Pureza + cobertura, versión mínima.** Un **peso manual** por vínculo empresa→cuello (leer segmentos XBRL se
   difiere) + un **aviso de cobertura baja** cuando los jugadores clave no presentan en la SEC (ej. módulos
   ópticos 800G: Innolight/Eoptolink son A-shares). Separar **"promesa"** (lo vemos, sin revenue) de **"no
   medible"** (no lo vemos) — hoy el binario los mezcla.
4. **El cuello como FILTRO, no bonus** (cero código, decisión de diseño):
   - **Promesa** → no hay tesis de cuello; el nombre queda en watchlist.
   - **Disolución** (≥3 de 4: inventario/ventas↑ · margen↓ · crecimiento desacelera 2T · anticipos/RPO↓) →
     **normalizar márgenes en `futuro.py` ANTES de llamar barata a una empresa** (anti value-trap cíclico).
   - **Confirmado** → el PM mira el nombre por su economía; el cuello es contexto.

## 4. ÚTIL, pero DESPUÉS (solo si el test de §6 lo justifica)
- **Percentil de exigencia con tasas base** (el aporte grande de IA 2): `futuro.py` dice "el precio exige 22%
  CAGR"; la tasa base (distribución histórica de crecimiento por tamaño×crecimiento inicial, del propio panel
  XBRL, estilo Mauboussin) dice "eso es el P35". Es lo más valioso a mediano plazo pero **es un proyecto en sí**.
  El **backfill** (estado a cada cierre trimestral desde ~2012; nuestro `fuente_xbrl` ya es point-in-time) lo
  habilita y de paso da el golden set.
- **Separar TENSIÓN de DISOLUCIÓN** (dos ejes: madurez × ciclo).
- **Backtest chico** (óptica 2017-18 → disuelve · Plug Power/quantum → nunca confirma · óptica IA 2023-25 →
  confirma+tensión).

## 5. RUIDO por ahora — descartar
Recalcular por cada filing (semanal alcanza; o por evento si es trivial) · techo del pagador + "capacidad en
camino" · screen de huérfanos + grafo de redundancia + métricas de precisión del discovery · el bloque detallado
al PM (alcanzan 3 líneas: **estado · economía · cobertura**).

## 6. El TEST que decide si vale construir más
Armar §3 (imprescindible), correr los 142 cuellos, y mirar DOS cosas:
1. **¿Fotónica sale CONFIRMADA y quantum queda PROMESA?** (ya validado en crudo, §1). Si con las reglas finas no
   pasa → las reglas están mal, ajustar antes de seguir.
2. **¿Cambia ALGUNA decisión del PM?** Si NO cambia ninguna → el PM ya captaba esto por la economía de cada
   nombre ⇒ el cuello queda como **contexto** y NO se invierte más. Si cambia alguna —sobre todo si evita un
   nombre barato en un cuello disolviéndose— ⇒ ahí sí conviene construir §4.

## 7. Qué queda de la visión original del operador
Quería que el PM "entienda el futuro para encontrar ganadores". Honesto: el mapa sirve para **NO comprar basura**
(promesa) ni **trampas** (disolución), no para encontrar ganadores — eso lo hace `futuro.py` sobre la economía
del nombre. La parte rescatable ("entender el futuro con datos") la da, a mediano plazo, el **percentil de
exigencia** (§4): no te dice el ganador, te dice si lo que el precio YA cree es alcanzable. El cuello es el
contexto que evita el error, no el que encuentra el acierto.
