# Backend Tools

This directory contains supplementary utilities that support analysis, testing, and research workflows without cluttering the main backend surface.

## Layout

- `analysis/`: audit digests, sample-data generation, ML dataset generation, and related offline utilities
- `checks/`: standalone diagnostic scripts and ad hoc behavior checks
- `llm/`: local LLM experimentation helpers and runners
- `runners/`: headless simulation runners and scenario-specific execution scripts

These files are intentionally separated from the core application entrypoints in `backend/` so the primary repository structure remains easy to scan.
