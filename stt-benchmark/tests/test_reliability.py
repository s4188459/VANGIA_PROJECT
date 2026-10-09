"""Independent scoring oracle and service lifecycle regressions."""
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.datasets import write_json
from benchmark.scoring import score
from server import make_server


def independent_distance(left, right):
    # Exhaustive recursive edit search with memoization, independent of the
    # production rolling-row algorithm and S/D/I bookkeeping.
    from functools import lru_cache
    @lru_cache(None)
    def visit(i, j):
        if i == len(left):
            return len(right) - j
        if j == len(right):
            return len(left) - i
        return min(visit(i + 1, j) + 1, visit(i, j + 1) + 1,
                   visit(i + 1, j + 1) + (left[i] != right[j]))
    return visit(0, 0)


class ReliabilityTests(unittest.TestCase):
    def test_wer_matches_independent_oracle_for_930_pairs(self):
        sequences = [words for length in range(5)
                     for words in itertools.product(('cat', 'dog'), repeat=length)]
        count = 0
        for reference in sequences[1:]:
            for hypothesis in sequences:
                result = score(' '.join(reference), ' '.join(hypothesis))
                expected = independent_distance(reference, hypothesis)
                self.assertEqual(result['errors'], expected, (reference, hypothesis))
                self.assertEqual(result['substitutions'] + result['deletions'] + result['insertions'], expected)
                self.assertEqual(result['wer'], expected / len(reference))
                count += 1
        self.assertEqual(count, 930)

    def test_second_server_on_used_port_does_not_rewrite_active_run(self):
        with tempfile.TemporaryDirectory() as directory:
            server = make_server(directory, 0)
            run_path = Path(directory)/'runs'/('a'*32)/'run.json'
            run = {'id':'a'*32,'status':'running','models':[], 'dataset':{'samples':[]}}
            write_json(run_path, run)
            before = run_path.read_bytes()
            try:
                with self.assertRaises(OSError):
                    second = make_server(directory, server.server_port)
                    second.server_close()
                self.assertEqual(run_path.read_bytes(), before,
                                 'Failed second startup must not mark a live run interrupted.')
            finally:
                server.server_close()


if __name__ == '__main__':
    unittest.main()
