"""
Suivi d'usage anonyme — une ligne par calcul dans un Google Sheet.

Principe
--------
Après chaque appel à POST /api/calculate (succès ou échec), le backend envoie
quelques compteurs et des codes courts à un webhook Google Apps Script
(voir tracking/Code.gs), qui ajoute une ligne au Google Sheet.

Garanties
---------
- **Jamais bloquant** : l'envoi se fait dans un thread à part, après la fin du
  calcul ; la réponse à l'utilisateur ne l'attend pas.
- **Jamais fatal** : toute erreur d'envoi (réseau, Google indisponible, variable
  mal renseignée) est avalée et simplement journalisée.
- **Désactivé par défaut** : sans variable TRACKING_URL, rien n'est envoyé
  (développement local, tests).
- **Anonyme** : seuls des compteurs et des codes sont envoyés. Ni noms de
  fichiers, ni identifiants RC, ni désignations de sections, ni texte des
  messages (ils peuvent contenir des noms de projet), ni adresse IP, ni pays.
  Seul ce que voit le serveur est tracé (pas de navigation sur le site).

Variables d'environnement (Render)
----------------------------------
    TRACKING_URL     URL du déploiement Apps Script (se termine par /exec)
    TRACKING_SECRET  même valeur que la propriété de script SECRET (Code.gs)

Colonnes envoyées
-----------------
    t              date et heure UTC (ISO 8601) — le script les convertit en heure de Paris
    ok             True / False
    duree_s        durée du traitement côté serveur (lecture des fichiers + calcul), en secondes
    materiaux      nombre de matériaux configurés
    rc             nombre de RC configurés
    cdc            nombre de cas de charge (fichiers déposés ; cas calculés en cas de succès)
    elements       nombre d'éléments calculés (succès uniquement, vide en cas d'échec)
    erreur         code d'erreur (échec uniquement) — voir CODES D'ERREUR
    avertissements codes d'avertissements affichés — voir CODES D'AVERTISSEMENT

CODES D'ERREUR (échec du calcul)
--------------------------------
    E_REQUETE          paramètres de calcul (JSON) invalides
    E_ELE              fichier ELE illisible ou invalide
    E_AUCUN_CDC        aucun fichier de cas de charge
    E_CDC_DOUBLON      même nom de cas de charge fourni deux fois
    E_CDC_FICHIER      fichier de cas de charge illisible ou invalide
    E_CDC_CONSOLIDATION  incohérence entre fichiers de cas de charge
    E_CATALOGUE        désignation de section introuvable au catalogue
    E_CALCUL           erreur de calcul (donnée incohérente)
    E_INTERNE          erreur interne attrapée par le filet de sécurité
    E_INATTENDU        erreur non prévue (hors du calcul proprement dit)

CODES D'AVERTISSEMENT (affichés en haut de « 3 — Résultats »)
--------------------------------------------------------------
    W_ELE_ABSENT       éléments des cas de charge absents du fichier ELE (écartés)
    W_RC_NON_CONFIG    RC du fichier ELE sans configuration (éléments écartés)
    W_SANS_CHARGE      éléments de l'ELE absents de tous les cas de charge
    W_CDC_PARTIELS     éléments présents dans certains cas de charge seulement
    W_CLASSE_FORCEE    classe de section forcée manuellement
    W_CLASSE4          section de classe 4
    W_VOILEMENT        voilement par cisaillement non négligeable
    W_AUTRE            tout autre avertissement (message non reconnu)

Un code répété pour plusieurs RC est suivi de ×n (ex. « W_CLASSE4×3 »).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

log = logging.getLogger("huox.tracking")

_TIMEOUT_S = 15
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tracking")

# Ordre = priorité de reconnaissance (premier fragment trouvé gagne).
# Les fragments sont comparés en minuscules aux messages de main.py / results.py.
_WARNING_CODES: tuple[tuple[str, str], ...] = (
    ("W_CLASSE_FORCEE", "forcée manuellement"),
    ("W_CLASSE4", "section de classe 4"),
    ("W_VOILEMENT", "voilement par cisaillement"),
    ("W_ELE_ABSENT", "absent(s) du fichier ele"),
    ("W_RC_NON_CONFIG", "sans configuration correspondante"),
    ("W_SANS_CHARGE", "absent(s) de tous les fichiers de cas de charge"),
    ("W_CDC_PARTIELS", "dans certains fichiers de cas de charge seulement"),
)
_ORDER = [c for c, _ in _WARNING_CODES] + ["W_AUTRE"]


def warning_code(message: str) -> str:
    """Code court d'un message d'avertissement (W_AUTRE si non reconnu)."""
    low = message.lower()
    for code, fragment in _WARNING_CODES:
        if fragment in low:
            return code
    return "W_AUTRE"


def summarize_warnings(messages: list[str]) -> str:
    """« W_CLASSE4×3, W_VOILEMENT » — codes distincts, comptés, ordre stable."""
    counts: dict[str, int] = {}
    for m in messages:
        c = warning_code(m)
        counts[c] = counts.get(c, 0) + 1
    parts = []
    for c in _ORDER:
        n = counts.get(c)
        if n:
            parts.append(c if n == 1 else f"{c}×{n}")
    return ", ".join(parts)


def _post(payload: dict) -> None:
    """Envoi bloquant (exécuté dans un thread). N'élève jamais d'exception."""
    try:
        url = os.getenv("TRACKING_URL", "").strip()
        if not url:
            return
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Apps Script répond par une redirection 302 ; urllib la suit.
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            resp.read(256)
    except Exception as exc:  # noqa: BLE001 — le suivi ne doit jamais gêner le calcul
        log.warning("Suivi d'usage : envoi impossible (%s)", type(exc).__name__)


class CalcRun:
    """Suit un appel à /api/calculate : chrono, compteurs, code d'erreur."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._started = datetime.now(timezone.utc)
        self.n_materiaux: Optional[int] = None
        self.n_rc: Optional[int] = None
        self.n_cdc: Optional[int] = None
        self.n_elements: Optional[int] = None
        self.error_code: str = ""

    def err(self, code: str, status: int, detail: str) -> HTTPException:
        """Mémorise le code d'erreur et renvoie l'HTTPException à lever."""
        self.error_code = code
        return HTTPException(status_code=status, detail=detail)

    def finish(self, ok: bool, response=None) -> None:
        """Clôt le suivi et envoie la ligne (sans attendre, sans jamais échouer)."""
        try:
            warnings: list[str] = []
            if ok and response is not None:
                self.n_elements = response.nb_elements
                self.n_cdc = response.nb_load_cases
                warnings = list(response.warnings)
            if not ok and not self.error_code:
                self.error_code = "E_INATTENDU"
            payload = {
                "secret": os.getenv("TRACKING_SECRET", ""),
                "t": self._started.isoformat(timespec="seconds"),
                "ok": ok,
                "duree_s": round(time.perf_counter() - self._t0, 2),
                "materiaux": self.n_materiaux,
                "rc": self.n_rc,
                "cdc": self.n_cdc,
                "elements": self.n_elements,
                "erreur": "" if ok else self.error_code,
                "avertissements": summarize_warnings(warnings),
            }
            if os.getenv("TRACKING_URL", "").strip():
                _EXECUTOR.submit(_post, payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("Suivi d'usage : préparation impossible (%s)", type(exc).__name__)
