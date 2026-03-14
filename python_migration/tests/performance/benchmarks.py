"""
Benchmark utilities for performance testing.

Provides timing and memory profiling helpers for pipeline benchmarks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class BenchmarkResult:
    """Container for benchmark results."""

    name: str
    elapsed_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    row_count: int = 0
    notes: str = ""


class BenchmarkRunner:
    """Simple benchmark runner for pipeline performance tests."""

    def __init__(self) -> None:
        self.results: list[BenchmarkResult] = []

    def time_it(self, name: str):
        """Context manager to time a block of code."""
        return _TimerContext(name, self)

    def report(self) -> str:
        """Generate a summary report of all benchmarks."""
        lines = ["Benchmark Results", "=" * 60]
        for r in self.results:
            lines.append(
                f"  {r.name}: {r.elapsed_seconds:.3f}s "
                f"({r.row_count} rows) {r.notes}"
            )
        return "\n".join(lines)


class _TimerContext:
    """Context manager for timing code blocks."""

    def __init__(self, name: str, runner: BenchmarkRunner) -> None:
        self.name = name
        self.runner = runner
        self._start: float = 0.0

    def __enter__(self) -> BenchmarkResult:
        self._result = BenchmarkResult(name=self.name)
        self._start = time.perf_counter()
        return self._result

    def __exit__(self, *args: object) -> None:
        self._result.elapsed_seconds = time.perf_counter() - self._start
        self.runner.results.append(self._result)
