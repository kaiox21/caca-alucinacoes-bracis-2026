"""Índice canônico de resolução sobre a base congelada do desafio."""
from .chaves import chave_numerica, validar_cnj
from .construcao import Candidato, ErroDeConstrucao, Indice, Relatorio, construir_indice

__all__ = [
    "Candidato",
    "ErroDeConstrucao",
    "Indice",
    "Relatorio",
    "chave_numerica",
    "construir_indice",
    "validar_cnj",
]
