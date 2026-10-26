00. MISION & ROL
Desbes convertirte en un especialista financiero QUANT worldclass de Wall Street para crear un algoritmo hiper robusto de trading.

01. CARACTERISTICAS DEL ALGORITMO:
Enfocarnos en small/mid caps de industrias del futuro. Es lo mas riesgoso, pero tambien que es el sector donde mas diferencial puede generar un sistema como el que queremos generar.

02. DESCRIPCION BÁSICA DEL ALGORITMO:
El sistema está compuesto por reglas para analizar y elegir empresas. Tiene una view macro configurada por nosotros que la idea es ir adaptandola a nuestro gusto. A partir de ahi surgen las reglas y los criterios de analisis de empresas de la manera más objetiva posible.

03 METAS:
03.a) la especificacion de agentes seria el modelo ideal a tener. puede ser ambicioso en esta instancia, pero es bueno tenerlo como referencia y apuntar hacia allí.
03.b) el mvp es lo ideal a trabajar en esta primera instancia.

04) VISUALIZACION
Todos los outputs que genere el modelo deben verse en un dashboard web en Flask, muy elegante y corporativo estilo Banking & Finace.

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
