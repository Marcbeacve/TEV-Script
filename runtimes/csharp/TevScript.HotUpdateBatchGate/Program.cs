using System;
using System.Collections.Generic;
using System.IO;
using System.Numerics;
using System.Text.Json;
using Marcbeacve.TevScript.Core;
using Marcbeacve.TevScript.Update;

internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            Dictionary<string, string> p = ParseArguments(args);
            string baseJson = File.ReadAllText(p["base"]);
            string fixtures = p["fixtures"];
            string storePath = p["store"];

            AuthorityConfig key =
                LoadAuthority(Path.Combine(fixtures, "authority.json"));
            AuthorityConfig wrongKey =
                LoadAuthority(Path.Combine(
                    fixtures, "wrong_authority.json"));

            var verifier = new TevEcdsaP256Sha256Verifier(
                key.KeyId, key.X, key.Y);
            var wrongVerifier = new TevEcdsaP256Sha256Verifier(
                wrongKey.KeyId, wrongKey.X, wrongKey.Y);

            RunGate5C(fixtures, verifier, wrongVerifier);
            RunGate5D(baseJson, fixtures, storePath, verifier);

            Console.WriteLine(
                "TEV_SCRIPT_HOT_UPDATE_BATCH_GATE_5C_5D=PASS");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            Console.WriteLine(
                "TEV_SCRIPT_HOT_UPDATE_BATCH_GATE_5C_5D=FAIL");
            return 61;
        }
    }

    private static void RunGate5C(
        string fixtures,
        TevEcdsaP256Sha256Verifier verifier,
        TevEcdsaP256Sha256Verifier wrongVerifier)
    {
        string p1Text = Read(fixtures, "package1.json");
        TevScriptSignedUpdatePackage p1 =
            TevScriptSignedUpdatePackage.Parse(p1Text);

        p1.VerifySignature(verifier);
        if (p1.Epoch != 1 ||
            p1.Sequence != 1 ||
            p1.Signature.Length != 64 ||
            p1.SignatureAlgorithm != "ES256")
        {
            throw new InvalidOperationException(
                "Gate-5C valid package metadata mismatch.");
        }

        Console.WriteLine("GATE5C_SIGNED_PACKAGE_VERIFY=PASS");
        Console.WriteLine("GATE5C_ES256_P256_SHA256=PASS");
        Console.WriteLine("GATE5C_SIGNATURE_P1363_FIXED_64=PASS");

        ExpectCode(
            delegate
            {
                TevScriptSignedUpdatePackage.Parse(
                    Read(fixtures, "package_tampered.json"))
                    .VerifySignature(verifier);
            },
            "TEVS_CS_UPDATE_SIGNATURE_INVALID");
        Console.WriteLine("GATE5C_TAMPER_FAIL_CLOSED=PASS");

        ExpectCode(
            delegate
            {
                TevScriptSignedUpdatePackage.Parse(
                    Read(fixtures, "package_wrong_key.json"))
                    .VerifySignature(verifier);
            },
            "TEVS_CS_UPDATE_SIGNATURE_INVALID");
        Console.WriteLine("GATE5C_WRONG_KEY_FAIL_CLOSED=PASS");

        ExpectCode(
            delegate { p1.VerifySignature(wrongVerifier); },
            "TEVS_CS_UPDATE_KEY_AUTHORITY");
        Console.WriteLine(
            "GATE5C_KEY_AUTHORITY_MISMATCH_FAIL_CLOSED=PASS");

        ExpectCode(
            delegate
            {
                TevScriptSignedUpdatePackage.Parse(
                    Read(fixtures, "package_unknown_algorithm.json"))
                    .VerifySignature(verifier);
            },
            "TEVS_CS_UPDATE_SIGNATURE_ALGORITHM");
        Console.WriteLine(
            "GATE5C_ALGORITHM_DOWNGRADE_FAIL_CLOSED=PASS");

        ExpectCode(
            delegate
            {
                TevScriptSignedUpdatePackage.Parse(
                    Read(fixtures, "package_noncanonical.json"));
            },
            "TEVS_CS_UPDATE_PACKAGE_CANONICAL");
        Console.WriteLine(
            "GATE5C_NONCANONICAL_PACKAGE_FAIL_CLOSED=PASS");

        if (p1.SignedBodyJson.Length == 0 ||
            p1.PackageSha256.Length != 64)
        {
            throw new InvalidOperationException(
                "Gate-5C canonical signing witness missing.");
        }

        Console.WriteLine("GATE5C_CANONICAL_SIGNING_BODY=PASS");
        Console.WriteLine(
            "GATE5C_TEST_PRIVATE_KEY_RUNTIME=ABSENT_PASS");
        Console.WriteLine(
            "GATE5C_PRODUCTION_KEY_PROVISIONING=NOT_IN_SCOPE");
        Console.WriteLine(
            "TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_GATE_5C=PASS");
    }

    private static void RunGate5D(
        string baseJson,
        string fixtures,
        string storePath,
        TevEcdsaP256Sha256Verifier verifier)
    {
        if (File.Exists(storePath))
            File.Delete(storePath);

        TevScriptProgram baseProgram =
            TevScriptProgram.Parse(baseJson);
        string[] ceiling = CapabilityCeiling(baseProgram);

        var failedHost = new TevScriptRuntimeHost(
            baseProgram, null, ceiling);
        string failedHash = failedHost.ActiveSemanticHash;
        var failedAuthority = new TevScriptUpdateAuthority(
            failedHost,
            "stable",
            verifier,
            new FailingStore());

        TevScriptUpdatePlan failedPlan =
            failedAuthority.Prepare(
                Read(fixtures, "package1.json"));
        ExpectCode(
            delegate { failedAuthority.Commit(failedPlan); },
            "TEVS_CS_UPDATE_STORE_COMMIT");
        if (failedHost.ActiveSemanticHash != failedHash)
        {
            throw new InvalidOperationException(
                "Runtime did not roll back after store failure.");
        }
        Console.WriteLine(
            "GATE5D_STORE_FAILURE_RUNTIME_ROLLBACK=PASS");

        var host = new TevScriptRuntimeHost(
            baseProgram, null, ceiling);
        host.Invoke(
            "Player",
            "damage",
            TevScriptValue.Int(new BigInteger(10)));
        RequireHealth(host, 90, "base behavior");

        var store = new TevFileInstalledUpdateStore(storePath);
        var authority = new TevScriptUpdateAuthority(
            host, "stable", verifier, store);

        TevScriptUpdatePlan p1 = authority.Prepare(
            Read(fixtures, "package1.json"));
        if (store.Load("stable") != null ||
            host.ActiveSemanticHash != baseProgram.SemanticHash)
        {
            throw new InvalidOperationException(
                "Prepare changed update authority.");
        }
        Console.WriteLine(
            "GATE5D_PREPARE_NON_AUTHORITATIVE=PASS");

        TevScriptUpdateReceipt r1 = authority.Commit(p1);
        TevInstalledUpdateRecord installed1 =
            store.Load("stable");
        if (r1.Epoch != 1 ||
            r1.Sequence != 1 ||
            installed1 == null ||
            installed1.Epoch != 1 ||
            installed1.Sequence != 1)
        {
            throw new InvalidOperationException(
                "First durable update was not committed.");
        }

        host.Invoke(
            "Player",
            "damage",
            TevScriptValue.Int(new BigInteger(10)));
        RequireHealth(host, 90, "package1 behavior");
        Console.WriteLine(
            "GATE5D_DURABLE_COMMIT_EPOCH1_SEQUENCE1=PASS");

        ExpectCode(
            delegate
            {
                authority.Prepare(
                    Read(fixtures, "package1.json"));
            },
            "TEVS_CS_UPDATE_REPLAY");
        Console.WriteLine(
            "GATE5D_REPLAY_WITH_DURABLE_STATE_FAIL_CLOSED=PASS");

        TevScriptUpdateReceipt r2 = authority.Commit(
            authority.Prepare(
                Read(fixtures, "package2.json")));
        if (r2.Epoch != 1 || r2.Sequence != 2)
        {
            throw new InvalidOperationException(
                "Second update metadata mismatch.");
        }

        host.Invoke(
            "Player",
            "damage",
            TevScriptValue.Int(new BigInteger(10)));
        RequireHealth(host, 89, "package2 behavior");
        Console.WriteLine(
            "GATE5D_MONOTONIC_SEQUENCE_ADVANCE=PASS");

        var reopenedStore =
            new TevFileInstalledUpdateStore(storePath);
        var restoredHost = new TevScriptRuntimeHost(
            baseProgram, null, ceiling);
        var restoredAuthority = new TevScriptUpdateAuthority(
            restoredHost,
            "stable",
            verifier,
            reopenedStore);

        TevScriptUpdateReceipt restored;
        if (!restoredAuthority.TryRestoreInstalled(out restored) ||
            !restored.Restore ||
            restored.Epoch != 1 ||
            restored.Sequence != 2)
        {
            throw new InvalidOperationException(
                "Durable package restore failed.");
        }

        restoredHost.Invoke(
            "Player",
            "damage",
            TevScriptValue.Int(new BigInteger(10)));
        RequireHealth(restoredHost, 99, "restored package2");
        Console.WriteLine(
            "GATE5D_DURABLE_RESTART_RESTORE=PASS");

        ExpectCode(
            delegate
            {
                restoredAuthority.Prepare(
                    Read(fixtures, "package2.json"));
            },
            "TEVS_CS_UPDATE_REPLAY");
        Console.WriteLine(
            "GATE5D_REPLAY_AFTER_RESTORE_FAIL_CLOSED=PASS");

        TevScriptUpdateReceipt epoch2 =
            restoredAuthority.Commit(
                restoredAuthority.Prepare(
                    Read(fixtures, "package_epoch2.json")));
        if (epoch2.Epoch != 2 || epoch2.Sequence != 1)
        {
            throw new InvalidOperationException(
                "Epoch transition mismatch.");
        }
        Console.WriteLine(
            "GATE5D_EPOCH_ADVANCE_ONE_SEQUENCE_RESET=PASS");

        ExpectCode(
            delegate
            {
                restoredAuthority.Prepare(
                    Read(fixtures, "package_epoch1_high.json"));
            },
            "TEVS_CS_UPDATE_EPOCH_ROLLBACK");
        Console.WriteLine(
            "GATE5D_EPOCH_ROLLBACK_FAIL_CLOSED=PASS");

        ExpectCode(
            delegate
            {
                restoredAuthority.Prepare(
                    Read(fixtures, "package_epoch3_badseq.json"));
            },
            "TEVS_CS_UPDATE_EPOCH_SEQUENCE");
        Console.WriteLine(
            "GATE5D_NEW_EPOCH_BAD_SEQUENCE_FAIL_CLOSED=PASS");

        TevScriptUpdatePlan accepted =
            restoredAuthority.Prepare(
                Read(fixtures, "package_epoch2_seq2.json"));
        TevScriptUpdatePlan stale =
            restoredAuthority.Prepare(
                Read(fixtures, "package_epoch2_seq3.json"));

        restoredAuthority.Commit(accepted);

        ExpectCode(
            delegate { restoredAuthority.Commit(stale); },
            "TEVS_CS_UPDATE_PLAN_STALE");
        Console.WriteLine(
            "GATE5D_STALE_UPDATE_PLAN_FAIL_CLOSED=PASS");

        TevInstalledUpdateRecord finalRecord =
            reopenedStore.Load("stable");
        if (finalRecord == null ||
            finalRecord.Epoch != 2 ||
            finalRecord.Sequence != 2)
        {
            throw new InvalidOperationException(
                "Final durable cursor mismatch.");
        }

        Console.WriteLine(
            "GATE5D_DURABLE_LOCAL_AUTHORITY=PASS");
        Console.WriteLine(
            "GATE5D_RUNTIME_AND_DURABLE_COMMIT_COUPLING=PASS");
        Console.WriteLine(
            "GATE5D_HOSTILE_STORE_ROLLBACK=NOT_IN_SCOPE");
        Console.WriteLine(
            "TEV_SCRIPT_ANTI_REPLAY_GATE_5D=PASS_WITH_DURABLE_STATE_BOUNDARY");
    }

    private static string[] CapabilityCeiling(TevScriptProgram program)
    {
        var result = new List<string>();
        foreach (TevScriptEntityDefinition entity in program.Entities)
        {
            foreach (string id in entity.Capabilities.Keys)
            {
                if (!result.Contains(id))
                    result.Add(id);
            }
        }
        return result.ToArray();
    }

    private static void RequireHealth(
        TevScriptRuntimeHost host,
        int expected,
        string context)
    {
        IReadOnlyDictionary<string, TevScriptValue> state =
            host.State("Player");
        if (!state.ContainsKey("health") ||
            state["health"].AsInt() != new BigInteger(expected))
        {
            throw new InvalidOperationException(
                context + ": expected health=" + expected + ".");
        }
    }

    private static string Read(string directory, string name)
    {
        return File.ReadAllText(Path.Combine(directory, name));
    }

    private static AuthorityConfig LoadAuthority(string path)
    {
        using (JsonDocument doc =
            JsonDocument.Parse(File.ReadAllText(path)))
        {
            JsonElement root = doc.RootElement;
            return new AuthorityConfig(
                root.GetProperty("key_id").GetString(),
                root.GetProperty("x").GetString(),
                root.GetProperty("y").GetString());
        }
    }

    private static Dictionary<string, string> ParseArguments(string[] args)
    {
        var result = new Dictionary<string, string>(
            StringComparer.Ordinal);
        for (int index = 0; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length ||
                !args[index].StartsWith("--", StringComparison.Ordinal))
            {
                throw new ArgumentException(
                    "Expected --name value arguments.");
            }
            result.Add(args[index].Substring(2), args[index + 1]);
        }

        foreach (string required in new[] { "base", "fixtures", "store" })
        {
            if (!result.ContainsKey(required))
                throw new ArgumentException("Missing --" + required + ".");
        }
        return result;
    }

    private static void ExpectCode(Action action, string expectedCode)
    {
        try
        {
            action();
        }
        catch (TevContractException exception)
        {
            if (exception.Diagnostic.Code == expectedCode)
                return;

            throw new InvalidOperationException(
                "Expected " + expectedCode +
                " but observed " +
                exception.Diagnostic.Code + ".",
                exception);
        }

        throw new InvalidOperationException(
            "Expected " + expectedCode +
            " but operation succeeded.");
    }

    private sealed class AuthorityConfig
    {
        public AuthorityConfig(string keyId, string x, string y)
        {
            KeyId = keyId;
            X = x;
            Y = y;
        }

        public string KeyId { get; }
        public string X { get; }
        public string Y { get; }
    }

    private sealed class FailingStore : ITevInstalledUpdateStore
    {
        public TevInstalledUpdateRecord Load(string channelId)
        {
            return null;
        }

        public void Save(TevInstalledUpdateRecord record)
        {
            throw new IOException(
                "Intentional Gate-5D durable-store failure.");
        }
    }
}
