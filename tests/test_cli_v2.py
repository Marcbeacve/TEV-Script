from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import os
import zipfile
import io
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v2 import main


class CliV2Tests(unittest.TestCase):
    PURE='''
    script Demo version "2.0.0";
    fn add(x:Int,y:Int)->Int=x+y;
    entry main:Int=add(2,3);
    '''
    RECURSIVE='''
    script Demo version "2.0.0";
    recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
    entry main:Int=factorial(5);
    '''
    EFFECTS='''
    script Demo version "2.0.0";
    state count:Int=0;
    capability observation sensor.read(Int)->Int;
    action tick(bias:Int) {
        observe sample=sensor.read(count);
        set count=sample+bias;
    }
    entry main=tick(3);
    '''

    EFFECTS_R2='''
    script FileDemo version "2.0.0";
    state writes:Int=0;
    command file.replace(Text,Text);
    action publish() {
        request file.replace("out.txt","hello");
        set writes=writes+1;
    }
    entry main=publish();
    '''

    def _call(self,args):
        out=io.StringIO(); err=io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            code=main(args)
        return code,out.getvalue(),err.getvalue()

    def test_descriptor_reports_v2_and_all_program_ir_profiles(self):
        code,out,err=self._call(["descriptor"])
        self.assertEqual(code,0); self.assertEqual(err,"")
        payload=json.loads(out)
        self.assertEqual(payload["language_version"],"2.0.0")
        self.assertEqual(len(payload["program_ir_schemas"]),4)
        self.assertFalse(payload["runtime_requires_source_compiler"])

    def test_check_closes_source_through_portable_ir_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"main.tevs"; src.write_text(self.PURE,encoding="utf-8")
            code,out,err=self._call(["check",str(src)])
            self.assertEqual(code,0); self.assertEqual(err,"")
            payload=json.loads(out)
            self.assertEqual(payload["entry_profile"],"pure")
            self.assertEqual(payload["status"],"PASS_CANDIDATE")
            self.assertEqual(len(payload["program_ir_hash"]),64)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),["main.tevs"])

    def test_compile_then_run_pure_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/"main.tevs"; ir=root/"main.irv4.json"; receipt=root/"receipt.json"
            src.write_text(self.PURE,encoding="utf-8")
            code,out,err=self._call(["compile",str(src),"-o",str(ir)])
            self.assertEqual(code,0); self.assertEqual(err,""); summary=json.loads(out)
            artifact=json.loads(ir.read_text(encoding="utf-8"))
            self.assertEqual(summary["program_ir_hash"],artifact["program_ir_hash"])
            code,out,err=self._call(["run",str(ir),"-o",str(receipt),"--expected-program-ir-hash",artifact["program_ir_hash"]])
            self.assertEqual(code,0); self.assertEqual(err,"")
            run_summary=json.loads(out); run_receipt=json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(run_summary["result_type"],"Int")
            self.assertEqual(run_receipt["result_encoded"],{"$int":"5"})

    def test_compile_then_run_recursive_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/"factorial.tevs"; ir=root/"factorial.irv4.json"; receipt=root/"receipt.json"
            src.write_text(self.RECURSIVE,encoding="utf-8")
            code,out,err=self._call(["compile",str(src),"-o",str(ir)])
            self.assertEqual(code,0); self.assertEqual(err,"")
            self.assertEqual(json.loads(out)["entry_profile"],"recursive")
            code,out,err=self._call(["run",str(ir),"-o",str(receipt)])
            self.assertEqual(code,0); self.assertEqual(err,"")
            self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["result_encoded"],{"$int":"120"})

    def test_effects_check_scenario_compile_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/"effects.tevs"; scenario=root/"scenario.json"; ir=root/"effects.irv4.json"; receipt=root/"receipt.json"
            src.write_text(self.EFFECTS,encoding="utf-8")
            code,out,err=self._call(["check-effects",str(src)])
            self.assertEqual(code,0); self.assertEqual(err,"")
            checked=json.loads(out)
            self.assertEqual(checked["entry_action"],"tick")
            self.assertEqual(len(checked["source_semantic_hash"]),64)

            code,out,err=self._call(["scenario-effects",str(src),"-o",str(scenario)])
            self.assertEqual(code,0); self.assertEqual(err,"")
            scenario_payload=json.loads(scenario.read_text(encoding="utf-8"))
            self.assertEqual(len(scenario_payload["capabilities"]),1)
            scenario_payload["capabilities"][0]["calls"]=[{"arguments":[{"$int":"0"}],"return":{"$int":"10"}}]
            scenario.write_text(json.dumps(scenario_payload,sort_keys=True,separators=(",",":")),encoding="utf-8")

            code,out,err=self._call(["compile-effects",str(src),"--scenario",str(scenario),"-o",str(ir)])
            self.assertEqual(code,0); self.assertEqual(err,"")
            compiled=json.loads(out)
            self.assertEqual(compiled["entry_profile"],"effects")
            artifact=json.loads(ir.read_text(encoding="utf-8"))
            self.assertEqual(artifact["profile"],"effects")

            code,out,err=self._call(["run",str(ir),"-o",str(receipt),"--expected-program-ir-hash",artifact["program_ir_hash"]])
            self.assertEqual(code,0); self.assertEqual(err,"")
            summary=json.loads(out); transition=json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(summary["profile"],"effects")
            self.assertEqual(summary["final_state_hash"],transition["final_state_hash"])
            self.assertEqual(transition["final_state"][0]["value"],{"$int":"13"})
            self.assertEqual(transition["observation_calls"],1)

    def test_effects_invalid_scenario_does_not_commit_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/"effects.tevs"; scenario=root/"scenario.json"; output=root/"program.json"
            src.write_text(self.EFFECTS,encoding="utf-8")
            scenario.write_text('{}',encoding="utf-8")
            output.write_text("SENTINEL",encoding="utf-8")
            code,out,err=self._call(["compile-effects",str(src),"--scenario",str(scenario),"-o",str(output)])
            self.assertEqual(code,2); self.assertEqual(out,""); self.assertTrue(err)
            self.assertEqual(output.read_text(encoding="utf-8"),"SENTINEL")

    def test_effects_r2_check_compile_and_plan_never_commits_physical_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/'r2.tevs'; scenario=root/'scenario.json'; ir=root/'r2.ir.json'; plan=root/'plan.json'; receipt=root/'plan-receipt.json'
            src.write_text(self.EFFECTS_R2,encoding='utf-8')
            code,out,err=self._call(['check-effects-r2',str(src)])
            self.assertEqual(code,0); self.assertEqual(err,'')
            self.assertFalse(json.loads(out)['physical_effects_committed'])
            self.assertEqual(self._call(['scenario-effects-r2',str(src),'-o',str(scenario)])[0],0)
            code,out,err=self._call(['compile-effects-r2',str(src),'--scenario',str(scenario),'-o',str(ir)])
            self.assertEqual(code,0); self.assertEqual(err,'')
            self.assertFalse(json.loads(out)['physical_effects_committed'])
            code,out,err=self._call(['plan-effects-r2',str(ir),'-o',str(plan),'--receipt',str(receipt)])
            self.assertEqual(code,0); self.assertEqual(err,'')
            summary=json.loads(out)
            self.assertEqual(summary['status'],'PLANNED_NOT_FINALIZED')
            self.assertFalse(summary['physical_effects_committed']); self.assertFalse(summary['state_finalized'])
            self.assertTrue(plan.exists()); self.assertTrue(receipt.exists())
            self.assertFalse((root/'out.txt').exists())

    def test_wrong_hash_pin_fails_before_output_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/"main.tevs"; ir=root/"main.json"; receipt=root/"receipt.json"
            src.write_text(self.PURE,encoding="utf-8")
            self.assertEqual(self._call(["compile",str(src),"-o",str(ir)])[0],0)
            code,out,err=self._call(["run",str(ir),"-o",str(receipt),"--expected-program-ir-hash","0"*64])
            self.assertEqual(code,2); self.assertEqual(out,""); self.assertFalse(receipt.exists())
            self.assertEqual(json.loads(err)["diagnostic"]["code"],"TEVS_PROGRAM_IR_V4_EXPECTED_HASH")

    def test_invalid_source_does_not_clobber_existing_compile_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/"bad.tevs"; output=root/"program.json"
            src.write_text('script Demo version "2.0.0"; entry main:Int=nope<Int>(1);',encoding="utf-8")
            output.write_text("SENTINEL",encoding="utf-8")
            code,out,err=self._call(["compile",str(src),"-o",str(output)])
            self.assertEqual(code,2); self.assertEqual(out,""); self.assertTrue(err)
            self.assertEqual(output.read_text(encoding="utf-8"),"SENTINEL")

    def test_reference_wheel_contains_v2_runtime_modules(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location("tev_script_build_backend",root/"tools"/"tev_script_build_backend.py")
        backend=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(backend)
        old_epoch=os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"]="1786380000"
        try:
            with tempfile.TemporaryDirectory(prefix="tev-v2-wheel-test-") as td:
                wheel=Path(td)/backend.build_wheel(td)
                with zipfile.ZipFile(wheel,"r") as archive:
                    names=set(archive.namelist())
                    entry_name=next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
                    entry_text=archive.read(entry_name).decode("utf-8")
                self.assertIn("tev_script/cli_v2.py",names)
                self.assertIn("tev_script/program_ir_v4.py",names)
                self.assertIn("tev_script/ir_v4_recursive.py",names)
                self.assertIn("tev_script/ir_v4_effects.py",names)
                self.assertIn("tev_script/source_effect_program_v2.py",names)
                self.assertIn("tev_script/program_ir_v4_effect_commands.py",names)
                self.assertIn("tev_script/ir_v4_effect_commands.py",names)
                self.assertIn("tev_script/file_effect_provider_v2.py",names)
                self.assertIn("tev_script/effect_commit_ledger_v2.py",names)
                self.assertIn("tev_script/task_scheduler_v2.py",names)
                self.assertIn("tev_script/file_observation_scheduler_v2.py",names)
                self.assertIn("tev_script/file_observation_acquisition_v2.py",names)
                self.assertIn("tev_script/scoped_filesystem_v2.py",names)
                self.assertIn("tev_script/descriptor_v2.py",names)
                self.assertIn("tev_script/describe_v2.py",names)
                self.assertIn("tev_script/module_linker_v2.py",names)
                self.assertIn("tev_script/remote_module_acquisition_v2.py",names)
                self.assertIn("tev_script/signed_remote_module_manifest_v2.py",names)
                self.assertIn("tev-script-v2 = tev_script.cli_v2:main",entry_text)
                self.assertIn("tev-script-v2-describe = tev_script.describe_v2:main",entry_text)
        finally:
            if old_epoch is None: os.environ.pop("SOURCE_DATE_EPOCH",None)
            else: os.environ["SOURCE_DATE_EPOCH"]=old_epoch


if __name__=="__main__": unittest.main()
