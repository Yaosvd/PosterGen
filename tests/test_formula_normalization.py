import unittest

from utils.evidence_utils import normalize_formula_multiplication


class FormulaNormalizationTests(unittest.TestCase):
    def test_normalizes_formula_variants_before_verification(self):
        variants = (
            (
                "epsilon_CutMix(alpha) = "
                "(alpha * max_{i in C} lambda_i / 2) * (Delta^2 D_s)."
            ),
            (
                "epsilon_CutMix(alpha) = "
                "(alpha max_{i in C} lambda_i / 2)"
                "\u00b7(Delta^2 D_s)."
            ),
            (
                "epsilon_CutMix(alpha) = "
                "(alpha max_{i in C} lambda_i / 2)"
                "\\cdot(Delta^2 D_s)."
            ),
        )
        expected = (
            "epsilon_CutMix(alpha) = "
            "(alpha \u00d7 max_{i in C} lambda_i / 2) "
            "\u00d7 (Delta^2 D_s)."
        )

        for formula in variants:
            with self.subTest(formula=formula):
                self.assertEqual(
                    expected,
                    normalize_formula_multiplication(formula),
                )

    def test_does_not_rewrite_non_formula_markdown(self):
        text = "The *privacy loss* is discussed in the paper."

        self.assertEqual(
            text,
            normalize_formula_multiplication(text),
        )


if __name__ == "__main__":
    unittest.main()
