"""
Refiner principale per Step 05 della pipeline di riassunzione.

Questo modulo implementa la classe BaseRefiner (interfaccia astratta) e le relative
implementazioni (MockRefiner, QwenRefiner) per la riscrittura stilistica del testo
riassunto. Supporta profili di stile multipli (neutral, academic, casual) e metriche
di leggibilità.

Author: Appunti Vision Team
License: MIT
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import yaml


# ─── Dataclass per risultati e metriche ───────────────────────────────────────
@dataclass
class RefinementMetrics:
    """
    Metriche dettagliate della riscrittura stilistica.

    Attributes:
        original_length: Numero caratteri del testo originale
        refined_length: Numero caratteri del testo raffinato
        length_delta_ratio: Rapporto (refined_length - original_length) / original_length
        readability_score: Score di leggibilità (0.0 - 1.0, higher = better)
        style_applied: Profilo di stile applicato (es. "neutral", "academic")
        processing_time: Tempo totale di elaborazione (secondi)
    """
    original_length: int
    refined_length: int
    length_delta_ratio: float
    readability_score: float
    style_applied: str
    processing_time: float


@dataclass
class RefinementResult:
    """
    Risultato completo della riscrittura stilistica.

    Attributes:
        refined_text: Testo risvitto in stile migliorato
        metrics: Metriche di elaborazione e miglioramento
        model_name: Nome del modello usato (es. "Qwen2.5-7B-Instruct")
        style_profile: Profilo di stile applicato
    """
    refined_text: str
    metrics: RefinementMetrics
    model_name: str
    style_profile: str


# ─── Classe Base Astratta ──────────────────────────────────────────────────────
class BaseRefiner(ABC):
    """
    Interfaccia astratta per i refiner di stile.

    Implementa l'interfaccia comune per tutte le implementazioni concrete di refiner.
    Ogni subclass deve implementare il metodo astratto `refine()`.
    """

    def __init__(self, model_name: str, logger: logging.Logger | None = None):
        """
        Inizializza il refiner.

        Args:
            model_name: Nome del modello (es. "Qwen2.5-7B-Instruct", "mock")
            logger: Logger opzionale (se None, crea uno locale)
        """
        self.model_name = model_name
        self.logger = logger or self._create_logger()

    @staticmethod
    def _create_logger() -> logging.Logger:
        """Crea un logger di default per il refiner."""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    @abstractmethod
    def refine(
        self,
        summary: str,
        style: Literal["neutral", "academic", "casual"] = "neutral",
        **kwargs
    ) -> RefinementResult:
        """
        Riscrive il testo riassunto in uno stile migliorato.

        Args:
            summary: Testo del riassunto da riscrivere
            style: Profilo di stile ("neutral", "academic", "casual")
            **kwargs: Parametri aggiuntivi per il modello (temperatura, max_length, ecc.)

        Returns:
            RefinementResult con testo raffinato e metriche
        """
        pass


# ─── MockRefiner per testing ──────────────────────────────────────────────────
class MockRefiner(BaseRefiner):
    """
    Refiner deterministico per test e debugging.

    Non usa modelli reali; applica trasformazioni semplici e prevedibili:
    - Normalizza whitespace
    - Corregge punteggiatura base
    - Simula miglioramento di leggibilità
    - Applica template di stile per modellare il comportamento
    """

    def __init__(self, logger: logging.Logger | None = None):
        """
        Inizializza il MockRefiner.

        Args:
            logger: Logger opzionale
        """
        super().__init__(model_name="mock", logger=logger)

    def refine(
        self,
        summary: str,
        style: Literal["neutral", "academic", "casual"] = "neutral",
        **kwargs
    ) -> RefinementResult:
        """
        Applica trasformazioni stilistiche deterministiche al testo.

        Args:
            summary: Testo da raffinare
            style: Profilo di stile
            **kwargs: Ignorati

        Returns:
            RefinementResult con testo trasformato e metriche
        """
        start_time = time.time()
        original_length = len(summary)

        # Fase 1: Normalizzazione whitespace
        refined = re.sub(r'\s+', ' ', summary).strip()

        # Fase 2: Correzione punteggiatura base
        refined = re.sub(r'([.!?])\s*([.!?])+', r'\1', refined)  # Punteggiatura doppia
        refined = re.sub(r'(\w)\s+([,;:])', r'\1\2', refined)  # Spazi prima punteggiatura

        # Fase 3: Applicazione profilo di stile
        refined = self._apply_style_profile(refined, style)

        refined_length = len(refined)
        processing_time = time.time() - start_time

        # Calcolo metriche
        readability_score = self._compute_readability(refined)
        length_delta_ratio = (refined_length - original_length) / original_length if original_length > 0 else 0.0

        metrics = RefinementMetrics(
            original_length=original_length,
            refined_length=refined_length,
            length_delta_ratio=length_delta_ratio,
            readability_score=readability_score,
            style_applied=style,
            processing_time=processing_time,
        )

        self.logger.info(
            f"MockRefiner: {original_length} → {refined_length} chars, "
            f"readability={readability_score:.3f}, style={style}"
        )

        return RefinementResult(
            refined_text=refined,
            metrics=metrics,
            model_name=self.model_name,
            style_profile=style,
        )

    @staticmethod
    def _apply_style_profile(text: str, style: str) -> str:
        """
        Applica template di stile al testo.

        Args:
            text: Testo da trasformare
            style: Profilo di stile

        Returns:
            Testo trasformato secondo lo stile
        """
        if style == "academic":
            # Accorcia frasi molto lunghe (> 80 chars)
            sentences = re.split(r'(?<=[.!?])\s+', text)
            processed_sentences = []
            for sent in sentences:
                if len(sent) > 80:
                    # Spezza in frasi più corte
                    parts = re.split(r'([,;])', sent)
                    short_sentences = []
                    buffer = ""
                    for part in parts:
                        buffer += part
                        if len(buffer) > 40 and part in [',', ';']:
                            short_sentences.append(buffer.strip())
                            buffer = ""
                    if buffer.strip():
                        short_sentences.append(buffer.strip())
                    processed_sentences.extend([s for s in short_sentences if s])
                else:
                    processed_sentences.append(sent)
            text = ". ".join(processed_sentences)
            text = re.sub(r'\.+', '.', text)  # Rimuovi punti multipli

        elif style == "casual":
            # Aggiunge connessioni più naturali (semplificato)
            text = re.sub(r'([.!?])\s+', r'\1 ', text)
            # Normalizza abbreviazioni common
            text = re.sub(r'\b(e\.g|i\.e|etc)\b', lambda m: m.group(1), text)

        # Stile neutral: no trasformazioni ulteriori (default)
        return text

    @staticmethod
    def _compute_readability(text: str) -> float:
        """
        Calcola score di leggibilità (0.0 - 1.0).

        Metrica semplificata basata su:
        - Lunghezza media frase
        - Percentuale parole brevi (< 6 char)
        - Assenza di parole molto lunghe (> 20 char)

        Args:
            text: Testo da valutare

        Returns:
            Score di leggibilità (0.0 = difficile, 1.0 = molto facile)
        """
        if not text or len(text) < 10:
            return 0.5

        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.5

        # Lunghezza media parola e frase
        words = text.split()
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        avg_sentence_length = len(words) / len(sentences) if sentences else 0

        # Score base (target: 5-6 char per parola, 12-15 parole per frase)
        word_length_score = 1.0 - abs(avg_word_length - 5.5) / 10
        sentence_length_score = 1.0 - abs(avg_sentence_length - 14) / 20

        # Penalità per parole molto lunghe (> 20 char)
        very_long_words = sum(1 for w in words if len(w) > 20)
        very_long_penalty = min(0.3, very_long_words * 0.05)

        # Score finale (pesato)
        readability = (
            0.4 * max(0, word_length_score) +
            0.4 * max(0, sentence_length_score) +
            0.2 * (1.0 - very_long_penalty)
        )

        return max(0.0, min(1.0, readability))


# ─── QwenRefiner per inferenza reale ───────────────────────────────────────────
class QwenRefiner(BaseRefiner):
    """
    Refiner basato su Qwen2.5-7B-Instruct per riscrittura stilistica.

    Usa il modello tramite la libreria `transformers` per generare riscritture
    fluide e naturali. L'import è opzionale; se transformers non è disponibile,
    fallback automatico a MockRefiner.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-7B-Instruct",
        temperature: float = 0.7,
        max_new_tokens: int = 512,
        logger: logging.Logger | None = None,
    ):
        """
        Inizializza QwenRefiner.

        Args:
            model_name: Identificativo del modello Hugging Face
            temperature: Temperatura di sampling (0.0 - 1.0)
            max_new_tokens: Lunghezza massima output
            logger: Logger opzionale

        Raises:
            ImportError: Se transformers non è disponibile
        """
        super().__init__(model_name=model_name, logger=logger)
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens

        # Tenta importazione di transformers; se fallisce, logga warning
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.transformers_available = True
            self.AutoTokenizer = AutoTokenizer
            self.AutoModelForCausalLM = AutoModelForCausalLM
            self.model = None
            self.tokenizer = None
            self.logger.debug(f"Transformers library available; lazy-loading {model_name}")
        except ImportError:
            self.transformers_available = False
            self.logger.warning(
                "transformers library not available. "
                "QwenRefiner will fall back to MockRefiner behavior."
            )

    def _ensure_model_loaded(self):
        """Carica il modello lazily (al primo uso)."""
        if not self.transformers_available:
            return False

        if self.model is None:
            try:
                self.logger.info(f"Loading {self.model_name}...")
                self.tokenizer = self.AutoTokenizer.from_pretrained(self.model_name)
                self.model = self.AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype="auto",
                    device_map="auto",
                )
                self.logger.info(f"Model {self.model_name} loaded successfully")
                return True
            except Exception as e:
                self.logger.error(f"Failed to load model: {e}")
                return False
        return True

    def refine(
        self,
        summary: str,
        style: Literal["neutral", "academic", "casual"] = "neutral",
        temperature: float | None = None,
        max_new_tokens: int | None = None,
    ) -> RefinementResult:
        """
        Riscrive il testo usando il modello Qwen.

        Args:
            summary: Testo da raffinare
            style: Profilo di stile
            temperature: Temperatura di sampling (override default)
            max_new_tokens: Max lunghezza output (override default)

        Returns:
            RefinementResult con testo raffinato

        Raises:
            RuntimeError: Se il modello non può essere caricato
        """
        start_time = time.time()
        original_length = len(summary)

        # Usa parametri passati o default
        temp = temperature if temperature is not None else self.temperature
        max_tokens = max_new_tokens if max_new_tokens is not None else self.max_new_tokens

        # Se transformers non disponibile, fallback a MockRefiner
        if not self.transformers_available or not self._ensure_model_loaded():
            self.logger.warning("Falling back to MockRefiner")
            mock_refiner = MockRefiner(logger=self.logger)
            return mock_refiner.refine(summary, style=style)

        # Prompt stilistico
        style_instructions = {
            "neutral": "Riscrivi il testo in modo più fluido e naturale. Requisiti: mantieni tutte le informazioni, non aggiungere contenuti, migliora leggibilità.",
            "academic": "Riscrivi il testo in stile accademico formale. Requisiti: mantieni tutte le informazioni, usa terminologia precisa, struttura logica chiara, non aggiungere contenuti.",
            "casual": "Riscrivi il testo in stile conversazionale e amichevole. Requisiti: mantieni tutte le informazioni, tonalità naturale, non aggiungere contenuti, migliora leggibilità.",
        }
        instruction = style_instructions.get(style, style_instructions["neutral"])

        prompt = f"{instruction}\n\nTesto: {summary}\n\nTesto riscritto:"

        try:
            # Tokenizzazione e generazione
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            outputs = self.model.generate(
                **inputs,
                temperature=temp,
                max_new_tokens=max_tokens,
                do_sample=True,
                top_p=0.9,
            )

            # Decode output
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Estrai la parte dopo il prompt (rimuovi prompt dal risultato)
            refined = generated_text[len(prompt):].strip() if generated_text.startswith(prompt) else generated_text

            refined_length = len(refined)
            processing_time = time.time() - start_time

            # Metriche
            readability_score = self._compute_readability_with_model(refined)
            length_delta_ratio = (refined_length - original_length) / original_length if original_length > 0 else 0.0

            metrics = RefinementMetrics(
                original_length=original_length,
                refined_length=refined_length,
                length_delta_ratio=length_delta_ratio,
                readability_score=readability_score,
                style_applied=style,
                processing_time=processing_time,
            )

            self.logger.info(
                f"QwenRefiner: {original_length} → {refined_length} chars, "
                f"readability={readability_score:.3f}, style={style}, time={processing_time:.2f}s"
            )

            return RefinementResult(
                refined_text=refined,
                metrics=metrics,
                model_name=self.model_name,
                style_profile=style,
            )

        except Exception as e:
            self.logger.error(f"Error during generation: {e}")
            raise RuntimeError(f"QwenRefiner generation failed: {e}") from e

    @staticmethod
    def _compute_readability_with_model(text: str) -> float:
        """
        Calcola leggibilità con un modello (per QwenRefiner).

        Args:
            text: Testo da valutare

        Returns:
            Score di leggibilità
        """
        # Usa la stessa logica di MockRefiner (semplificata)
        if not text or len(text) < 10:
            return 0.5

        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.5

        words = text.split()
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        avg_sentence_length = len(words) / len(sentences) if sentences else 0

        word_length_score = 1.0 - abs(avg_word_length - 5.5) / 10
        sentence_length_score = 1.0 - abs(avg_sentence_length - 14) / 20
        very_long_words = sum(1 for w in words if len(w) > 20)
        very_long_penalty = min(0.3, very_long_words * 0.05)

        readability = (
            0.4 * max(0, word_length_score) +
            0.4 * max(0, sentence_length_score) +
            0.2 * (1.0 - very_long_penalty)
        )

        return max(0.0, min(1.0, readability))
