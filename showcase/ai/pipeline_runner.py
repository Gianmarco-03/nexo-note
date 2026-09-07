"""
End-to-End Pipeline Runner per la riassunzione Appunti Vision.

Questo modulo orchestra tutti e 5 gli step della pipeline di riassunzione
in sequenza, con supporto per mock (senza dipendenze di modelli reali):

1. Step 01 - Input & Preprocessing: Pulizia testo grezzo
2. Step 02 - Chunking: Divisione in chunk con overlap
3. Step 03 - Content Selection: Map-Reduce per riassunto (mock)
4. Step 04 - Faithfulness Checking: Validazione coerenza (mock)
5. Step 05 - Style Refinement: Riscrittura stilistica (mock/Qwen)

Utilizzo:
    from pipeline_runner import run_full_pipeline
    result = run_full_pipeline(
        raw_text="Testo da riassumere...",
        target_summary_ratio=0.3,
        style="neutral"
    )
    print(result["refined_text"])

Author: Appunti Vision Team
License: MIT
"""

from __future__ import annotations

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


def _try_install_packages(*packages: str) -> bool:
    """
    Tenta di installare pacchetti Python via pip.
    Torch viene installato con il wheel CPU-only da pytorch.org.
    Ritorna True se l'installazione ha avuto successo.
    """
    import subprocess
    pkg_list = list(packages)

    # Separa torch dagli altri (richiede URL speciale)
    torch_pkgs = [p for p in pkg_list if p.lower() in ("torch", "torchvision", "torchaudio")]
    other_pkgs = [p for p in pkg_list if p.lower() not in ("torch", "torchvision", "torchaudio")]

    success = True

    # Installa torch CPU-only
    if torch_pkgs:
        # Controlla se torch è già disponibile
        try:
            import torch
            print(f"[auto-install] torch già disponibile ({torch.__version__}).")
        except ImportError:
            print(f"[auto-install] Installazione torch (CPU-only): {', '.join(torch_pkgs)}")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages",
                     "--index-url", "https://download.pytorch.org/whl/cpu"] + torch_pkgs,
                    capture_output=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    print(f"[auto-install] torch installato con successo.")
                else:
                    # Fallback pip standard
                    result2 = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + torch_pkgs,
                        capture_output=True,
                        timeout=300,
                    )
                    if result2.returncode != 0:
                        print(f"[auto-install] torch installation failed.")
                        success = False
            except Exception as e:
                print(f"[auto-install] Errore installazione torch: {e}")
                success = False

    # Installa altri pacchetti normalmente
    if other_pkgs:
        print(f"[auto-install] Installazione: {', '.join(other_pkgs)}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + other_pkgs,
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0:
                print(f"[auto-install] Pacchetti installati: {', '.join(other_pkgs)}")
            else:
                stderr = result.stderr.decode(errors="replace")
                print(f"[auto-install] Installazione fallita:\n{stderr[:500]}")
                success = False
        except Exception as e:
            print(f"[auto-install] Errore: {e}")
            success = False

    return success


# Aggiungi path per importare i moduli degli step
RIASSUNZIONE_DIR = Path(__file__).parent
sys.path.insert(0, str(RIASSUNZIONE_DIR / "pipeline.Input & Preprocessing" / "src"))
sys.path.insert(0, str(RIASSUNZIONE_DIR / "pipeline.Step 02 - Chunking" / "src"))
sys.path.insert(0, str(RIASSUNZIONE_DIR / "pipeline.Step 03 - Content Selection" / "src"))
sys.path.insert(0, str(RIASSUNZIONE_DIR / "pipeline.Step 04 - Faithfulness Checking" / "src"))
sys.path.insert(0, str(RIASSUNZIONE_DIR / "pipeline.Step 05 - Style Refinement" / "src"))

# Importa dai moduli degli step
try:
    from appunti_preprocessing import Preprocessor, PreprocessorConfig
except ImportError:
    print("Warning: appunti_preprocessing module not available")
    Preprocessor = None
    PreprocessorConfig = None

try:
    from appunti_chunking import Chunker, ChunkerConfig
except ImportError:
    print("Warning: appunti_chunking module not available")
    Chunker = None
    ChunkerConfig = None

try:
    from appunti_style import MockRefiner, QwenRefiner, StyleConfig
except ImportError:
    print("Warning: appunti_style module not available, trying auto-install...")
    if _try_install_packages("torch", "transformers", "accelerate"):
        try:
            from appunti_style import MockRefiner, QwenRefiner, StyleConfig
        except ImportError:
            MockRefiner = None
            QwenRefiner = None
            StyleConfig = None
    else:
        MockRefiner = None
        QwenRefiner = None
        StyleConfig = None

try:
    from appunti_content_selection import create_selector  # o path corretto
except ImportError:
    print("Warning: appunti_content_selection module not available, trying auto-install...")
    if _try_install_packages("torch", "transformers", "accelerate"):
        try:
            from appunti_content_selection import create_selector
        except ImportError:
            create_selector = None
    else:
        create_selector = None

try:
    from appunti_faithfulness import NLIChecker, MockChecker, CheckerConfig
except ImportError:
    print("Warning: appunti_faithfulness module not available, trying auto-install...")
    if _try_install_packages("torch", "transformers", "accelerate"):
        try:
            from appunti_faithfulness import NLIChecker, MockChecker, CheckerConfig
        except ImportError:
            NLIChecker = None
            MockChecker = None
            CheckerConfig = None
    else:
        NLIChecker = None
        MockChecker = None
        CheckerConfig = None

# ─────────────────────────────────────────────────────────────────────────────
# Dataclass per risultati intermedi e finali
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Step01Result:
    """Risultato dello Step 01 - Preprocessing."""
    cleaned_text: str
    original_length: int
    cleaned_length: int
    processing_time: float


@dataclass
class Step02Result:
    """Risultato dello Step 02 - Chunking."""
    chunks: list[str]
    num_chunks: int
    avg_chunk_size: float
    processing_time: float


@dataclass
class Step03Result:
    """Risultato dello Step 03 - Content Selection (mock)."""
    summary: str
    summary_length: int
    compression_ratio: float
    processing_time: float


@dataclass
class Step04Result:
    """Risultato dello Step 04 - Faithfulness Checking (mock)."""
    summary: str
    is_faithful: bool
    faithfulness_score: float
    processing_time: float


@dataclass
class Step05Result:
    """Risultato dello Step 05 - Style Refinement."""
    refined_text: str
    style_applied: str
    readability_score: float
    processing_time: float


@dataclass
class PipelineResult:
    """Risultato finale della pipeline completa."""
    step_01: Step01Result
    step_02: Step02Result
    step_03: Step03Result
    step_04: Step04Result
    step_05: Step05Result
    total_processing_time: float
    final_text: str


# ─────────────────────────────────────────────────────────────────────────────
# Funzioni per gli step della pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_step_01_preprocessing(raw_text: str, logger: logging.Logger | None = None) -> Step01Result:
    """
    Esegue Step 01 - Input & Preprocessing.

    Args:
        raw_text: Testo grezzo in input
        logger: Logger opzionale

    Returns:
        Step01Result con testo pulito e metriche

    Raises:
        ImportError: Se appunti_preprocessing non è disponibile
    """
    if logger is None:
        logger = _setup_logger()

    if Preprocessor is None:
        raise ImportError("appunti_preprocessing module not available")

    start_time = time.time()
    logger.info("Step 01 - Preprocessing: starting...")

    try:
        config = PreprocessorConfig()
        preprocessor = Preprocessor(config)
        cleaned_text = preprocessor.process(raw_text)
        processing_time = time.time() - start_time

        result = Step01Result(
            cleaned_text=cleaned_text,
            original_length=len(raw_text),
            cleaned_length=len(cleaned_text),
            processing_time=processing_time,
        )

        logger.info(
            f"Step 01 complete: {result.original_length} → {result.cleaned_length} chars "
            f"({processing_time:.2f}s)"
        )
        return result

    except Exception as e:
        logger.warning(f"Step 01 preprocessing failed, using mock: {e}")
        # Fallback: mock preprocessing (semplice normalizzazione whitespace)
        import re
        cleaned_text = re.sub(r'\s+', ' ', raw_text).strip()
        processing_time = time.time() - start_time

        result = Step01Result(
            cleaned_text=cleaned_text,
            original_length=len(raw_text),
            cleaned_length=len(cleaned_text),
            processing_time=processing_time,
        )

        logger.info(
            f"Step 01 (MOCK) complete: {result.original_length} → {result.cleaned_length} chars "
            f"({processing_time:.2f}s)"
        )
        return result


def run_step_02_chunking(text: str, logger: logging.Logger | None = None) -> Step02Result:
    """
    Esegue Step 02 - Chunking.

    Args:
        text: Testo pulito dallo step 01
        logger: Logger opzionale

    Returns:
        Step02Result con chunk e metriche

    Raises:
        ImportError: Se appunti_chunking non è disponibile
    """
    if logger is None:
        logger = _setup_logger()

    if Chunker is None:
        raise ImportError("appunti_chunking module not available")

    start_time = time.time()
    logger.info("Step 02 - Chunking: starting...")

    try:
        config = ChunkerConfig()
        chunker = Chunker(config)
        chunks = chunker.chunk(text)
        # Estrai testi come list[str] dai Chunk objects
        if chunks and hasattr(chunks[0], 'text'):
            chunks = [c.text for c in chunks]
        processing_time = time.time() - start_time

        avg_chunk_size = sum(len(c) for c in chunks) / len(chunks) if chunks else 0

        result = Step02Result(
            chunks=chunks,
            num_chunks=len(chunks),
            avg_chunk_size=avg_chunk_size,
            processing_time=processing_time,
        )

        logger.info(f"Step 02 complete: {result.num_chunks} chunks, avg {result.avg_chunk_size:.0f} chars ({processing_time:.2f}s)")
        return result

    except Exception as e:
        logger.warning(f"Step 02 chunking failed, using mock: {e}")
        # Fallback: mock chunking (split su periodi/frasi)
        import re
        sentences = re.split(r'[.!?]+', text)
        chunks = [s.strip() for s in sentences if s.strip()]

        processing_time = time.time() - start_time
        avg_chunk_size = sum(len(c) for c in chunks) / len(chunks) if chunks else 0

        result = Step02Result(
            chunks=chunks,
            num_chunks=len(chunks),
            avg_chunk_size=avg_chunk_size,
            processing_time=processing_time,
        )

        logger.info(f"Step 02 (MOCK) complete: {result.num_chunks} chunks, avg {result.avg_chunk_size:.0f} chars ({processing_time:.2f}s)")
        return result


def run_step_03_content_selection(
      chunks: list[str],
      target_ratio: float = 0.3,
      logger: logging.Logger | None = None,
      use_real_model: bool = True,
  ):
      if logger is None:
          logger = _setup_logger()

      if not chunks:
          raise ValueError("Nessun chunk fornito")

      start_time = time.time()

      # ─── PROVA CON IL SELEZIONATORE REALE ─────────────────────────────
      if use_real_model and create_selector is not None:
          try:
              logger.info("Passaggio 3 - Selezionatore (REALE): inizio...")

              # Converti chunk → formato atteso dal selezionatore
              selector_chunks = [
                  {"id": i, "text": c}
                  for i, c in enumerate(chunks)
              ]

              selector = create_selector(
                  summarizer_type="huggingface",
                  fallback_to_mock=True,
              )

              mini_summaries, final_summary = selector.process(selector_chunks)

              processing_time = time.time() - start_time
              original_length = sum(len(c) for c in chunks)

              return Step03Result(
                  summary=final_summary,
                  summary_length=len(final_summary),
                  compression_ratio=len(final_summary) / original_length if original_length > 0 else 0.0,
                  processing_time=processing_time,
              )

          except Exception as e:
              logger.warning(f"Passaggio 3 selezionatore reale non funzionante, caduta indietro al mock: {e}")

      # ─── CADUTA INDIETRO AL MOCK (già presente) ───────────────────
      logger.info("Passaggio 3 - Selezionatore (MOCK): inizio...")

      num_to_select = max(1, int(len(chunks) * target_ratio))

      ranked_chunks = sorted(
          enumerate(chunks),
          key=lambda x: len(x[1]),
          reverse=True
      )

      selected_indices = set()

      for i in range(min(num_to_select, len(ranked_chunks))):
          selected_indices.add(ranked_chunks[i][0])

      selected_indices.add(0)
      selected_indices.add(len(chunks) - 1)

      selected_indices = sorted(selected_indices)
      selected_chunks = [chunks[i] for i in selected_indices]

      summary = " ".join(selected_chunks)

      original_length = sum(len(c) for c in chunks)
      processing_time = time.time() - start_time

      return Step03Result(
          summary=summary,
          summary_length=len(summary),
          compression_ratio=len(summary) / original_length if original_length > 0 else 0.0,
          processing_time=processing_time,
      )

def run_step_04_faithfulness_checking(
    summary: str,
    original_text: str,
    use_real_model: bool = True,
    logger: logging.Logger | None = None,
) -> Step04Result:
    """
    Esegue Step 04 - Faithfulness Checking.

    Tenta di usare NLIChecker (mDeBERTa) se disponibile,
    altrimenti tenta auto-install transformers,
    altrimenti cade su MockChecker,
    infine su euristica word-coverage come ultimo fallback.
    """
    if logger is None:
        logger = _setup_logger()

    if not summary or not original_text:
        raise ValueError("Summary and original_text must not be empty")

    start_time = time.time()

    # ─── TENTATIVO CON NLIChecker REALE ───────────────────────────────────────
    checker_used = "heuristic"

    if use_real_model:
        # Tenta importazione diretta
        nli_checker = None
        checker_class = NLIChecker
        checker_config_class = CheckerConfig

        # Se non disponibile, tenta auto-install
        if checker_class is None:
            logger.info("Step 04: NLIChecker non disponibile, tentativo auto-install transformers...")
            if _try_install_packages("transformers", "accelerate"):
                try:
                    # Forza re-import dopo installazione
                    import importlib
                    step04_path = str(
                        Path(__file__).parent /
                        "pipeline.Step 04 - Faithfulness Checking" / "src"
                    )
                    if step04_path not in sys.path:
                        sys.path.insert(0, step04_path)
                    faithfulness_mod = importlib.import_module("appunti_faithfulness")
                    checker_class = faithfulness_mod.NLIChecker
                    checker_config_class = faithfulness_mod.CheckerConfig
                    logger.info("Step 04: NLIChecker caricato dopo auto-install.")
                except Exception as e:
                    logger.warning(f"Step 04: Re-import dopo install fallito: {e}")

        if checker_class is not None:
            try:
                logger.info("Step 04 - Faithfulness Checking (NLI): starting...")
                config = checker_config_class()
                nli_checker = checker_class(config)
                result_obj = nli_checker.check(original_text, summary)
                processing_time = time.time() - start_time

                result = Step04Result(
                    summary=summary,
                    is_faithful=result_obj.is_faithful,
                    faithfulness_score=result_obj.confidence,
                    processing_time=processing_time,
                )
                logger.info(
                    f"Step 04 (NLI) complete: faithfulness={result.faithfulness_score:.2%}, "
                    f"valid={result.is_faithful} ({processing_time:.2f}s)"
                )
                return result
            except Exception as e:
                logger.warning(f"Step 04 NLIChecker fallito: {e}. Caduta su MockChecker.")

        # Prova con MockChecker dall'appunti_faithfulness
        if CheckerConfig is not None:
            try:
                logger.info("Step 04 - Faithfulness Checking (MockChecker): starting...")
                mock_checker_class = MockChecker
                if mock_checker_class is None:
                    raise ImportError("MockChecker non disponibile")
                mc = mock_checker_class()
                result_obj = mc.check(original_text, summary)
                processing_time = time.time() - start_time

                result = Step04Result(
                    summary=summary,
                    is_faithful=result_obj.is_faithful,
                    faithfulness_score=result_obj.confidence,
                    processing_time=processing_time,
                )
                logger.info(
                    f"Step 04 (MockChecker) complete: faithfulness={result.faithfulness_score:.2%}, "
                    f"valid={result.is_faithful} ({processing_time:.2f}s)"
                )
                return result
            except Exception as e:
                logger.warning(f"Step 04 MockChecker fallito: {e}. Caduta su euristica.")

    # ─── FALLBACK FINALE: euristica word-coverage ────────────────────────────
    logger.info("Step 04 - Faithfulness Checking (euristica): starting...")
    try:
        summary_words = set(summary.lower().split())
        original_words = set(original_text.lower().split())

        if summary_words:
            word_coverage = len(summary_words & original_words) / len(summary_words)
        else:
            word_coverage = 0.0

        length_ok = 0 < len(summary) <= len(original_text)
        faithfulness_score = word_coverage * 0.7 + (0.3 if length_ok else 0.0)
        is_faithful = faithfulness_score >= 0.5 and length_ok

        processing_time = time.time() - start_time
        result = Step04Result(
            summary=summary,
            is_faithful=is_faithful,
            faithfulness_score=faithfulness_score,
            processing_time=processing_time,
        )
        logger.info(
            f"Step 04 (euristica) complete: faithfulness={result.faithfulness_score:.2%}, "
            f"valid={result.is_faithful} ({processing_time:.2f}s)"
        )
        return result

    except Exception as e:
        logger.error(f"Step 04 failed: {e}", exc_info=True)
        raise


def run_step_05_style_refinement(
    summary: str,
    style: Literal["neutral", "academic", "casual"] = "neutral",
    refiner_type: str = "mock",
    logger: logging.Logger | None = None,
) -> Step05Result:
    """
    Esegue Step 05 - Style Refinement.

    Riscrive il riassunto in uno stile naturale e fluido.

    Args:
        summary: Riassunto da raffinare
        style: Profilo di stile
        refiner_type: Tipo di refiner ("mock" o "qwen")
        logger: Logger opzionale

    Returns:
        Step05Result con testo raffinato

    Raises:
        ImportError: Se moduli non disponibili
    """
    if logger is None:
        logger = _setup_logger()

    if MockRefiner is None:
        raise ImportError("appunti_style module not available")

    start_time = time.time()
    logger.info(f"Step 05 - Style Refinement ({refiner_type}): starting...")

    try:
        # Crea refiner appropriato
        if refiner_type.lower() == "qwen" and QwenRefiner is not None:
            refiner = QwenRefiner()
        else:
            refiner = MockRefiner()

        # Raffina
        result_obj = refiner.refine(summary, style=style)
        processing_time = time.time() - start_time

        result = Step05Result(
            refined_text=result_obj.refined_text,
            style_applied=result_obj.style_profile,
            readability_score=result_obj.metrics.readability_score,
            processing_time=processing_time,
        )

        logger.info(
            f"Step 05 complete: readability={result.readability_score:.2%}, "
            f"style={result.style_applied} ({processing_time:.2f}s)"
        )
        return result

    except Exception as e:
        logger.error(f"Step 05 failed: {e}", exc_info=True)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Funzione principale della pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_full_pipeline(
    raw_text: str,
    target_summary_ratio: float = 0.3,
    style: Literal["neutral", "academic", "casual"] = "neutral",
    refiner_type: str = "mock",
    log_level: int = logging.INFO,
    logger: logging.Logger | None = None,
) -> PipelineResult:
    """
    Esegue l'intera pipeline di riassunzione in 5 step.

    Args:
        raw_text: Testo grezzo da riassumere
        target_summary_ratio: Rapporto compressione (default 30%)
        style: Profilo di stile (neutral, academic, casual)
        refiner_type: Tipo refiner (mock, qwen)
        log_level: Livello di logging
        logger: Logger opzionale

    Returns:
        PipelineResult con risultati di tutti gli step

    Raises:
        ValueError: Se input invalido
        ImportError: Se moduli non disponibili
    """
    if logger is None:
        logger = _setup_logger(log_level=log_level)

    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text cannot be empty")

    if not 0.0 < target_summary_ratio <= 1.0:
        raise ValueError("target_summary_ratio must be between 0 and 1")

    pipeline_start_time = time.time()

    try:
        logger.info("=" * 80)
        logger.info("APPUNTI VISION - RIASSUNZIONE PIPELINE (5 STEP)")
        logger.info(f"Input: {len(raw_text)} chars, target ratio: {target_summary_ratio:.1%}")
        logger.info("=" * 80)

        # Step 01
        step_01_result = run_step_01_preprocessing(raw_text, logger)

        # Step 02
        step_02_result = run_step_02_chunking(step_01_result.cleaned_text, logger)

        # Step 03
        step_03_result = run_step_03_content_selection(
            step_02_result.chunks,
            target_ratio=target_summary_ratio,
            logger=logger,
        )

        # Step 04
        step_04_result = run_step_04_faithfulness_checking(
            step_03_result.summary,
            raw_text,
            use_real_model=True,
            logger=logger,
        )

        # Step 05
        step_05_result = run_step_05_style_refinement(
            step_04_result.summary,
            style=style,
            refiner_type=refiner_type,
            logger=logger,
        )

        total_time = time.time() - pipeline_start_time

        result = PipelineResult(
            step_01=step_01_result,
            step_02=step_02_result,
            step_03=step_03_result,
            step_04=step_04_result,
            step_05=step_05_result,
            total_processing_time=total_time,
            final_text=step_05_result.refined_text,
        )

        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info(f"Final compression: {len(result.final_text) / len(raw_text):.1%}")
        logger.info(f"Final readability: {result.step_05.readability_score:.2%}")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Utility functions
# ─────────────────────────────────────────────────────────────────────────────

def _setup_logger(
    name: str = "PipelineRunner",
    log_level: int = logging.INFO,
) -> logging.Logger:
    """Configura un logger semplice."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(log_level)
    return logger


def pipeline_result_to_dict(result: PipelineResult) -> dict[str, Any]:
    """Converte PipelineResult a dizionario per serializzazione JSON."""
    return {
        "step_01": asdict(result.step_01),
        "step_02": {
            "num_chunks": result.step_02.num_chunks,
            "avg_chunk_size": result.step_02.avg_chunk_size,
            "processing_time": result.step_02.processing_time,
        },
        "step_03": asdict(result.step_03),
        "step_04": asdict(result.step_04),
        "step_05": asdict(result.step_05),
        "total_processing_time": result.total_processing_time,
        "final_text": result.final_text,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="End-to-End Pipeline Runner - Appunti Vision Riassunzione"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Testo da riassumere",
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=0.3,
        help="Rapporto di compressione (default: 0.3)",
    )
    parser.add_argument(
        "--style",
        choices=["neutral", "academic", "casual"],
        default="neutral",
        help="Stile di riscrittura (default: neutral)",
    )
    parser.add_argument(
        "--refiner",
        choices=["mock", "qwen"],
        default="mock",
        help="Tipo di refiner (default: mock)",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Path per salvare risultati in JSON",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Livello di logging",
    )

    args = parser.parse_args()

    try:
        logger = _setup_logger(log_level=getattr(logging, args.log_level))

        result = run_full_pipeline(
            raw_text=args.input,
            target_summary_ratio=args.ratio,
            style=args.style,
            refiner_type=args.refiner,
            log_level=getattr(logging, args.log_level),
            logger=logger,
        )

        print("\n" + "=" * 80)
        print("RISULTATO FINALE")
        print("=" * 80)
        print(f"\n{result.final_text}\n")
        print("=" * 80)

        if args.output_json:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(pipeline_result_to_dict(result), f, indent=2, ensure_ascii=False)
            logger.info(f"Risultati salvati in {args.output_json}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
