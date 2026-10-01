"""Tolerância a ruído de letra em palavras conhecidas (palavra-chave, diploma, conectivo).

O alfabeto de contexto alfabético do harness (`5úmula`, `Fedcral`, `profcrido`, `Júnlor`)
vale só para as palavras que a extração já espera naquela posição, nunca para o texto
corrido: é o que impede `Terna` ou `Tema` solto de virar citação.

O `m` escrito como `rn` (`RSK-17`) entra aqui do mesmo jeito, e cada `m` da palavra é
tratado por conta própria, porque o OCR estraga uma ocorrência de cada vez
(`Cornplementar`, e não `Cornplerncntar`).
"""
from __future__ import annotations

import re

_VARIANTES = {
    "a": "aáàâã", "e": "eéêc", "i": "iíl1", "o": "oóôõ0", "u": "uú", "c": "cç", "s": "s5",
}
_ACENTOS = {"á": "a", "à": "a", "â": "a", "ã": "a", "é": "e", "ê": "e", "í": "i",
            "ó": "o", "ô": "o", "õ": "o", "ú": "u", "ç": "c"}


def _classe(letra: str) -> str:
    base = _ACENTOS.get(letra.lower(), letra.lower())
    variantes = _VARIANTES.get(base)
    if variantes is None:
        return f"[{letra.lower()}{letra.upper()}]" if letra.isalpha() else re.escape(letra)
    conjunto = "".join(dict.fromkeys(variantes + variantes.upper()))
    return f"[{re.escape(conjunto)}]"


def tolerante(palavra: str) -> str:
    """Padrão de regex que aceita a palavra com o ruído de letra observado e `rn` no lugar de `m`."""
    return "".join("(?:[mM]|[rR][nN])" if letra.lower() == "m" else _classe(letra) for letra in palavra)
