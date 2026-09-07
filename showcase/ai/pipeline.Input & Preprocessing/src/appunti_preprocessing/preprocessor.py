"""
Preprocessor principale per Step 01 della pipeline di riassunzione.

Questo modulo implementa la classe Preprocessor che orchestra tutte le operazioni
di pulizia e normalizzazione del testo, con supporto per:
- Configurazione via YAML
- Logging strutturato
- Type hints completi
- Gestione robusta degli edge cases

Author: Appunti Vision Team
License: MIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import yaml

from . import patterns, utils
from .utils import PreprocessingMetrics, setup_logging, validate_text_input


# ─── Configurazione ──────────────────────────────────────────────────────────
@dataclass
class PreprocessorConfig:
    """
    Configurazione per il Preprocessor.

    Attributes:
        remove_invisible_chars: Rimuovere caratteri invisibili/controllo
        normalize_whitespace: Normalizzare whitespace multipli
        normalize_newlines: Normalizzare sequenze di newlines
        remove_page_numbers: Rimuovere numeri di pagina isolati
        remove_duplicate_lines: Rimuovere linee duplicate consecutive
        remove_empty_lines: Rimuovere linee vuote
        normalize_punctuation: Normalizzare punteggiatura ripetuta
        normalize_dashes: Normalizzare dash types
        normalize_quotes: Normalizzare quote style
        strip_lines: Trim whitespace da inizio/fine linee
        min_text_length: Lunghezza minima testo accettata
        encoding: Encoding per I/O file
        log_level: Livello di logging
        log_file: Path opzionale per file di log
    """

    remove_invisible_chars: bool = True
    normalize_whitespace: bool = True
    normalize_newlines: bool = True
    remove_page_numbers: bool = True
    remove_duplicate_lines: bool = True
    remove_empty_lines: bool = True
    normalize_punctuation: bool = True
    normalize_dashes: bool = True
    normalize_quotes: bool = False  # Conserva smart quotes per default
    strip_lines: bool = True
    min_text_length: int = 1
    encoding: str = "utf-8"
    log_level: int = logging.INFO
    log_file: Path | str | None = None

    @classmethod
    def from_yaml(cls, config_path: Path | str) -> PreprocessorConfig:
        """
        Crea configurazione da file YAML.

        Args:
            config_path: Path del file YAML

        Returns:
            PreprocessorConfig popolata

        Raises:
            FileNotFoundError: Se il file non esiste
            yaml.YAMLError: Se il YAML è malformato
        """
        config_dict = utils.load_yaml_config(config_path)
        return cls.from_dict(config_dict.get("preprocessing", {}))

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> PreprocessorConfig:
        """
        Crea configurazione da dizionario.

        Args:
            config_dict: Dizionario di configurazione

        Returns:
            PreprocessorConfig popolata
        """
        return cls(
            remove_invisible_chars=config_dict.get("remove_invisible_chars", True),
            normalize_whitespace=config_dict.get("normalize_whitespace", True),
            normalize_newlines=config_dict.get("normalize_newlines", True),
            remove_page_numbers=config_dict.get("remove_page_numbers", True),
            remove_duplicate_lines=config_dict.get("remove_duplicate_lines", True),
            remove_empty_lines=config_dict.get("remove_empty_lines", True),
            normalize_punctuation=config_dict.get("normalize_punctuation", True),
            normalize_dashes=config_dict.get("normalize_dashes", True),
            normalize_quotes=config_dict.get("normalize_quotes", False),
            strip_lines=config_dict.get("strip_lines", True),
            min_text_length=config_dict.get("min_text_length", 1),
            encoding=config_dict.get("encoding", "utf-8"),
            log_level=getattr(logging, config_dict.get("log_level", "INFO")),
            log_file=config_dict.get("log_file"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Esporta configurazione come dizionario."""
        return {
            "remove_invisible_chars": self.remove_invisible_chars,
            "normalize_whitespace": self.normalize_whitespace,
            "normalize_newlines": self.normalize_newlines,
            "remove_page_numbers": self.remove_page_numbers,
            "remove_duplicate_lines": self.remove_duplicate_lines,
            "remove_empty_lines": self.remove_empty_lines,
            "normalize_punctuation": self.normalize_punctuation,
            "normalize_dashes": self.normalize_dashes,
            "normalize_quotes": self.normalize_quotes,
            "strip_lines": self.strip_lines,
            "min_text_length": self.min_text_length,
            "encoding": self.encoding,
            "log_level": logging.getLevelName(self.log_level),
            "log_file": str(self.log_file) if self.log_file else None,
        }


# ─── Classe Preprocessor ─────────────────────────────────────────────────────
class Preprocessor:
    """
    Preprocessor per la pulizia e normalizzazione del testo.

    Questa classe implementa tutte le operazioni di preprocessing per Step 01
    della pipeline di riassunzione, con supporto per configurazione dinamica,
    logging strutturato e metriche di qualità.

    Example:
        >>> config = PreprocessorConfig.from_yaml("config.yaml")
        >>> preprocessor = Preprocessor(config)
        >>> cleaned_text = preprocessor.process(raw_text)
        >>> metrics = preprocessor.get_metrics()
    """

    def __init__(
        self,
        config: PreprocessorConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Inizializza il Preprocessor.

        Args:
            config: Configurazione (default: PreprocessorConfig con defaults)
            logger: Logger custom (default: auto-configurato)
        """
        self.config = config if config is not None else PreprocessorConfig()
        self._metrics: PreprocessingMetrics | None = None
        self._patterns = patterns.PATTERNS

        # Setup logging
        if logger is not None:
            self.logger = logger
        else:
            self.logger = setup_logging(
                level=self.config.log_level,
                log_file=self.config.log_file,
            )

        self.logger.info("Preprocessor inizializzato con configurazione: %s", self.config)

    def process(
        self,
        text: str,
        track_metrics: bool = True,
    ) -> str:
        """
        Esegue il preprocessing completo sul testo.

        Args:
            text: Testo da processare
            track_metrics: Se True, traccia metriche di pulizia

        Returns:
            Testo pulito e normalizzato

        Raises:
            ValueError: Se l'input non è valido
            UnicodeDecodeError: Se ci sono problemi di encoding
        """
        self.logger.debug("Inizio preprocessing, lunghezza originale: %d", len(text))

        # Validazione input
        if not validate_text_input(text, self.config.min_text_length):
            raise ValueError(
                f"Input testo non valido: lunghezza {len(text or 0)} "
                f"< min {self.config.min_text_length}"
            )

        # Inizializza metriche
        if track_metrics:
            self._metrics = PreprocessingMetrics(
                original_length=len(text),
                cleaned_length=len(text),
            )

        result = text

        # 1. Rimozione caratteri invisibili
        if self.config.remove_invisible_chars:
            result = self._remove_invisible_chars(result)

        # 2. Normalizzazione line endings
        if self.config.normalize_newlines:
            result = self._normalize_line_endings(result)

        # 3. Strip linee
        if self.config.strip_lines:
            result = self._strip_lines(result)

        # 4. Rimozione numeri di pagina
        if self.config.remove_page_numbers:
            result = self._remove_page_numbers(result)

        # 5. Rimozione linee duplicate
        if self.config.remove_duplicate_lines:
            result = self._remove_duplicate_lines(result)

        # 6. Rimozione linee vuote
        if self.config.remove_empty_lines:
            result = self._remove_empty_lines(result)

        # 7. Normalizzazione whitespace
        if self.config.normalize_whitespace:
            result = self._normalize_whitespace(result)

        # 8. Normalizzazione punteggiatura
        if self.config.normalize_punctuation:
            result = self._normalize_punctuation(result)

        # 9. Normalizzazione dashes
        if self.config.normalize_dashes:
            result = self._normalize_dashes(result)

        # 10. Normalizzazione quotes (opzionale)
        if self.config.normalize_quotes:
            result = self._normalize_quotes(result)

        # Final trim
        result = result.strip()

        # Aggiorna metriche finali
        if track_metrics and self._metrics:
            self._metrics = replace(self._metrics, original_length=len(text), cleaned_length=len(result))
            self.logger.info(
                "Preprocessing completato: riduzione %.2f%%, ops totali: %d",
                self._metrics.reduction_ratio * 100,
                self._metrics.total_cleaning_ops,
            )

        return result

    def process_file(
        self,
        input_path: Path | str,
        output_path: Path | str | None = None,
        track_metrics: bool = True,
    ) -> str:
        """
        Processa un file di testo e opzionalmente scrive l'output.

        Args:
            input_path: Path del file input
            output_path: Path del file output (None per non scrivere)
            track_metrics: Se True, traccia metriche di pulizia

        Returns:
            Testo pulito e normalizzato

        Raises:
            FileNotFoundError: Se il file input non esiste
            IsADirectoryError: Se il path non è un file
        """
        input_path = Path(input_path)
        self.logger.info("Processamento file: %s", input_path)

        # Leggi file con gestione encoding robusta
        text = utils.read_text_safe(
            input_path,
            encoding=self.config.encoding,
        )

        # Processa testo
        cleaned_text = self.process(text, track_metrics=track_metrics)

        # Scrivi output (opzionale)
        if output_path is not None:
            output_path = Path(output_path)
            utils.write_text_safe(
                output_path,
                cleaned_text,
                encoding=self.config.encoding,
            )
            self.logger.info("Output scritto su: %s", output_path)

        return cleaned_text

    def get_metrics(self) -> PreprocessingMetrics | None:
        """
        Restituisce le metriche dell'ultima operazione di preprocessing.

        Returns:
            PreprocessingMetrics o None se process() non è stato chiamato
            con track_metrics=True
        """
        return self._metrics

    def reset_metrics(self) -> None:
        """Resetta le metriche trackate."""
        self._metrics = None

    # ─── Metodi privati di pulizia ───────────────────────────────────────────
    def _remove_invisible_chars(self, text: str) -> str:
        """Rimuove caratteri invisibili e di controllo Unicode."""
        count = len(self._patterns.invisible_chars.findall(text))
        result = self._patterns.invisible_chars.sub("", text)

        if self._metrics:
            self._metrics = replace(self._metrics, invisible_chars_removed=count)

        self.logger.debug("Rimossi %d caratteri invisibili", count)
        return result

    def _normalize_line_endings(self, text: str) -> str:
        """Normalizza tutti i line endings a LF (\n)."""
        # Prima conta le newlines multiple
        if self.config.normalize_newlines:
            count = len(self._patterns.multiple_newlines.findall(text))
            text = self._patterns.multiple_newlines.sub("\n\n", text)

            if self._metrics:
                self._metrics = replace(self._metrics, newlines_normalized=count)

            self.logger.debug("Normalizzate %d sequenze di newlines", count)

        # Normalizza CRLF e CR a LF
        result = self._patterns.line_ending_normalizer.sub("\n", text)
        return result

    def _strip_lines(self, text: str) -> str:
        """Rimuove whitespace da inizio e fine di ogni linea."""
        return self._patterns.line_trim.sub("", text)

    def _remove_page_numbers(self, text: str) -> str:
        """Rimuove numeri di pagina isolati e footer/header di pagina."""
        lines = text.split("\n")
        removed_count = 0
        filtered_lines = []

        for line in lines:
            # Check standalone page number
            if self._patterns.page_number_standalone.match(line):
                removed_count += 1
                continue

            # Check page header con dashes
            if self._patterns.page_header_dashes.match(line):
                removed_count += 1
                continue

            # Check page footer pattern
            if self._patterns.page_footer.search(line):
                removed_count += 1
                continue

            filtered_lines.append(line)

        if self._metrics:
            self._metrics = replace(self._metrics, page_numbers_removed=removed_count)

        self.logger.debug("Rimossi %d numeri di pagina", removed_count)
        return "\n".join(filtered_lines)

    def _remove_duplicate_lines(self, text: str) -> str:
        """Rimuove linee duplicate consecutive."""
        lines = text.split("\n")
        result_lines: list[str] = []
        removed_count = 0

        if not lines:
            return text

        prev_line_hash: str | None = None

        for line in lines:
            current_hash = utils.text_hash(line.strip())

            if current_hash == prev_line_hash:
                removed_count += 1
                self.logger.debug("Linea duplicata rimossa: %s", line[:50])
            else:
                result_lines.append(line)

            prev_line_hash = current_hash

        if self._metrics:
            self._metrics = replace(self._metrics, duplicate_lines_removed=removed_count)

        self.logger.debug("Rimosse %d linee duplicate", removed_count)
        return "\n".join(result_lines)

    def _remove_empty_lines(self, text: str) -> str:
        """Rimuove linee che contengono solo whitespace."""
        lines = text.split("\n")
        result_lines = [line for line in lines if line.strip()]
        result = "\n".join(result_lines)

        self.logger.debug(
            "Rimosse %d linee vuote",
            len(lines) - len(result_lines),
        )
        return result

    def _normalize_whitespace(self, text: str) -> str:
        """Normalizza whitespace multipli a singolo spazio."""
        result = self._patterns.multiple_whitespace.sub(" ", text)
        self.logger.debug("Whitespace normalizzato")
        return result

    def _normalize_punctuation(self, text: str) -> str:
        """Normalizza punteggiatura ripetuta (es. "..." -> ".", "!!" -> "!")."""
        result = self._patterns.multiple_punctuation.sub(r"\1", text)
        self.logger.debug("Punteggiatura normalizzata")
        return result

    def _normalize_dashes(self, text: str) -> str:
        """Normalizza dash Unicode a hyphen standard."""
        result = self._patterns.dash_normalizer.sub("-", text)
        self.logger.debug("Dash normalizzati")
        return result

    def _normalize_quotes(self, text: str) -> str:
        """Normalizza smart quotes a quote standard."""
        result = self._patterns.smart_quotes.sub('"', text)
        self.logger.debug("Quote normalizzate")
        return result

    # ─── Utility methods ─────────────────────────────────────────────────────
    def get_config_summary(self) -> dict[str, Any]:
        """Restituisce summary della configurazione corrente."""
        return self.config.to_dict()

    def enable_step(self, step_name: str) -> None:
        """
        Abilita un step di preprocessing.

        Args:
            step_name: Nome dello step (es. "remove_invisible_chars")
        """
        if hasattr(self.config, step_name):
            setattr(self.config, step_name, True)
            self.logger.info("Step '%s' abilitato", step_name)
        else:
            self.logger.warning("Step '%s' non trovato", step_name)

    def disable_step(self, step_name: str) -> None:
        """
        Disabilita un step di preprocessing.

        Args:
            step_name: Nome dello step (es. "remove_page_numbers")
        """
        if hasattr(self.config, step_name):
            setattr(self.config, step_name, False)
            self.logger.info("Step '%s' disabilitato", step_name)
        else:
            self.logger.warning("Step '%s' non trovato", step_name)

    def list_available_steps(self) -> list[str]:
        """
        Lista tutti gli step di preprocessing disponibili.

        Returns:
            Lista di nomi di step
        """
        return [
            "remove_invisible_chars",
            "normalize_whitespace",
            "normalize_newlines",
            "remove_page_numbers",
            "remove_duplicate_lines",
            "remove_empty_lines",
            "normalize_punctuation",
            "normalize_dashes",
            "normalize_quotes",
            "strip_lines",
        ]


# ─── Factory function ────────────────────────────────────────────────────────
def create_preprocessor(
    config_path: Path | str | None = None,
    **kwargs: Any,
) -> Preprocessor:
    """
    Factory function per creare un Preprocessor.

    Args:
        config_path: Path opzionale per file YAML di configurazione
        **kwargs: Parametri override per PreprocessorConfig

    Returns:
        Preprocessor configurato

    Example:
        >>> pp = create_preprocessor("config.yaml", remove_page_numbers=False)
    """
    if config_path is not None:
        config = PreprocessorConfig.from_yaml(config_path)
    else:
        config = PreprocessorConfig()

    # Apply overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return Preprocessor(config)
