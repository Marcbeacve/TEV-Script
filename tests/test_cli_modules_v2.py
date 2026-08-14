from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v2 import main


class CliModulesV2Tests(unittest.TestCase):
    def call(self, args):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_bundle_is_the_compile_source_of_truth_after_module_file_changes(self):
        module_source = 'module math.util version "2.0.0"; export fn inc(x:Int)->Int=x+1; export fn twice(x:Int)->Int=inc(inc(x));'
        app_source = 'script App version "2.0.0"; import math.util as util; fn solve(x:Int)->Int=util.twice(x); entry main:Int=solve(5);'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            module = root / 'util.tevs'
            app = root / 'app.tevs'
            bundle = root / 'modules.json'
            ir = root / 'program.json'
            receipt = root / 'receipt.json'
            module.write_text(module_source, encoding='utf-8')
            app.write_text(app_source, encoding='utf-8')
            code, out, err = self.call(['bundle-modules', '--module', str(module), '-o', str(bundle)])
            self.assertEqual((code, err), (0, ''))
            bundled = json.loads(out)
            self.assertEqual(bundled['module_count'], 1)
            self.assertFalse(bundled['runtime_module_acquisition'])
            self.assertFalse(bundled['network_acquisition'])
            module.write_text('module math.util version "2.0.0"; export fn inc(x:Int)->Int=x+100;', encoding='utf-8')
            code, out, err = self.call(['check-modules', str(app), '--bundle', str(bundle)])
            self.assertEqual((code, err), (0, ''))
            checked = json.loads(out)
            self.assertFalse(checked['runtime_module_acquisition'])
            self.assertFalse(checked['runtime_requires_source_compiler'])
            code, out, err = self.call(['compile-modules', str(app), '--bundle', str(bundle), '-o', str(ir)])
            self.assertEqual((code, err), (0, ''))
            compiled = json.loads(out)
            self.assertEqual(compiled['entry_profile'], 'pure')
            code, out, err = self.call(['run', str(ir), '-o', str(receipt)])
            self.assertEqual((code, err), (0, ''))
            result = json.loads(receipt.read_text(encoding='utf-8'))
            self.assertEqual(result['result_encoded'], {'$int': '7'})


if __name__ == '__main__':
    unittest.main()
