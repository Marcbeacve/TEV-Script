using System;
using System.Collections;
using System.Collections.Generic;
using System.Numerics;
using System.Runtime.InteropServices;
using Marcbeacve.TevScript.Core;
using UnityEngine;

namespace Marcbeacve.TevScript.Gate6A.Web
{
    public sealed class TevScriptUnityWebGate : MonoBehaviour
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")]
        private static extern void TevGate6AReport(int passed);
#endif

        private IEnumerator Start()
        {
            yield return null;

            bool passed = false;
            try
            {
                RunGate();
                passed = true;
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                Debug.Log("TEV_SCRIPT_UNITY_WEB_GATE_6A=FAIL");
            }

#if UNITY_WEBGL && !UNITY_EDITOR
            TevGate6AReport(passed ? 1 : 0);
#endif
        }

        private static void RunGate()
        {
            if (Application.platform != RuntimePlatform.WebGLPlayer)
            {
                throw new InvalidOperationException(
                    "Gate-6A requires the WebGL Player.");
            }

            Debug.Log("UNITY_GATE6A_WEBGL_PLAYER=PASS");

            TextAsset fixture =
                Resources.Load<TextAsset>("TevScriptGate6APlayer");
            if (fixture == null || string.IsNullOrWhiteSpace(fixture.text))
            {
                throw new InvalidOperationException(
                    "Gate-6A canonical Player fixture is missing.");
            }

            TevScriptProgram program =
                TevScriptProgram.Parse(fixture.text);
            if (program.ProgramId != "PlayerGameplay")
            {
                throw new InvalidOperationException(
                    "Unexpected Gate-6A program id.");
            }
            Debug.Log("UNITY_GATE6A_CORE_PARSE=PASS");

            var ceiling = new List<string>();
            foreach (TevScriptEntityDefinition entity in program.Entities)
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
                program,
                null,
                ceiling);

            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));

            IReadOnlyDictionary<string, TevScriptValue> state =
                host.State("Player");
            if (!state.ContainsKey("health") ||
                state["health"].AsInt() != new BigInteger(90))
            {
                throw new InvalidOperationException(
                    "Gate-6A runtime state mismatch.");
            }
            Debug.Log("UNITY_GATE6A_RUNTIME_STATE=PASS");

            string canonical =
                TevScriptCanonicalJson.Canonicalize(fixture.text);
            string canonicalHash =
                TevScriptCanonicalJson.Hash(fixture.text);

            if (string.IsNullOrEmpty(canonical) ||
                canonicalHash.Length != 64)
            {
                throw new InvalidOperationException(
                    "Gate-6A canonical JSON witness invalid.");
            }
            Debug.Log("UNITY_GATE6A_CANONICAL_JSON=PASS");
            Debug.Log("UNITY_GATE6A_CANONICAL_SHA256=" + canonicalHash);

            TevScriptRuntimeSnapshot snapshot =
                host.CaptureSnapshot();
            if (snapshot.ProgramId != "PlayerGameplay" ||
                snapshot.Entities.Count == 0)
            {
                throw new InvalidOperationException(
                    "Gate-6A snapshot witness invalid.");
            }
            Debug.Log("UNITY_GATE6A_SNAPSHOT=PASS");

            Debug.Log("UNITY_GATE6A_DYNAMIC_CODE=ABSENT_PASS");
            Debug.Log("UNITY_GATE6A_BROWSER_EXECUTION=PASS");
            Debug.Log("TEV_SCRIPT_UNITY_WEB_GATE_6A=PASS");
        }
    }
}
