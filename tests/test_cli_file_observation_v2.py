from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v2 import main


class CliFileObservationV2Tests(unittest.TestCase):
    SOURCE = """
    script ReadDemo version \"2.0.0\";
    state content:Text=\"\";
    capability observation file.read(Text)->Text;
    action load() {
        observe body=file.read(\"input.txt\");
        set content=body;
    }
    entry main=load();
    """

    def call(self, args):
        out=io.StringIO(); err=io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code=main(args)
        return code,out.getvalue(),err.getvalue()

    def test_request_and_acquire_emit_provenance_separate_from_scenario(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); data=root/"data"; data.mkdir()
            source=root/"read.tevs"; source.write_text(self.SOURCE,encoding="utf-8")
            (data/"input.txt").write_text("alpha",encoding="utf-8")
            request=root/"request.json"; scenario=root/"scenario.json"; evidence=root/"evidence.json"
            code,out,err=self.call(["request-file-observations",str(source),"--path","input.txt","-o",str(request)])
            self.assertEqual((code,err),(0,"")); self.assertFalse(json.loads(out)["host_observations_acquired"])
            code,out,err=self.call(["acquire-file-observations",str(source),"--request",str(request),"--root",str(data),"--scenario-output",str(scenario),"--evidence-output",str(evidence)])
            self.assertEqual((code,err),(0,""))
            summary=json.loads(out); self.assertTrue(summary["host_observations_acquired"]); self.assertFalse(summary["physical_effects_committed"]); self.assertFalse(summary["state_finalized"])
            e=json.loads(evidence.read_text(encoding="utf-8")); s=json.loads(scenario.read_text(encoding="utf-8"))
            self.assertIn("provider",e); self.assertIn("authority_scope_hash",e)
            self.assertNotIn("provider",s); self.assertNotIn("authority_scope_hash",s)
            self.assertEqual(s["capabilities"][0]["calls"][0]["return"],"alpha")


    def test_parallel_acquisition_is_byte_identical_and_reports_operational_scheduler(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); data=root/"data"; data.mkdir()
            source=root/"read.tevs"; source.write_text(self.SOURCE,encoding="utf-8")
            (data/"a.txt").write_text("alpha",encoding="utf-8"); (data/"b.txt").write_text("beta",encoding="utf-8")
            request=root/"request.json"
            code,out,err=self.call(["request-file-observations",str(source),"--path","a.txt","--path","b.txt","-o",str(request)])
            self.assertEqual((code,err),(0,""))
            seq_s=root/"seq-scenario.json"; seq_e=root/"seq-evidence.json"
            par_s=root/"par-scenario.json"; par_e=root/"par-evidence.json"
            code,_out,err=self.call(["acquire-file-observations",str(source),"--request",str(request),"--root",str(data),"--scenario-output",str(seq_s),"--evidence-output",str(seq_e)])
            self.assertEqual((code,err),(0,""))
            code,out,err=self.call(["acquire-file-observations",str(source),"--request",str(request),"--root",str(data),"--read-workers","2","--scenario-output",str(par_s),"--evidence-output",str(par_e)])
            self.assertEqual((code,err),(0,""))
            self.assertEqual(par_s.read_bytes(),seq_s.read_bytes())
            self.assertEqual(par_e.read_bytes(),seq_e.read_bytes())
            summary=json.loads(out)
            self.assertEqual(summary["acquisition_scheduler"]["worker_count"],2)
            self.assertFalse(summary["acquisition_scheduler"]["worker_count_is_semantic"])

    def test_invalid_parallel_worker_count_does_not_clobber_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); data=root/"data"; data.mkdir()
            source=root/"read.tevs"; source.write_text(self.SOURCE,encoding="utf-8"); (data/"input.txt").write_text("alpha",encoding="utf-8")
            request=root/"request.json"; scenario=root/"scenario.json"; evidence=root/"evidence.json"
            code,_out,err=self.call(["request-file-observations",str(source),"--path","input.txt","-o",str(request)])
            self.assertEqual((code,err),(0,""))
            scenario.write_bytes(b"scenario-sentinel"); evidence.write_bytes(b"evidence-sentinel")
            code,_out,_err=self.call(["acquire-file-observations",str(source),"--request",str(request),"--root",str(data),"--read-workers","0","--scenario-output",str(scenario),"--evidence-output",str(evidence)])
            self.assertEqual(code,2)
            self.assertEqual(scenario.read_bytes(),b"scenario-sentinel"); self.assertEqual(evidence.read_bytes(),b"evidence-sentinel")

if __name__ == "__main__": unittest.main()
