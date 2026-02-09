"""Detector registry — manages all registered failure detectors.

New detectors can be added without refactoring by simply registering them here.
"""

import logging

from agent_autopsy.core.models import CanonicalTrace, DetectedFailure
from agent_autopsy.detectors.base import FailureDetector
from agent_autopsy.detectors.false_terminal_success import FalseTerminalSuccessDetector
from agent_autopsy.detectors.retry_without_learning import RetryWithoutLearningDetector
from agent_autopsy.detectors.silent_retry_masking import SilentRetryMaskingDetector
from agent_autopsy.detectors.state_drift import StateDriftDetector

logger = logging.getLogger(__name__)

# Default detector instances
_DEFAULT_DETECTORS: list[FailureDetector] = [
    StateDriftDetector(),
    SilentRetryMaskingDetector(),
    FalseTerminalSuccessDetector(),
    RetryWithoutLearningDetector(),
]

# Mutable registry for extensibility
_registered_detectors: list[FailureDetector] = list(_DEFAULT_DETECTORS)


def get_all_detectors() -> list[FailureDetector]:
    """Return all registered detectors."""
    return list(_registered_detectors)


def register_detector(detector: FailureDetector) -> None:
    """Register a new failure detector.

    Args:
        detector: An instance implementing FailureDetector.
    """
    _registered_detectors.append(detector)
    logger.info("Registered detector: %s", detector.name)


def run_all_detectors(trace: CanonicalTrace) -> tuple[list[DetectedFailure], list[str]]:
    """Execute all registered detectors against a canonical trace.

    Args:
        trace: The normalized trace to analyze.

    Returns:
        A tuple of (all_failures, detector_names_run).
    """
    all_failures: list[DetectedFailure] = []
    detectors_run: list[str] = []

    for detector in _registered_detectors:
        try:
            logger.info("Running detector: %s", detector.name)
            found = detector.detect(trace)
            all_failures.extend(found)
            detectors_run.append(detector.name)
            if found:
                logger.info(
                    "Detector '%s' found %d failure(s)", detector.name, len(found)
                )
        except Exception:
            logger.exception("Detector '%s' raised an exception", detector.name)
            detectors_run.append(detector.name)

    return all_failures, detectors_run
