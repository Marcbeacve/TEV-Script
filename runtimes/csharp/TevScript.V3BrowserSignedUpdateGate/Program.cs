using System.Reflection;
using TevScript.Core.V3;
using ManagedVerifier = Marcbeacve.TevScript.Update.TevManagedEcdsaP256Sha256Verifier;

internal static class Program
{
    private const string KeyId = "tev-test-update-key-v1";
    private const string PublicX = "JV8YUahvnNr8TZouyW7ek7jgGLnGW59062dKKDrsozM=";
    private const string PublicY = "lelmvUQzVnJKnfQKqXWHEchkUySpSZFcxfLskTG52rA=";

    private sealed class VerifierAdapter : ITevUpdateSignatureVerifierV3
    {
        private readonly ManagedVerifier _inner = new(KeyId, PublicX, PublicY);
        public string KeyId => _inner.KeyId;
        public string AlgorithmId => _inner.AlgorithmId;
        public bool Verify(byte[] data, byte[] signature) => _inner.Verify(data, signature);
    }

    private sealed class MemoryStore : ITevInstalledUpdateStoreV3
    {
        private TevInstalledUpdateRecordV3? _record;
        public bool FailSave { get; set; }
        public TevInstalledUpdateRecordV3? Load(string channelId) =>
            _record is not null && _record.ChannelId == channelId ? _record : null;
        public void Save(TevInstalledUpdateRecordV3 record)
        {
            if (FailSave) throw new IOException("synthetic browser store failure");
            _record = record;
        }
    }

    private static int Main()
    {
        try
        {
            if (!OperatingSystem.IsBrowser())
                throw new InvalidOperationException("signed update V3 browser gate requires browser-wasm");
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_ACTIVE=PASS");

            var baseJson = ReadResource("base.ir.json");
            var packageJson = ReadResource("package1.json");
            var package = TevScriptSignedUpdatePackageV3.Parse(packageJson);
            var verifier = new VerifierAdapter();
            package.VerifySignature(verifier);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_SIGNATURE=PASS");

            var store = new MemoryStore();
            var host = NewHost(baseJson);
            host.Invoke("E", "start");
            var authority = new TevScriptUpdateAuthorityV3(host, "stable", verifier, store);
            var receipt = authority.Commit(authority.Prepare(packageJson));
            if (StateInt(host, "out") != 1 || StateInt(host, "marker") != 11)
                throw new InvalidOperationException("browser signed update migration mismatch");
            host.Invoke("E", "start");
            if (StateInt(host, "out") != 11)
                throw new InvalidOperationException("browser signed update target behavior mismatch");
            if (receipt.TargetSemanticHash != package.TargetIrSemanticHash)
                throw new InvalidOperationException("browser signed update receipt target mismatch");
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_TRANSACTION=PASS");

            ExpectCode("TEVS_UPDATE_V3_SIGNATURE_INVALID", () =>
                NewAuthority(baseJson, verifier, new MemoryStore()).Prepare(ReadResource("package_wrong_key.json")));
            ExpectCode("TEVS_UPDATE_V3_FROM_HASH", () =>
                NewAuthority(baseJson, verifier, new MemoryStore()).Prepare(ReadResource("package_wrong_from.json")));
            ExpectCode("TEVS_IR_V3_SWAP_CAPABILITY_SIGNATURE_CEILING", () =>
                NewAuthority(baseJson, verifier, new MemoryStore()).Prepare(ReadResource("package_capability_abi_changed.json")));
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_NEGATIVES=PASS");

            var failingStore = new MemoryStore { FailSave = true };
            var rollbackHost = NewHost(baseJson);
            rollbackHost.Invoke("E", "start");
            var sourceHash = rollbackHost.ActiveSemanticHash;
            var rollbackAuthority = new TevScriptUpdateAuthorityV3(rollbackHost, "stable", verifier, failingStore);
            var rollbackPlan = rollbackAuthority.Prepare(packageJson);
            ExpectCode("TEVS_UPDATE_V3_STORE_COMMIT", () => rollbackAuthority.Commit(rollbackPlan));
            if (rollbackHost.ActiveSemanticHash != sourceHash
                || StateInt(rollbackHost, "out") != 1
                || rollbackHost.State("E").ContainsKey("marker"))
                throw new InvalidOperationException("browser signed update store rollback mismatch");
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_STORE_ROLLBACK=PASS");

            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PACKAGE_SHA256=" + package.PackageSha256);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_TARGET_HASH=" + package.TargetIrSemanticHash);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=PASS");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            Console.WriteLine("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=FAIL");
            return 91;
        }
    }

    private static TevScriptUpdateAuthorityV3 NewAuthority(
        string baseJson,
        VerifierAdapter verifier,
        MemoryStore store) =>
        new(NewHost(baseJson), "stable", verifier, store);

    private static TevScriptRuntimeHostV3 NewHost(string programJson) =>
        new(
            TevScriptStrictJsonV3.ParseElement(programJson),
            new Dictionary<string, TevScriptCapabilityV3>(StringComparer.Ordinal)
            {
                ["sink.write"] = _ => null,
            },
            new[]
            {
                new TevScriptCapabilityContractV3(
                    "sink.write",
                    new[] { "Root.Pair" },
                    "Unit",
                    "effect"),
            });

    private static int StateInt(TevScriptRuntimeHostV3 host, string name) =>
        host.State("E")[name] is TevIntV3 value
            ? checked((int)value.Value)
            : throw new InvalidOperationException("state " + name + " is not Int");

    private static void ExpectCode(string code, Action action)
    {
        try { action(); }
        catch (TevScriptV3Exception error) when (error.Code == code) { return; }
        throw new InvalidOperationException("expected failure " + code);
    }

    private static string ReadResource(string name)
    {
        var assembly = typeof(Program).Assembly;
        using var stream = assembly.GetManifestResourceStream(name)
            ?? throw new InvalidOperationException("embedded resource missing: " + name);
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }
}
