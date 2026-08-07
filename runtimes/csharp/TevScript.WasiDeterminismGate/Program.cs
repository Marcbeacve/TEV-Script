using System;
using System.IO;
using System.Reflection;
using System.Text;

internal static class Program
{
    private static readonly UTF8Encoding Utf8 =
        new UTF8Encoding(false, true);

    private static int Main(string[] args)
    {
        string phase = "unresolved";
        try
        {
            if (!OperatingSystem.IsWasi())
                throw new InvalidOperationException(
                    "Gate-7 WASI requires wasi-wasm.");

            if (args.Length != 2)
                throw new ArgumentException(
                    "Expected <fresh|restore> <checkpoint-path>.");

            phase = args[0];
            string checkpointPath =
                Path.GetFullPath(args[1]);

            if (phase != "fresh" && phase != "restore")
                throw new ArgumentException(
                    "Gate-7 WASI phase invalid: " + phase);

            string programJson = ReadResource("Player.tevs.ir.json");
            string scenarioJson =
                ReadResource("distributed-lockstep.scenario.json");

            if (phase == "fresh")
            {
                string fullReceipt =
                    Gate7Shared.RunFullConformanceReceipt(
                        programJson,
                        scenarioJson);
                EmitBase64(
                    "GATE7_WASI_FULL_RECEIPT_B64",
                    fullReceipt);

                Gate7CheckpointFreshResult checkpoint =
                    Gate7Shared.RunCheckpointFresh(programJson);

                File.WriteAllText(
                    checkpointPath,
                    checkpoint.CheckpointJson,
                    Utf8);

                Console.WriteLine(
                    "GATE7_WASI_CHECKPOINT_HASH=" +
                    Marcbeacve.TevScript.Core.TevScriptCanonicalJson.Hash(
                        checkpoint.CheckpointJson));
                EmitBase64(
                    "GATE7_WASI_CONTINUATION_RECEIPT_B64",
                    checkpoint.ContinuationReceipt);

                string signedReceipt =
                    Gate7Shared.RunSignedUpdateLockstep(
                        programJson,
                        ReadResource("package1.json"),
                        ReadResource("authority.json"));
                EmitBase64(
                    "GATE7_WASI_SIGNED_UPDATE_RECEIPT_B64",
                    signedReceipt);

                Console.WriteLine(
                    "GATE7_WASI_CHECKPOINT_PERSISTED=PASS");
            }
            else
            {
                string checkpointJson =
                    File.ReadAllText(
                        checkpointPath,
                        Utf8);
                Console.WriteLine(
                    "GATE7_WASI_CHECKPOINT_RELOAD=PASS");

                string restored =
                    Gate7Shared.RunCheckpointRestore(
                        programJson,
                        checkpointJson);
                EmitBase64(
                    "GATE7_WASI_CONTINUATION_RECEIPT_B64",
                    restored);
            }

            Console.WriteLine("GATE7_WASI_PHASE=" + phase);
            Console.WriteLine(
                "TEV_SCRIPT_WASI_DISTRIBUTED_DETERMINISM_GATE7=PASS");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            Console.WriteLine(
                "GATE7_WASI_FAILURE_PHASE=" + phase);
            Console.WriteLine(
                "GATE7_WASI_FAILURE_TYPE=" +
                exception.GetType().Name);
            Console.WriteLine(
                "TEV_SCRIPT_WASI_DISTRIBUTED_DETERMINISM_GATE7=FAIL");
            return 131;
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
                Utf8))
            {
                return reader.ReadToEnd();
            }
        }
    }
}
