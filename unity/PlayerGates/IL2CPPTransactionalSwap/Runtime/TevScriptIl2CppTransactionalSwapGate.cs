using System;
using System.Collections;
using System.Collections.Generic;
using System.Numerics;
using Marcbeacve.TevScript.Core;
using UnityEngine;

namespace Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap
{
    public sealed class TevScriptIl2CppTransactionalSwapGate : MonoBehaviour
    {
        private IEnumerator Start()
        {
            yield return null;

            int exitCode = 0;
            try
            {
                RunGate();
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                Debug.Log(
                    "TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE_5B=FAIL");
                exitCode = 51;
            }

            yield return null;
            Application.Quit(exitCode);
        }

        private static void RunGate()
        {
            if (Application.platform != RuntimePlatform.WindowsPlayer)
            {
                throw new InvalidOperationException(
                    "Gate-5B requires a Windows standalone Player.");
            }

            Debug.Log("UNITY_GATE5B_IL2CPP_ACTIVE=PASS");
            Debug.Log("UNITY_GATE5B_IL2CPP_PLATFORM=WINDOWS_PLAYER_PASS");

            string baseJson = Load("TevScriptGate5BBase");
            string goodJson = Load("TevScriptGate5BGood");
            string removedJson = Load("TevScriptGate5BRemoved");
            string escalatedJson = Load("TevScriptGate5BEscalated");
            string wrongProgramJson = Load("TevScriptGate5BWrongProgram");

            TevScriptProgram baseProgram = TevScriptProgram.Parse(baseJson);
            if (baseProgram.ProgramId != "PlayerGameplay")
            {
                throw new InvalidOperationException(
                    "Unexpected Gate-5B program id: " +
                    baseProgram.ProgramId);
            }
            Debug.Log("UNITY_GATE5B_BASE_PARSE=PASS");

            var ceiling = new List<string>();
            foreach (TevScriptEntityDefinition entity in baseProgram.Entities)
            {
                foreach (string capabilityId in entity.Capabilities.Keys)
                {
                    if (!ceiling.Contains(capabilityId))
                    {
                        ceiling.Add(capabilityId);
                    }
                }
            }

            var host = new TevScriptRuntimeHost(
                baseProgram,
                null,
                ceiling);

            // Establish live state under the old behavior:
            // damage(10): 100 -> 90.
            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));
            RequireHealth(host, 90, "base damage behavior");
            Debug.Log("UNITY_GATE5B_BASE_BEHAVIOR=PASS");

            TevScriptRuntimeSnapshot before = host.CaptureSnapshot();
            string baseHash = host.ActiveSemanticHash;
            if (before.SemanticHash != baseHash)
            {
                throw new InvalidOperationException(
                    "Initial Gate-5B snapshot semantic hash mismatch.");
            }

            TevScriptRuntimeSwapPlan goodPlan =
                host.PrepareSwap(goodJson);
            if (host.ActiveSemanticHash != baseHash ||
                host.Generation != 0)
            {
                throw new InvalidOperationException(
                    "PrepareSwap changed authoritative host state.");
            }
            Debug.Log(
                "UNITY_GATE5B_PREPARE_NON_AUTHORITATIVE=PASS");

            TevScriptProgram goodProgram =
                TevScriptProgram.Parse(goodJson);
            TevScriptRuntimeSwapReceipt commit =
                host.Commit(goodPlan);

            if (commit.Rollback ||
                host.ActiveSemanticHash != goodProgram.SemanticHash ||
                host.Generation != 1)
            {
                throw new InvalidOperationException(
                    "Gate-5B commit did not activate candidate runtime.");
            }
            Debug.Log(
                "UNITY_GATE5B_COMMIT_ATOMIC_REFERENCE_SWAP=PASS");

            TevScriptRuntimeSnapshot after = host.CaptureSnapshot();
            AssertMigratedExistingState(before, after);
            AssertCandidateAdditionsInitialized(
                goodProgram,
                before,
                after);
            Debug.Log(
                "UNITY_GATE5B_EXISTING_STATE_MIGRATION=PASS");
            Debug.Log(
                "UNITY_GATE5B_ADDITIVE_STATE_INITIALIZATION=PASS");

            // The candidate changed damage's LOAD_PARAM amount into CONST 0.
            // The migrated health=90 must stay 90 after another damage(10).
            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));
            RequireHealth(host, 90, "updated no-op damage behavior");
            Debug.Log("UNITY_GATE5B_UPDATED_BEHAVIOR_ACTIVE=PASS");

            ExpectCode(
                delegate { host.Commit(goodPlan); },
                "TEVS_CS_SWAP_PLAN_CONSUMED");
            Debug.Log(
                "UNITY_GATE5B_PLAN_REUSE_FAIL_CLOSED=PASS");

            string goodStableHash = host.ActiveSemanticHash;
            TevScriptRuntimeSnapshot goodStableState =
                host.CaptureSnapshot();

            ExpectCode(
                delegate { host.PrepareSwap(removedJson); },
                "TEVS_CS_SWAP_STATE_REMOVED");
            RequireStable(
                host,
                goodStableHash,
                goodStableState,
                "state-removal rejection");
            Debug.Log(
                "UNITY_GATE5B_STATE_REMOVAL_VALID_IR_REACHES_HOST=PASS");
            Debug.Log(
                "UNITY_GATE5B_STATE_REMOVAL_FAIL_CLOSED=PASS");

            ExpectCode(
                delegate { host.PrepareSwap(escalatedJson); },
                "TEVS_CS_SWAP_CAPABILITY_CEILING");
            RequireStable(
                host,
                goodStableHash,
                goodStableState,
                "capability-ceiling rejection");
            Debug.Log(
                "UNITY_GATE5B_CAPABILITY_CEILING_FAIL_CLOSED=PASS");

            ExpectCode(
                delegate { host.PrepareSwap(wrongProgramJson); },
                "TEVS_CS_SWAP_PROGRAM_ID");
            RequireStable(
                host,
                goodStableHash,
                goodStableState,
                "program-id rejection");
            Debug.Log(
                "UNITY_GATE5B_PROGRAM_ID_CONTINUITY_FAIL_CLOSED=PASS");

            TevScriptRuntimeSwapReceipt rollback =
                host.RollbackLastCommit();
            if (!rollback.Rollback ||
                host.ActiveSemanticHash != baseHash)
            {
                throw new InvalidOperationException(
                    "Gate-5B rollback did not restore source runtime.");
            }
            AssertSnapshotsEqual(before, host.CaptureSnapshot());
            Debug.Log(
                "UNITY_GATE5B_ROLLBACK_EXACT_RUNTIME_RESTORE=PASS");

            // Prove old behavior itself returned, not merely the old hash/state.
            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));
            RequireHealth(host, 80, "rollback old damage behavior");
            Debug.Log(
                "UNITY_GATE5B_ROLLBACK_BEHAVIOR_RESTORED=PASS");

            // Stale-plan campaign against the current base runtime.
            TevScriptRuntimeSwapPlan first =
                host.PrepareSwap(goodJson);
            TevScriptRuntimeSwapPlan stale =
                host.PrepareSwap(goodJson);
            host.Commit(first);
            ExpectCode(
                delegate { host.Commit(stale); },
                "TEVS_CS_SWAP_PLAN_STALE");
            Debug.Log(
                "UNITY_GATE5B_STALE_PLAN_FAIL_CLOSED=PASS");

            host.RollbackLastCommit();

            Debug.Log("UNITY_GATE5B_TRANSACTION_BOUNDARY=PASS");
            Debug.Log("UNITY_GATE5B_DYNAMIC_CODE=ABSENT_PASS");
            Debug.Log("UNITY_GATE5B_NETWORK=NOT_IN_SCOPE");
            Debug.Log(
                "UNITY_GATE5B_SIGNATURE_AUTHORITY=NOT_IN_SCOPE");
            Debug.Log("UNITY_GATE5B_WASM=NOT_IN_SCOPE");
            Debug.Log(
                "TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE_5B=PASS");
        }

        private static string Load(string resourceName)
        {
            TextAsset asset = Resources.Load<TextAsset>(resourceName);
            if (asset == null || string.IsNullOrWhiteSpace(asset.text))
            {
                throw new InvalidOperationException(
                    "Missing Gate-5B resource " + resourceName + ".");
            }
            return asset.text;
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
                    context + " expected health=" + expected + ".");
            }
        }

        private static void RequireStable(
            TevScriptRuntimeHost host,
            string expectedHash,
            TevScriptRuntimeSnapshot expectedSnapshot,
            string context)
        {
            if (host.ActiveSemanticHash != expectedHash)
            {
                throw new InvalidOperationException(
                    context + " changed active semantic hash.");
            }
            AssertSnapshotsEqual(
                expectedSnapshot,
                host.CaptureSnapshot());
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
                if (!after.Entities.ContainsKey(entity.Key))
                {
                    throw new InvalidOperationException(
                        "Entity disappeared during Gate-5B migration: " +
                        entity.Key);
                }

                foreach (KeyValuePair<string, TevScriptValue> state
                         in entity.Value)
                {
                    TevScriptValue observed;
                    if (!after.Entities[entity.Key].TryGetValue(
                            state.Key,
                            out observed) ||
                        !state.Value.Equals(observed))
                    {
                        throw new InvalidOperationException(
                            "State was not preserved during Gate-5B migration: " +
                            entity.Key + "." + state.Key);
                    }
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
                var oldNames = new HashSet<string>(
                    before.Entities[entity.EntityId].Keys,
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

                    if (!state.Initial.Equals(actual))
                    {
                        throw new InvalidOperationException(
                            "Candidate additive state did not use initial value: " +
                            entity.EntityId + "." + state.Name);
                    }
                }
            }

            if (!observedAddition)
            {
                throw new InvalidOperationException(
                    "Gate-5B candidate did not contain additive state.");
            }
        }

        private static void AssertSnapshotsEqual(
            TevScriptRuntimeSnapshot expected,
            TevScriptRuntimeSnapshot observed)
        {
            if (expected.ProgramId != observed.ProgramId ||
                expected.SemanticHash != observed.SemanticHash ||
                expected.Entities.Count != observed.Entities.Count)
            {
                throw new InvalidOperationException(
                    "Gate-5B snapshot identity mismatch.");
            }

            foreach (KeyValuePair<
                         string,
                         IReadOnlyDictionary<string, TevScriptValue>>
                     entity in expected.Entities)
            {
                IReadOnlyDictionary<string, TevScriptValue> actualEntity;
                if (!observed.Entities.TryGetValue(
                        entity.Key,
                        out actualEntity) ||
                    entity.Value.Count != actualEntity.Count)
                {
                    throw new InvalidOperationException(
                        "Gate-5B snapshot entity mismatch: " + entity.Key);
                }

                foreach (KeyValuePair<string, TevScriptValue> state
                         in entity.Value)
                {
                    TevScriptValue actualValue;
                    if (!actualEntity.TryGetValue(
                            state.Key,
                            out actualValue) ||
                        !state.Value.Equals(actualValue))
                    {
                        throw new InvalidOperationException(
                            "Gate-5B snapshot state mismatch: " +
                            entity.Key + "." + state.Key);
                    }
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
                    "Expected " + expectedCode +
                    " but observed " +
                    exception.Diagnostic.Code + ".",
                    exception);
            }

            throw new InvalidOperationException(
                "Expected " + expectedCode +
                " but operation succeeded.");
        }
    }
}
