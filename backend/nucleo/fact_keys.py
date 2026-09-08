"""Registry de `fact_key` (componente C del MVP, doc 22 §11bis).

Catálogo canónico: por cada hecho a extraer, la pregunta para el extractor, los anchors para
ubicar el pasaje relevante (retrieval dirigido), el fact_type (gobierna vigencia) y, si es
numérico, la clave XBRL para contraste. Es la fuente de verdad de QUÉ extrae el motor.
Arranca mínimo; se amplía con el gold set.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FactKeySpec:
    fact_key: str
    pregunta: str
    anchors: list[str]                 # regex para ubicar el window relevante en el filing
    fact_type: str = "SNAPSHOT"        # SNAPSHOT | EVENT | STRUCTURAL
    xbrl: str | None = None            # clave de contraste numérico (extraer_deterministas)
    # Hechos que ESCALAN una tier / gate → chequeo de entailment adversarial: la cita verbatim no
    # alcanza, el pasaje tiene que SOSTENER el claim (evita que el LLM infle y engañe al PM).
    entailment: str | None = None      # el claim estricto que el pasaje debe establecer


# Solo hechos CUALITATIVOS citados (lo que XBRL no da). Los NÚMEROS (margen, revenue, dilución,
# EV) salen de EDGAR/XBRL determinista — NUNCA del LLM (validación gold: el LLM es frágil en
# números; XBRL es exacto y gratis).
FACT_KEYS: list[FactKeySpec] = [
    FactKeySpec(
        "growth_hecho_continuidad",
        "¿La empresa reporta Remaining Performance Obligations (RPO), backlog o contratos "
        "plurianuales que den continuidad de revenue? Respondé value=true/false.",
        [r"Remaining Performance Obligation", r"performance obligation", r"\bbacklog\b"], "EVENT",
    ),
    FactKeySpec(
        "last_material_acquisition",
        "¿Cuál fue la última adquisición material y su fecha de cierre? value = objeto "
        '{"nombre":..., "closing_date":...} o null si no hubo.',
        [r"the closing of the acquisition of", r"acquisition of", r"business combination"],
        "STRUCTURAL",
    ),
    # ---- Pilar 1: Demanda + cuello ----
    # La tier de demanda (VALIDATED/COMMITTED/REALIZED) NO la clasifica el LLM (eso infla) — se
    # DERIVA de estos 3 hechos binarios citados. Cada uno es un hecho duro, no un juicio.
    FactKeySpec(
        # Renombrado desde "demanda_contraparte": la palabra "demanda" hacía que el auditor (y a
        # veces el extractor) lo confundiera con "demanda"=juicio legal. Es puramente comercial.
        "cliente_nombrado",
        "¿La empresa tiene un contrato o acuerdo COMERCIAL material con un CLIENTE NOMBRADO "
        "(comprador identificado)? Es sobre ventas/compras, NO sobre litigios ni juicios. "
        "value true/false.",
        [r"[Tt]ransaction [Aa]greement", r"supply agreement", r"master agreement",
         r"agreement with", r"customer"], "EVENT",
    ),
    FactKeySpec(
        "demanda_minimo",
        "¿El acuerdo con el cliente tiene un MÍNIMO de compra ejecutable, cláusula take-or-pay, o "
        "backlog NO CANCELABLE con plazo? Una 'partnership', un forecast, o compras DISCRECIONALES "
        "NO cuentan. value true/false.",
        [r"take-or-pay", r"minimum (?:purchase|volume|commitment)", r"non-cancel",
         r"firm (?:commitment|order)", r"binding"], "EVENT",
        entailment="el pasaje establece una obligación de compra NO CANCELABLE, un mínimo ejecutable "
                   "o una cláusula take-or-pay (un 'commitment'/'partnership' GENÉRICO no alcanza)",
    ),
    FactKeySpec(
        "demanda_realizada",
        "¿Hay compras o revenue de un cliente nombrado OBSERVADOS y REPETIDOS en los filings "
        "(revenue reconocido de ese cliente, no solo un acuerdo firmado)? value true/false.",
        # `revenues? from` (clase: pluralización) → matchea "revenueS from <Cliente>" (caso AAOI/Digicomm).
        [r"revenues? from", r"accounted for", r"purchases (?:from|by)", r"sales to"], "SNAPSHOT",
        entailment="el pasaje muestra revenue o compras EFECTIVAMENTE reconocidos de un cliente nombrado "
                   "(no un acuerdo futuro ni un pipeline)",
    ),
    FactKeySpec(
        "customer_concentration_pct",
        "Concentración de CLIENTE FINAL: la fracción del revenue del ÚNICO cliente FINAL más grande. Devolvé el "
        "porcentaje INDIVIDUAL más alto de un cliente. REGLAS (normalización, doc 32 2026-08-27): (1) Si el filing "
        "lista %s INDIVIDUALES —aunque los introduzca como 'three customers individually represented 10%+ (32%, "
        "17%, 14%)'— extraé el MAYOR individual → 0.32. Eso NO es un agregado; son clientes individuales. (2) "
        "EXCLUÍ distribuidores/revendedores/channel partners/'Partner A' — es concentración de CANAL, no de cliente "
        "final; si el mayor nombrado es un distribuidor/partner, devolvé null. (3) Devolvé null SOLO si el filing "
        "da únicamente una SUMA agregada sin desglose individual ('top 10 customers = 83%'). (4) Si dice explícito "
        "que ningún cliente supera 10%, value = 0.10 (diversificado). null si no se divulga.",
        # Clases lingüísticas: cliente INDIVIDUAL, no top-N ni canal.
        [r"(?:one|a single|our largest|[Tt]hree|[Tt]wo|[Ff]our|[Ff]ive) customers?",
         r"[Cc]ustomer [A-Z]\b", r"largest customer", r"individually represented",
         r"accounted for (?:approximately )?[\$\d~]", r"no (?:single )?customer (?:accounted|represented|exceeded)",
         r"[\d.]+\s?% (?:or more )?of (?:[\w'’]+ ){0,3}revenues?\b"], "SNAPSHOT",
        entailment="el pasaje da el % INDIVIDUAL de al menos un cliente final (aceptable aunque liste varios "
                   "clientes con sus %s individuales, ej '32%, 17%, 14%' → el mayor es 32%); NO vale si el mayor "
                   "es un distribuidor/reseller/channel partner, ni si SOLO hay una suma agregada sin desglose",
    ),
    FactKeySpec(
        "ventaja_estructural",
        "¿Hay ventaja estructural documentada (sole-source cualificado, IP defendida, switching "
        "cost, posición de cuello con captura de renta)? value true/false.",
        [r"sole[- ]source", r"single[- ]source", r"qualif", r"switching cost", r"proprietary",
         r"\bpatent", r"barriers to entry"], "STRUCTURAL",
    ),
    # ---- Pilar 2: Economía + captura de valor ----
    FactKeySpec(
        "revenue_recurrente",
        "¿El filing DESCRIBE el revenue como recurrente/subscription/SaaS? Citá la ORACIÓN de texto "
        "que lo dice (NO una tabla de números). value true/false.",
        [r"subscription (?:revenue|arrangement|basis)", r"recurring revenue", r"annual recurring",
         r"revenue is (?:primarily|generated|derived)", r"derive(?:d)? (?:our )?revenue",
         r"ratably over"], "SNAPSHOT",
    ),
    FactKeySpec(
        "margen_en_expansion",
        "¿El gross margin está en expansión SOSTENIDA (mejoró vs. el período anterior)? value "
        "true/false. Citá el pasaje que lo indica.",
        [r"gross margin (?:increased|improved|expand|rose)", r"margin (?:increased|improved|expand)",
         r"improvement in (?:gross )?margin"], "SNAPSHOT",
    ),
    FactKeySpec(
        "hechos_comerciales",
        "¿Cuántos hechos comerciales independientes CON fuente (contratos firmados, design-wins "
        "económicos, órdenes vinculantes, expansiones con cliente) aparecen en el filing? value = "
        "número entero.",
        [r"design win", r"purchase order", r"awarded", r"new (?:contract|customer)", r"signed"],
        "EVENT",
    ),
    # ---- Pilar 3: Ejecución (lo cualitativo; dilución/insider salen de XBRL/Form 4) ----
    FactKeySpec(
        "restatement_reciente",
        "¿Hay un restatement reciente, non-reliance (8-K Item 4.02) o material weakness del control "
        "interno (ICFR)? value true/false.",
        [r"restat", r"material weakness", r"non-reliance", r"internal control over financial"],
        "EVENT",
    ),
    # ---- Pilar 4: Valuación + asimetría (lo cualitativo; EV/revenue salen de XBRL) ----
    FactKeySpec(
        "respaldo_backlog",
        "¿Hay backlog CONTRATADO que respalde el crecimiento futuro: remaining performance "
        "obligations (RPO), order backlog, órdenes en firme, o contratos plurianuales con revenue "
        "comprometido? Un forecast o pipeline NO cuenta (tiene que ser contratado). value true/false.",
        [r"remaining performance obligation", r"\bbacklog\b", r"unfilled orders?", r"firm orders?",
         r"order(?:s)? (?:on hand|in (?:our )?backlog)", r"multi[- ]?year", r"contracted revenue",
         r"committed (?:revenue|contract)"],
        "EVENT",
    ),
    FactKeySpec(
        "backlog_no_cancelable",
        "¿El filing describe el RPO / backlog / performance obligations como NO CANCELABLE, en firme, "
        "o comprometido (non-cancelable, firm, committed, take-or-pay)? Un backlog cancelable a "
        "discreción del cliente, o sin describir la fuerza del compromiso, NO cuenta. value true/false.",
        [r"non-?cancel", r"firm (?:order|commitment|backlog)", r"take-or-pay", r"committed (?:revenue|contract|backlog)",
         r"cannot be cancel", r"not (?:be )?cancel", r"cancelable"], "SNAPSHOT",
        entailment="el pasaje establece que el backlog/RPO es NO CANCELABLE, en firme o comprometido "
                   "(no simplemente 'contracted' genérico ni cancelable a discreción del cliente)",
    ),
    FactKeySpec(
        "capacidad_expansion",
        "¿Hay expansión de capacidad instalada o capex material anunciado (nueva fábrica/línea/fab, "
        "ampliación)? value true/false.",
        [r"capacity (?:expansion|increase)", r"new (?:plant|fab|facility)", r"facility (?:expansion|construction)",
         r"increased? production capacity"], "EVENT",
    ),
    # ---- Cross-cutting: arquetipo Binary ----
    FactKeySpec(
        "es_binary",
        "¿Existe UN ÚNICO evento no-comercial (regulatorio/clínico/técnico/legal) que define el "
        "éxito y deja el equity con recuperación residual ~nula si falla? value true/false.",
        [r"\bFDA\b", r"clinical (?:trial|data)", r"regulatory approval", r"marketing authorization",
         r"phase [123]"], "STRUCTURAL",
    ),
]

# ---- Carril especulativo (doc 29 §2 gate + §3 rúbrica) — LISTA SEPARADA a propósito: NO entran a `FACT_KEYS`
#      para NO inflar el denominador de cobertura del libro duro (son un concern distinto). Escalan la
#      ADMISIÓN/ORDEN del carril → entailment adversarial estricto: TAM, guidance, deck o ceiling NO cuentan. ----
FACT_KEYS_CARRIL: list[FactKeySpec] = [
    FactKeySpec(
        "opcion_evidencia_externa",
        "¿Hay evidencia EXTERNA REAL de una oportunidad no contratada: design-win, piloto PAGO, proceso de "
        "calificación en curso, RFP concreto, cliente IDENTIFICADO, o permiso EN TRÁMITE? Un TAM, guidance, "
        "un deck, un 'partnership' vago o un ceiling anunciado ('hasta $X') NO cuentan. value true/false.",
        [r"design[- ]win", r"\bpilot\b", r"qualification (?:process|program)", r"\bRFP\b", r"request for proposal",
         r"letter of intent", r"awarded", r"permit(?:ting)?", r"named customer"], "EVENT",
        entailment="el pasaje establece una oportunidad externa REAL y verificable (design-win/piloto pago/"
                   "calificación/RFP/cliente identificado/permiso en trámite), NO un TAM, guidance, deck o ceiling",
    ),
    FactKeySpec(
        "opcion_hito_cercano",
        "¿Hay un HITO con fecha o ventana que resuelve en ~12-18 meses (adjudicación, decisión regulatoria, "
        "primer pedido, resultado de calificación)? Tiene que ser fechado/acotado, no 'en el futuro'. value true/false.",
        [r"expected (?:in|by|during)", r"anticipat", r"decision (?:expected|by)", r"award (?:expected|decision)",
         r"first (?:order|delivery|production)", r"20(?:26|27)", r"next (?:twelve months|year|fiscal year)"], "EVENT",
        entailment="el pasaje establece un hito con fecha o ventana concreta que resuelve en ~12-18 meses",
    ),
    FactKeySpec(
        "opcion_materialidad",
        "Si la oportunidad ocurre, ¿cambia la ESCALA de la empresa (el hito representa una fracción MATERIAL "
        "de los ingresos actuales, ej. ≥30%)? Se mide por la definición del hito vs revenue actual, NO por el "
        "ceiling anunciado. value true/false.",
        [r"material(?:ly)?", r"significant portion", r"substantial", r"transform", r"% of (?:our )?revenue",
         r"multiple of"], "EVENT",
        entailment="el pasaje establece que el hito, si ocurre, es material relativo a los ingresos ACTUALES "
                   "(cambia la escala), no medido por el ceiling anunciado",
    ),
    FactKeySpec(
        "opcion_contraparte_financiada",
        "La contraparte de la oportunidad (cliente/agencia/programa), ¿está IDENTIFICADA y además FINANCIADA "
        "(tiene el presupuesto/fondos para ejecutar)? value true/false.",
        [r"funded", r"appropriat", r"budget", r"program of record", r"awarded", r"customer", r"agency"], "EVENT",
        entailment="el pasaje identifica a la contraparte Y establece que está financiada (fondos/presupuesto)",
    ),
    FactKeySpec(
        "opcion_dinero_autorizado",
        "El dinero de la oportunidad, ¿está APROPIADO/AUTORIZADO (apropiación, orden, PO, línea presupuestaria "
        "concreta), a diferencia de solo un ceiling o autorización marco? value true/false.",
        [r"appropriat", r"obligated", r"purchase order", r"task order", r"authoriz", r"contract award"], "EVENT",
        entailment="el pasaje establece dinero apropiado/autorizado concreto (no un ceiling/autorización marco)",
    ),
    FactKeySpec(
        "opcion_transaccion_precedente",
        "¿Hay una TRANSACCIÓN PRECEDENTE con esa MISMA contraparte (un contrato/pedido previo ya ejecutado con "
        "el mismo cliente/agencia)? value true/false.",
        [r"prior (?:contract|order|award)", r"previously awarded", r"existing (?:customer|relationship)",
         r"repeat", r"follow[- ]on", r"expansion of (?:our )?(?:existing|prior)"], "EVENT",
        entailment="el pasaje establece una transacción previa YA ejecutada con la misma contraparte",
    ),
    FactKeySpec(
        "opcion_falsador_documento",
        "¿La oportunidad tiene una FALSABILIDAD ESCRITA: qué tiene que pasar, antes de qué fecha, verificable "
        "en qué documento específico (adjudicación DoD, lista DOE, línea del 10-Q, 10-K del cliente)? value true/false.",
        [r"expected (?:to|by)", r"decision (?:by|expected)", r"filing", r"10-[KQ]", r"award", r"by (?:the )?end of",
         r"during (?:fiscal )?20(?:26|27)"], "EVENT",
        entailment="el pasaje da una falsabilidad escrita concreta: qué pasa, antes de qué fecha, en qué documento",
    ),
]
