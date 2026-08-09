using System.Reflection;
using System.Runtime.InteropServices.JavaScript;
using System.Text.Json;
using TevScript.Core.V3;

internal static partial class BrowserWitness
{
    [JSImport("globalThis.tevIrV3BrowserReport")]
    internal static partial void Report(
        string status,
        string receiptHash,
        string checkpointHash,
        string detail);
}

internal static class Program
{
    private static int Main()
    {
        try
        {
            if (!OperatingSystem.IsBrowser())
                throw new InvalidOperationException("IR V3 browser gate requires browser-wasm.");

            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_WASM_ACTIVE=PASS");

            var cases = TevScriptStrictJsonV3.ParseElement(ReadResource("ir-v3-validator-cases.json"));
            var program = cases.GetProperty("valid_program").Clone();
            var scenario = TevScriptStrictJsonV3.ParseElement(ReadResource("ir-v3-portable.scenario.json"));

            TevScriptProgramValidatorV3.Validate(program);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_VALIDATOR=PASS");

            var receipt = TevScriptV3Conformance.Run(program, scenario);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_RECEIPT_HASH=" + receipt.ReceiptHash);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_CONFORMANCE=PASS");

            var runtime = new TevScriptRuntimeV3(program);
            runtime.Invoke("E", "start");
            var checkpoint = TevScriptRuntimeCheckpointV2.Capture(runtime);
            var checkpointBytes = checkpoint.ToCanonicalJson();
            var parsed = TevScriptRuntimeCheckpointV2.Parse(checkpointBytes);
            var restored = parsed.RestoreExact(program);
            if (!StringComparer.Ordinal.Equals(
                    restored.CanonicalStateJson("E"),
                    runtime.CanonicalStateJson("E")))
                throw new InvalidOperationException("IR V3 browser checkpoint restored state mismatch.");
            var events = restored.Invoke("E", "update");
            if (events.Count != 1 || events[0].EventId != "changed")
                throw new InvalidOperationException("IR V3 browser checkpoint continuation mismatch.");

            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_CHECKPOINT_HASH=" + checkpoint.CheckpointHash);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_CHECKPOINT_RESTORE=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_WASM_AOT_REQUESTED=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=PASS");
            BrowserWitness.Report("PASS", receipt.ReceiptHash, checkpoint.CheckpointHash, "");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=FAIL");
            BrowserWitness.Report("FAIL", "", "", error.GetType().Name);
            return 91;
        }
    }

    private static string ReadResource(string name)
    {
        var assembly = typeof(Program).Assembly;
        using var stream = assembly.GetManifestResourceStream(name)
            ?? throw new InvalidOperationException("Embedded resource missing: " + name);
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }
}
