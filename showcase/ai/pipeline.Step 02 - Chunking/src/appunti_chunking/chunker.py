"""
Chunker principale per Step 02 della pipeline di riassunzione.

Questo modulo implementa la classe Chunker che orchestra tutte le operazioni
di divisione del testo in chunk, con supporto per:
- Configurazione via YAML
- Logging strutturato
- Type hints completi
- Sliding window con overlapping
- Paragraph-based splitting
- Sentence-level granularity

Author: Appunti Vision Team
License: MIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from . import utils
from .utils import ChunkingMetrics, Chunk, setup_logging


# ─── Configurazione ──────────────────────────────────────────────────────────
@dataclass
class ChunkerConfig:
    """
    Configurazione per il Chunker.

    Attributes:
        strategy: Strategia di chunking ("paragraph", "sliding_window", "hybrid")
        chunk_size: Dimensione target del chunk (caratteri o parole)
        chunk_unit: Unità di misura ("chars", "words", "sentences")
        overlap_ratio: Percentuale di overlapping (0.0-0.5)
        min_chunk_size: Dimensione minima accettata per un chunk
        max_chunks: Numero massimo di chunk (None = illimitato)
        sentence_detection: Metodo per sentence detection ("regex", "nltk", "spacy")
        preserve_paragraphs: Preservare confini di paragrafo
        language: Lingua del testo ("it", "en")
        encoding: Encoding per I/O file
        log_level: Livello di logging
        log_file: Path opzionale per file di log
    """

    strategy: Literal["paragraph", "sliding_window", "hybrid"] = "hybrid"
    chunk_size: int = 512
    chunk_unit: Literal["chars", "words", "sentences"] = "chars"
    overlap_ratio: float = 0.15
    min_chunk_size: int = 64
    max_chunks: int | None = None
    sentence_detection: Literal["regex", "nltk", "spacy"] = "regex"
    preserve_paragraphs: bool = True
    language: Literal["it", "en"] = "it"
    encoding: str = "utf-8"
    log_level: int = logging.INFO
    log_file: Path | str | None = None

    def __post_init__(self) -> None:
        """Validazione post-inizializzazione."""
        if not (0.0 <= self.overlap_ratio <= 0.5):
            raise ValueError(
                f"overlap_ratio deve essere tra 0.0 e 0.5, ricevuto {self.overlap_ratio}"
            )
        if self.chunk_size <= 0:
            raise ValueError(f"chunk_size deve essere > 0, ricevuto {self.chunk_size}")
        if self.min_chunk_size < 0:
            raise ValueError(f"min_chunk_size deve essere >= 0, ricevuto {self.min_chunk_size}")
        if self.max_chunks is not None and self.max_chunks <= 0:
            raise ValueError(f"max_chunks deve essere > 0, ricevuto {self.max_chunks}")

    @classmethod
    def from_yaml(cls, config_path: Path | str) -> ChunkerConfig:
        """
        Crea configurazione da file YAML.

        Args:
            config_path: Path del file YAML

        Returns:
            ChunkerConfig popolata

        Raises:
            FileNotFoundError: Se il file non esiste
            yaml.YAMLError: Se il YAML è malformato
        """
        config_dict = utils.load_yaml_config(config_path)
        return cls.from_dict(config_dict.get("chunking", {}))

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> ChunkerConfig:
        """
        Crea configurazione da dizionario.

        Args:
            config_dict: Dizionario di configurazione

        Returns:
            ChunkerConfig popolata
        """
        return cls(
            strategy=config_dict.get("strategy", "hybrid"),
            chunk_size=config_dict.get("chunk_size", 512),
            chunk_unit=config_dict.get("chunk_unit", "chars"),
            overlap_ratio=config_dict.get("overlap_ratio", 0.15),
            min_chunk_size=config_dict.get("min_chunk_size", 64),
            max_chunks=config_dict.get("max_chunks"),
            sentence_detection=config_dict.get("sentence_detection", "regex"),
            preserve_paragraphs=config_dict.get("preserve_paragraphs", True),
            language=config_dict.get("language", "it"),
            encoding=config_dict.get("encoding", "utf-8"),
            log_level=getattr(logging, config_dict.get("log_level", "INFO")),
            log_file=config_dict.get("log_file"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Esporta configurazione come dizionario."""
        return {
            "strategy": self.strategy,
            "chunk_size": self.chunk_size,
            "chunk_unit": self.chunk_unit,
            "overlap_ratio": self.overlap_ratio,
            "min_chunk_size": self.min_chunk_size,
            "max_chunks": self.max_chunks,
            "sentence_detection": self.sentence_detection,
            "preserve_paragraphs": self.preserve_paragraphs,
            "language": self.language,
            "encoding": self.encoding,
            "log_level": logging.getLevelName(self.log_level),
            "log_file": str(self.log_file) if self.log_file else None,
        }


# ─── Classe Chunker ───────────────────────────────────────────────────────────
class Chunker:
    """
    Chunker per la divisione del testo in unità processabili.

    Questa classe implementa tutte le strategie di chunking per Step 02
    della pipeline di riassunzione, con supporto per configurazione dinamica,
    logging strutturato e metriche di qualità.

    Example:
        >>> config = ChunkerConfig.from_yaml("config.yaml")
        >>> chunker = Chunker(config)
        >>> chunks = chunker.chunk(normalized_text)
        >>> metrics = chunker.get_metrics()
    """

    def __init__(
        self,
        config: ChunkerConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Inizializza il Chunker.

        Args:
            config: Configurazione (default: ChunkerConfig con defaults)
            logger: Logger custom (default: auto-configurato)
        """
        self.config = config if config is not None else ChunkerConfig()
        self._metrics: ChunkingMetrics | None = None
        self._chunks: list[Chunk] = []

        # Setup logging
        if logger is not None:
            self.logger = logger
        else:
            self.logger = setup_logging(
                level=self.config.log_level,
                log_file=self.config.log_file,
            )

        self.logger.info("Chunker inizializzato con configurazione: %s", self.config)

    def chunk(
        self,
        text: str,
        track_metrics: bool = True,
    ) -> list[Chunk]:
        """
        Esegue il chunking completo sul testo.

        Args:
            text: Testo normalizzato da chunkare
            track_metrics: Se True, traccia metriche di chunking

        Returns:
            Lista di Chunk objects

        Raises:
            ValueError: Se l'input non è valido
        """
        # Validazione input PRIMA del log
        if not isinstance(text, str) or not text:
            raise ValueError("Input testo non valido")

        self.logger.debug("Inizio chunking, lunghezza testo: %d caratteri", len(text))

        # Inizializza metriche
        if track_metrics:
            self._metrics = ChunkingMetrics(
                original_length=len(text),
                total_chunks=0,
            )

        # Applica strategia configurata
        if self.config.strategy == "paragraph":
            self._chunks = self._chunk_by_paragraph(text)
        elif self.config.strategy == "sliding_window":
            self._chunks = self._chunk_sliding_window(text)
        elif self.config.strategy == "hybrid":
            self._chunks = self._chunk_hybrid(text)
        else:
            raise ValueError(f"Strategia non supportata: {self.config.strategy}")

        # Applica limite max chunks se configurato
        if self.config.max_chunks and len(self._chunks) > self.config.max_chunks:
            self.logger.warning(
                "Chunking riduce da %d a %d chunk (max_chunks=%d)",
                len(self._chunks),
                self.config.max_chunks,
                self.config.max_chunks,
            )
            self._chunks = self._chunks[: self.config.max_chunks]

        # Filtra chunk troppo piccoli
        self._chunks = self._filter_small_chunks(self._chunks)

        # Rinumerazione IDs sequenziali
        for i, chunk in enumerate(self._chunks):
            chunk.id = i

        # Aggiorna metriche finali
        if track_metrics and self._metrics:
            chunk_sizes = [c.end - c.start for c in self._chunks]
            total_covered_length = sum(chunk_sizes)

            self._metrics = ChunkingMetrics(
                original_length=len(text),
                total_chunks=len(self._chunks),
                avg_chunk_size=total_covered_length / len(self._chunks) if self._chunks else 0.0,
                min_chunk_size=min(chunk_sizes) if chunk_sizes else 0,
                max_chunk_size=max(chunk_sizes) if chunk_sizes else 0,
                overlapping_applied=self.config.overlap_ratio > 0,
                coverage_ratio=total_covered_length / len(text) if len(text) > 0 else 0.0,
            )
            self.logger.info(
                "Chunking completato: %d chunk, avg size %.0f %s, coverage %.1f%%",
                self._metrics.total_chunks,
                self._metrics.avg_chunk_size,
                self.config.chunk_unit,
                self._metrics.coverage_ratio * 100,
            )

        return self._chunks

    def chunk_file(
        self,
        input_path: Path | str,
        output_path: Path | str | None = None,
        track_metrics: bool = True,
    ) -> list[Chunk]:
        """
        Processa un file di testo ed estrae i chunk.

        Args:
            input_path: Path del file input
            output_path: Path del file output per chunks JSON (None per non scrivere)
            track_metrics: Se True, traccia metriche di chunking

        Returns:
            Lista di Chunk objects

        Raises:
            FileNotFoundError: Se il file input non esiste
            IsADirectoryError: Se il path non è un file
        """
        input_path = Path(input_path)
        self.logger.info("Chunking file: %s", input_path)

        # Leggi file con gestione encoding robusta
        text = utils.read_text_safe(
            input_path,
            encoding=self.config.encoding,
        )

        # Esegui chunking
        chunks = self.chunk(text, track_metrics=track_metrics)

        # Scrivi output (opzionale)
        if output_path is not None:
            output_path = Path(output_path)
            utils.write_chunks_json(output_path, chunks)
            self.logger.info("Chunks scritti su: %s", output_path)

        return chunks

    def get_chunks(self) -> list[Chunk]:
        """
        Restituisce i chunk dell'ultima operazione.

        Returns:
            Lista di Chunk objects o lista vuoata
        """
        return self._chunks.copy()

    def get_metrics(self) -> ChunkingMetrics | None:
        """
        Restituisce le metriche dell'ultima operazione di chunking.

        Returns:
            ChunkingMetrics o None se chunk() non è stato chiamato
            con track_metrics=True
        """
        return self._metrics

    def reset_metrics(self) -> None:
        """Resetta le metriche trackate."""
        self._metrics = None

    def get_chunk_texts(self) -> list[str]:
        """
        Estrae i testi dei chunk come lista di stringhe.

        Returns:
            Lista di testi dei chunk
        """
        return [chunk.text for chunk in self._chunks]

    # ─── Metodi privati di chunking ──────────────────────────────────────────
    def _chunk_by_paragraph(self, text: str) -> list[Chunk]:
        """
        Divide il testo per paragrafi (doppio newline).

        Args:
            text: Testo da chunkare

        Returns:
            Lista di Chunk per paragrafo
        """
        paragraphs = text.split("\n\n")
        chunks: list[Chunk] = []
        current_pos = 0

        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            start = current_pos
            end = current_pos + len(paragraph)

            chunks.append(
                Chunk(
                    id=i,
                    text=paragraph,
                    start=start,
                    end=end,
                    metadata={"type": "paragraph", "index": i},
                )
            )

            current_pos = end + 2  # +2 per "\n\n"

        self.logger.debug("Chunking per paragrafi: %d chunk creati", len(chunks))
        return chunks

    def _chunk_sliding_window(self, text: str) -> list[Chunk]:
        """
        Divide il testo con sliding window e overlapping.

        Args:
            text: Testo da chunkare

        Returns:
            Lista di Chunk con sliding window
        """
        chunks: list[Chunk] = []

        if self.config.chunk_unit == "words":
            words = text.split()
            window_size = self.config.chunk_size
            overlap_size = int(window_size * self.config.overlap_ratio)

            i = 0
            chunk_id = 0
            char_pos = 0

            while i < len(words):
                window_words = words[i : i + window_size]
                chunk_text = " ".join(window_words)

                chunks.append(
                    Chunk(
                        id=chunk_id,
                        text=chunk_text,
                        start=char_pos,
                        end=char_pos + len(chunk_text),
                        metadata={
                            "type": "sliding_window",
                            "index": chunk_id,
                            "word_count": len(window_words),
                        },
                    )
                )

                char_pos = char_pos + len(chunk_text)
                chunk_id += 1

                # Avanza finestra
                if i + window_size >= len(words):
                    break
                i += window_size - overlap_size

        elif self.config.chunk_unit == "sentences":
            sentences = self._split_sentences(text)
            window_size = self.config.chunk_size
            overlap_size = int(window_size * self.config.overlap_ratio)

            i = 0
            chunk_id = 0

            while i < len(sentences):
                window_sents = sentences[i : i + window_size]
                chunk_text = " ".join(window_sents)

                chunks.append(
                    Chunk(
                        id=chunk_id,
                        text=chunk_text,
                        start=text.find(chunk_text),
                        end=text.find(chunk_text) + len(chunk_text),
                        metadata={
                            "type": "sliding_window",
                            "index": chunk_id,
                            "sentence_count": len(window_sents),
                        },
                    )
                )

                chunk_id += 1

                if i + window_size >= len(sentences):
                    break
                i += window_size - overlap_size

        else:  # chars
            window_size = self.config.chunk_size
            overlap_size = int(window_size * self.config.overlap_ratio)

            i = 0
            chunk_id = 0

            while i < len(text):
                chunk_text = text[i : i + window_size]

                chunks.append(
                    Chunk(
                        id=chunk_id,
                        text=chunk_text,
                        start=i,
                        end=i + len(chunk_text),
                        metadata={"type": "sliding_window", "index": chunk_id},
                    )
                )

                chunk_id += 1

                if i + window_size >= len(text):
                    break
                i += window_size - overlap_size

        self.logger.debug(
            "Sliding window chunking: %d chunk creati (window=%d, overlap=%.0f%%)",
            len(chunks),
            self.config.chunk_size,
            self.config.overlap_ratio * 100,
        )
        return chunks

    def _chunk_hybrid(self, text: str) -> list[Chunk]:
        """
        Strategia ibrida: prima divide per paragrafi, poi applica sliding window
        se i paragrafi sono troppo grandi.

        Args:
            text: Testo da chunkare

        Returns:
            Lista di Chunk con strategia ibrida
        """
        # Primo passo: chunking per paragrafi
        paragraph_chunks = self._chunk_by_paragraph(text)

        # Secondo passo: se un paragrafo è troppo grande, applica sliding window
        final_chunks: list[Chunk] = []

        for p_chunk in paragraph_chunks:
            if self._is_too_large(p_chunk.text):
                # Sub-chunking con sliding window
                sub_chunks = self._chunk_sliding_window(p_chunk.text)
                # Aggiorna metadata con riferimento al paragrafo originale
                for sc in sub_chunks:
                    sc.metadata["parent_paragraph"] = p_chunk.id
                    sc.metadata["type"] = "hybrid"
                final_chunks.extend(sub_chunks)
            else:
                p_chunk.metadata["type"] = "hybrid"
                final_chunks.append(p_chunk)

        self.logger.debug(
            "Hybrid chunking: %d paragrafi -> %d chunk finali",
            len(paragraph_chunks),
            len(final_chunks),
        )
        return final_chunks

    def _is_too_large(self, text: str) -> bool:
        """
        Verifica se un testo è troppo grande per un singolo chunk.

        Args:
            text: Testo da verificare

        Returns:
            True se supera la soglia
        """
        if self.config.chunk_unit == "words":
            return len(text.split()) > self.config.chunk_size
        elif self.config.chunk_unit == "sentences":
            return len(self._split_sentences(text)) > self.config.chunk_size
        else:
            return len(text) > self.config.chunk_size

    def _filter_small_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Rimuove chunk troppo piccoli.

        Args:
            chunks: Lista di chunk da filtrare

        Returns:
            Lista filtrata
        """
        filtered = [
            c for c in chunks if len(c.text) >= self.config.min_chunk_size
        ]
        removed = len(chunks) - len(filtered)
        if removed > 0:
            self.logger.debug("Rimossi %d chunk troppo piccoli", removed)
        return filtered

    def _split_sentences(self, text: str) -> list[str]:
        """
        Divide il testo in frasi.

        Args:
            text: Testo da dividere

        Returns:
            Lista di frasi
        """
        if self.config.sentence_detection == "nltk":
            try:
                import nltk

                return nltk.sent_tokenize(text, language=self.config.language)
            except ImportError:
                self.logger.warning("nltk non disponibile, fallback a regex")
        elif self.config.sentence_detection == "spacy":
            try:
                import spacy

                nlp = spacy.load(self.config.language)
                doc = nlp(text)
                return [sent.text for sent in doc.sents]
            except ImportError:
                self.logger.warning("spacy non disponibile, fallback a regex")

        # Fallback regex per italiano
        import re

        # Pattern migliorato per sentence boundary in italiano
        # Gestisce: abbreviazioni (Dr., Prof., etc.), ellissi (...), fine paragrafo
        # Negative lookbehind per abbreviazioni comuni
        sentence_pattern = re.compile(
            r"(?<!\b(?:Dr|Prof|Ing|dott|Dott|avv|Avv|p\.es|es|art|artt|n°|nn°|vol|pp|sez|gen|fig|tab|eq)\.)"
            r"(?<!\.)([.!?])+(?=\s+[A-Z]|\Z)",
            re.IGNORECASE
        )

        sentences = []
        current = []
        i = 0

        while i < len(text):
            char = text[i]

            if char in ".!?" and i + 1 < len(text):
                # Controlla se è una fine di frase (seguito da maiuscula o fine testo)
                j = i + 1
                while j < len(text) and text[j] == char:
                    j += 1  # Salta punteggiatura multipla

                # Controlla abbrev italiane comuni
                is_abbrev = False
                if i > 0:
                    # Guarda indietro per abbreviazioni
                    word_start = i - 1
                    while word_start >= 0 and text[word_start].isalpha():
                        word_start -= 1
                    word = text[word_start + 1 : i]
                    abbrevs = {
                        "dr", "prof", "ing", "dott", "avv", "p es", "es",
                        "art", "artt", "n", "nn", "vol", "pp", "sez", "gen",
                        "fig", "tab", "eq", "sig", "vs", "etc"
                    }
                    is_abbrev = word.lower() in abbrevs

                # Controlla se c'è whitespace dopo punteggiatura
                has_space = j < len(text) and text[j].isspace()

                # È una fine frase se: ha spazio dopo E (non abbrev OR seguito da maiuscula)
                if has_space and not is_abbrev:
                    k = j
                    while k < len(text) and text[k].isspace():
                        k += 1
                    # Se seguito da fine testo o maiuscula, è fine frase
                    if k >= len(text) or text[k].isupper():
                        current.append(text[i:j])
                        i = j
                        # Aggiungi frase se non vuota
                        frase = "".join(current).strip()
                        if frase:
                            sentences.append(frase)
                        current = []
                        continue

            current.append(char)
            i += 1

        # Aggiungi ultima frase se rimasta
        if current:
            frase = "".join(current).strip()
            if frase:
                sentences.append(frase)

        return sentences if sentences else [text.strip()]

    # ─── Utility methods ─────────────────────────────────────────────────────
    def get_config_summary(self) -> dict[str, Any]:
        """Restituisce summary della configurazione corrente."""
        return self.config.to_dict()

    def enable_strategy(self, strategy_name: str) -> None:
        """
        Cambia la strategia di chunking.

        Args:
            strategy_name: Nome della strategia
        """
        if strategy_name in ["paragraph", "sliding_window", "hybrid"]:
            self.config.strategy = strategy_name
            self.logger.info("Strategia cambiata a '%s'", strategy_name)
        else:
            self.logger.warning("Strategia '%s' non supportata", strategy_name)

    def set_overlap(self, ratio: float) -> None:
        """
        Imposta il ratio di overlapping.

        Args:
            ratio: Ratio tra 0.0 e 0.5
        """
        if 0.0 <= ratio <= 0.5:
            self.config.overlap_ratio = ratio
            self.logger.info("Overlap ratio impostato a %.2f", ratio)
        else:
            self.logger.warning("Overlap ratio deve essere tra 0.0 e 0.5")


# ─── Factory function ────────────────────────────────────────────────────────
def create_chunker(
    config_path: Path | str | None = None,
    **kwargs: Any,
) -> Chunker:
    """
    Factory function per creare un Chunker.

    Args:
        config_path: Path opzionale per file YAML di configurazione
        **kwargs: Parametri override per ChunkerConfig

    Returns:
        Chunker configurato

    Example:
        >>> chunker = create_chunker("config.yaml", overlap_ratio=0.1)
    """
    if config_path is not None:
        config = ChunkerConfig.from_yaml(config_path)
    else:
        config = ChunkerConfig()

    # Apply overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return Chunker(config)
