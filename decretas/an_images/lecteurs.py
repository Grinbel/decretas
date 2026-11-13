"""Readers: the pluggable ways to turn one page image into text.

One interface, three implementations:

- ``manuel``     a plain-text transcription placed next to the image by a person
                 (``page.jpg`` -> ``page.txt`` or ``page.jpg.txt``);
- ``tesseract``  the Tesseract OCR program, when it is installed (it is detected, never
                 assumed; when absent the reader says so and how to install it);
- ``commande``   any external program described in a configuration file. It receives the
                 path of the image and prints the transcription on its standard output.
                 This is the socket for a vision model or any other tool the owner chooses
                 later. Nothing is configured by default, nothing is called by default, and
                 this project ships no credential: whatever the external program needs
                 (a key, an account) is its own business, read from its own environment.

Contract of an external command (``commande``):

- configuration: a JSON file ``{"commande": ["program", "arg", "{image}"], "delai_s": 300,
  "nom": "label"}``. ``commande`` is a list of arguments, started WITHOUT a shell;
  the item ``{image}`` is replaced by the absolute path of the image (appended as the last
  argument when no item contains it);
- output: the transcription as UTF-8 text on standard output, one line of the page per
  line, in reading order, the margin number at the start of the line it faces;
- exit status 0 on success; any other status, a time-out or an empty output is reported as
  a failure for that image (never silently skipped).

A reader never raises on a bad image: it returns a `Reading` whose `error` says what happened.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

AUTOMATIC = "lecture automatique — à vérifier sur l'image"
MANUAL = "transcription manuelle — à vérifier sur l'image"

TESSERACT_INSTALL = ("Tesseract n'est pas installé sur cette machine. Pour l'installer (Debian, Ubuntu) : "
                     "`sudo apt install tesseract-ocr tesseract-ocr-fra` — `sudo` exécute la commande avec les droits "
                     "d'administration, `apt install` installe des paquets ; `tesseract-ocr` est le programme, "
                     "`tesseract-ocr-fra` son modèle du français. Rien d'autre n'est requis.")


@dataclass
class Reading:
    """What a reader returns for one image."""

    reader: str
    confidence: str
    text: str | None = None
    error: str | None = None
    source: str | None = None        # the transcription file, or the command that ran


class ReaderUnavailable(Exception):
    """The requested reader cannot work on this machine or with this configuration (French message)."""


@dataclass
class ManualReader:
    name: str = "manuel"
    confidence: str = MANUAL

    @staticmethod
    def transcription_of(image: Path) -> Path | None:
        for candidate in (image.with_name(image.name + ".txt"), image.with_suffix(".txt")):
            if candidate.is_file():
                return candidate
        return None

    def available(self) -> tuple[bool, str]:
        return True, "lit le fichier .txt placé à côté de chaque image"

    def read(self, image: Path) -> Reading:
        path = self.transcription_of(image)
        if path is None:
            return Reading(self.name, self.confidence, error="pas de transcription : ni " + image.name + ".txt ni "
                           + image.with_suffix(".txt").name + " à côté de l'image")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        except OSError as error:
            return Reading(self.name, self.confidence, error=f"transcription illisible : {error.strerror}", source=str(path))
        if not text.strip():
            return Reading(self.name, self.confidence, error="transcription vide", source=str(path))
        return Reading(self.name, self.confidence, text=text, source=str(path))


def _run(arguments: list[str], timeout: float) -> tuple[str | None, str | None]:
    """Run a program without a shell. Returns (stdout text, None) or (None, French error)."""
    try:
        done = subprocess.run(arguments, capture_output=True, timeout=timeout, check=False, stdin=subprocess.DEVNULL)  # noqa: S603
    except FileNotFoundError:
        return None, f"programme introuvable : {arguments[0]}"
    except PermissionError:
        return None, f"programme non exécutable : {arguments[0]}"
    except subprocess.TimeoutExpired:
        return None, f"délai de {timeout:g} s dépassé"
    except OSError as error:
        return None, f"lancement impossible : {error.strerror or type(error).__name__}"
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip().splitlines()
        return None, f"code de sortie {done.returncode}" + (f" ({detail[-1][:200]})" if detail else "")
    text = done.stdout.decode("utf-8", "replace")
    if not text.strip():
        return None, "sortie vide"
    return text, None


@dataclass
class TesseractReader:
    binary: str = "tesseract"
    language: str = "fra"
    page_mode: int = 4               # --psm: 4 = one column of text of variable sizes (to tune on a real page)
    timeout: float = 300.0
    name: str = "tesseract"
    confidence: str = AUTOMATIC

    def available(self) -> tuple[bool, str]:
        path = shutil.which(self.binary)
        if path is None:
            return False, TESSERACT_INSTALL
        listing, error = _run([path, "--list-langs"], 30)
        if error:
            return False, f"Tesseract est présent ({path}) mais ne répond pas : {error}."
        if self.language not in listing.split():
            return False, (f"Tesseract est présent ({path}) mais son modèle « {self.language} » manque. Pour l'installer : "
                           f"`sudo apt install tesseract-ocr-{self.language}` (`sudo` : droits d'administration ; "
                           "`apt install` : installer un paquet).")
        return True, f"Tesseract trouvé : {path}, langue {self.language}, mode de page {self.page_mode}"

    def read(self, image: Path) -> Reading:
        path = shutil.which(self.binary) or self.binary
        # tesseract <image> stdout : print the text instead of writing a file ; -l : language model ;
        # --psm : page segmentation mode.
        command = [path, str(image), "stdout", "-l", self.language, "--psm", str(self.page_mode)]
        text, error = _run(command, self.timeout)
        return Reading(self.name, self.confidence, text=text, error=error, source=" ".join(command[:1] + command[2:]))


@dataclass
class CommandReader:
    arguments: list[str] = field(default_factory=list)
    timeout: float = 300.0
    name: str = "commande"
    confidence: str = AUTOMATIC

    @classmethod
    def from_config(cls, path: Path) -> "CommandReader":
        try:
            config = json.loads(Path(path).read_text(encoding="utf-8"))
        except OSError as error:
            raise ReaderUnavailable(f"Fichier de configuration illisible : {path} ({error.strerror}).") from error
        except json.JSONDecodeError as error:
            raise ReaderUnavailable(f"Fichier de configuration {path} : JSON invalide ({error.msg}, ligne {error.lineno}).") from error
        command = config.get("commande") if isinstance(config, dict) else None
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise ReaderUnavailable(f"Fichier de configuration {path} : la clé « commande » doit être une liste non vide de "
                                    'textes, par exemple ["mon-lecteur", "--image", "{image}"]. Une commande en une seule '
                                    "chaîne n'est pas acceptée : elle n'est jamais passée à un interpréteur de commandes.")
        timeout = config.get("delai_s", 300)
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 3600:
            raise ReaderUnavailable(f"Fichier de configuration {path} : « delai_s » doit être un nombre de secondes entre 1 et 3600.")
        label = config.get("nom")
        return cls(arguments=list(command), timeout=float(timeout),
                   name="commande:" + label if isinstance(label, str) and label else "commande")

    def available(self) -> tuple[bool, str]:
        if not self.arguments:
            return False, "Aucune commande configurée (option --config)."
        program = self.arguments[0]
        if shutil.which(program) is None and not Path(program).is_file():
            return False, f"Le programme de la commande configurée est introuvable : {program}."
        return True, f"commande externe : {program} ({len(self.arguments) - 1} argument(s)), délai {self.timeout:g} s"

    def read(self, image: Path) -> Reading:
        absolute = str(Path(image).resolve())
        if any("{image}" in item for item in self.arguments):
            command = [item.replace("{image}", absolute) for item in self.arguments]
        else:
            command = [*self.arguments, absolute]
        text, error = _run(command, self.timeout)
        return Reading(self.name, self.confidence, text=text, error=error, source=self.arguments[0])
