"""
Checker principale per Step 04 - Faithfulness Checking della pipeline di riassunzione.

Questo modulo implementa:
- BaseChecker: interfaccia astratta
- NLIChecker: implementazione con transformers (mDeBERTa)
- Logica NLI per valutare fedeltà fattuale

Author: Appunti Vision Team
License: MIT
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from .utils import (
    FaithfulnessMetrics,
    FaithfulnessResult,
    Timer,
    filter_short_sentences,
    setup_logging,
    split_sentences,
    validate_texts,
)


# ─── Configurazione ────────────────────────────────────────────────────────────
@dataclass
class CheckerConfig:
    """
    Configurazione per il Checker.

    Attributes:
        model_name: Nome del modello HuggingFace per NLI (default: mDeBERTa)
        threshold_entailment: Score minimo per considerare entailment (0.0-1.0)
        threshold_neutral: Score minimo per considerare neutral (0.0-1.0)
        threshold_contradiction: Score minimo per considerare contradiction (0.0-1.0)
        aggregation_strategy: Come aggregare i verdetti ("voting", "threshold")
        min_entailment_ratio: Percentuale minima di frasi entailed per consider faithful
        min_sentence_length: Lunghezza minima di una frase (caratteri)
        sentence_detection: Metodo di sentence splitting ("regex")
        language: Lingua del testo ("it", "en")
        batch_size: Batch size per processing (trasformers)
        device: Device per model ("cpu", "cuda", "auto")
        log_level: Livello di logging
        log_file: Path opzionale per file di log
    """

    model_name: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    threshold_entailment: float = 0.5
    threshold_neutral: float = 0.3
    threshold_contradiction: float = 0.3
    aggregation_strategy: Literal["voting", "threshold"] = "voting"
    min_entailment_ratio: float = 0.7  # 70% delle frasi devono essere entailed
    min_sentence_length: int = 5
    sentence_detection: Literal["regex"] = "regex"
    language: Literal["it", "en"] = "it"
    batch_size: int = 8
    device: Literal["cpu", "cuda", "auto"] = "cuda"
    log_level: int = logging.INFO
    log_file: Path | str | None = None

    def __post_init__(self) -> None:
        """Validazione post-inizializzazione."""
        if not (0.0 <= self.threshold_entailment <= 1.0):
            raise ValueError("threshold_entailment deve essere tra 0.0 e 1.0")
        if not (0.0 <= self.threshold_neutral <= 1.0):
            raise ValueError("threshold_neutral deve essere tra 0.0 e 1.0")
        if not (0.0 <= self.min_entailment_ratio <= 1.0):
            raise ValueError("min_entailment_ratio deve essere tra 0.0 e 1.0")

    @classmethod
    def from_yaml(cls, config_path: Path | str) -> CheckerConfig:
        """
        Crea configurazione da file YAML.

        Args:
            config_path: Path del file YAML

        Returns:
            CheckerConfig popolata

        Raises:
            FileNotFoundError: Se il file non esiste
            yaml.YAMLError: Se il YAML è malformato
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}

        return cls.from_dict(config_dict.get("faithfulness", {}))

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> CheckerConfig:
        """
        Crea configurazione da dizionario.

        Args:
            config_dict: Dizionario con configurazione

        Returns:
            CheckerConfig
        """
        # Filtrare solo gli attributi validi
        valid_attrs = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in config_dict.items() if k in valid_attrs}
        return cls(**filtered)


# ─── Base Class ─────────────────────────────────────────────────────────────────
class BaseChecker(ABC):
    """
    Classe base astratta per Faithfulness Checker.

    Tutti i checker devono implementare il metodo check().
    """

    @abstractmethod
    def check(self, source: str, summary: str) -> FaithfulnessResult:
        """
        Verificare la fedeltà fattuale del riassunto rispetto al testo originale.

        Args:
            source: Testo originale
            summary: Riassunto da verificare

        Returns:
            FaithfulnessResult con verdetto e dettagli
        """
        pass


# ─── NLI Checker ────────────────────────────────────────────────────────────────
class NLIChecker(BaseChecker):
    """
    Implementazione del Faithfulness Checker usando NLI (Natural Language Inference).

    Utilizza un modello mDeBERTa fine-tuned su MNLI/XNLI per valutare se le frasi
    del riassunto sono entailed dal testo originale.

    Logica:
    - Testo originale = premessa (premise)
    - Ogni frase del riassunto = ipotesi (hypothesis)
    - Classificazione: entailment (0), neutral (1), contradiction (2)
    - Verdetto aggregato basato su percentuale di frasi entailed
    """

    def __init__(self, config: CheckerConfig) -> None:
        """
        Inizializzare il checker.

        Args:
            config: CheckerConfig

        Raises:
            ImportError: Se transformers non è disponibile
        """
        self.config = config
        self.logger = setup_logging(
            "NLIChecker",
            level=config.log_level,
            log_file=config.log_file,
        )

        self.logger.info(f"Initializing NLIChecker with model: {config.model_name}")

        # Import transformers (opzionale)
        try:
            from transformers import pipeline

            # Risolvi "auto" in un device concreto.
            # transformers.pipeline() accetta int (-1=CPU, 0=prima GPU) oppure
            # stringhe tipo "cpu" / "cuda:0", ma NON "auto".
            device_arg: int | str = config.device
            if config.device == "auto":
                try:
                    import torch
                    device_arg = 0 if torch.cuda.is_available() else -1
                except ImportError:
                    device_arg = -1  # senza torch usa CPU
            elif config.device == "cuda":
                device_arg = 0
            elif config.device == "cpu":
                device_arg = -1

            self.pipeline = pipeline(
                "zero-shot-classification",
                model=config.model_name,
                device=device_arg,
            )
            self.logger.info(f"Model {config.model_name} loaded on device={device_arg}")
        except ImportError as e:
            self.logger.warning(
                f"transformers not available: {e}. NLIChecker will not work."
            )
            self.pipeline = None

    def check(self, source: str, summary: str) -> FaithfulnessResult:
        """
        Verificare la fedeltà fattuale.

        Args:
            source: Testo originale
            summary: Riassunto da verificare

        Returns:
            FaithfulnessResult con verdetto, confidence, issues, metrics
        """
        # Validare input
        is_valid, error_msg = validate_texts(source, summary)
        if not is_valid:
            return FaithfulnessResult(
                is_faithful=False,
                confidence=0.0,
                issues=[error_msg],
                metrics=FaithfulnessMetrics(),
            )

        # Timing
        with Timer() as timer:
            # Split in frasi
            summary_sentences = split_sentences(summary, language=self.config.language)
            summary_sentences = filter_short_sentences(
                summary_sentences, min_length=self.config.min_sentence_length
            )

            if not summary_sentences:
                return FaithfulnessResult(
                    is_faithful=False,
                    confidence=0.0,
                    issues=["No sentences found in summary after filtering"],
                    metrics=FaithfulnessMetrics(),
                )

            # Fare l'inferenza NLI
            if self.pipeline is None:
                return FaithfulnessResult(
                    is_faithful=False,
                    confidence=0.0,
                    issues=["NLI pipeline not initialized (transformers not available)"],
                    metrics=FaithfulnessMetrics(),
                )

            results = self._run_nli_inference(source, summary_sentences)

        # Aggregare risultati
        metrics = self._aggregate_results(results, summary_sentences, timer.elapsed_time)
        is_faithful = self._make_verdict(metrics)
        confidence = self._compute_confidence(metrics)
        issues = self._extract_issues(results, summary_sentences)

        return FaithfulnessResult(
            is_faithful=is_faithful,
            confidence=confidence,
            issues=issues,
            metrics=metrics,
            summary_sentences=summary_sentences,
            verdict_details={
                "aggregation_strategy": self.config.aggregation_strategy,
                "min_entailment_ratio": self.config.min_entailment_ratio,
                "threshold_entailment": self.config.threshold_entailment,
            },
        )

    def _run_nli_inference(self, source: str, summary_sentences: list[str]) -> list[dict[str, Any]]:
        """
        Eseguire inferenza NLI per ogni frase del riassunto.

        Args:
            source: Testo originale (premessa)
            summary_sentences: Liste di frasi (ipotesi)

        Returns:
            Lista di risultati NLI
        """
        results = []

        for sentence in summary_sentences:
            # zero-shot-classification ritorna {"labels": [label1, label2, ...], "scores": [score1, score2, ...]}
            # Labels: entailment, neutral, contradiction
            output = self.pipeline(
                sentence,
                [source],
                multi_label=True,  # multi_class è stato rinominato in multi_label nelle versioni recenti di transformers
            )

            # Estract label principale e score
            label = output["labels"][0] if output["labels"] else "neutral"
            score = output["scores"][0] if output["scores"] else 0.0

            results.append({
                "sentence": sentence,
                "label": label,
                "score": score,
                "all_scores": dict(zip(output.get("labels", []), output.get("scores", []))),
            })

        return results

    def _aggregate_results(
        self,
        results: list[dict[str, Any]],
        summary_sentences: list[str],
        elapsed_time: float,
    ) -> FaithfulnessMetrics:
        """
        Aggregare risultati dell'inferenza in metriche.

        Args:
            results: Lista di risultati NLI
            summary_sentences: Liste di frasi analizzate
            elapsed_time: Tempo di processing

        Returns:
            FaithfulnessMetrics
        """
        num_sentences = len(summary_sentences)
        num_entailed = 0
        num_neutral = 0
        num_contradicted = 0

        for result in results:
            label = result.get("label", "neutral").lower()
            if label == "entailment":
                num_entailed += 1
            elif label == "neutral":
                num_neutral += 1
            elif label == "contradiction":
                num_contradicted += 1

        entailment_ratio = num_entailed / num_sentences if num_sentences > 0 else 0.0
        neutral_ratio = num_neutral / num_sentences if num_sentences > 0 else 0.0
        contradiction_ratio = num_contradicted / num_sentences if num_sentences > 0 else 0.0

        return FaithfulnessMetrics(
            num_sentences_checked=num_sentences,
            num_sentences_entailed=num_entailed,
            num_sentences_neutral=num_neutral,
            num_sentences_contradicted=num_contradicted,
            entailment_ratio=entailment_ratio,
            neutral_ratio=neutral_ratio,
            contradiction_ratio=contradiction_ratio,
            processing_time_seconds=elapsed_time,
            model_used=self.config.model_name,
            threshold_entailment=self.config.threshold_entailment,
            threshold_neutral=self.config.threshold_neutral,
        )

    def _make_verdict(self, metrics: FaithfulnessMetrics) -> bool:
        """
        Decidere se il riassunto è fedele.

        Verdetto basato su:
        - Percentuale di frasi entailed >= min_entailment_ratio
        - Nessuna contradictio

        Args:
            metrics: FaithfulnessMetrics

        Returns:
            True se fedele, False altrimenti
        """
        if self.config.aggregation_strategy == "voting":
            # Almeno min_entailment_ratio delle frasi devono essere entailed
            # e nessuna contradda
            is_faithful = (
                metrics.entailment_ratio >= self.config.min_entailment_ratio
                and metrics.contradiction_ratio == 0.0
            )
        else:
            # threshold-based: similar logic
            is_faithful = (
                metrics.entailment_ratio >= self.config.min_entailment_ratio
                and metrics.contradiction_ratio == 0.0
            )

        return is_faithful

    def _compute_confidence(self, metrics: FaithfulnessMetrics) -> float:
        """
        Calcolare score di confidenza.

        Args:
            metrics: FaithfulnessMetrics

        Returns:
            Confidence score (0.0-1.0)
        """
        # Confidence = entailment_ratio, penalizzato se ci sono contradictions
        confidence = metrics.entailment_ratio
        if metrics.contradiction_ratio > 0.0:
            confidence *= (1.0 - metrics.contradiction_ratio)
        return max(0.0, min(1.0, confidence))

    def _extract_issues(
        self,
        results: list[dict[str, Any]],
        summary_sentences: list[str],
    ) -> list[str]:
        """
        Estrarre issues dal risultato dell'inferenza.

        Args:
            results: Lista di risultati NLI
            summary_sentences: Liste di frasi analizzate

        Returns:
            Lista di issue descriptions
        """
        issues = []

        for result in results:
            label = result.get("label", "neutral").lower()
            sentence = result.get("sentence", "")

            if label == "contradiction":
                issues.append(f"Contradictory statement: {sentence}")
            elif label == "neutral":
                issues.append(f"Not supported by source text: {sentence}")

        return issues
