using System;
using System.IO;
using System.Linq;
using System.Text;
using Marcbeacve.TevScript.Core;
using UnityEditor.PackageManager;
using UnityEngine;

namespace Marcbeacve.TevScript.Unity.Editor
{
    public static class TevScriptUnityEditorGate
    {
        private static readonly UTF8Encoding StrictUtf8 =
            new UTF8Encoding(false, true);

        private sealed class Vector
        {
            public Vector(string id, string program)
            {
                Id = id;
                Program = program;
            }

            public string Id { get; }
            public string Program { get; }
        }

        private static readonly Vector[] Vectors =
        {
            new Vector("player", "Player.tevs.ir.json"),
            new Vector("matrix", "ConformanceMatrix.tevs.ir.json"),
            new Vector("player-idle", "Player.tevs.ir.json"),
            new Vector("event-chain", "EventChain.tevs.ir.json")
        };

        public static void Run()
        {
            PackageInfo package = PackageInfo.FindForAssembly(
                typeof(TevScriptUnityEditorGate).Assembly);
            if (package == null)
                throw new InvalidOperationException(
                    "TEV Script package is not registered in the Unity project.");

            string root = package.resolvedPath;
            Debug.Log("UNITY_VERSION=" + Application.unityVersion);
            Debug.Log("UNITY_TEV_SCRIPT_PACKAGE=" + package.version);

            string canonicalVectors = ReadStrictUtf8(Path.Combine(
                root,
                "Tests",
                "Fixtures",
                "conformance",
                "canonical.vectors.json"));
            int canonicalCount =
                TevScriptCanonicalJson.VerifyVectorSet(canonicalVectors);
            if (canonicalCount != 12)
                throw new InvalidOperationException(
                    "Expected 12 canonical vectors, got " + canonicalCount + ".");
            Debug.Log("UNITY_CANONICAL_VECTORS=12_PASS");

            foreach (Vector vector in Vectors)
            {
                string programJson = ReadStrictUtf8(Path.Combine(
                    root,
                    "Tests",
                    "Fixtures",
                    "examples",
                    vector.Program));
                string scenarioJson = ReadStrictUtf8(Path.Combine(
                    root,
                    "Tests",
                    "Fixtures",
                    "conformance",
                    vector.Id + ".scenario.json"));
                byte[] expected = File.ReadAllBytes(Path.Combine(
                    root,
                    "Tests",
                    "Fixtures",
                    "conformance",
                    vector.Id + ".expected.json"));
                string receipt = TevScriptConformance.RunCanonicalReceipt(
                    programJson,
                    scenarioJson);
                byte[] observed = StrictUtf8.GetBytes(receipt);
                if (!observed.SequenceEqual(expected))
                    throw new InvalidOperationException(
                        "Unity receipt mismatch for " + vector.Id + ".");

                Debug.Log(
                    "UNITY_" + Marker(vector.Id) + "_BYTE_PARITY=PASS");
            }

            VerifySemanticHashTamperingFails(root);
            VerifyMissingCapabilityFailsClosed(root);
            VerifyStrictUtf8Decoder();

            Debug.Log("UNITY_CSHARP_CORE_CONFORMANCE_SCENARIOS=4_PASS");
            Debug.Log("UNITY_THREE_RUNTIME_REFERENCE_PARITY=PASS");
            Debug.Log("UNITY_HOST_SEMANTIC_DRIFT=NONE_OBSERVED");
            Debug.Log("UNITY_PLAYMODE=NOT_PROBED");
            Debug.Log("UNITY_MONO_PLAYER=NOT_PROBED");
            Debug.Log("UNITY_IL2CPP=NOT_PROBED");
            Debug.Log("TEV_SCRIPT_UNITY_EDITOR_GATE_1=PASS");
        }

        private static void VerifySemanticHashTamperingFails(string root)
        {
            string program = ReadStrictUtf8(Path.Combine(
                root,
                "Tests",
                "Fixtures",
                "examples",
                "Player.tevs.ir.json"));
            TevScriptProgram parsed = TevScriptProgram.Parse(program);
            string tampered = program.Replace(
                parsed.SemanticHash,
                new string('0', 64));
            ExpectContract(
                "TEVS_CS_PROGRAM_HASH",
                () => TevScriptProgram.Parse(tampered));
            Debug.Log("UNITY_SEMANTIC_HASH_TAMPERING_FAIL_CLOSED=PASS");
        }

        private static void VerifyMissingCapabilityFailsClosed(string root)
        {
            string program = ReadStrictUtf8(Path.Combine(
                root,
                "Tests",
                "Fixtures",
                "examples",
                "Player.tevs.ir.json"));
            var runtime = new TevScriptRuntime(TevScriptProgram.Parse(program));
            ExpectContract(
                "TEVS_CS_CAPABILITY_MISSING",
                () => runtime.Invoke("Player", "update"));
            Debug.Log("UNITY_MISSING_CAPABILITY_FAIL_CLOSED=PASS");
        }

        private static void VerifyStrictUtf8Decoder()
        {
            try
            {
                StrictUtf8.GetString(new byte[] { 0xC3, 0x28 });
            }
            catch (DecoderFallbackException)
            {
                Debug.Log("UNITY_STRICT_UTF8_BOUNDARY=PASS");
                return;
            }

            throw new InvalidOperationException(
                "Strict UTF-8 decoder accepted malformed input.");
        }

        private static void ExpectContract(string code, Action action)
        {
            try
            {
                action();
            }
            catch (TevContractException error)
            {
                if (error.Diagnostic.Code == code)
                    return;
                throw new InvalidOperationException(
                    "Expected " + code + ", got " +
                    error.Diagnostic.Code + ".",
                    error);
            }

            throw new InvalidOperationException(
                "Expected contract failure " + code + ".");
        }

        private static string ReadStrictUtf8(string path)
        {
            return StrictUtf8.GetString(File.ReadAllBytes(path));
        }

        private static string Marker(string id)
        {
            return id.Replace('-', '_').ToUpperInvariant();
        }
    }
}
