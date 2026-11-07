import importlib.util
import runpy
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("grpc_tools"), "requires the dev dependency group")
class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generate = staticmethod(runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "scripts/generate_python.py")
        )["generate"])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "build/python"
        self.domain = self.root / "avoar/core/opendata/example/domain.proto"
        self.domain.parent.mkdir(parents=True)
        self.domain.write_text('syntax = "proto3"; package example; message Example { optional uint64 id = 1; }')

    def outputs(self):
        return {
            p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in self.output.rglob("*")
            if p.is_file() and p.suffix in (".py", ".pyi")
        }

    def test_clean_generation_is_repeatable_and_detects_contract_changes(self):
        self.generate(self.root)
        self.assertEqual(list(self.domain.parent.iterdir()), [self.domain])
        first = self.outputs()
        for filename in ("domain.py", "domain_pb2.py", "domain_pb2.pyi", "__init__.py"):
            self.assertTrue((self.output / self.domain.parent.relative_to(self.root) / filename).is_file())
        self.generate(self.root)
        self.assertEqual(first, self.outputs())
        self.domain.write_text('syntax = "proto3"; package example; message Example { optional uint64 id = 1; optional string name = 2; }')
        self.generate(self.root)
        self.assertNotEqual(first, self.outputs())
        self.assertIn("name", (self.output / self.domain.parent.relative_to(self.root) / "domain_pb2.pyi").read_text())

    def test_clean_preserves_sources_and_installed_outputs_are_separate(self):
        clean = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "scripts/generate_python.py")
        )["clean"]
        helper = self.domain.parent / "helper.py"
        helper.write_text("VALUE = 1\n")
        self.generate(self.root)
        clean(self.root)
        self.assertFalse(self.output.exists())
        self.assertTrue(self.domain.exists())
        self.assertEqual(helper.read_text(), "VALUE = 1\n")
        clean(self.root)

    def test_failed_compilation_preserves_existing_outputs(self):
        self.generate(self.root)
        previous = self.outputs()
        self.domain.write_text("invalid protobuf")
        with self.assertRaises(RuntimeError):
            self.generate(self.root)
        self.assertEqual(previous, self.outputs())

    def test_removed_schema_cleans_only_owned_files(self):
        extra = self.domain.parent.parent / "removed/domain.proto"
        extra.parent.mkdir()
        extra.write_text('syntax = "proto3"; package removed; message Removed {}')
        manual = extra.parent / "helper.py"
        manual.write_text("VALUE = 1\n")
        self.generate(self.root)
        generated = self.output / extra.relative_to(self.root).with_suffix(".py")
        self.assertTrue(generated.exists())
        extra.unlink()
        self.generate(self.root)
        self.assertEqual(list(extra.parent.iterdir()), [manual])
        self.assertFalse(generated.exists())


if __name__ == "__main__":
    unittest.main()
