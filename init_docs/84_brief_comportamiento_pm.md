# Doc 84 — Brief de triangulación: el comportamiento del PM (bucle de decisión)

> **Para IAs externas.** Autocontenido. Objetivo: diseñar el **comportamiento operativo del PM** para que
> funcione de forma AUTÓNOMA y CORRECTA. No se re-abre el diseño de la ficha viva (doc 80) ni del equity bridge
> (doc 83) — eso está cerrado. Se diseña el BUCLE: cuándo mira, qué puede comprar, qué pasa si quiere algo sin
> analizar, cuándo vende, cada cuánto. Devolvé por cada punto: acuerdo/forma concreta/modo de falla.
> Fecha: 2026-11-17.

## 0. Contexto mínimo

BORJA es un sistema **advisory** (asesora; el humano ejecuta) para small/mid caps de industrias del futuro, con
**paper trading** autónomo que valida el método. **El determinismo informa y limita; un PM-LLM decide la cartera.**

**Primitiva central — la FICHA VIVA (doc 80, cerrado):** cada nombre analizado tiene una ficha con dos relojes.
- **Rápido** (precio → zonas de compra/venta): el código lo recalcula a diario, gratis. Zonas: COMPRA / MANTENER /
  RECORTE / SALIDA, derivadas de un puente de valuación por escenarios (ningún agente escribe un precio a dedo).
- **Lento** (tesis, escenarios, falsadores): solo lo cambia el **comité** (Analista Opus+web → Bear → Verificador)
  corriendo un **deep** (~$0.70-5/nombre). Vigencia por EVENTO: si aparece un 10-Q/10-K posterior a la tesis, la
  ficha pasa a EN_REVISION y **deja de ser comprable** hasta refrescarla.

**Lo que el PM ve (packet):** sus posiciones (con ficha) + la **banca** (fichas VIGENTES en zona COMPRA) + las
**oportunidades** (score de nombres sin ficha) + alertas + dossiers frescos del ciclo. Decide bajo el IPS
(límites del operador: pesos, caps por sector/cuello/factor, liquidez, etc.). Un gate determinista rechaza lo
que viola el IPS; las reducciones (vender/recortar) SIEMPRE se ejecutan (risk-off).

**Filosofía: PACIENCIA.** Se despliega capital solo en nombres con margen de seguridad (zona COMPRA). Lo que no
encuentra margen se estaciona en ETFs temáticos. La caja no es fracaso.

## 1. El problema que este brief resuelve

Hoy el comportamiento del PM tiene **la lógica construida y correcta**, pero **dos huecos que lo hacen sentir
muerto**:
1. **NADA corre solo.** El comité y el latido diario de las fichas se disparan A MANO. No hay scheduler del
   comité. Entonces el PM no "vigila" — solo actúa cuando alguien aprieta el botón.
2. **"Deep requerido para comprar" es implícito, no enforced.** El PM solo ve info de lo que tiene ficha/dossier,
   pero el gate NO tiene una regla dura "sin ficha VIGENTE no se abre".

Y una decisión NUEVA del operador que hay que diseñar:
3. **Si el PM quiere un nombre que no tiene deep, hay que HACERLE el deep** (no solo bloquear). El deseo del PM
   dispara la investigación.

## 2. Las preguntas a resolver

### #1 — El bucle "el PM quiere algo sin deep → se le hace el deep"
El PM, mirando el mapa/oportunidades/su intuición, puede querer un nombre que NO tiene ficha VIGENTE (nunca
analizado, o vencido). Hoy no hay mecanismo. Opciones:
- **(a) Dos pasadas en el mismo ciclo:** el PM marca "quiero mirar X"; el sistema corre el deep de X; el PM
  re-decide con la ficha fresca. Más caro y lento por ciclo, pero resuelve en el acto.
- **(b) Cola para el próximo ciclo:** el "quiero X" entra a la cola de deep; se analiza; el PM lo ve con ficha en
  la corrida siguiente. Más barato, pero demora la decisión.
- **(c) Híbrido:** dos pasadas si hay presupuesto/urgencia (p.ej. el precio está en zona), cola si no.

**Preguntas:** ¿Cuál? ¿El PM debería poder pedir deep de un nombre **fuera del universo/mapa** (input del
operador: "mirá esta empresa aunque no esté en la lista")? ¿Cuántos "quiero X" por ciclo (tope de costo)? ¿El
deseo del PM compite con el carril de oportunidad por el cupo, o es aparte?

### #2 — El candado: ¿se puede abrir sin ficha VIGENTE?
Propuesta: **regla dura — no abrir ni aumentar una posición sin una ficha VIGENTE y datos limpios.** Si el PM lo
quiere igual, dispara #1 (deep), no la compra a ciegas. ¿De acuerdo? ¿Excepciones (p.ej. promediar a la baja una
posición existente cuya ficha venció)? ¿Y las reducciones no necesitan ficha (risk-off siempre ejecuta)?

### #3 — Cadencia: ¿cada cuánto mira y corre?
Propuesta: **latido diario** (recalcula zonas de TODAS las fichas + emite alertas de cambio de zona, $0) +
**comité semanal** (deep sobre el carril de oportunidad + banca + posiciones que lo necesiten). ¿Es correcto?
¿El comité debería ser **por evento** además de semanal (un 8-K material de una posición → deep inmediato)?
¿Qué dispara una corrida extra fuera del calendario? ¿El latido diario alcanza para "vigilar" o las posiciones
necesitan un deep-refresh periódico (TTL) aunque no haya evento?

### #4 — Las salidas: ¿cuánto regla, cuánto juicio?
Hoy las zonas (RECORTE/SALIDA) + falsadores + 5 vías de salida son INFORMACIÓN → el PM decide; las reducciones
que el PM ordena siempre se ejecutan. El operador quiere salidas "más crujientes". Opciones de dónde poner la
línea entre regla automática y juicio:
- **Falsador que se cumple** (un hito objetivo falló) → ¿auto-trim/alerta dura, o solo abre revisión?
- **Zona SALIDA** (precio arriba de lo que paga hasta el bull) → ¿auto-recorte parcial, o info?
- **Stop por tesis ROTA** (material weakness, going concern) → ¿auto-salida?

**Preguntas:** ¿Qué salidas deberían ser REGLA (deterministas, sin esperar al PM) y cuáles JUICIO? El riesgo de
reglas automáticas: cortar al ganador por ruido. El riesgo de todo-juicio: el PM no corre seguido (ver #3) y una
tesis rota queda sin accionar.

### #5 — Revisión de posiciones
¿Con qué frecuencia y profundidad se revisa CADA posición? Propuesta: zona recalculada a diario (latido);
deep-refresh solo por evento (nuevo filing) o si el PM/Auditor lo pide. ¿Alcanza, o una posición necesita un
deep-refresh obligatorio cada N meses aunque no haya evento (anti-tesis-congelada)?

### #6 — Input del operador
El operador quiere **pasar tickers propios** (dentro o fuera del universo/mapa) para que se analicen, y que "si
una empresa es buena, la tengamos en cuenta aunque no esté en el mapa". ¿Cómo entra ese input al bucle sin
romper la disciplina (el filtro de fuentes primarias del discovery)? ¿Un ticker pasado por el operador salta la
validación de discovery (confía en el humano) o pasa por los mismos gates?

## 3. Lo que NO está en discusión (cerrado)
- La ficha viva (dos relojes, zonas derivadas, vigencia por evento) — doc 80.
- El equity bridge / instrumentos / verificador ciego / factores — doc 83.
- Que el PM-LLM decide y el determinismo limita (IPS). Que las zonas son información, no órdenes.
- PACIENCIA y el estacionamiento en ETFs.

## 4. Qué devolver
Por cada punto (#1–#6): la forma concreta recomendada · el modo de falla si se implementa mal · qué datos/piezas
requiere. Y una lectura transversal: **¿cuál es el mínimo que hace que el PM "vigile y decida bien" de forma
autónoma, sin sobre-ingeniería?** Priorizá.
