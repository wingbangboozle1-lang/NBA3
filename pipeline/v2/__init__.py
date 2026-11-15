"""V2 pipeline: freshness-gated official data -> two estimators -> gated leaderboard.

Every module here is standard library only and deterministic.  ``build.py`` is
the entry point; it refuses to publish anything unless the freshness and
provenance gates in ``gates.py`` pass first.
"""
