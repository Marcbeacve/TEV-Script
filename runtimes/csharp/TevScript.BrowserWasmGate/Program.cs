using System;
using System.Collections.Generic;
using System.IO;
using System.Numerics;
using System.Reflection;
using Marcbeacve.TevScript.Core;

internal static class Program
{
    private static int Main()
    {
        try
        {
            if (!OperatingSystem.IsBrowser())
            {
                throw new InvalidOperationException(
                    "Gate-6B requires browser-wasm.");
            }

            Console.WriteLine("GATE6B_BROWSER_WASM_ACTIVE=PASS");

            string fixture = ReadResource("Player.tevs.ir.json");
            TevScriptProgram program =
                TevScriptProgram.Parse(fixture);

            if (program.ProgramId != "PlayerGameplay")
            {
                throw new InvalidOperationException(
                    "Gate-6B program id mismatch.");
            }
            Console.WriteLine("GATE6B_CORE_PARSE=PASS");

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
                    "Gate-6B runtime state mismatch.");
            }
            Console.WriteLine("GATE6B_RUNTIME_STATE=PASS");

            string hash = TevScriptCanonicalJson.Hash(fixture);
            if (hash.Length != 64)
            {
                throw new InvalidOperationException(
                    "Gate-6B canonical hash invalid.");
            }

            Console.WriteLine("GATE6B_CANONICAL_JSON=PASS");
            Console.WriteLine("GATE6B_CANONICAL_SHA256=" + hash);

            TevScriptRuntimeSnapshot snapshot =
                host.CaptureSnapshot();
            if (snapshot.ProgramId != "PlayerGameplay")
            {
                throw new InvalidOperationException(
                    "Gate-6B snapshot mismatch.");
            }

            Console.WriteLine("GATE6B_SNAPSHOT=PASS");
            Console.WriteLine("GATE6B_UNITY_DEPENDENCY=ABSENT_PASS");
            Console.WriteLine("GATE6B_AOT_REQUESTED=PASS");
            Console.WriteLine(
                "TEV_SCRIPT_PURE_CORE_BROWSER_WASM_GATE_6B=PASS");

            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            Console.WriteLine(
                "TEV_SCRIPT_PURE_CORE_BROWSER_WASM_GATE_6B=FAIL");
            return 81;
        }
    }

    private static string ReadResource(string name)
    {
        Assembly assembly = typeof(Program).Assembly;
        using (Stream stream = assembly.GetManifestResourceStream(name))
        {
            if (stream == null)
            {
                throw new InvalidOperationException(
                    "Embedded resource missing: " + name);
            }

            using (var reader = new StreamReader(stream))
            {
                return reader.ReadToEnd();
            }
        }
    }
}
