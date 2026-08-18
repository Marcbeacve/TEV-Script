from __future__ import annotations

import unittest

from tools.run_v31_total_core_optimized_differential_fuzz import (
    _partition_seed_ranges,
)


class RuntimeV5TotalOptimizedFuzzHarnessTests(unittest.TestCase):
    def test_partition_seed_ranges_covers_each_seed_exactly_once(self) -> None:
        ranges = _partition_seed_ranges(seed_count=1_000, shard_count=32)

        observed = [
            seed
            for start, stop in ranges
            for seed in range(start, stop)
        ]

        self.assertEqual(observed, list(range(1_000)))
        self.assertEqual(len(observed), len(set(observed)))

    def test_partition_seed_ranges_is_balanced(self) -> None:
        ranges = _partition_seed_ranges(seed_count=1_000, shard_count=32)
        sizes = [stop - start for start, stop in ranges]

        self.assertEqual(sum(sizes), 1_000)
        self.assertLessEqual(max(sizes) - min(sizes), 1)

    def test_partition_seed_ranges_handles_more_shards_than_seeds(self) -> None:
        ranges = _partition_seed_ranges(seed_count=3, shard_count=8)

        self.assertEqual(ranges, ((0, 1), (1, 2), (2, 3)))

    def test_partition_seed_ranges_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            _partition_seed_ranges(seed_count=0, shard_count=1)
        with self.assertRaises(ValueError):
            _partition_seed_ranges(seed_count=1, shard_count=0)


if __name__ == "__main__":
    unittest.main()
