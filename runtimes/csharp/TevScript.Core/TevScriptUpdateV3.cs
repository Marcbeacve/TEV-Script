using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace TevScript.Core.V3;

public interface ITevUpdateSignatureVerifierV3
{
    string KeyId { get; }
    string AlgorithmId { get; }
    bool Verify(byte[] data, byte[] signature);
}

public interface ITevInstalledUpdateStoreV3
{
    TevInstalledUpdateRecordV3? Load(string channelId);
    void Save(TevInstalledUpdateRecordV3 record);
}

public sealed class TevScriptSignedUpdatePackageV3
{
    public const string PackageSchema = "TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V2";
    public const string BodySchema = "TEV_SCRIPT_UPDATE_BODY_V2";
    private const long MaximumStructuralInteger = 9007199254740991L;
    private static readonly Regex Stable = new(
        "^[A-Za-z_][A-Za-z0-9_.:/-]*$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Hash = new(
        "^[0-9a-f]{64}$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private readonly byte[] _signature;
    private readonly byte[] _signedBodyBytes;

    private TevScriptSignedUpdatePackageV3(
        string canonicalJson,
        string packageSha256,
        string channelId,
        string programId,
        long epoch,
        long sequence,
        string fromIrSemanticHash,
        string targetIrSemanticHash,
        string targetSourceSemanticHash,
        string irSha256,
        string programJson,
        string signatureAlgorithm,
        string keyId,
        byte[] signature,
        string signedBodyJson,
        byte[] signedBodyBytes)
    {
        CanonicalJson = canonicalJson;
        PackageSha256 = packageSha256;
        ChannelId = channelId;
        ProgramId = programId;
        Epoch = epoch;
        Sequence = sequence;
        FromIrSemanticHash = fromIrSemanticHash;
        TargetIrSemanticHash = targetIrSemanticHash;
        TargetSourceSemanticHash = targetSourceSemanticHash;
        IrSha256 = irSha256;
        ProgramJson = programJson;
        SignatureAlgorithm = signatureAlgorithm;
        KeyId = keyId;
        _signature = (byte[])signature.Clone();
        SignedBodyJson = signedBodyJson;
        _signedBodyBytes = (byte[])signedBodyBytes.Clone();
    }

    public string CanonicalJson { get; }
    public string PackageSha256 { get; }
    public string ChannelId { get; }
    public string ProgramId { get; }
    public long Epoch { get; }
    public long Sequence { get; }
    public string FromIrSemanticHash { get; }
    public string TargetIrSemanticHash { get; }
    public string TargetSourceSemanticHash { get; }
    public string IrSha256 { get; }
    public string ProgramJson { get; }
    public string SignatureAlgorithm { get; }
    public string KeyId { get; }
    public string SignedBodyJson { get; }
    public byte[] Signature => (byte[])_signature.Clone();

    public static TevScriptSignedUpdatePackageV3 Parse(string json)
    {
        if (json is null) throw new ArgumentNullException(nameof(json));
        var root = TevScriptStrictJsonV3.ParseElement(json);
        var canonical = TevScriptCanonicalV3.Json(root);
        if (!StringComparer.Ordinal.Equals(json, canonical))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_PACKAGE_CANONICAL",
                "signed update package must use exact canonical JSON bytes");
        RequireObject(root, "$");
        RequireExactKeys(root, "$", "schema", "body", "signature");
        if (RequireString(root.GetProperty("schema"), "$.schema") != PackageSchema)
            Fail("TEVS_UPDATE_V3_PACKAGE_SCHEMA", "$.schema", $"expected {PackageSchema}");

        var body = root.GetProperty("body");
        RequireObject(body, "$.body");
        RequireExactKeys(
            body,
            "$.body",
            "schema",
            "channel_id",
            "program_id",
            "epoch",
            "sequence",
            "from_ir_semantic_hash",
            "target_ir_semantic_hash",
            "target_source_semantic_hash",
            "ir_sha256",
            "ir");
        if (RequireString(body.GetProperty("schema"), "$.body.schema") != BodySchema)
            Fail("TEVS_UPDATE_V3_BODY_SCHEMA", "$.body.schema", $"expected {BodySchema}");

        var channelId = RequireStable(body.GetProperty("channel_id"), "$.body.channel_id");
        var programId = RequireString(body.GetProperty("program_id"), "$.body.program_id");
        var epoch = RequirePositiveInteger(body.GetProperty("epoch"), "$.body.epoch");
        var sequence = RequirePositiveInteger(body.GetProperty("sequence"), "$.body.sequence");
        var fromHash = RequireHash(body.GetProperty("from_ir_semantic_hash"), "$.body.from_ir_semantic_hash");
        var targetHash = RequireHash(body.GetProperty("target_ir_semantic_hash"), "$.body.target_ir_semantic_hash");
        var targetSourceHash = RequireHash(
            body.GetProperty("target_source_semantic_hash"),
            "$.body.target_source_semantic_hash");
        var irSha = RequireHash(body.GetProperty("ir_sha256"), "$.body.ir_sha256");
        var ir = body.GetProperty("ir").Clone();
        var programJson = TevScriptCanonicalV3.Json(ir);
        var observedIrSha = TevScriptCanonicalV3.Sha256(ir);
        if (!StringComparer.Ordinal.Equals(observedIrSha, irSha))
            Fail("TEVS_UPDATE_V3_IR_HASH", "$.body.ir_sha256", "embedded IR hash does not match ir_sha256");
        TevScriptProgramValidatorV3.Validate(ir);
        if (!StringComparer.Ordinal.Equals(ir.GetProperty("program_id").GetString(), programId))
            Fail("TEVS_UPDATE_V3_PROGRAM_ID", "$.body.program_id", "package program_id does not match embedded IR");
        if (!StringComparer.Ordinal.Equals(ir.GetProperty("semantic_hash").GetString(), targetHash))
            Fail("TEVS_UPDATE_V3_TARGET_HASH", "$.body.target_ir_semantic_hash", "target semantic hash does not match embedded IR");
        if (!StringComparer.Ordinal.Equals(ir.GetProperty("source_semantic_hash").GetString(), targetSourceHash))
            Fail("TEVS_UPDATE_V3_TARGET_SOURCE_HASH", "$.body.target_source_semantic_hash", "target source hash does not match embedded IR");
        if (StringComparer.Ordinal.Equals(fromHash, targetHash))
            Fail("TEVS_UPDATE_V3_NOOP", "$.body", "signed update must change IR semantic identity");

        var signatureObject = root.GetProperty("signature");
        RequireObject(signatureObject, "$.signature");
        RequireExactKeys(signatureObject, "$.signature", "algorithm", "key_id", "value");
        var algorithm = RequireStable(signatureObject.GetProperty("algorithm"), "$.signature.algorithm");
        var keyId = RequireStable(signatureObject.GetProperty("key_id"), "$.signature.key_id");
        var signatureText = RequireString(signatureObject.GetProperty("value"), "$.signature.value");
        byte[] signature;
        try
        {
            signature = Convert.FromBase64String(signatureText);
        }
        catch (FormatException error)
        {
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_SIGNATURE_BASE64",
                "update signature is not valid Base64",
                error);
        }
        if (signature.Length == 0
            || !StringComparer.Ordinal.Equals(Convert.ToBase64String(signature), signatureText))
            Fail("TEVS_UPDATE_V3_SIGNATURE_BASE64", "$.signature.value", "signature must use canonical non-empty Base64");

        var signedBodyJson = TevScriptCanonicalV3.Json(body);
        var signedBodyBytes = Encoding.UTF8.GetBytes(signedBodyJson);
        return new TevScriptSignedUpdatePackageV3(
            canonical,
            TevScriptCanonicalV3.Sha256Text(canonical),
            channelId,
            programId,
            epoch,
            sequence,
            fromHash,
            targetHash,
            targetSourceHash,
            irSha,
            programJson,
            algorithm,
            keyId,
            signature,
            signedBodyJson,
            signedBodyBytes);
    }

    public void VerifySignature(ITevUpdateSignatureVerifierV3 verifier)
    {
        if (verifier is null) throw new ArgumentNullException(nameof(verifier));
        if (!StringComparer.Ordinal.Equals(verifier.KeyId, KeyId))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_KEY_AUTHORITY",
                "package key_id is not authorized");
        if (!StringComparer.Ordinal.Equals(verifier.AlgorithmId, SignatureAlgorithm))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_SIGNATURE_ALGORITHM",
                "package signature algorithm is not authorized");
        bool valid;
        try
        {
            valid = verifier.Verify(_signedBodyBytes, _signature);
        }
        catch (Exception error)
        {
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_SIGNATURE_ENGINE",
                "signature verification failed closed: " + error.GetType().Name,
                error);
        }
        if (!valid)
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_SIGNATURE_INVALID",
                "update package signature is invalid");
    }

    private static long RequirePositiveInteger(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.Number || !value.TryGetInt64(out var result)
            || result < 1 || result > MaximumStructuralInteger)
            Fail("TEVS_UPDATE_V3_MONOTONIC_INTEGER", path, "expected positive portable structural integer");
        return result;
    }

    private static void RequireObject(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.Object)
            Fail("TEVS_UPDATE_V3_SHAPE", path, "expected object");
    }

    private static void RequireExactKeys(JsonElement value, string path, params string[] expected)
    {
        RequireObject(value, path);
        var observed = value.EnumerateObject().Select(item => item.Name).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var wanted = expected.OrderBy(item => item, StringComparer.Ordinal).ToArray();
        if (!observed.SequenceEqual(wanted, StringComparer.Ordinal))
            Fail("TEVS_UPDATE_V3_SHAPE", path, $"field set mismatch; expected=[{string.Join(',', wanted)}], observed=[{string.Join(',', observed)}]");
    }

    private static string RequireString(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.String)
            Fail("TEVS_UPDATE_V3_SHAPE", path, "expected string");
        return value.GetString()!;
    }

    private static string RequireStable(JsonElement value, string path)
    {
        var result = RequireString(value, path);
        if (!Stable.IsMatch(result))
            Fail("TEVS_UPDATE_V3_ID", path, "expected stable identifier");
        return result;
    }

    private static string RequireHash(JsonElement value, string path)
    {
        var result = RequireString(value, path);
        if (!Hash.IsMatch(result))
            Fail("TEVS_UPDATE_V3_SHA256", path, "expected lowercase SHA-256");
        return result;
    }

    private static void Fail(string code, string path, string message) =>
        throw new TevScriptV3Exception(code, $"{path}: {message}");
}

public sealed class TevInstalledUpdateRecordV3
{
    public const string Schema = "TEV_SCRIPT_INSTALLED_UPDATE_V2";

    public TevInstalledUpdateRecordV3(
        string channelId,
        long epoch,
        long sequence,
        string packageSha256,
        string packageJson)
    {
        ChannelId = channelId ?? throw new ArgumentNullException(nameof(channelId));
        if (epoch < 1) throw new ArgumentOutOfRangeException(nameof(epoch));
        if (sequence < 1) throw new ArgumentOutOfRangeException(nameof(sequence));
        Epoch = epoch;
        Sequence = sequence;
        PackageSha256 = packageSha256 ?? throw new ArgumentNullException(nameof(packageSha256));
        PackageJson = packageJson ?? throw new ArgumentNullException(nameof(packageJson));
    }

    public string ChannelId { get; }
    public long Epoch { get; }
    public long Sequence { get; }
    public string PackageSha256 { get; }
    public string PackageJson { get; }

    public static TevInstalledUpdateRecordV3 FromPackage(TevScriptSignedUpdatePackageV3 package)
    {
        if (package is null) throw new ArgumentNullException(nameof(package));
        return new TevInstalledUpdateRecordV3(
            package.ChannelId,
            package.Epoch,
            package.Sequence,
            package.PackageSha256,
            package.CanonicalJson);
    }

    public string ToCanonicalJson() => TevScriptObjectTreeJsonV3.Json(
        new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = Schema,
            ["channel_id"] = ChannelId,
            ["epoch"] = Epoch,
            ["sequence"] = Sequence,
            ["package_sha256"] = PackageSha256,
            ["package_json"] = PackageJson,
        });

    public static TevInstalledUpdateRecordV3 Parse(string json)
    {
        if (json is null) throw new ArgumentNullException(nameof(json));
        var root = TevScriptStrictJsonV3.ParseElement(json);
        if (!StringComparer.Ordinal.Equals(TevScriptCanonicalV3.Json(root), json))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_STORE_CANONICAL",
                "installed update record must use exact canonical JSON bytes");
        var properties = root.EnumerateObject().Select(item => item.Name).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var expected = new[] { "channel_id", "epoch", "package_json", "package_sha256", "schema", "sequence" };
        if (!properties.SequenceEqual(expected, StringComparer.Ordinal))
            throw new TevScriptV3Exception("TEVS_UPDATE_V3_STORE_SHAPE", "installed update record field set mismatch");
        if (root.GetProperty("schema").GetString() != Schema)
            throw new TevScriptV3Exception("TEVS_UPDATE_V3_STORE_SCHEMA", "unexpected installed update schema");
        var epoch = RequirePositive(root.GetProperty("epoch"), "$.epoch");
        var sequence = RequirePositive(root.GetProperty("sequence"), "$.sequence");
        var channel = root.GetProperty("channel_id").GetString()
            ?? throw new TevScriptV3Exception("TEVS_UPDATE_V3_STORE_SHAPE", "channel_id must be text");
        var packageSha = root.GetProperty("package_sha256").GetString()
            ?? throw new TevScriptV3Exception("TEVS_UPDATE_V3_STORE_SHAPE", "package_sha256 must be text");
        var packageJson = root.GetProperty("package_json").GetString()
            ?? throw new TevScriptV3Exception("TEVS_UPDATE_V3_STORE_SHAPE", "package_json must be text");
        var package = TevScriptSignedUpdatePackageV3.Parse(packageJson);
        if (!StringComparer.Ordinal.Equals(package.ChannelId, channel)
            || package.Epoch != epoch
            || package.Sequence != sequence
            || !StringComparer.Ordinal.Equals(package.PackageSha256, packageSha))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_STORE_INTEGRITY",
                "installed record does not match embedded package");
        return new TevInstalledUpdateRecordV3(channel, epoch, sequence, packageSha, packageJson);
    }

    internal bool SameAuthorityState(TevInstalledUpdateRecordV3? other) =>
        other is not null
        && StringComparer.Ordinal.Equals(ChannelId, other.ChannelId)
        && Epoch == other.Epoch
        && Sequence == other.Sequence
        && StringComparer.Ordinal.Equals(PackageSha256, other.PackageSha256);

    private static long RequirePositive(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.Number || !value.TryGetInt64(out var result)
            || result < 1 || result > 9007199254740991L)
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_STORE_MONOTONIC",
                $"{path}: expected positive portable structural integer");
        return result;
    }
}

public sealed class TevScriptUpdatePlanV3
{
    private bool _consumed;

    internal TevScriptUpdatePlanV3(
        object owner,
        TevInstalledUpdateRecordV3? sourceRecord,
        TevScriptSignedUpdatePackageV3 package,
        TevScriptRuntimeSwapPlanV3 runtimePlan)
    {
        Owner = owner;
        SourceRecord = sourceRecord;
        Package = package;
        RuntimePlan = runtimePlan;
    }

    internal object Owner { get; }
    internal TevInstalledUpdateRecordV3? SourceRecord { get; }
    internal TevScriptRuntimeSwapPlanV3 RuntimePlan { get; }
    public TevScriptSignedUpdatePackageV3 Package { get; }
    public bool IsConsumed => _consumed;

    internal void Consume()
    {
        if (_consumed)
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_PLAN_CONSUMED",
                "update plan has already been consumed");
        _consumed = true;
    }
}

public sealed record TevScriptUpdateReceiptV3(
    long Generation,
    string PackageSha256,
    long Epoch,
    long Sequence,
    string SourceSemanticHash,
    string TargetSemanticHash);

public sealed class TevScriptUpdateAuthorityV3
{
    private readonly object _planOwner = new();
    private readonly TevScriptRuntimeHostV3 _runtimeHost;
    private readonly string _channelId;
    private readonly ITevUpdateSignatureVerifierV3 _signatureVerifier;
    private readonly ITevInstalledUpdateStoreV3 _store;

    public TevScriptUpdateAuthorityV3(
        TevScriptRuntimeHostV3 runtimeHost,
        string channelId,
        ITevUpdateSignatureVerifierV3 signatureVerifier,
        ITevInstalledUpdateStoreV3 store)
    {
        _runtimeHost = runtimeHost ?? throw new ArgumentNullException(nameof(runtimeHost));
        _channelId = string.IsNullOrWhiteSpace(channelId)
            ? throw new ArgumentException("a channel id is required", nameof(channelId))
            : channelId.Trim();
        _signatureVerifier = signatureVerifier ?? throw new ArgumentNullException(nameof(signatureVerifier));
        _store = store ?? throw new ArgumentNullException(nameof(store));
    }

    public TevScriptUpdatePlanV3 Prepare(string packageJson)
    {
        var package = TevScriptSignedUpdatePackageV3.Parse(packageJson);
        package.VerifySignature(_signatureVerifier);
        if (!StringComparer.Ordinal.Equals(package.ChannelId, _channelId))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_CHANNEL",
                "package channel does not match this authority");
        if (!StringComparer.Ordinal.Equals(package.FromIrSemanticHash, _runtimeHost.ActiveSemanticHash))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_FROM_HASH",
                "package does not authorize a transition from the active IR semantic hash");

        var current = _store.Load(_channelId);
        ValidateReplay(current, package);
        var runtimePlan = _runtimeHost.PrepareSwap(package.ProgramJson);
        if (!StringComparer.Ordinal.Equals(runtimePlan.CandidateSemanticHash, package.TargetIrSemanticHash))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_TARGET_HASH",
                "runtime candidate hash differs from signed target hash");
        if (!StringComparer.Ordinal.Equals(runtimePlan.CandidateSourceSemanticHash, package.TargetSourceSemanticHash))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_TARGET_SOURCE_HASH",
                "runtime candidate source hash differs from signed target source hash");
        return new TevScriptUpdatePlanV3(
            _planOwner,
            current,
            package,
            runtimePlan);
    }

    public TevScriptUpdateReceiptV3 Commit(TevScriptUpdatePlanV3 plan)
    {
        if (plan is null) throw new ArgumentNullException(nameof(plan));
        if (!ReferenceEquals(plan.Owner, _planOwner))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_PLAN_OWNER",
                "update plan belongs to another authority");
        if (plan.IsConsumed)
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_PLAN_CONSUMED",
                "update plan has already been consumed");

        var current = _store.Load(_channelId);
        if (!SameRecord(current, plan.SourceRecord))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_PLAN_STALE",
                "update plan was prepared against stale durable state");

        var runtimeReceipt = _runtimeHost.Commit(plan.RuntimePlan);
        plan.Consume();
        var target = TevInstalledUpdateRecordV3.FromPackage(plan.Package);
        try
        {
            _store.Save(target);
        }
        catch (Exception error)
        {
            try
            {
                _runtimeHost.RollbackLastCommit();
            }
            catch (Exception rollbackError)
            {
                throw new TevScriptV3Exception(
                    "TEVS_UPDATE_V3_STORE_ROLLBACK",
                    "durable commit failed and runtime rollback also failed: "
                    + error.GetType().Name + "/" + rollbackError.GetType().Name,
                    rollbackError);
            }
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_STORE_COMMIT",
                "durable commit failed closed: " + error.GetType().Name,
                error);
        }

        return new TevScriptUpdateReceiptV3(
            runtimeReceipt.Generation,
            plan.Package.PackageSha256,
            plan.Package.Epoch,
            plan.Package.Sequence,
            runtimeReceipt.SourceSemanticHash,
            runtimeReceipt.TargetSemanticHash);
    }

    public bool TryLoadInstalledPackage(out TevScriptSignedUpdatePackageV3? package)
    {
        var record = _store.Load(_channelId);
        if (record is null)
        {
            package = null;
            return false;
        }
        var parsed = TevScriptSignedUpdatePackageV3.Parse(record.PackageJson);
        parsed.VerifySignature(_signatureVerifier);
        if (!StringComparer.Ordinal.Equals(parsed.ChannelId, _channelId)
            || parsed.Epoch != record.Epoch
            || parsed.Sequence != record.Sequence
            || !StringComparer.Ordinal.Equals(parsed.PackageSha256, record.PackageSha256))
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_RESTORE_INTEGRITY",
                "durable state does not match installed package");
        package = parsed;
        return true;
    }

    private static bool SameRecord(
        TevInstalledUpdateRecordV3? left,
        TevInstalledUpdateRecordV3? right)
    {
        if (left is null || right is null) return left is null && right is null;
        return left.SameAuthorityState(right);
    }

    private static void ValidateReplay(
        TevInstalledUpdateRecordV3? current,
        TevScriptSignedUpdatePackageV3 package)
    {
        if (current is null)
        {
            if (package.Epoch != 1 || package.Sequence != 1)
                throw new TevScriptV3Exception(
                    "TEVS_UPDATE_V3_BOOTSTRAP_SEQUENCE",
                    "first update must be epoch=1 sequence=1");
            return;
        }
        if (package.Epoch < current.Epoch)
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_EPOCH_ROLLBACK",
                "package epoch is older than durable state");
        if (package.Epoch == current.Epoch)
        {
            if (package.Sequence <= current.Sequence)
                throw new TevScriptV3Exception(
                    "TEVS_UPDATE_V3_REPLAY",
                    "package sequence is not newer than durable state");
            return;
        }
        if (package.Epoch != current.Epoch + 1)
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_EPOCH_JUMP",
                "epoch may advance by exactly one");
        if (package.Sequence != 1)
            throw new TevScriptV3Exception(
                "TEVS_UPDATE_V3_EPOCH_SEQUENCE",
                "a new epoch must begin at sequence 1");
    }
}
