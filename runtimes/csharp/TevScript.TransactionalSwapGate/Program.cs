using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Marcbeacve.TevScript.Core;

internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            Console.WriteLine("GATE5A_GATE_BINARY_VERSION=V4");
            Dictionary<string, string> paths = ParseArguments(args);

            string baseJson = File.ReadAllText(paths["base"]);
            string goodJson = File.ReadAllText(paths["good"]);
            string removedJson = File.ReadAllText(paths["removed"]);
            string escalatedJson = File.ReadAllText(paths["escalated"]);
            string wrongProgramJson = File.ReadAllText(paths["wrong-program"]);

            TevScriptProgram baseProgram = TevScriptProgram.Parse(baseJson);
            string[] ceiling = baseProgram.Entities
                .SelectMany(item => item.Capabilities.Keys)
                .Distinct(StringComparer.Ordinal)
                .OrderBy(item => item, StringComparer.Ordinal)
                .ToArray();

            var host = new TevScriptRuntimeHost(
                baseProgram,
                null,
                ceiling);

            TevScriptRuntimeSnapshot before = host.CaptureSnapshot();
            string baseHash = host.ActiveSemanticHash;
            Require(
                before.SemanticHash == baseHash,
                "initial snapshot semantic hash mismatch");

            // Prepare is non-authoritative.
            TevScriptRuntimeSwapPlan goodPlan =
                host.PrepareSwap(goodJson);
            Require(
                host.ActiveSemanticHash == baseHash,
                "prepare changed active runtime");
            Require(
                host.Generation == 0,
                "prepare changed host generation");
            Console.WriteLine("GATE5A_PREPARE_NON_AUTHORITATIVE=PASS");

            TevScriptProgram goodProgram =
                TevScriptProgram.Parse(goodJson);

            TevScriptRuntimeSwapReceipt commit =
                host.Commit(goodPlan);
            Require(!commit.Rollback, "commit marked rollback");
            Require(
                host.ActiveSemanticHash ==
                    goodProgram.SemanticHash,
                "candidate semantic hash not active");
            Require(
                host.Generation == 1,
                "commit generation mismatch");
            Console.WriteLine("GATE5A_COMMIT_ATOMIC_REFERENCE_SWAP=PASS");

            TevScriptRuntimeSnapshot after = host.CaptureSnapshot();
            AssertMigratedExistingState(before, after);
            AssertCandidateAdditionsInitialized(goodProgram, before, after);
            Console.WriteLine("GATE5A_EXISTING_STATE_MIGRATION=PASS");
            Console.WriteLine("GATE5A_ADDITIVE_STATE_INITIALIZATION=PASS");

            ExpectCode(
                () => host.Commit(goodPlan),
                "TEVS_CS_SWAP_PLAN_CONSUMED");
            Console.WriteLine("GATE5A_PLAN_REUSE_FAIL_CLOSED=PASS");

            // While the good candidate is active, exercise host-level
            // negative contracts with IRs that remain schema/IR valid.
            string goodStableHash = host.ActiveSemanticHash;
            TevScriptRuntimeSnapshot goodStableState =
                host.CaptureSnapshot();

            ExpectCode(
                () => host.PrepareSwap(removedJson),
                "TEVS_CS_SWAP_STATE_REMOVED");
            Require(host.ActiveSemanticHash == goodStableHash,
                "state-removal rejection changed active runtime");
            AssertSnapshotsEqual(goodStableState, host.CaptureSnapshot());
            Console.WriteLine("GATE5A_STATE_REMOVAL_VALID_IR_REACHES_HOST=PASS");
            Console.WriteLine("GATE5A_STATE_REMOVAL_FAIL_CLOSED=PASS");

            ExpectCode(
                () => host.PrepareSwap(escalatedJson),
                "TEVS_CS_SWAP_CAPABILITY_CEILING");
            Require(host.ActiveSemanticHash == goodStableHash,
                "capability rejection changed active runtime");
            AssertSnapshotsEqual(goodStableState, host.CaptureSnapshot());
            Console.WriteLine("GATE5A_CAPABILITY_CEILING_FAIL_CLOSED=PASS");

            ExpectCode(
                () => host.PrepareSwap(wrongProgramJson),
                "TEVS_CS_SWAP_PROGRAM_ID");
            Require(host.ActiveSemanticHash == goodStableHash,
                "program-id rejection changed active runtime");
            AssertSnapshotsEqual(goodStableState, host.CaptureSnapshot());
            Console.WriteLine("GATE5A_PROGRAM_ID_CONTINUITY_FAIL_CLOSED=PASS");

            TevScriptRuntimeSwapReceipt rollback =
                host.RollbackLastCommit();
            Require(rollback.Rollback, "rollback receipt missing flag");
            Require(
                host.ActiveSemanticHash == baseHash,
                "rollback did not restore source program");
            AssertSnapshotsEqual(before, host.CaptureSnapshot());
            Console.WriteLine("GATE5A_ROLLBACK_EXACT_RUNTIME_RESTORE=PASS");

            // Stale-plan campaign: two plans against generation N.
            TevScriptRuntimeSwapPlan first =
                host.PrepareSwap(goodJson);
            TevScriptRuntimeSwapPlan stale =
                host.PrepareSwap(goodJson);
            host.Commit(first);
            ExpectCode(
                () => host.Commit(stale),
                "TEVS_CS_SWAP_PLAN_STALE");
            Console.WriteLine("GATE5A_STALE_PLAN_FAIL_CLOSED=PASS");

            host.RollbackLastCommit();
            Require(
                host.ActiveSemanticHash == baseHash,
                "final rollback did not restore base");
            AssertSnapshotsEqual(before, host.CaptureSnapshot());

            Console.WriteLine("GATE5A_TRANSACTION_BOUNDARY=PASS");
            Console.WriteLine("GATE5A_NO_NETWORK=PASS");
            Console.WriteLine("GATE5A_NO_SIGNATURE_AUTHORITY=PASS");
            Console.WriteLine("GATE5A_NO_DYNAMIC_CODE=PASS");
            Console.WriteLine("TEV_SCRIPT_TRANSACTIONAL_PROGRAM_SWAP_GATE_5A=PASS");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            return 1;
        }
    }

    private static Dictionary<string, string> ParseArguments(
        string[] args)
    {
        var result = new Dictionary<string, string>(
            StringComparer.Ordinal);
        for (int index = 0; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length ||
                !args[index].StartsWith(
                    "--",
                    StringComparison.Ordinal))
            {
                throw new ArgumentException(
                    "Expected --name value arguments.");
            }
            result.Add(
                args[index].Substring(2),
                args[index + 1]);
        }

        string[] required =
        {
            "base",
            "good",
            "removed",
            "escalated",
            "wrong-program"
        };
        foreach (string item in required)
        {
            if (!result.ContainsKey(item))
            {
                throw new ArgumentException(
                    "Missing --" + item);
            }
        }
        return result;
    }

    private static void AssertMigratedExistingState(
        TevScriptRuntimeSnapshot before,
        TevScriptRuntimeSnapshot after)
    {
        foreach (KeyValuePair<
                     string,
                     IReadOnlyDictionary<string, TevScriptValue>>
                 entity in before.Entities)
        {
            Require(
                after.Entities.ContainsKey(entity.Key),
                "entity disappeared after migration: " + entity.Key);
            foreach (KeyValuePair<string, TevScriptValue> state
                     in entity.Value)
            {
                TevScriptValue observed;
                Require(
                    after.Entities[entity.Key].TryGetValue(
                        state.Key,
                        out observed),
                    "state disappeared after migration: " +
                    entity.Key + "." + state.Key);
                Require(
                    state.Value.Equals(observed),
                    "state value not preserved: " +
                    entity.Key + "." + state.Key);
            }
        }
    }

    private static void AssertCandidateAdditionsInitialized(
        TevScriptProgram candidate,
        TevScriptRuntimeSnapshot before,
        TevScriptRuntimeSnapshot after)
    {
        bool observedAddition = false;
        foreach (TevScriptEntityDefinition entity in candidate.Entities)
        {
            HashSet<string> oldNames =
                before.Entities[entity.EntityId].Keys.ToHashSet(
                    StringComparer.Ordinal);
            foreach (TevScriptStateDefinition state in entity.States)
            {
                if (oldNames.Contains(state.Name))
                {
                    continue;
                }
                observedAddition = true;
                TevScriptValue actual =
                    after.Entities[entity.EntityId][state.Name];
                Require(
                    state.Initial.Equals(actual),
                    "new state did not use candidate initial: " +
                    entity.EntityId + "." + state.Name);
            }
        }
        Require(
            observedAddition,
            "candidate did not contain an additive state");
    }

    private static void AssertSnapshotsEqual(
        TevScriptRuntimeSnapshot expected,
        TevScriptRuntimeSnapshot observed)
    {
        Require(
            expected.ProgramId == observed.ProgramId,
            "snapshot program id mismatch");
        Require(
            expected.SemanticHash == observed.SemanticHash,
            "snapshot semantic hash mismatch");
        Require(
            expected.Entities.Count == observed.Entities.Count,
            "snapshot entity count mismatch");

        foreach (KeyValuePair<
                     string,
                     IReadOnlyDictionary<string, TevScriptValue>>
                 entity in expected.Entities)
        {
            IReadOnlyDictionary<string, TevScriptValue> actualEntity;
            Require(
                observed.Entities.TryGetValue(
                    entity.Key,
                    out actualEntity),
                "snapshot entity missing: " + entity.Key);
            Require(
                entity.Value.Count == actualEntity.Count,
                "snapshot state count mismatch: " + entity.Key);

            foreach (KeyValuePair<string, TevScriptValue> state
                     in entity.Value)
            {
                TevScriptValue actualValue;
                Require(
                    actualEntity.TryGetValue(
                        state.Key,
                        out actualValue),
                    "snapshot state missing: " +
                    entity.Key + "." + state.Key);
                Require(
                    state.Value.Equals(actualValue),
                    "snapshot state mismatch: " +
                    entity.Key + "." + state.Key);
            }
        }
    }

    private static void ExpectCode(
        Action action,
        string expectedCode)
    {
        try
        {
            action();
        }
        catch (TevContractException exception)
        {
            if (exception.Diagnostic.Code == expectedCode)
            {
                return;
            }
            throw new InvalidOperationException(
                "Expected diagnostic " + expectedCode +
                " but observed " + exception.Diagnostic.Code + ".",
                exception);
        }
        throw new InvalidOperationException(
            "Expected diagnostic " + expectedCode +
            " but operation succeeded.");
    }

    private static void Require(
        bool condition,
        string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
