"""Manifest aggregation is reproducible and never rewrites approved inputs."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("visualizer_manifest", ROOT / "visualizer/tools/build_visualizer_manifest.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class VisualizerManifestTests(unittest.TestCase):
    def test_reproducible_manifest_matches_approved_inputs(self):
        output = ROOT / "visualizer/public/audio/tukana-visualizer-manifest.json"
        committed = json.loads(output.read_text(encoding="utf-8"))
        paths = [ROOT / source["path"] for source in committed["provenance"].values()]
        paths.append(ROOT / "visualizer/public" / committed["master_url"].lstrip("/"))
        before = {path: builder.digest(path) for path in paths}
        self.assertEqual(builder.build_manifest(), committed)
        self.assertEqual(before, {path: builder.digest(path) for path in paths})


if __name__ == "__main__":
    unittest.main()
