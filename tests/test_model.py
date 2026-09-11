import math
import unittest

from x20.model import FACTOR_NAMES, QuadraticSignalModel


class QuadraticSignalModelTests(unittest.TestCase):
    def setUp(self):
        self.model = QuadraticSignalModel()
        self.x = {name: ((index % 7) - 3) / 10 for index, name in enumerate(FACTOR_NAMES)}

    def test_factor_count_and_hessian_symmetry(self):
        self.assertEqual(len(FACTOR_NAMES), 20)
        for i in range(20):
            for j in range(20):
                self.assertEqual(self.model.hessian[i][j], self.model.hessian[j][i])

    def test_analytic_gradient_matches_finite_difference(self):
        vector = list(self.model.vector(self.x))
        analytic = self.model.gradient(vector)
        epsilon = 1e-6
        for i in range(20):
            plus, minus = vector.copy(), vector.copy()
            plus[i] += epsilon
            minus[i] -= epsilon
            numeric = (self.model.score(plus) - self.model.score(minus)) / (2 * epsilon)
            self.assertAlmostEqual(analytic[i], numeric, places=6)

    def test_chain_rule(self):
        velocity = {name: 0.001 * (index - 10) for index, name in enumerate(FACTOR_NAMES)}
        result = self.model.evaluate(self.x, velocity)
        expected = sum(a * b for a, b in zip(result.gradient, self.model.vector(velocity)))
        self.assertAlmostEqual(result.chain_rate, expected, places=10)

    def test_exact_second_order_stress(self):
        shock = {"news_sentiment": -0.2, "event_risk": 0.3, "float_unlock_pressure": 0.1}
        result = self.model.stress_delta(self.x, shock)
        base = self.model.vector(self.x)
        shifted = [base[i] + shock.get(name, 0.0) for i, name in enumerate(FACTOR_NAMES)]
        exact = self.model.score(shifted) - self.model.score(base)
        self.assertAlmostEqual(result["total"], exact, places=10)

    def test_probability_is_bounded(self):
        output = self.model.evaluate(self.x)
        self.assertGreater(output.probability_up, 0.0)
        self.assertLess(output.probability_up, 1.0)
        self.assertTrue(math.isfinite(output.uncertainty))


if __name__ == "__main__":
    unittest.main()

