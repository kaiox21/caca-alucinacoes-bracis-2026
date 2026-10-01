"""Extração de citações: cada família acha candidatos sobre o texto normalizado.

As famílias não sabem umas das outras; `resolver_conflitos` escolhe entre candidatos
que se sobrepõem, e os emitidos nunca se sobrepõem.
"""
from .achado import Achado, Familia
from .descritiva import extrair_descritivas
from .lei import extrair_leis
from .processo import extrair_processos
from .spans import resolver_conflitos
from .sumula_tema import extrair_sumulas, extrair_temas


def extrair_citacoes(texto: str) -> list[Achado]:
    """Todas as citações do texto normalizado, sem sobreposição, ordenadas pelo início."""
    candidatos = [
        *extrair_processos(texto), *extrair_leis(texto), *extrair_sumulas(texto),
        *extrair_temas(texto), *extrair_descritivas(texto),
    ]
    return resolver_conflitos(candidatos)


__all__ = [
    "Achado", "Familia", "extrair_citacoes", "extrair_descritivas", "extrair_leis",
    "extrair_processos", "extrair_sumulas", "extrair_temas", "resolver_conflitos",
]
