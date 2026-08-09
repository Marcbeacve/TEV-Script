using System.Text;
using TevScript.Core.V3;

internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            if (!OperatingSystem.IsWasi())
                throw new InvalidOperationException("IR V3 WASI gate requires wasi-wasm.");
            if (args.Length != 4 || (args[0] != "fresh" && args[0] != "restore"))
                throw new ArgumentException(
                    "usage: TevScript.V3WasiGate <fresh|restore> <validator-cases.json> <scenario.json> <checkpoint.json>");

            var mode = args[0];
            var casesPath = args[1];
            var scenarioPath = args[2];
            var checkpointPath = args[3];
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_ACTIVE=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_MODE=" + mode.ToUpperInvariant());

            var cases = TevScriptStrictJsonV3.ParseElement(File.ReadAllText(casesPath, Encoding.UTF8));
            var program = cases.GetProperty("valid_program").Clone();
            var scenario = TevScriptStrictJsonV3.ParseElement(File.ReadAllText(scenarioPath, Encoding.UTF8));
            TevScriptProgramValidatorV3.Validate(program);
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_VALIDATOR=PASS");

            var receipt = TevScriptV3Conformance.Run(program, scenario);
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_RECEIPT_HASH=" + receipt.ReceiptHash);
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_CONFORMANCE=PASS");

            if (mode == "fresh")
            {
                var runtime = new TevScriptRuntimeV3(program);
                runtime.Invoke("E", "start");
                var checkpoint = TevScriptRuntimeCheckpointV2.Capture(runtime);
                var bytes = checkpoint.ToCanonicalJson();
                File.WriteAllText(checkpointPath, bytes, new UTF8Encoding(false));
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_HASH=" + checkpoint.CheckpointHash);
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_CAPTURE=PASS");
            }
            else
            {
                if (!File.Exists(checkpointPath))
                    throw new FileNotFoundException("WASI checkpoint file missing.", checkpointPath);
                var bytes = File.ReadAllText(checkpointPath, Encoding.UTF8);
                var checkpoint = TevScriptRuntimeCheckpointV2.Parse(bytes);
                var restored = checkpoint.RestoreExact(program);
                var events = restored.Invoke("E", "update");
                if (events.Count != 1 || events[0].EventId != "changed")
                    throw new InvalidOperationException("WASI checkpoint continuation event mismatch.");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_HASH=" + checkpoint.CheckpointHash);
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_RESTORE=PASS");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_RESTART_CONTINUATION=PASS");
            }

            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_GATE=PASS");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_GATE=FAIL");
            return 91;
        }
    }
}
