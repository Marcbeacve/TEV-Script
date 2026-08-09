using System;
using System.Collections.Generic;
using System.IO;
using System.Numerics;
using System.Reflection;
using System.Runtime.InteropServices.JavaScript;
using System.Text;
using System.Text.Json;
using Marcbeacve.TevScript.Core;
using Marcbeacve.TevScript.Update;

internal static partial class BrowserInterop
{
    [JSImport("globalThis.tevGate6DPhase")]
    internal static partial string Phase();

    [JSImport("globalThis.tevGate6DStoreLoad")]
    internal static partial string StoreLoad(string key);

    [JSImport("globalThis.tevGate6DStoreSave")]
    internal static partial void StoreSave(string key, string value);

    [JSImport("globalThis.tevGate6DStoreRemove")]
    internal static partial void StoreRemove(string key);
}

internal sealed class BrowserInstalledUpdateStore : ITevInstalledUpdateStore
{
    private const string Prefix = "tev-script-gate6d-installed:";

    public TevInstalledUpdateRecord Load(string channelId)
    {
        string json = BrowserInterop.StoreLoad(Key(channelId));
        if (string.IsNullOrEmpty(json)) return null;
        TevInstalledUpdateRecord record = TevInstalledUpdateRecord.Parse(json);
        if (!string.Equals(record.ChannelId, channelId, StringComparison.Ordinal))
            throw new TevContractException(
                "TEVS_CS_UPDATE_STORE_CHANNEL",
                "Browser durable record belongs to another channel.");
        return record;
    }

    public void Save(TevInstalledUpdateRecord record)
    {
        if (record == null) throw new ArgumentNullException(nameof(record));
        BrowserInterop.StoreSave(Key(record.ChannelId), record.ToCanonicalJson());
    }

    internal static void Clear(string channelId)
    {
        BrowserInterop.StoreRemove(Key(channelId));
    }

    private static string Key(string channelId) { return Prefix + channelId; }
}

internal static class Program
{
    private const string Channel = "stable";

    private static int Main()
    {
        string phase = "unresolved";
        try
        {
            if (!OperatingSystem.IsBrowser())
                throw new InvalidOperationException("Gate-6D Browser requires browser-wasm.");

            phase = BrowserInterop.Phase();
            if (phase != "fresh" && phase != "restore")
                throw new InvalidOperationException("Gate-6D Browser phase invalid: " + phase);

            AuthorityConfig authority = LoadAuthority("authority.json");
            AuthorityConfig wrongAuthority = LoadAuthority("wrong_authority.json");
            var verifier = new TevManagedEcdsaP256Sha256Verifier(
                authority.KeyId, authority.X, authority.Y);
            var wrongVerifier = new TevManagedEcdsaP256Sha256Verifier(
                wrongAuthority.KeyId, wrongAuthority.X, wrongAuthority.Y);

            RunSignatureBoundary(verifier, wrongVerifier);
            RunStoreFailureRollback(verifier);

            if (phase == "fresh") RunFresh(verifier);
            else RunRestore(verifier);

            EmitWebCryptoOracle(authority, "package1.json");
            Console.WriteLine("GATE6D_BROWSER_PHASE=" + phase);
            Console.WriteLine("GATE6D_BROWSER_MANAGED_ES256=PASS");
            Console.WriteLine("GATE6D_BROWSER_UPDATE_AUTHORITY=SAME_TEV_AUTHORITY_PASS");
            Console.WriteLine("TEV_SCRIPT_BROWSER_WASM_SIGNED_UPDATE_GATE_6D=PASS");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            Console.WriteLine("GATE6D_BROWSER_FAILURE_PHASE=" + phase);
            TevContractException contract = exception as TevContractException;
            if (contract != null)
                Console.WriteLine("GATE6D_BROWSER_FAILURE_CODE=" + contract.Diagnostic.Code);
            Console.WriteLine("GATE6D_BROWSER_FAILURE_TYPE=" + exception.GetType().Name);
            Console.WriteLine("TEV_SCRIPT_BROWSER_WASM_SIGNED_UPDATE_GATE_6D=FAIL");
            return 101;
        }
    }

    private static void RunSignatureBoundary(
        ITevUpdateSignatureVerifier verifier,
        ITevUpdateSignatureVerifier wrongVerifier)
    {
        TevScriptSignedUpdatePackage p1 = Package("package1.json");
        p1.VerifySignature(verifier);
        Console.WriteLine("GATE6D_BROWSER_VALID_SIGNATURE=PASS");

        ExpectCode(delegate { Package("package_tampered.json").VerifySignature(verifier); },
            "TEVS_CS_UPDATE_SIGNATURE_INVALID");
        ExpectCode(delegate { Package("package_wrong_key.json").VerifySignature(verifier); },
            "TEVS_CS_UPDATE_SIGNATURE_INVALID");
        ExpectCode(delegate { p1.VerifySignature(wrongVerifier); },
            "TEVS_CS_UPDATE_KEY_AUTHORITY");
        ExpectCode(delegate { Package("package_unknown_algorithm.json").VerifySignature(verifier); },
            "TEVS_CS_UPDATE_SIGNATURE_ALGORITHM");
        Console.WriteLine("GATE6D_BROWSER_SIGNATURE_NEGATIVES=FAIL_CLOSED_PASS");
    }

    private static void RunStoreFailureRollback(ITevUpdateSignatureVerifier verifier)
    {
        TevScriptProgram baseProgram = TevScriptProgram.Parse(ReadResource("base.json"));
        var host = new TevScriptRuntimeHost(baseProgram, null, CapabilityCeiling(baseProgram));
        string before = host.ActiveSemanticHash;
        var authority = new TevScriptUpdateAuthority(host, Channel, verifier, new FailingStore());
        TevScriptUpdatePlan plan = authority.Prepare(ReadResource("package1.json"));
        ExpectCode(delegate { authority.Commit(plan); }, "TEVS_CS_UPDATE_STORE_COMMIT");
        if (!string.Equals(host.ActiveSemanticHash, before, StringComparison.Ordinal))
            throw new InvalidOperationException("Browser store-failure rollback changed active program.");
        Console.WriteLine("GATE6D_BROWSER_STORE_FAILURE_RUNTIME_ROLLBACK=PASS");
    }

    private static void RunFresh(ITevUpdateSignatureVerifier verifier)
    {
        BrowserInstalledUpdateStore.Clear(Channel);
        TevScriptProgram baseProgram = TevScriptProgram.Parse(ReadResource("base.json"));
        var host = new TevScriptRuntimeHost(baseProgram, null, CapabilityCeiling(baseProgram));
        var store = new BrowserInstalledUpdateStore();
        var authority = new TevScriptUpdateAuthority(host, Channel, verifier, store);

        TevScriptUpdatePlan p1 = authority.Prepare(ReadResource("package1.json"));
        if (store.Load(Channel) != null || host.ActiveSemanticHash != baseProgram.SemanticHash)
            throw new InvalidOperationException("Browser Prepare became authoritative.");
        authority.Commit(p1);
        InvokeDamageAndRequire(host, 100, "browser package1");
        ExpectCode(delegate { authority.Prepare(ReadResource("package1.json")); }, "TEVS_CS_UPDATE_REPLAY");

        authority.Commit(authority.Prepare(ReadResource("package2.json")));
        InvokeDamageAndRequire(host, 99, "browser package2");
        TevInstalledUpdateRecord record = store.Load(Channel);
        if (record == null || record.Epoch != 1 || record.Sequence != 2)
            throw new InvalidOperationException("Browser durable cursor mismatch after phase fresh.");

        Console.WriteLine("GATE6D_BROWSER_PREPARE_NON_AUTHORITATIVE=PASS");
        Console.WriteLine("GATE6D_BROWSER_REPLAY_FAIL_CLOSED=PASS");
        Console.WriteLine("GATE6D_BROWSER_DURABLE_PHASE1=PASS");
    }

    private static void RunRestore(ITevUpdateSignatureVerifier verifier)
    {
        TevScriptProgram baseProgram = TevScriptProgram.Parse(ReadResource("base.json"));
        var host = new TevScriptRuntimeHost(baseProgram, null, CapabilityCeiling(baseProgram));
        var store = new BrowserInstalledUpdateStore();
        var authority = new TevScriptUpdateAuthority(host, Channel, verifier, store);

        TevInstalledUpdateRecord persisted = store.Load(Channel);
        if (persisted == null)
        {
            Console.WriteLine("GATE6D_BROWSER_RESTORE_STORE_RECORD=MISSING");
            throw new InvalidOperationException("Browser durable restore record missing after process restart.");
        }
        Console.WriteLine(
            "GATE6D_BROWSER_RESTORE_STORE_RECORD=PRESENT epoch=" +
            persisted.Epoch + " sequence=" + persisted.Sequence);

        TevScriptUpdateReceipt restored;
        if (!authority.TryRestoreInstalled(out restored) || !restored.Restore ||
            restored.Epoch != 1 || restored.Sequence != 2)
            throw new InvalidOperationException("Browser durable restore failed.");
        InvokeDamageAndRequire(host, 99, "browser restored package2");
        ExpectCode(delegate { authority.Prepare(ReadResource("package2.json")); }, "TEVS_CS_UPDATE_REPLAY");

        TevScriptUpdateReceipt epoch2 = authority.Commit(
            authority.Prepare(ReadResource("package_epoch2.json")));
        if (epoch2.Epoch != 2 || epoch2.Sequence != 1)
            throw new InvalidOperationException("Browser epoch transition mismatch.");
        InvokeDamageAndRequire(host, 97, "browser epoch2");

        Console.WriteLine("GATE6D_BROWSER_DURABLE_RESTORE=PASS");
        Console.WriteLine("GATE6D_BROWSER_REPLAY_AFTER_RESTORE_FAIL_CLOSED=PASS");
        Console.WriteLine("GATE6D_BROWSER_EPOCH_ADVANCE=PASS");
    }

    private static void EmitWebCryptoOracle(AuthorityConfig authority, string packageName)
    {
        TevScriptSignedUpdatePackage package = Package(packageName);
        Console.WriteLine("GATE6D_ORACLE_X=" + authority.X);
        Console.WriteLine("GATE6D_ORACLE_Y=" + authority.Y);
        Console.WriteLine("GATE6D_ORACLE_BODY_BASE64=" +
            Convert.ToBase64String(Encoding.UTF8.GetBytes(package.SignedBodyJson)));
        Console.WriteLine("GATE6D_ORACLE_SIGNATURE_BASE64=" +
            Convert.ToBase64String(package.Signature));
    }

    private static TevScriptSignedUpdatePackage Package(string name)
    {
        return TevScriptSignedUpdatePackage.Parse(ReadResource(name));
    }

    private static void InvokeDamageAndRequire(TevScriptRuntimeHost host, int expected, string context)
    {
        host.Invoke("Player", "damage", TevScriptValue.Int(new BigInteger(10)));
        IReadOnlyDictionary<string, TevScriptValue> state = host.State("Player");
        if (!state.ContainsKey("health") || state["health"].AsInt() != new BigInteger(expected))
            throw new InvalidOperationException(context + ": expected health=" + expected + ".");
    }

    private static string[] CapabilityCeiling(TevScriptProgram program)
    {
        var result = new List<string>();
        foreach (TevScriptEntityDefinition entity in program.Entities)
            foreach (string id in entity.Capabilities.Keys)
                if (!result.Contains(id)) result.Add(id);
        return result.ToArray();
    }

    private static AuthorityConfig LoadAuthority(string name)
    {
        using (JsonDocument document = JsonDocument.Parse(ReadResource(name)))
        {
            JsonElement root = document.RootElement;
            return new AuthorityConfig(
                root.GetProperty("key_id").GetString(),
                root.GetProperty("x").GetString(),
                root.GetProperty("y").GetString());
        }
    }

    private static string ReadResource(string name)
    {
        Assembly assembly = typeof(Program).Assembly;
        using (Stream stream = assembly.GetManifestResourceStream(name))
        {
            if (stream == null) throw new InvalidOperationException("Embedded resource missing: " + name);
            using (var reader = new StreamReader(stream, Encoding.UTF8, true)) return reader.ReadToEnd();
        }
    }

    private static void ExpectCode(Action action, string expectedCode)
    {
        try { action(); }
        catch (TevContractException exception)
        {
            if (exception.Diagnostic.Code == expectedCode) return;
            throw new InvalidOperationException(
                "Expected code " + expectedCode + " but observed " + exception.Diagnostic.Code + ".", exception);
        }
        throw new InvalidOperationException("Expected failure code " + expectedCode + ".");
    }

    private sealed class FailingStore : ITevInstalledUpdateStore
    {
        public TevInstalledUpdateRecord Load(string channelId) { return null; }
        public void Save(TevInstalledUpdateRecord record) { throw new IOException("gate6d forced store failure"); }
    }

    private sealed class AuthorityConfig
    {
        internal AuthorityConfig(string keyId, string x, string y) { KeyId=keyId; X=x; Y=y; }
        internal string KeyId { get; }
        internal string X { get; }
        internal string Y { get; }
    }
}
