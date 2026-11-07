"""Generate contracts outside the checkout and install them into the environment."""
import runpy
import tempfile
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        root = Path(self.root)
        generator = runpy.run_path(str(root / "scripts/generate_python.py"))
        self._generated = tempfile.TemporaryDirectory(prefix="avoar-python-build-")
        output = Path(self._generated.name)
        try:
            generator["generate"](root, output)
        except BaseException:
            self._generated.cleanup()
            raise
        # Forced files are embedded in both normal and editable wheels. Only the
        # handwritten Python source is editable; contracts regenerate on rebuild.
        build_data["force_include"].update({str(output / "avoar"): "avoar"})

    def finalize(self, version, build_data, artifact_path):
        if self.target_name == "wheel":
            self._generated.cleanup()
