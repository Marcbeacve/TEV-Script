using System.Numerics;
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

    private sealed class MemoryStore : ITevInstalledUpdateStoreV3
    {
        private TevInstalledUpdateRecordV3? _record;
        public bool FailSave { get; set; }
        public TevInstalledUpdateRecordV3? Load(string channelId) =>
            _record is not null && StringComparer.Ordinal.Equals(_record.ChannelId, channelId)
                ? _record
                : null;
        public void Save(TevInstalledUpdateRecordV3 record)
        {
            if (FailSave) throw new IOException("synthetic durable store failure");
            _record = record;
        }
    }

    private sealed record FixtureSet(
        string Base,
        string Target1,
        string Target2,
        string Target3,
        string Package1,
        string Package2,
        string PackageEpoch2,
        string PackageRemovedState,
        string PackageTypeChanged,
        string PackageCapabilityChanged,
        string PackageRecordChanged,
        string PackageWrongFrom,
        string PackageWrongKey,
        string PackageUnknownAlgorithm,
        string PackageTampered,
        string PackageNoncanonical);

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length != 2 || args[0] != "--dir")
                throw new ArgumentException("usage: TevScript.V3SignedUpdateGate --dir <fixture-dir>");
            var fixtureRoot = Path.GetFullPath(args[1]);
            var fixtures = LoadFixtures(fixtureRoot);
            var verifier = new VerifierAdapter();

            TestPackageBoundary(fixtures, verifier);
            TestTransactionalHotSwap(fixtures);
            TestSignedLiveSequence(fixtures, verifier);
            TestTransitionAndMigrationNegatives(fixtures, verifier);
            TestReplayAndDurableStaleness(fixtures, verifier);
            TestStoreFailureRollback(fixtures, verifier);
            TestInstalledTargetAndCheckpointRestart(fixtures, verifier);

            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_PACKAGE_V2=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_MANAGED_ES256=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FROM_HASH=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_CAPABILITY_ABI_CEILING=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_TRANSACTIONAL_SWAP=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_REPLAY_ROLLBACK=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_STORE_ROLLBACK=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_INSTALLED_TARGET_CHECKPOINT=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_GATE=PASS");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            Console.WriteLine("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_GATE=FAIL");
            return 91;
        }
    }

    private static void TestPackageBoundary(FixtureSet fixtures, VerifierAdapter verifier)
    {
        var package1 = TevScriptSignedUpdatePackageV3.Parse(fixtures.Package1);
        package1.VerifySignature(verifier);
        if (package1.Epoch != 1 || package1.Sequence != 1 || package1.Signature.Length != 64)
            throw new InvalidOperationException("package1 monotonic/signature fixture mismatch");
        ExpectCode("TEVS_UPDATE_V3_PACKAGE_CANONICAL", () =>
            TevScriptSignedUpdatePackageV3.Parse(fixtures.PackageNoncanonical));
        ExpectCode("TEVS_UPDATE_V3_SIGNATURE_INVALID", () =>
        {
            var tampered = TevScriptSignedUpdatePackageV3.Parse(fixtures.PackageTampered);
            tampered.VerifySignature(verifier);
        });
        ExpectCode("TEVS_UPDATE_V3_SIGNATURE_INVALID", () =>
        {
            var wrongKey = TevScriptSignedUpdatePackageV3.Parse(fixtures.PackageWrongKey);
            wrongKey.VerifySignature(verifier);
        });
        ExpectCode("TEVS_UPDATE_V3_SIGNATURE_ALGORITHM", () =>
        {
            var unknown = TevScriptSignedUpdatePackageV3.Parse(fixtures.PackageUnknownAlgorithm);
            unknown.VerifySignature(verifier);
        });
    }

    private static void TestTransactionalHotSwap(FixtureSet fixtures)
    {
        var host = NewHost(fixtures.Base);
        host.Invoke("E", "start");
        if (StateInt(host, "out") != 1) throw new InvalidOperationException("base start did not set out=1");
        var plan1 = host.PrepareSwap(fixtures.Target1);
        var plan2 = host.PrepareSwap(fixtures.Target1);
        var receipt = host.Commit(plan1);
        if (receipt.Generation != 1 || StateInt(host, "out") != 1 || StateInt(host, "marker") != 11)
            throw new InvalidOperationException("transactional migration did not preserve old state/add candidate default");
        ExpectCode("TEVS_IR_V3_SWAP_PLAN_STALE", () => host.Commit(plan2));
        var rollback = host.RollbackLastCommit();
        if (!rollback.Rollback || host.Generation != 2 || StateInt(host, "out") != 1)
            throw new InvalidOperationException("runtime rollback did not restore authoritative source runtime");
        if (host.State("E").ContainsKey("marker"))
            throw new InvalidOperationException("runtime rollback retained candidate-only state");
    }

    private static void TestSignedLiveSequence(FixtureSet fixtures, VerifierAdapter verifier)
    {
        var store = new MemoryStore();
        var host = NewHost(fixtures.Base);
        var authority = new TevScriptUpdateAuthorityV3(host, "stable", verifier, store);
        host.Invoke("E", "start");
        var baseHash = host.ActiveSemanticHash;

        var plan1 = authority.Prepare(fixtures.Package1);
        var receipt1 = authority.Commit(plan1);
        if (receipt1.Generation != 1
            || !StringComparer.Ordinal.Equals(receipt1.SourceSemanticHash, baseHash)
            || StateInt(host, "out") != 1
            || StateInt(host, "marker") != 11)
            throw new InvalidOperationException("signed update 1 state/receipt mismatch");
        host.Invoke("E", "start");
        if (StateInt(host, "out") != 11)
            throw new InvalidOperationException("target1 behavior did not become authoritative");

        var plan2 = authority.Prepare(fixtures.Package2);
        var receipt2 = authority.Commit(plan2);
        if (receipt2.Generation != 2 || StateInt(host, "marker") != 11)
            throw new InvalidOperationException("signed update 2 did not preserve target1 marker state");
        host.Invoke("E", "start");
        if (StateInt(host, "out") != 21)
            throw new InvalidOperationException("target2 behavior did not become authoritative");

        var plan3 = authority.Prepare(fixtures.PackageEpoch2);
        var receipt3 = authority.Commit(plan3);
        if (receipt3.Generation != 3 || receipt3.Epoch != 2 || receipt3.Sequence != 1)
            throw new InvalidOperationException("epoch transition receipt mismatch");
        host.Invoke("E", "start");
        if (StateInt(host, "out") != 31)
            throw new InvalidOperationException("target3 behavior did not become authoritative");
    }

    private static void TestTransitionAndMigrationNegatives(FixtureSet fixtures, VerifierAdapter verifier)
    {
        ExpectCode("TEVS_UPDATE_V3_FROM_HASH", () =>
            NewAuthority(fixtures.Base, new MemoryStore(), verifier).Prepare(fixtures.PackageWrongFrom));
        ExpectCode("TEVS_IR_V3_SWAP_STATE_REMOVED", () =>
            NewAuthority(fixtures.Base, new MemoryStore(), verifier).Prepare(fixtures.PackageRemovedState));
        ExpectCode("TEVS_IR_V3_SWAP_STATE_TYPE", () =>
            NewAuthority(fixtures.Base, new MemoryStore(), verifier).Prepare(fixtures.PackageTypeChanged));
        ExpectCode("TEVS_IR_V3_SWAP_CAPABILITY_SIGNATURE_CEILING", () =>
            NewAuthority(fixtures.Base, new MemoryStore(), verifier).Prepare(fixtures.PackageCapabilityChanged));
        ExpectRejected(() =>
            NewAuthority(fixtures.Base, new MemoryStore(), verifier).Prepare(fixtures.PackageRecordChanged));
    }

    private static void TestReplayAndDurableStaleness(FixtureSet fixtures, VerifierAdapter verifier)
    {
        var package1 = TevScriptSignedUpdatePackageV3.Parse(fixtures.Package1);
        var epoch2 = TevScriptSignedUpdatePackageV3.Parse(fixtures.PackageEpoch2);

        var replayStore = new MemoryStore();
        replayStore.Save(TevInstalledUpdateRecordV3.FromPackage(package1));
        ExpectCode("TEVS_UPDATE_V3_REPLAY", () =>
            NewAuthority(fixtures.Base, replayStore, verifier).Prepare(fixtures.Package1));

        var rollbackStore = new MemoryStore();
        rollbackStore.Save(TevInstalledUpdateRecordV3.FromPackage(epoch2));
        ExpectCode("TEVS_UPDATE_V3_EPOCH_ROLLBACK", () =>
            NewAuthority(fixtures.Base, rollbackStore, verifier).Prepare(fixtures.Package1));

        var staleStore = new MemoryStore();
        var host = NewHost(fixtures.Base);
        var authority = new TevScriptUpdateAuthorityV3(host, "stable", verifier, staleStore);
        var plan = authority.Prepare(fixtures.Package1);
        staleStore.Save(TevInstalledUpdateRecordV3.FromPackage(package1));
        ExpectCode("TEVS_UPDATE_V3_PLAN_STALE", () => authority.Commit(plan));
        if (!StringComparer.Ordinal.Equals(host.ActiveSemanticHash, TevScriptStrictJsonV3.ParseElement(fixtures.Base).GetProperty("semantic_hash").GetString()))
            throw new InvalidOperationException("durable stale rejection mutated runtime");
    }

    private static void TestStoreFailureRollback(FixtureSet fixtures, VerifierAdapter verifier)
    {
        var store = new MemoryStore { FailSave = true };
        var host = NewHost(fixtures.Base);
        host.Invoke("E", "start");
        var sourceHash = host.ActiveSemanticHash;
        var authority = new TevScriptUpdateAuthorityV3(host, "stable", verifier, store);
        var plan = authority.Prepare(fixtures.Package1);
        ExpectCode("TEVS_UPDATE_V3_STORE_COMMIT", () => authority.Commit(plan));
        if (!StringComparer.Ordinal.Equals(host.ActiveSemanticHash, sourceHash)
            || StateInt(host, "out") != 1
            || host.State("E").ContainsKey("marker"))
            throw new InvalidOperationException("store failure rollback did not restore source runtime exactly");
    }

    private static void TestInstalledTargetAndCheckpointRestart(FixtureSet fixtures, VerifierAdapter verifier)
    {
        var store = new MemoryStore();
        var host = NewHost(fixtures.Base);
        var authority = new TevScriptUpdateAuthorityV3(host, "stable", verifier, store);
        authority.Commit(authority.Prepare(fixtures.Package1));
        if (!authority.TryLoadInstalledPackage(out var installed) || installed is null)
            throw new InvalidOperationException("installed package was not loadable");
        installed.VerifySignature(verifier);

        var installedIr = TevScriptStrictJsonV3.ParseElement(installed.ProgramJson);
        var runtime = new TevScriptRuntimeV3(installedIr, Capabilities());
        runtime.Invoke("E", "start");
        var checkpoint = TevScriptRuntimeCheckpointV2.Capture(runtime);
        var parsed = TevScriptRuntimeCheckpointV2.Parse(checkpoint.ToCanonicalJson());
        var restored = parsed.RestoreExact(installedIr, Capabilities());
        if (!StringComparer.Ordinal.Equals(runtime.CanonicalStateJson("E"), restored.CanonicalStateJson("E")))
            throw new InvalidOperationException("installed-target checkpoint restart state mismatch");
        restored.Invoke("E", "start");
        if (StateInt(restored, "out") != 11)
            throw new InvalidOperationException("installed-target checkpoint restart did not continue target behavior");

        var corruptedStore = new MemoryStore();
        corruptedStore.Save(new TevInstalledUpdateRecordV3(
            installed.ChannelId,
            installed.Epoch,
            installed.Sequence,
            new string('0', 64),
            installed.CanonicalJson));
        var corruptedAuthority = new TevScriptUpdateAuthorityV3(
            NewHost(fixtures.Base),
            "stable",
            verifier,
            corruptedStore);
        ExpectCode("TEVS_UPDATE_V3_RESTORE_INTEGRITY", () =>
            corruptedAuthority.TryLoadInstalledPackage(out _));
    }

    private static FixtureSet LoadFixtures(string root) => new(
        Read(root, "base.ir.json"),
        Read(root, "target1.ir.json"),
        Read(root, "target2.ir.json"),
        Read(root, "target3.ir.json"),
        Read(root, "package1.json"),
        Read(root, "package2.json"),
        Read(root, "package_epoch2.json"),
        Read(root, "package_removed_state.json"),
        Read(root, "package_type_changed.json"),
        Read(root, "package_capability_abi_changed.json"),
        Read(root, "package_record_abi_changed.json"),
        Read(root, "package_wrong_from.json"),
        Read(root, "package_wrong_key.json"),
        Read(root, "package_unknown_algorithm.json"),
        Read(root, "package_tampered.json"),
        Read(root, "package_noncanonical.json"));

    private static string Read(string root, string name) =>
        File.ReadAllText(Path.Combine(root, name));

    private static TevScriptRuntimeHostV3 NewHost(string programJson) =>
        new(
            TevScriptStrictJsonV3.ParseElement(programJson),
            Capabilities(),
            Ceiling());

    private static TevScriptUpdateAuthorityV3 NewAuthority(
        string programJson,
        MemoryStore store,
        VerifierAdapter verifier) =>
        new(NewHost(programJson), "stable", verifier, store);

    private static IReadOnlyDictionary<string, TevScriptCapabilityV3> Capabilities() =>
        new Dictionary<string, TevScriptCapabilityV3>(StringComparer.Ordinal)
        {
            ["sink.write"] = _ => null,
        };

    private static IReadOnlyList<TevScriptCapabilityContractV3> Ceiling() =>
        new[]
        {
            new TevScriptCapabilityContractV3(
                "sink.write",
                new[] { "Root.Pair" },
                "Unit",
                "effect"),
        };

    private static int StateInt(TevScriptRuntimeHostV3 host, string name) =>
        host.State("E")[name] is TevIntV3 value
            ? checked((int)value.Value)
            : throw new InvalidOperationException("state " + name + " is not Int");

    private static int StateInt(TevScriptRuntimeV3 runtime, string name) =>
        runtime.State("E")[name] is TevIntV3 value
            ? checked((int)value.Value)
            : throw new InvalidOperationException("state " + name + " is not Int");

    private static void ExpectCode(string expectedCode, Action action)
    {
        try
        {
            action();
        }
        catch (TevScriptV3Exception error) when (error.Code == expectedCode)
        {
            return;
        }
        throw new InvalidOperationException("expected failure " + expectedCode);
    }

    private static void ExpectRejected(Action action)
    {
        try
        {
            action();
        }
        catch
        {
            return;
        }
        throw new InvalidOperationException("expected candidate migration rejection");
    }
}
