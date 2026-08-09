using System.Text;
using TevScript.Core.V3;
using ManagedVerifier = Marcbeacve.TevScript.Update.TevManagedEcdsaP256Sha256Verifier;

internal static class Program
{
    private const string KeyId = "tev-test-update-key-v1";
    private const string PublicX = "JV8YUahvnNr8TZouyW7ek7jgGLnGW59062dKKDrsozM=";
    private const string PublicY = "lelmvUQzVnJKnfQKqXWHEchkUySpSZFcxfLskTG52rA=";

    private sealed class VerifierAdapter : ITevUpdateSignatureVerifierV3
    {
        private readonly ManagedVerifier _inner = new(Program.KeyId, PublicX, PublicY);
        public string KeyId => _inner.KeyId;
        public string AlgorithmId => _inner.AlgorithmId;
        public bool Verify(byte[] data, byte[] signature) => _inner.Verify(data, signature);
    }

    private sealed class FileStore : ITevInstalledUpdateStoreV3
    {
        private readonly string _path;
        public FileStore(string path) => _path = path;
        public TevInstalledUpdateRecordV3? Load(string channelId)
        {
            if (!File.Exists(_path)) return null;
            var record = TevInstalledUpdateRecordV3.Parse(File.ReadAllText(_path, Encoding.UTF8));
            return record.ChannelId == channelId ? record : null;
        }
        public void Save(TevInstalledUpdateRecordV3 record) =>
            File.WriteAllText(_path, record.ToCanonicalJson(), new UTF8Encoding(false));
    }

    private static int Main(string[] args)
    {
        try
        {
            if (!OperatingSystem.IsWasi())
                throw new InvalidOperationException("signed update V3 WASI gate requires wasi-wasm");
            if (args.Length != 3 || (args[0] != "fresh" && args[0] != "restore"))
                throw new ArgumentException("usage: TevScript.V3WasiSignedUpdateGate <fresh|restore> <installed.json> <checkpoint.json>");

            var mode = args[0];
            var installedPath = args[1];
            var checkpointPath = args[2];
            var baseJson = File.ReadAllText("base.ir.json", Encoding.UTF8);
            var packageJson = File.ReadAllText("package1.json", Encoding.UTF8);
            var verifier = new VerifierAdapter();
            var package = TevScriptSignedUpdatePackageV3.Parse(packageJson);
            package.VerifySignature(verifier);

            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_ACTIVE=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_MODE=" + mode.ToUpperInvariant());
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SIGNATURE=PASS");

            var store = new FileStore(installedPath);
            if (mode == "fresh")
            {
                var host = NewHost(baseJson);
                host.Invoke("E", "start");
                var authority = new TevScriptUpdateAuthorityV3(host, "stable", verifier, store);
                authority.Commit(authority.Prepare(packageJson));
                if (StateInt(host, "out") != 1 || StateInt(host, "marker") != 11)
                    throw new InvalidOperationException("WASI signed update live migration mismatch");
                host.Invoke("E", "start");
                if (StateInt(host, "out") != 11)
                    throw new InvalidOperationException("WASI signed update target behavior mismatch");
                if (!authority.TryLoadInstalledPackage(out var installed) || installed is null)
                    throw new InvalidOperationException("WASI installed target missing after commit");

                var targetIr = TevScriptStrictJsonV3.ParseElement(installed.ProgramJson);
                var targetRuntime = new TevScriptRuntimeV3(targetIr, Capabilities());
                targetRuntime.Invoke("E", "start");
                var checkpoint = TevScriptRuntimeCheckpointV2.Capture(targetRuntime);
                File.WriteAllText(checkpointPath, checkpoint.ToCanonicalJson(), new UTF8Encoding(false));
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_LIVE_COMMIT=PASS");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_INSTALLED_RECORD=PASS");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_CAPTURE=PASS");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_HASH=" + checkpoint.CheckpointHash);
            }
            else
            {
                if (!File.Exists(installedPath) || !File.Exists(checkpointPath))
                    throw new FileNotFoundException("installed record or target checkpoint missing");
                var bootstrap = NewHost(baseJson);
                var authority = new TevScriptUpdateAuthorityV3(bootstrap, "stable", verifier, store);
                if (!authority.TryLoadInstalledPackage(out var installed) || installed is null)
                    throw new InvalidOperationException("WASI restart could not verify installed target");
                var targetIr = TevScriptStrictJsonV3.ParseElement(installed.ProgramJson);
                var checkpoint = TevScriptRuntimeCheckpointV2.Parse(File.ReadAllText(checkpointPath, Encoding.UTF8));
                var restored = checkpoint.RestoreExact(targetIr, Capabilities());
                restored.Invoke("E", "start");
                if (StateInt(restored, "out") != 11)
                    throw new InvalidOperationException("WASI signed update restart continuation mismatch");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_INSTALLED_REVERIFY=PASS");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_RESTORE=PASS");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTART_CONTINUATION=PASS");
                Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_HASH=" + checkpoint.CheckpointHash);
            }

            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PACKAGE_SHA256=" + package.PackageSha256);
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_TARGET_HASH=" + package.TargetIrSemanticHash);
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=PASS");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            Console.WriteLine("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=FAIL");
            return 91;
        }
    }

    private static TevScriptRuntimeHostV3 NewHost(string programJson) =>
        new(
            TevScriptStrictJsonV3.ParseElement(programJson),
            Capabilities(),
            new[]
            {
                new TevScriptCapabilityContractV3(
                    "sink.write",
                    new[] { "Root.Pair" },
                    "Unit",
                    "effect"),
            });

    private static IReadOnlyDictionary<string, TevScriptCapabilityV3> Capabilities() =>
        new Dictionary<string, TevScriptCapabilityV3>(StringComparer.Ordinal)
        {
            ["sink.write"] = _ => null,
        };

    private static int StateInt(TevScriptRuntimeHostV3 host, string name) =>
        host.State("E")[name] is TevIntV3 value
            ? checked((int)value.Value)
            : throw new InvalidOperationException("state " + name + " is not Int");

    private static int StateInt(TevScriptRuntimeV3 runtime, string name) =>
        runtime.State("E")[name] is TevIntV3 value
            ? checked((int)value.Value)
            : throw new InvalidOperationException("state " + name + " is not Int");
}
