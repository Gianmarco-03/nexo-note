"""
Content Selector principale per Step 03 della pipeline di riassunzione.

Questo modulo implementa la classe Selector che orchestra l'architettura
Map-Reduce per la selezione e compressione dei contenuti rilevanti.

Architettura:
  MAP: Compressione di ogni chunk → mini-summary (1 per chunk)
  REDUCE: Fusione dei mini-summary → summary finale unico

Author: Appunti Vision Team
License: MIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from . import utils
from .summarizers import BaseSummarizer, MockSummarizer
from .utils import SelectionMetrics, setup_logging, Timer


# ─── Configurazione Selector ─────────────────────────────────────────────────
@dataclass
class SelectorConfig:
    """
    Configurazione per il Selector (Content Selection).

    Attributes:
        map_n_sentences: Numero di frasi per mini-summary (MAP step)
        map_model: Nome modello MAP (IT5-large)
        map_temperature: Temperatura generazione MAP
        map_batch_size: Dimensione batch MAP

        reduce_max_words: Massimo parole nel summary finale (REDUCE step)
        reduce_model: Nome modello REDUCE (Qwen2.5-7B-Instruct)
        reduce_temperature: Temperatura generazione REDUCE

        track_metrics: Abilita tracking metriche
        export_metrics: Esporta metriche su file JSON
        export_metrics_path: Path per export metriche

        log_level: Livello logging
        log_file: Path opzionale per file di log
    """

    # MAP step
    map_n_sentences: int = 3
    map_model: str = "ARTeLab/it5-summarization"  # IT5 fine-tuned su summarizzazione italiana
    map_temperature: float = 0.7
    map_batch_size: int = 32
    map_device: str = "cuda"
    summarizer_type: Literal["mock", "huggingface"] = "huggingface"
    fallback_to_mock: bool = False


    # REDUCE step
    reduce_max_words: int = 500
    reduce_model: str = "Qwen/Qwen2.5-7B-Instruct"
    reduce_temperature: float = 0.7
    reduce_device: str = "cuda"

    # Metriche
    track_metrics: bool = True
    export_metrics: bool = False
    export_metrics_path: Path | str | None = None

    # Logging
    log_level: int = logging.INFO
    log_file: Path | str | None = None

    def __post_init__(self) -> None:
        """Validazione post-inizializzazione."""
        if self.map_n_sentences <= 0:
            raise ValueError(f"map_n_sentences deve essere > 0, ricevuto {self.map_n_sentences}")
        if self.reduce_max_words <= 0:
            raise ValueError(f"reduce_max_words deve essere > 0, ricevuto {self.reduce_max_words}")
        if not (0.0 <= self.map_temperature <= 1.0):
            raise ValueError(
                f"map_temperature deve essere tra 0.0 e 1.0, ricevuto {self.map_temperature}"
            )

    @classmethod
    def from_yaml(cls, config_path: Path | str) -> SelectorConfig:
        """
        Crea configurazione da file YAML.

        Args:
            config_path: Path del file YAML

        Returns:
            SelectorConfig popolata

        Raises:
            FileNotFoundError: Se il file non esiste
            yaml.YAMLError: Se il YAML è malformato
        """
        config_dict = utils.load_yaml_config(config_path)

        # Estrai sezioni
        map_config = config_dict.get("map", {})
        reduce_config = config_dict.get("reduce", {})
        metrics_config = config_dict.get("metrics", {})
        io_config = config_dict.get("io", {})

        return cls(
            map_n_sentences=map_config.get("n_sentences_map", 3),
            map_model=map_config.get("model", "IT5-large"),
            map_temperature=map_config.get("temperature_map", 0.7),
            map_batch_size=map_config.get("batch_size_map", 32),
            map_device=map_config.get("device_map", "auto"),
            reduce_max_words=reduce_config.get("max_words_reduce", 500),
            reduce_model=reduce_config.get("model", "Qwen/Qwen2.5-7B-Instruct"),
            reduce_temperature=reduce_config.get("temperature_reduce", 0.7),
            reduce_device=reduce_config.get("device_reduce", "auto"),
            track_metrics=metrics_config.get("track_enabled", True),
            export_metrics=metrics_config.get("export_enabled", False),
            export_metrics_path=metrics_config.get("export_path"),
            log_level=getattr(logging, io_config.get("log_level", "INFO")),
            log_file=io_config.get("log_file"),
        )

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> SelectorConfig:
        """Crea configurazione da dizionario."""
        map_config = config_dict.get("map", {})
        reduce_config = config_dict.get("reduce", {})

        return cls(
            map_n_sentences=map_config.get("n_sentences_map", 3),
            map_model=map_config.get("model", "IT5-large"),
            map_temperature=map_config.get("temperature_map", 0.7),
            map_batch_size=map_config.get("batch_size_map", 32),
            reduce_max_words=reduce_config.get("max_words_reduce", 500),
            reduce_model=reduce_config.get("model", "Qwen/Qwen2.5-7B-Instruct"),
            reduce_temperature=reduce_config.get("temperature_reduce", 0.7),
            track_metrics=config_dict.get("track_metrics", True),
            export_metrics=config_dict.get("export_metrics", False),
            export_metrics_path=config_dict.get("export_metrics_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Esporta configurazione come dizionario."""
        return {
            "map_n_sentences": self.map_n_sentences,
            "map_model": self.map_model,
            "map_temperature": self.map_temperature,
            "reduce_max_words": self.reduce_max_words,
            "reduce_model": self.reduce_model,
            "reduce_temperature": self.reduce_temperature,
            "track_metrics": self.track_metrics,
            "export_metrics": self.export_metrics,
        }


# ─── Classe Selector ─────────────────────────────────────────────────────────
class Selector:
    """
    Content Selector per Step 03 (Map-Reduce).

    Orchestrazione architettura Map-Reduce:
    1. MAP: Compressione di ogni chunk → mini-summary
    2. REDUCE: Fusione dei mini-summary → summary finale

    Example:
        >>> config = SelectorConfig.from_yaml("config.yaml")
        >>> selector = Selector(config)
        >>> mini_summaries = selector.select(chunks)
        >>> final_summary = selector.reduce(mini_summaries)
        >>> metrics = selector.get_metrics()
    """

    def __init__(
        self,
        config: SelectorConfig,
        summarizer: BaseSummarizer | None = None,
    ):
        """
        Inizializza Selector.

        Args:
            config: Configurazione SelectorConfig
            summarizer: BaseSummarizer (default: MockSummarizer per testing)
        """
        self.config = config
        self.logger = setup_logging(config.log_level, config.log_file)

        # Usa MockSummarizer di default (no dipendenze modelli)
        if summarizer is None:
            self.summarizer = MockSummarizer()
            self.logger.info("Usando MockSummarizer (no modelli reali)")
        else:
            self.summarizer = summarizer
            self.logger.info(f"Usando {summarizer.__class__.__name__}")

        # Metriche
        self.metrics = SelectionMetrics()
        self.logger.info(f"Selector inizializzato: {self.config.to_dict()}")

    def select(self, chunks: list[dict[str, Any]]) -> list[str]:
        """
        MAP step: Compressione di ogni chunk.

        Input: lista di chunk (output Step 02)
        Output: lista di mini-summary (1 per chunk)

        Args:
            chunks: Lista di chunk (dicts con chiavi id, text, ecc.)

        Returns:
            Lista di mini-summary (stringhe)

        Raises:
            ValueError: Se chunks non valido
        """
        utils.validate_chunks(chunks)

        self.logger.info(f"Inizio MAP step: {len(chunks)} chunk")

        mini_summaries = []
        chunk_stats = []

        with Timer("MAP_step") as map_timer:
            for i, chunk in enumerate(chunks, 1):
                chunk_id = chunk.get("id", i)
                chunk_text = chunk.get("text", "").strip()

                # Calcola metriche pre-processing
                input_tokens = utils.estimate_tokens(chunk_text)

                # MAP: Compressione chunk
                mini_summary = self.summarizer.map_chunk(
                    chunk_text,
                    n_sentences=self.config.map_n_sentences,
                )

                mini_summaries.append(mini_summary)

                # Metriche post-processing
                output_tokens = utils.estimate_tokens(mini_summary)
                compression_ratio = output_tokens / input_tokens if input_tokens > 0 else 0.0

                chunk_stats.append(
                    {
                        "chunk_id": chunk_id,
                        "input_chars": len(chunk_text),
                        "output_chars": len(mini_summary),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "compression_ratio": round(compression_ratio, 4),
                    }
                )

                self.logger.debug(
                    f"MAP chunk {i}/{len(chunks)}: "
                    f"{input_tokens}→{output_tokens} tokens "
                    f"(ratio {compression_ratio:.2%})"
                )

        # Aggiungi statistiche globali
        self.metrics.num_chunks_processed = len(chunks)
        self.metrics.num_mini_summaries = len(mini_summaries)
        self.metrics.chunk_by_chunk_stats = chunk_stats
        self.metrics.map_step_time = map_timer.elapsed_time

        # Calcola compression ratio medio
        if chunk_stats:
            avg_compression = sum(s["compression_ratio"] for s in chunk_stats) / len(
                chunk_stats
            )
            self.metrics.compression_ratio_map = avg_compression

        self.logger.info(
            f"MAP step completato in {map_timer.elapsed_time:.3f}s "
            f"({len(mini_summaries)} mini-summary, "
            f"compression ratio {self.metrics.compression_ratio_map:.2%})"
        )

        return mini_summaries

    def reduce(self, mini_summaries: list[str]) -> str:
        """
        REDUCE step: Fusione dei mini-summary.

        Input: lista di mini-summary (output MAP)
        Output: summary finale unico

        Args:
            mini_summaries: Lista di mini-summary

        Returns:
            Summary finale (stringa unica)

        Raises:
            ValueError: Se mini_summaries vuota
        """
        if not mini_summaries:
            raise ValueError("mini_summaries non può essere vuota")

        self.logger.info(f"Inizio REDUCE step: {len(mini_summaries)} mini-summary")

        with Timer("REDUCE_step") as reduce_timer:
            # Concatena input per metriche
            combined_text = " ".join(mini_summaries)
            input_tokens = utils.estimate_tokens(combined_text)

            # REDUCE: Fusione mini-summary
            final_summary = self.summarizer.reduce_summaries(
                mini_summaries,
                max_words=self.config.reduce_max_words,
            )

            # Metriche output
            output_tokens = utils.estimate_tokens(final_summary)

        # Aggiorna metriche
        self.metrics.reduce_step_time = reduce_timer.elapsed_time
        self.metrics.total_input_tokens = input_tokens
        self.metrics.total_output_tokens = output_tokens
        self.metrics.total_time = self.metrics.map_step_time + reduce_timer.elapsed_time
        self.metrics.compression_ratio_final = (
            output_tokens / input_tokens if input_tokens > 0 else 0.0
        )

        self.logger.info(
            f"REDUCE step completato in {reduce_timer.elapsed_time:.3f}s "
            f"({input_tokens}→{output_tokens} tokens, "
            f"compression ratio finale {self.metrics.compression_ratio_final:.2%})"
        )

        return final_summary

    def process(self, chunks: list[dict[str, Any]]) -> tuple[list[str], str]:
        """
        Esegui full pipeline Map-Reduce.

        Args:
            chunks: Lista di chunk (output Step 02)

        Returns:
            Tuple (mini_summaries, final_summary)
        """
        mini_summaries = self.select(chunks)
        final_summary = self.reduce(mini_summaries)
        return mini_summaries, final_summary

    def get_metrics(self) -> SelectionMetrics:
        """Restituisce metriche di esecuzione."""
        return self.metrics

    def export_metrics(self, output_path: Path | str | None = None) -> str:
        """
        Esporta metriche come JSON.

        Args:
            output_path: Path per salvataggio (default: config.export_metrics_path)

        Returns:
            JSON string
        """
        output_path = output_path or self.config.export_metrics_path

        metrics_json = self.metrics.to_json()

        if output_path:
            utils.save_json_file(self.metrics.to_dict(), output_path)
            self.logger.info(f"Metriche esportate in {output_path}")

        return metrics_json


# ─── Factory function ────────────────────────────────────────────────────────
def create_selector(
    config_path: Path | str | None = None,
    summarizer: BaseSummarizer | None = None,
    **config_overrides: Any,
) -> Selector:
    """
    Factory function per creare Selector con configurazione.

    Args:
        config_path: Path file YAML (default: config.yaml)
        summarizer: BaseSummarizer custom (default: MockSummarizer)
        **config_overrides: Override parametri configurazione

    Returns:
        Istanza Selector configurata

    Raises:
        FileNotFoundError: Se config file non esiste
    """
    if config_path:
        config = SelectorConfig.from_yaml(config_path)
    else:
        config = SelectorConfig()

    # Apply overrides
    for key, value in config_overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            raise ValueError(f"SelectorConfig non ha attributo: {key}")

    # Create summarizer se non fornito
    if summarizer is None and config_overrides.get("summarizer_type") == "huggingface":
        try:
            from .summarizers import HuggingFaceSummarizer

            summarizer = HuggingFaceSummarizer(
                map_model=config.map_model,
                reduce_model=config.reduce_model,
                device=config.map_device,
            )
        except ImportError:
            logger = setup_logging()
            logger.warning(
                "HuggingFaceSummarizer non disponibile, fallback su MockSummarizer"
            )
            summarizer = MockSummarizer()

    return Selector(config, summarizer)
