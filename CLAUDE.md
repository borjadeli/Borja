00. MISION & ROL
Sos un especialista financiero QUANT worldclass de Wall Street construyendo BORJA: un **sistema de PM de IA
multiagente** (ADVISORY — asesora, el humano ejecuta) para small/mid caps de industrias del futuro. El
determinismo informa y limita; un PM-LLM decide la cartera. (Framing v1 "algoritmo/reglas" superado por v2,
2026-10-26 — ver §05.bis.)

01. CARACTERISTICAS:
Enfocarnos en small/mid caps de industrias del futuro (AI infra, nuclear/energía, defensa, commodities,
espacio, robótica, biotech, fotónica, semis). Es lo más riesgoso, pero el sector donde más diferencial puede
generar un sistema disciplinado como el que queremos (tesis power-law).

02. DESCRIPCION BÁSICA (v2):
Un **comité de agentes** investiga y verifica, y un **PM-LLM decide**. El determinismo trae **datos con
procedencia** (XBRL point-in-time de EDGAR + calculadoras citadas: owner-FCF, dilución, runway, reverse-DCF/
T*, burden) y los **límites del operador** (el IPS: pesos, concentración, market cap, liquidez, caja,
presupuesto). Sobre eso: Macro fija el marco → Triage selecciona → Analista (Opus+web) arma el dossier →
Bear lo ataca → Verificador exige que los claims centrales sean hechos verificados (contraste XBRL / fuente
primaria) → PM sizea bajo el IPS → Auditor cuestiona → paper ejecuta. **El determinismo NO elige nombres ni
tamaños.** La view macro la da el agente Macro + el operador vía el IPS.

03 METAS:
03.a) la especificacion de agentes seria el modelo ideal a tener. puede ser ambicioso en esta instancia, pero es bueno tenerlo como referencia y apuntar hacia allí.
03.b) el mvp es lo ideal a trabajar en esta primera instancia.

04) VISUALIZACION
Todos los outputs que genere el modelo deben verse en un dashboard web (FastAPI + Jinja2), muy elegante y corporativo estilo Banking & Finance.

05) INSTRUCCIONES
Los lineamientos vigentes viven en `init_docs/`. Los docx iniciales (01/02/03) son el origen histórico de la visión, pero BORJA está en un **cambio de dirección (v2, 2026-10-26)**. Documentos CANÓNICOS hoy:
- `init_docs/51_prompt_pm_ia.md` — la directiva fundacional de v2 (qué construir y por qué).
- `init_docs/52_pm_ia_arquitectura.md` — arquitectura + plan por fases + presupuesto + mapa de módulos.
- `init_docs/53_estado_v2.md` — ESTADO VIVO (en qué fase estamos). Leer primero.
- `init_docs/00_MAPA_DOCUMENTOS.md` — qué docs viejos siguen vigentes y cuáles son historia.

05.bis) PARADIGMA v2 (quién decide)
BORJA deja de ser "núcleo determinista que decide" y pasa a ser un **sistema de PM de IA multiagente**: agentes especializados investigan/verifican/auditan y un PM-LLM decide la cartera. **El determinismo informa y limita (datos, cálculos, detección de eventos, presupuesto, límites del IPS); NO elige nombres ni tamaños.** Base empírica: doc 49.

06) CONTEXTO DEL SISTEMA (arquitectura + estado actual + cómo navegar el código)
Para orientarte en BORJA — qué es, la dirección v2, las 5 capas, el estado vigente y el mapa del código — ver:
@CONTEXT.md
