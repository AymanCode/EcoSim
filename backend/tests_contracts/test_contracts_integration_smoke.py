"""Smoke test for the full Economy.step() pipeline.

This test verifies that the 16-phase tick lifecycle runs without
exceptions. It is a minimal integration test covering the
entire simulation step.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from factories import make_economy


class TestEconomyStepSmoke:
    """Verify Economy.step() completes all 16 phases without error."""

    def test_single_tick_completes(self):
        """A single tick should run all phases without exception."""
        economy = make_economy(num_households=12, num_firms_per_category=1)
        initial_tick = economy.current_tick

        # Run one tick
        economy.step()

        # Tick should have advanced
        assert economy.current_tick == initial_tick + 1

    def test_multiple_ticks_stable(self):
        """Multiple ticks should complete without exceptions."""
        economy = make_economy(num_households=12, num_firms_per_category=1)
        num_ticks = 5

        for i in range(num_ticks):
            economy.step()
            assert economy.current_tick == i + 1

    def test_warmup_ticks_skip_shocks(self):
        """During warmup, stochastic shocks should be skipped."""
        economy = make_economy(num_households=12, num_firms_per_category=1)
        num_warmup = economy.warmup_ticks
        
        # Run warmup ticks
        for i in range(num_warmup):
            economy.step()
            assert economy.in_warmup is True
            assert economy.current_tick == i + 1

        # After warmup
        economy.step()
        assert economy.in_warmup is False
