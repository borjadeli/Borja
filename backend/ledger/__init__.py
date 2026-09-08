"""Ledger determinista del núcleo nuevo (Etapa 2 — init_docs/16_ledger_etapa2.md).

Contabilidad real de acciones y caja, aislada del sistema viejo (Base propia,
prefijo nx_). Plata SIMULADA. El estado (posición/caja/equity) es SIEMPRE una
proyección del log inmutable — nunca se guarda mutado.
"""
