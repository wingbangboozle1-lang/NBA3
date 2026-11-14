#!/usr/bin/env python3
"""
Regression tests for the defects found by session 3655c68d.

These exist so that the two arithmetic defects corrected on 2026-11-14 cannot silently
return. They test the SAME code paths that produce the published artefacts, not
re-implementations.

Run: python3 -m unittest verify.tests.test_verification
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
sys.path.insert(0, os.path.join(ROOT, 'verify'))

from verify.build import (  # noqa: E402
    _load_parlay_joint, test_parlay_copula, test_pick_spread_signs,
    test_game_logs_agree, test_injury_rows_match_official, test_ledger_integrity,
    check_no_blank_verified_values, check_sources_have_urls, problems,
)


class TestParlayCopula(unittest.TestCase):
    """FX-01: parlay_joint used to return the second leg's marginal probability."""

    def setUp(self):
        self.f = _load_parlay_joint()

    def test_parlay_joint_no_longer_returns_the_marginal(self):
        # The old code returned p2 for every input. At rho=+0.3 that was 0.58.
        got = self.f(0.58, 0.58, 0.3)
        self.assertNotAlmostEqual(got, 0.58, places=2,
                                  msg='parlay_joint still returns the marginal (FX-01 regression)')
        self.assertAlmostEqual(got, 0.3832, places=3)

    def test_independence_reproduces_the_product(self):
        self.assertAlmostEqual(self.f(0.58, 0.58, 0.0), 0.58 * 0.58, places=3)
        self.assertAlmostEqual(self.f(0.2, 0.9, 0.0), 0.18, places=3)

    def test_monotone_in_rho(self):
        vals = [self.f(0.58, 0.58, r) for r in (-0.3, 0.0, 0.3, 0.6, 0.9)]
        for a, b in zip(vals, vals[1:]):
            self.assertLess(a, b)

    def test_respects_frechet_bounds(self):
        for r in (-0.9, -0.3, 0.0, 0.3, 0.6, 0.9):
            j = self.f(0.58, 0.58, r)
            self.assertGreaterEqual(j, 0.16 - 1e-6)
            self.assertLessEqual(j, 0.58 + 1e-6)

    def test_matches_monte_carlo(self):
        # Deterministic Monte Carlo (fixed seed) as an independent method.
        import random
        rnd = random.Random(4242)
        p = 0.58
        for rho in (0.0, 0.3):
            a = 0.0  # not used; threshold below
            # threshold from the same helper the implementation uses
            sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
            from run_model import _invnorm
            a = _invnorm(1 - p)
            hit = 0
            n = 60000
            for _ in range(n):
                x = rnd.gauss(0, 1)
                y = rho * x + (1 - rho * rho) ** 0.5 * rnd.gauss(0, 1)
                if x > a and y > a:
                    hit += 1
            mc = hit / n
            self.assertAlmostEqual(self.f(p, p, rho), mc, delta=0.02,
                                   msg=f'copula vs Monte Carlo disagree at rho={rho}')


class TestPickLabels(unittest.TestCase):
    """FX-02: the printed spread named the wrong side of the market on every card."""

    def test_pick_spread_sign_matches_moneyline(self):
        before = len(problems)
        test_pick_spread_signs()
        self.assertEqual(len(problems), before, msg='; '.join(problems[before:]))

    def test_every_card_carries_a_minus_on_the_favourite(self):
        picks = json.load(open(os.path.join(ROOT, 'data/picks/picks_2026-11-14_to_16.json')))
        minus = 0
        for k in picks['picks']:
            if ' -' in k['origin_spread']:
                minus += 1
        self.assertEqual(minus, len(picks['picks']),
                         'every card should show its favourite with a minus handicap')

    def test_spread_label_helper(self):
        from make_picks import _spread_label
        cases = [
            (dict(home='NOP', away='DEN', origin_spread_home=-8.6), 'DEN -8.6'),
            (dict(home='MIN', away='CHI', origin_spread_home=17.4), 'MIN -17.4'),
            (dict(home='PHI', away='IND', origin_spread_home=10.4), 'PHI -10.4'),
            (dict(home='LAC', away='CHO', origin_spread_home=0.6), 'LAC -0.6'),
            (dict(home='BOS', away='NYK', origin_spread_home=-2.9), 'NYK -2.9'),
        ]
        for line, expect in cases:
            self.assertEqual(_spread_label(line), expect)


class TestStrategyLabelling(unittest.TestCase):
    """FX-03: STRAT1/STRAT2 settle on the winner but were published as spread bets."""

    def test_moneyline_strategies_are_not_priced_at_minus_110(self):
        v = json.load(open(os.path.join(ROOT, 'data/model/validation_report.json')))
        self.assertIn('strategy_market', v)
        self.assertIn('moneyline', v['strategy_market']['STRAT1'])
        self.assertIn('moneyline', v['strategy_market']['STRAT2'])
        self.assertIn('roi_caveat', v)


class TestCorrelationReport(unittest.TestCase):
    """FX-04: the published parlay example carried the defective 0.58."""

    def test_correlation_report_matches_recomputation(self):
        c = json.load(open(os.path.join(ROOT, 'data/model/correlation_report.json')))
        ex = c['parlay_example']
        self.assertAlmostEqual(ex['copula_prob'], 0.3832, places=3)
        self.assertAlmostEqual(ex['fair_joint_price'], 2.61, places=2)
        self.assertNotAlmostEqual(ex['copula_prob'], 0.58, places=2)
        # the corrected curve must be monotone and match the book's own style
        curve = ex['corrected_curve']
        self.assertEqual(len(curve), 5)
        joints = [r['joint'] for r in curve]
        self.assertEqual(joints, sorted(joints))


class TestDataAgreement(unittest.TestCase):

    def test_two_game_logs_agree(self):
        before = len(problems)
        test_game_logs_agree()
        self.assertEqual(len(problems), before, msg='; '.join(problems[before:]))

    def test_injury_rows_match_the_official_pdf(self):
        before = len(problems)
        test_injury_rows_match_official()
        self.assertEqual(len(problems), before, msg='; '.join(problems[before:]))

    def test_ledger_is_internally_consistent(self):
        before = len(problems)
        test_ledger_integrity()
        self.assertEqual(len(problems), before, msg='; '.join(problems[before:]))

    def test_no_verified_claim_is_blank(self):
        before = len(problems)
        check_no_blank_verified_values()
        self.assertEqual(len(problems), before, msg='; '.join(problems[before:]))

    def test_every_verified_claim_has_a_https_source(self):
        before = len(problems)
        check_sources_have_urls()
        self.assertEqual(len(problems), before, msg='; '.join(problems[before:]))

    def test_copula_suite_passes_as_a_whole(self):
        before = len(problems)
        test_parlay_copula()
        self.assertEqual(len(problems), before, msg='; '.join(problems[before:]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
