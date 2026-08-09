using System;
using System.IO;
using System.Text;
using Marcbeacve.TevScript.Core;

internal static class Program
{
    private static readonly UTF8Encoding Utf8 =
        new UTF8Encoding(false, true);

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length != 5)
            {
                Console.Error.WriteLine(
                    "Usage: TevScript.DeterminismHostGate " +
                    "<program> <scenario> <package> <authority> <out-dir>");
                return 2;
            }

            string programJson = File.ReadAllText(args[0], Utf8);
            string scenarioJson = File.ReadAllText(args[1], Utf8);
            string packageJson = File.ReadAllText(args[2], Utf8);
            string authorityJson = File.ReadAllText(args[3], Utf8);
            string output = Path.GetFullPath(args[4]);
            Directory.CreateDirectory(output);

            string receipt = null;
            for (int run = 0; run < 64; run++)
            {
                string current =
                    Gate7Shared.RunFullConformanceReceipt(
                        programJson,
                        scenarioJson);
                if (receipt == null)
                    receipt = current;
                else if (!string.Equals(
                             receipt,
                             current,
                             StringComparison.Ordinal))
                    throw new InvalidOperationException(
                        "Gate-7A deterministic replay diverged at run " +
                        run + ".");
            }

            File.WriteAllText(
                Path.Combine(output, "host.full.receipt.json"),
                receipt,
                Utf8);
            Console.WriteLine("GATE7A_CSHARP_REPLAY_64=PASS");
            Console.WriteLine(
                "GATE7_HOST_FULL_RECEIPT_SHA256=" +
                Gate7Shared.HashCanonicalLine(receipt));

            Gate7CheckpointFreshResult checkpoint =
                Gate7Shared.RunCheckpointFresh(programJson);
            string restored =
                Gate7Shared.RunCheckpointRestore(
                    programJson,
                    checkpoint.CheckpointJson);

            if (!string.Equals(
                    checkpoint.ContinuationReceipt,
                    restored,
                    StringComparison.Ordinal))
                throw new InvalidOperationException(
                    "Gate-7D host checkpoint continuation diverged.");

            File.WriteAllText(
                Path.Combine(output, "host.checkpoint.json"),
                checkpoint.CheckpointJson,
                Utf8);
            File.WriteAllText(
                Path.Combine(
                    output,
                    "host.continuation.receipt.json"),
                checkpoint.ContinuationReceipt,
                Utf8);

            Console.WriteLine(
                "GATE7D_HOST_CHECKPOINT_HASH=" +
                TevScriptCanonicalJson.Hash(
                    checkpoint.CheckpointJson));
            Console.WriteLine(
                "GATE7D_HOST_RESTORE_CONTINUATION=PASS");

            string signedReceipt =
                Gate7Shared.RunSignedUpdateLockstep(
                    programJson,
                    packageJson,
                    authorityJson);
            File.WriteAllText(
                Path.Combine(
                    output,
                    "host.signed-update.receipt.json"),
                signedReceipt,
                Utf8);
            Console.WriteLine(
                "GATE7E_HOST_SIGNED_UPDATE_RECEIPT_SHA256=" +
                Gate7Shared.HashCanonicalLine(signedReceipt));

            Console.WriteLine(
                "TEV_SCRIPT_DISTRIBUTED_DETERMINISM_HOST_GATE7=PASS");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            Console.WriteLine(
                "TEV_SCRIPT_DISTRIBUTED_DETERMINISM_HOST_GATE7=FAIL");
            return 111;
        }
    }
}
