from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_baseline import generate_baseline_response  # noqa: E402
from tryops.semantic_cache import (  # noqa: E402
    SemanticCache,
    build_cache_metadata,
    build_semantic_cache_entry,
    lookup_semantic_cache,
)


class SemanticCacheTests(unittest.TestCase):
    def test_fallback_lookup_hits_similar_prompt_without_raw_prompt_metadata(self) -> None:
        generation = generate_baseline_response(
            prompt="Explain why MLOps is the core of TryOps in five bullet points.",
            model_alias="baseline",
            max_tokens=128,
        )
        entry = build_semantic_cache_entry(
            prompt="model=baseline structured=True prompt=Explain why MLOps is the core of TryOps in five bullet points.",
            generation=generation,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            lookup = lookup_semantic_cache(
                query="model=baseline structured=True prompt=Explain TryOps MLOps core in bullet points.",
                entries=[entry],
                threshold=0.70,
                cli_path=Path(temp_dir) / "missing-native-cache",
            )

        metadata = build_cache_metadata(lookup=lookup, matched_generation=generation)
        self.assertTrue(metadata["lookup"]["hit"])
        self.assertEqual(metadata["lookup"]["matched_entry_id"], entry.id)
        self.assertGreater(metadata["savings"]["tokens_saved"], 0)
        self.assertNotIn("Explain TryOps", str(metadata))
        self.assertIn("query_fingerprint", metadata["lookup"])

    def test_runtime_cache_returns_cached_generation(self) -> None:
        cache = SemanticCache(threshold=0.70)
        prompt = "model=baseline structured=True prompt=Compare GPTQ and AWQ for TryOps."
        generation = generate_baseline_response(
            prompt="Compare GPTQ and AWQ for TryOps.",
            model_alias="baseline",
            max_tokens=128,
        )
        entry = cache.put(prompt=prompt, generation=generation)

        lookup = cache.lookup(
            "model=baseline structured=True prompt=Compare GPTQ AWQ quantization for TryOps.",
            threshold=0.70,
            cli_path=Path("/tmp/missing-tryops-cache"),
        )
        cached = cache.get_generation(str(lookup["lookup"]["matched_entry_id"]))

        self.assertTrue(lookup["lookup"]["hit"])
        self.assertEqual(entry.id, lookup["lookup"]["matched_entry_id"])
        self.assertIsNotNone(cached)
        self.assertEqual(cached["output"]["text"], generation["output"]["text"])


if __name__ == "__main__":
    unittest.main()
