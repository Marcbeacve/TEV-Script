using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices.JavaScript;
using System.Text;
using Marcbeacve.TevScript.Core;

internal static partial class Gate7BrowserInterop
{
    [JSImport("globalThis.tevGate7Phase")]
    internal static partial string Phase();

    [JSImport("globalThis.tevGate7StoreLoad")]
    internal static partial string StoreLoad(string key);

    [JSImport("globalThis.tevGate7StoreSave")]
    internal static partial void StoreSave(string key, string value);

    [JSImport("globalThis.tevGate7StoreRemove")]
    internal static partial void StoreRemove(string key);
}

internal static class Program
{
    private const string CheckpointKey =
        "tev-script-gate7-checkpoint-v1";

    private static int Main()
    {
        string phase = "unresolved";
        string stage = "STARTUP";
        try
        {
            if (!OperatingSystem.IsBrowser())
                throw new InvalidOperationException(
                    "Gate-7 Browser requires browser-wasm.");

            stage = "PHASE";
            phase = Gate7BrowserInterop.Phase();
            if (phase != "fresh" && phase != "restore")
                throw new InvalidOperationException(
                    "Gate-7 Browser phase invalid: " + phase);

            stage = "RESOURCES";
            string programJson = ReadResource("Player.tevs.ir.json");
            string scenarioJson =
                ReadResource("distributed-lockstep.scenario.json");
            Console.WriteLine("GATE7_BROWSER_STAGE_RESOURCES=PASS");

            if (phase == "fresh")
            {
                stage = "STORE_CLEAR";
                Gate7BrowserInterop.StoreRemove(CheckpointKey);
                Console.WriteLine("GATE7_BROWSER_STAGE_STORE_CLEAR=PASS");

                stage = "FULL_RECEIPT";
                string fullReceipt =
                    Gate7Shared.RunFullConformanceReceipt(
                        programJson,
                        scenarioJson);
                EmitBase64(
                    "GATE7_BROWSER_FULL_RECEIPT_B64",
                    fullReceipt);
                Console.WriteLine("GATE7_BROWSER_STAGE_FULL_RECEIPT=PASS");

                stage = "CHECKPOINT_FRESH";
                Gate7CheckpointFreshResult checkpoint =
                    Gate7Shared.RunCheckpointFresh(programJson);
                Console.WriteLine("GATE7_BROWSER_STAGE_CHECKPOINT_FRESH=PASS");

                stage = "STORE_SAVE";
                Gate7BrowserInterop.StoreSave(
                    CheckpointKey,
                    checkpoint.CheckpointJson);
                Console.WriteLine("GATE7_BROWSER_STAGE_STORE_SAVE=PASS");

                stage = "CHECKPOINT_HASH";
                Console.WriteLine(
                    "GATE7_BROWSER_CHECKPOINT_HASH=" +
                    Marcbeacve.TevScript.Core.TevScriptCanonicalJson.Hash(
                        checkpoint.CheckpointJson));
                EmitBase64(
                    "GATE7_BROWSER_CONTINUATION_RECEIPT_B64",
                    checkpoint.ContinuationReceipt);
                Console.WriteLine("GATE7_BROWSER_STAGE_CHECKPOINT_RECEIPT=PASS");

                stage = "SIGNED_UPDATE";
                string signedReceipt =
                    Gate7Shared.RunSignedUpdateLockstep(
                        programJson,
                        ReadResource("package1.json"),
                        ReadResource("authority.json"));
                EmitBase64(
                    "GATE7_BROWSER_SIGNED_UPDATE_RECEIPT_B64",
                    signedReceipt);
                Console.WriteLine("GATE7_BROWSER_STAGE_SIGNED_UPDATE=PASS");

                Console.WriteLine(
                    "GATE7_BROWSER_CHECKPOINT_PERSISTED=PASS");
            }
            else
            {
                stage = "STORE_LOAD";
                string checkpointJson =
                    Gate7BrowserInterop.StoreLoad(CheckpointKey);
                if (string.IsNullOrEmpty(checkpointJson))
                    throw new InvalidOperationException(
                        "Gate-7 Browser checkpoint missing after restart.");

                Console.WriteLine(
                    "GATE7_BROWSER_CHECKPOINT_RELOAD=PASS");
                Console.WriteLine("GATE7_BROWSER_STAGE_STORE_LOAD=PASS");
                stage = "CHECKPOINT_RESTORE";
                string restored =
                    Gate7Shared.RunCheckpointRestore(
                        programJson,
                        checkpointJson);
                EmitBase64(
                    "GATE7_BROWSER_CONTINUATION_RECEIPT_B64",
                    restored);
                Console.WriteLine("GATE7_BROWSER_STAGE_CHECKPOINT_RESTORE=PASS");
            }

            stage = "COMPLETE";
            Console.WriteLine("GATE7_BROWSER_PHASE=" + phase);
            Console.WriteLine(
                "TEV_SCRIPT_BROWSER_DISTRIBUTED_DETERMINISM_GATE7=PASS");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            Console.WriteLine(
                "GATE7_BROWSER_FAILURE_PHASE=" + phase);
            Console.WriteLine(
                "GATE7_BROWSER_FAILURE_STAGE=" + stage);
            TevContractException contract = exception as TevContractException;
            Console.WriteLine(
                "GATE7_BROWSER_FAILURE_CODE=" +
                (contract == null ? "NONE" : contract.Diagnostic.Code));
            Console.WriteLine(
                "GATE7_BROWSER_FAILURE_TYPE=" +
                exception.GetType().Name);
            Console.WriteLine(
                "GATE7_BROWSER_FAILURE_MESSAGE_B64=" +
                Convert.ToBase64String(
                    Encoding.UTF8.GetBytes(exception.Message ?? string.Empty)));
            Console.WriteLine(
                "TEV_SCRIPT_BROWSER_DISTRIBUTED_DETERMINISM_GATE7=FAIL");
            return 121;
        }
    }

    private static void EmitBase64(
        string marker,
        string text)
    {
        Console.WriteLine(
            marker + "=" +
            Convert.ToBase64String(
                Encoding.UTF8.GetBytes(text)));
    }

    private static string ReadResource(string name)
    {
        Assembly assembly = typeof(Program).Assembly;
        using (Stream stream =
            assembly.GetManifestResourceStream(name))
        {
            if (stream == null)
                throw new InvalidOperationException(
                    "Embedded resource missing: " + name);
            using (var reader = new StreamReader(
                stream,
                new UTF8Encoding(false, true)))
            {
                return reader.ReadToEnd();
            }
        }
    }
}
