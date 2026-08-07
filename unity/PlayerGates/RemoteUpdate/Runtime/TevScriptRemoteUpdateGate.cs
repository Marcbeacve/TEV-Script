using System;
using System.Collections;
using System.Collections.Generic;
using System.Numerics;
using Marcbeacve.TevScript.Core;
using Marcbeacve.TevScript.Update;
using UnityEngine;
using UnityEngine.Networking;

namespace Marcbeacve.TevScript.Gate5E.RemoteUpdate
{
    public sealed class TevScriptRemoteUpdateGate : MonoBehaviour
    {
        [Serializable]
        private sealed class KeyAuthority
        {
            public string schema;
            public string algorithm;
            public string key_id;
            public string x;
            public string y;
        }

        private IEnumerator Start()
        {
            yield return null;

            var stack = new Stack<IEnumerator>();
            stack.Push(RunGate());
            Exception failure = null;

            while (stack.Count > 0 && failure == null)
            {
                IEnumerator currentRoutine = stack.Peek();
                bool moved = false;
                object current = null;

                try
                {
                    moved = currentRoutine.MoveNext();
                    if (moved)
                    {
                        current = currentRoutine.Current;
                    }
                }
                catch (Exception exception)
                {
                    failure = exception;
                }

                if (failure != null)
                {
                    break;
                }

                if (!moved)
                {
                    stack.Pop();
                    continue;
                }

                IEnumerator nested = current as IEnumerator;
                if (nested != null)
                {
                    stack.Push(nested);
                    continue;
                }

                // The actual yield is deliberately outside try/catch.
                yield return current;
            }

            int exitCode = 0;
            if (failure != null)
            {
                Debug.LogException(failure);
                Debug.Log("TEV_SCRIPT_REMOTE_TRANSPORT_GATE_5E=FAIL");
                exitCode = 71;
            }

            yield return null;
            Application.Quit(exitCode);
        }

        private IEnumerator RunGate()
        {
            if (Application.platform != RuntimePlatform.WindowsPlayer)
            {
                throw new InvalidOperationException(
                    "Gate-5E requires a Windows standalone Player.");
            }

            string baseUrl = Environment.GetEnvironmentVariable(
                "TEV_SCRIPT_GATE5E_BASE_URL");
            string storePath = Environment.GetEnvironmentVariable(
                "TEV_SCRIPT_GATE5E_STORE_PATH");
            string mode = Environment.GetEnvironmentVariable(
                "TEV_SCRIPT_GATE5E_MODE");

            if (string.IsNullOrWhiteSpace(baseUrl) ||
                string.IsNullOrWhiteSpace(storePath) ||
                string.IsNullOrWhiteSpace(mode))
            {
                throw new InvalidOperationException(
                    "Gate-5E environment contract is incomplete.");
            }

            Debug.Log("UNITY_GATE5E_REMOTE_PLAYER_ACTIVE=PASS");

            TextAsset baseAsset =
                Resources.Load<TextAsset>("TevScriptGate5EBase");
            TextAsset authorityAsset =
                Resources.Load<TextAsset>("TevScriptGate5EAuthority");
            if (baseAsset == null || authorityAsset == null)
            {
                throw new InvalidOperationException(
                    "Gate-5E embedded resources are missing.");
            }

            KeyAuthority key = JsonUtility.FromJson<KeyAuthority>(
                authorityAsset.text);
            if (key == null ||
                key.schema != "TEV_SCRIPT_UPDATE_KEY_AUTHORITY_V1" ||
                key.algorithm != "ES256")
            {
                throw new InvalidOperationException(
                    "Gate-5E key authority resource is invalid.");
            }

            TevScriptProgram baseProgram =
                TevScriptProgram.Parse(baseAsset.text);
            var host = new TevScriptRuntimeHost(
                baseProgram,
                null,
                CapabilityCeiling(baseProgram));
            var verifier =
                new TevWindowsCngEcdsaP256Sha256Verifier(
                    key.key_id,
                    key.x,
                    key.y);
            Debug.Log(
                "UNITY_GATE5E_SIGNATURE_PROVIDER=WINDOWS_CNG_BOUND");
            var store = new TevFileInstalledUpdateStore(storePath);
            var authority = new TevScriptUpdateAuthority(
                host,
                "stable",
                verifier,
                store);

            if (mode == "first")
            {
                yield return RunFirst(baseUrl, host, authority);
            }
            else if (mode == "restore")
            {
                yield return RunRestore(baseUrl, host, authority);
            }
            else
            {
                throw new InvalidOperationException(
                    "Unknown Gate-5E mode " + mode + ".");
            }

            Debug.Log("TEV_SCRIPT_REMOTE_TRANSPORT_GATE_5E=PASS");
        }

        private static IEnumerator RunFirst(
            string baseUrl,
            TevScriptRuntimeHost host,
            TevScriptUpdateAuthority authority)
        {
            string package1 = null;
            yield return FetchOk(
                baseUrl + "/package1",
                delegate(string value) { package1 = value; });

            TevScriptUpdateReceipt first =
                authority.Commit(authority.Prepare(package1));
            if (first.Epoch != 1 || first.Sequence != 1)
                throw new InvalidOperationException(
                    "Gate-5E package1 metadata mismatch.");

            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));
            RequireHealth(host, 100, "remote package1");
            Debug.Log(
                "UNITY_GATE5E_SIGNATURE_PROVIDER_WINDOWS_CNG=PASS");
            Debug.Log(
                "UNITY_GATE5E_REMOTE_PACKAGE1_ACTIVATED=PASS");

            ExpectCode(
                delegate { authority.Prepare(package1); },
                "TEVS_CS_UPDATE_REPLAY");
            Debug.Log(
                "UNITY_GATE5E_REMOTE_REPLAY_FAIL_CLOSED=PASS");

            string tampered = null;
            yield return FetchOk(
                baseUrl + "/tampered",
                delegate(string value) { tampered = value; });
            ExpectCode(
                delegate { authority.Prepare(tampered); },
                "TEVS_CS_UPDATE_SIGNATURE_INVALID");
            RequireHealth(host, 100, "tamper stability");
            Debug.Log(
                "UNITY_GATE5E_REMOTE_TAMPER_FAIL_CLOSED=PASS");

            string truncated = null;
            yield return FetchOk(
                baseUrl + "/truncated",
                delegate(string value) { truncated = value; });
            bool rejected = false;
            try
            {
                authority.Prepare(truncated);
            }
            catch (TevContractException)
            {
                rejected = true;
            }
            if (!rejected)
                throw new InvalidOperationException(
                    "Truncated remote package was accepted.");
            RequireHealth(host, 100, "truncated stability");
            Debug.Log(
                "UNITY_GATE5E_TRUNCATED_PACKAGE_FAIL_CLOSED=PASS");

            using (UnityWebRequest request =
                UnityWebRequest.Get(baseUrl + "/status500"))
            {
                yield return request.SendWebRequest();
                if (request.result !=
                    UnityWebRequest.Result.ProtocolError)
                {
                    throw new InvalidOperationException(
                        "Expected HTTP protocol error.");
                }
            }
            RequireHealth(host, 100, "HTTP error stability");
            Debug.Log(
                "UNITY_GATE5E_HTTP_ERROR_FAIL_CLOSED=PASS");

            string package2 = null;
            yield return FetchOk(
                baseUrl + "/package2",
                delegate(string value) { package2 = value; });

            TevScriptUpdateReceipt second =
                authority.Commit(authority.Prepare(package2));
            if (second.Epoch != 1 || second.Sequence != 2)
                throw new InvalidOperationException(
                    "Gate-5E package2 metadata mismatch.");

            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));
            RequireHealth(host, 99, "remote package2");
            Debug.Log(
                "UNITY_GATE5E_REMOTE_PACKAGE2_ACTIVATED=PASS");
            Debug.Log(
                "UNITY_GATE5E_DURABLE_INSTALL_WRITTEN=PASS");
        }

        private static IEnumerator RunRestore(
            string baseUrl,
            TevScriptRuntimeHost host,
            TevScriptUpdateAuthority authority)
        {
            TevScriptUpdateReceipt restored;
            if (!authority.TryRestoreInstalled(out restored) ||
                !restored.Restore ||
                restored.Epoch != 1 ||
                restored.Sequence != 2)
            {
                throw new InvalidOperationException(
                    "Gate-5E durable restore failed.");
            }

            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));
            RequireHealth(host, 99, "restored package2");
            Debug.Log(
                "UNITY_GATE5E_RESTART_PACKAGE_RESTORE=PASS");

            string package2 = null;
            yield return FetchOk(
                baseUrl + "/package2",
                delegate(string value) { package2 = value; });
            ExpectCode(
                delegate { authority.Prepare(package2); },
                "TEVS_CS_UPDATE_REPLAY");
            RequireHealth(host, 99, "restart replay stability");
            Debug.Log(
                "UNITY_GATE5E_REPLAY_AFTER_RESTART_FAIL_CLOSED=PASS");

            string epoch2 = null;
            yield return FetchOk(
                baseUrl + "/epoch2",
                delegate(string value) { epoch2 = value; });

            TevScriptUpdateReceipt next =
                authority.Commit(authority.Prepare(epoch2));
            if (next.Epoch != 2 || next.Sequence != 1)
                throw new InvalidOperationException(
                    "Gate-5E epoch2 metadata mismatch.");

            host.Invoke(
                "Player",
                "damage",
                TevScriptValue.Int(new BigInteger(10)));
            RequireHealth(host, 97, "remote epoch2");
            Debug.Log(
                "UNITY_GATE5E_REMOTE_EPOCH2_ACTIVATED=PASS");
            Debug.Log(
                "UNITY_GATE5E_DURABLE_REPLAY_STATE=PASS");
        }

        private static IEnumerator FetchOk(
            string url,
            Action<string> onSuccess)
        {
            using (UnityWebRequest request = UnityWebRequest.Get(url))
            {
                yield return request.SendWebRequest();
                if (request.result !=
                    UnityWebRequest.Result.Success)
                {
                    throw new InvalidOperationException(
                        "GET failed: " + request.result + " " + url);
                }

                string text = request.downloadHandler.text;
                if (string.IsNullOrEmpty(text))
                    throw new InvalidOperationException(
                        "Gate-5E returned empty bytes.");
                onSuccess(text);
            }
        }

        private static string[] CapabilityCeiling(
            TevScriptProgram program)
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
    }
}
