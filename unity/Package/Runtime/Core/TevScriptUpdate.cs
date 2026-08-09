using System;
using System.Collections.Generic;
using System.Numerics;
using System.Text;

namespace Marcbeacve.TevScript.Core
{
    public interface ITevUpdateSignatureVerifier
    {
        string KeyId { get; }
        string AlgorithmId { get; }
        bool Verify(byte[] data, byte[] signature);
    }

    public interface ITevInstalledUpdateStore
    {
        TevInstalledUpdateRecord Load(string channelId);
        void Save(TevInstalledUpdateRecord record);
    }

    public sealed class TevScriptSignedUpdatePackage
    {
        public const string PackageSchema =
            "TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V1";
        public const string BodySchema =
            "TEV_SCRIPT_UPDATE_BODY_V1";

        private readonly byte[] _signature;
        private readonly byte[] _signedBodyBytes;

        private TevScriptSignedUpdatePackage(
            string canonicalJson,
            string packageSha256,
            string channelId,
            string programId,
            long epoch,
            long sequence,
            string programSemanticHash,
            string irSha256,
            string programJson,
            string algorithm,
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
            ProgramSemanticHash = programSemanticHash;
            IrSha256 = irSha256;
            ProgramJson = programJson;
            SignatureAlgorithm = algorithm;
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
        public string ProgramSemanticHash { get; }
        public string IrSha256 { get; }
        public string ProgramJson { get; }
        public string SignatureAlgorithm { get; }
        public string KeyId { get; }
        public string SignedBodyJson { get; }
        public byte[] Signature { get { return (byte[])_signature.Clone(); } }

        public static TevScriptSignedUpdatePackage Parse(string json)
        {
            if (json == null) throw new ArgumentNullException(nameof(json));

            object parsed = TevJson.Parse(json);
            string canonical = TevJson.Canonicalize(parsed);
            if (!string.Equals(json, canonical, StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_PACKAGE_CANONICAL",
                    "Signed update package must use exact canonical JSON.");
            }

            Dictionary<string, object> root =
                TevJson.RequireObject(parsed, "$");
            TevJson.RequireExactKeys(root, "$", "schema", "body", "signature");

            if (TevJson.RequireString(root, "schema") != PackageSchema)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_PACKAGE_SCHEMA",
                    "Unexpected signed update package schema.");
            }

            Dictionary<string, object> body =
                TevJson.RequireObject(root, "body");
            TevJson.RequireExactKeys(
                body,
                "$.body",
                "schema",
                "channel_id",
                "program_id",
                "epoch",
                "sequence",
                "program_semantic_hash",
                "ir_sha256",
                "ir");

            if (TevJson.RequireString(body, "schema") != BodySchema)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_BODY_SCHEMA",
                    "Unexpected update body schema.");
            }

            string channelId = RequireStableId(
                TevJson.RequireString(body, "channel_id"),
                "$.body.channel_id");
            string programId = TevJson.RequireString(body, "program_id");
            long epoch = RequirePositiveInt64(
                TevJson.RequireInteger(body["epoch"], "$.body.epoch"),
                "$.body.epoch");
            long sequence = RequirePositiveInt64(
                TevJson.RequireInteger(body["sequence"], "$.body.sequence"),
                "$.body.sequence");
            string semanticHash = RequireSha256(
                TevJson.RequireString(body, "program_semantic_hash"),
                "$.body.program_semantic_hash");
            string irSha = RequireSha256(
                TevJson.RequireString(body, "ir_sha256"),
                "$.body.ir_sha256");

            string programJson = TevJson.Canonicalize(body["ir"]);
            string observedIrSha = TevJson.Hash(body["ir"]);
            if (!string.Equals(observedIrSha, irSha, StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_IR_HASH",
                    "Embedded IR hash does not match ir_sha256.");
            }

            TevScriptProgram program = TevScriptProgram.Parse(programJson);
            if (!string.Equals(
                    program.ProgramId, programId, StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_PROGRAM_ID",
                    "Package program_id does not match embedded IR.");
            }
            if (!string.Equals(
                    program.SemanticHash,
                    semanticHash,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_SEMANTIC_HASH",
                    "Package semantic hash does not match embedded IR.");
            }

            Dictionary<string, object> signatureObject =
                TevJson.RequireObject(root, "signature");
            TevJson.RequireExactKeys(
                signatureObject,
                "$.signature",
                "algorithm",
                "key_id",
                "value");

            string algorithm = RequireStableId(
                TevJson.RequireString(signatureObject, "algorithm"),
                "$.signature.algorithm");
            string keyId = RequireStableId(
                TevJson.RequireString(signatureObject, "key_id"),
                "$.signature.key_id");
            string signatureText =
                TevJson.RequireString(signatureObject, "value");

            byte[] signature;
            try
            {
                signature = Convert.FromBase64String(signatureText);
            }
            catch (FormatException)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_SIGNATURE_BASE64",
                    "Update signature is not valid Base64.");
            }

            if (signature.Length == 0 ||
                !string.Equals(
                    Convert.ToBase64String(signature),
                    signatureText,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_SIGNATURE_BASE64",
                    "Update signature is not canonical Base64.");
            }

            string signedBodyJson = TevJson.Canonicalize(body);
            byte[] signedBodyBytes = Encoding.UTF8.GetBytes(signedBodyJson);

            return new TevScriptSignedUpdatePackage(
                canonical,
                TevJson.Sha256(canonical),
                channelId,
                programId,
                epoch,
                sequence,
                semanticHash,
                irSha,
                programJson,
                algorithm,
                keyId,
                signature,
                signedBodyJson,
                signedBodyBytes);
        }

        public void VerifySignature(ITevUpdateSignatureVerifier verifier)
        {
            if (verifier == null)
                throw new ArgumentNullException(nameof(verifier));

            if (!string.Equals(verifier.KeyId, KeyId, StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_KEY_AUTHORITY",
                    "Package key_id is not authorized.");
            }

            if (!string.Equals(
                    verifier.AlgorithmId,
                    SignatureAlgorithm,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_SIGNATURE_ALGORITHM",
                    "Package signature algorithm is not authorized.");
            }

            bool valid;
            try
            {
                valid = verifier.Verify(_signedBodyBytes, _signature);
            }
            catch (Exception exception)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_SIGNATURE_ENGINE",
                    "Signature verification failed closed: " +
                    exception.GetType().Name + ".");
            }

            if (!valid)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_SIGNATURE_INVALID",
                    "Update package signature is invalid.");
            }
        }

        private static long RequirePositiveInt64(BigInteger value, string path)
        {
            if (value < BigInteger.One ||
                value > new BigInteger(long.MaxValue))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_MONOTONIC_INTEGER",
                    "Expected a positive Int64.",
                    path);
            }
            return (long)value;
        }

        private static string RequireSha256(string value, string path)
        {
            if (value == null || value.Length != 64)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_SHA256",
                    "Expected lowercase SHA-256 hexadecimal.",
                    path);
            }
            for (int index = 0; index < value.Length; index++)
            {
                char c = value[index];
                if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')))
                {
                    throw new TevContractException(
                        "TEVS_CS_UPDATE_SHA256",
                        "Expected lowercase SHA-256 hexadecimal.",
                        path);
                }
            }
            return value;
        }

        private static string RequireStableId(string value, string path)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_ID",
                    "Expected stable identifier.",
                    path);
            }

            string text = value.Trim();
            if (!IsIdentifierStart(text[0]))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_ID",
                    "Expected stable identifier.",
                    path);
            }

            for (int index = 1; index < text.Length; index++)
            {
                char c = text[index];
                if (!IsIdentifierContinue(c) &&
                    c != '.' && c != ':' && c != '/' && c != '-')
                {
                    throw new TevContractException(
                        "TEVS_CS_UPDATE_ID",
                        "Expected stable identifier.",
                        path);
                }
            }
            return text;
        }

        private static bool IsIdentifierStart(char value)
        {
            return (value >= 'A' && value <= 'Z') ||
                (value >= 'a' && value <= 'z') ||
                value == '_';
        }

        private static bool IsIdentifierContinue(char value)
        {
            return IsIdentifierStart(value) ||
                (value >= '0' && value <= '9');
        }
    }

    public sealed class TevInstalledUpdateRecord
    {
        public const string Schema = "TEV_SCRIPT_INSTALLED_UPDATE_V1";

        public TevInstalledUpdateRecord(
            string channelId,
            long epoch,
            long sequence,
            string packageSha256,
            string packageJson)
        {
            ChannelId = channelId ??
                throw new ArgumentNullException(nameof(channelId));
            if (epoch < 1) throw new ArgumentOutOfRangeException(nameof(epoch));
            if (sequence < 1)
                throw new ArgumentOutOfRangeException(nameof(sequence));
            Epoch = epoch;
            Sequence = sequence;
            PackageSha256 = packageSha256 ??
                throw new ArgumentNullException(nameof(packageSha256));
            PackageJson = packageJson ??
                throw new ArgumentNullException(nameof(packageJson));
        }

        public string ChannelId { get; }
        public long Epoch { get; }
        public long Sequence { get; }
        public string PackageSha256 { get; }
        public string PackageJson { get; }

        public static TevInstalledUpdateRecord FromPackage(
            TevScriptSignedUpdatePackage package)
        {
            if (package == null)
                throw new ArgumentNullException(nameof(package));
            return new TevInstalledUpdateRecord(
                package.ChannelId,
                package.Epoch,
                package.Sequence,
                package.PackageSha256,
                package.CanonicalJson);
        }

        public string ToCanonicalJson()
        {
            var value = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                { "schema", Schema },
                { "channel_id", ChannelId },
                { "epoch", new BigInteger(Epoch) },
                { "sequence", new BigInteger(Sequence) },
                { "package_sha256", PackageSha256 },
                { "package_json", PackageJson }
            };
            return TevJson.Canonicalize(value);
        }

        public static TevInstalledUpdateRecord Parse(string json)
        {
            if (json == null) throw new ArgumentNullException(nameof(json));

            object parsed = TevJson.Parse(json);
            string canonical = TevJson.Canonicalize(parsed);
            if (!string.Equals(json, canonical, StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_STORE_CANONICAL",
                    "Installed update record is not canonical.");
            }

            Dictionary<string, object> root =
                TevJson.RequireObject(parsed, "$");
            TevJson.RequireExactKeys(
                root,
                "$",
                "schema",
                "channel_id",
                "epoch",
                "sequence",
                "package_sha256",
                "package_json");

            if (TevJson.RequireString(root, "schema") != Schema)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_STORE_SCHEMA",
                    "Unexpected installed update store schema.");
            }

            BigInteger epochInteger =
                TevJson.RequireInteger(root["epoch"], "$.epoch");
            BigInteger sequenceInteger =
                TevJson.RequireInteger(root["sequence"], "$.sequence");
            if (epochInteger < BigInteger.One ||
                epochInteger > new BigInteger(long.MaxValue) ||
                sequenceInteger < BigInteger.One ||
                sequenceInteger > new BigInteger(long.MaxValue))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_STORE_MONOTONIC",
                    "Installed epoch/sequence is invalid.");
            }

            string channelId =
                TevJson.RequireString(root, "channel_id");
            string packageSha =
                TevJson.RequireString(root, "package_sha256");
            string packageJson =
                TevJson.RequireString(root, "package_json");

            TevScriptSignedUpdatePackage package =
                TevScriptSignedUpdatePackage.Parse(packageJson);

            if (!string.Equals(
                    package.PackageSha256,
                    packageSha,
                    StringComparison.Ordinal) ||
                !string.Equals(
                    package.ChannelId,
                    channelId,
                    StringComparison.Ordinal) ||
                package.Epoch != (long)epochInteger ||
                package.Sequence != (long)sequenceInteger)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_STORE_INTEGRITY",
                    "Installed record does not match embedded package.");
            }

            return new TevInstalledUpdateRecord(
                channelId,
                (long)epochInteger,
                (long)sequenceInteger,
                packageSha,
                packageJson);
        }

        internal bool SameAuthorityState(TevInstalledUpdateRecord other)
        {
            return other != null &&
                string.Equals(
                    ChannelId, other.ChannelId, StringComparison.Ordinal) &&
                Epoch == other.Epoch &&
                Sequence == other.Sequence &&
                string.Equals(
                    PackageSha256,
                    other.PackageSha256,
                    StringComparison.Ordinal);
        }
    }

    public sealed class TevScriptUpdatePlan
    {
        private bool _consumed;

        internal TevScriptUpdatePlan(
            object owner,
            TevInstalledUpdateRecord sourceRecord,
            TevScriptSignedUpdatePackage package,
            TevScriptRuntimeSwapPlan runtimePlan)
        {
            Owner = owner;
            SourceRecord = sourceRecord;
            Package = package;
            RuntimePlan = runtimePlan;
        }

        internal object Owner { get; }
        internal TevInstalledUpdateRecord SourceRecord { get; }
        internal TevScriptRuntimeSwapPlan RuntimePlan { get; }
        public TevScriptSignedUpdatePackage Package { get; }
        public bool IsConsumed { get { return _consumed; } }

        internal void Consume()
        {
            if (_consumed)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_PLAN_CONSUMED",
                    "Update plan has already been consumed.");
            }
            _consumed = true;
        }
    }

    public sealed class TevScriptUpdateReceipt
    {
        internal TevScriptUpdateReceipt(
            long generation,
            string packageSha256,
            long epoch,
            long sequence,
            bool restore)
        {
            Generation = generation;
            PackageSha256 = packageSha256;
            Epoch = epoch;
            Sequence = sequence;
            Restore = restore;
        }

        public long Generation { get; }
        public string PackageSha256 { get; }
        public long Epoch { get; }
        public long Sequence { get; }
        public bool Restore { get; }
    }

    public sealed class TevScriptUpdateAuthority
    {
        private readonly object _planOwner = new object();
        private readonly TevScriptRuntimeHost _runtimeHost;
        private readonly string _channelId;
        private readonly ITevUpdateSignatureVerifier _signatureVerifier;
        private readonly ITevInstalledUpdateStore _store;

        public TevScriptUpdateAuthority(
            TevScriptRuntimeHost runtimeHost,
            string channelId,
            ITevUpdateSignatureVerifier signatureVerifier,
            ITevInstalledUpdateStore store)
        {
            _runtimeHost = runtimeHost ??
                throw new ArgumentNullException(nameof(runtimeHost));
            if (string.IsNullOrWhiteSpace(channelId))
                throw new ArgumentException(
                    "A channel id is required.", nameof(channelId));
            _channelId = channelId.Trim();
            _signatureVerifier = signatureVerifier ??
                throw new ArgumentNullException(nameof(signatureVerifier));
            _store = store ??
                throw new ArgumentNullException(nameof(store));
        }

        public TevScriptUpdatePlan Prepare(string packageJson)
        {
            TevScriptSignedUpdatePackage package =
                TevScriptSignedUpdatePackage.Parse(packageJson);
            package.VerifySignature(_signatureVerifier);

            if (!string.Equals(
                    package.ChannelId,
                    _channelId,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_CHANNEL",
                    "Package channel does not match this authority.");
            }

            TevInstalledUpdateRecord current = _store.Load(_channelId);
            ValidateReplay(current, package);

            TevScriptRuntimeSwapPlan runtimePlan =
                _runtimeHost.PrepareSwap(package.ProgramJson);

            return new TevScriptUpdatePlan(
                _planOwner,
                current,
                package,
                runtimePlan);
        }

        public TevScriptUpdateReceipt Commit(TevScriptUpdatePlan plan)
        {
            if (plan == null) throw new ArgumentNullException(nameof(plan));
            if (!ReferenceEquals(plan.Owner, _planOwner))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_PLAN_OWNER",
                    "Update plan belongs to another authority.");
            }
            if (plan.IsConsumed)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_PLAN_CONSUMED",
                    "Update plan has already been consumed.");
            }

            TevInstalledUpdateRecord current = _store.Load(_channelId);
            if (!SameRecord(current, plan.SourceRecord))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_PLAN_STALE",
                    "Update plan was prepared against stale durable state.");
            }

            TevScriptRuntimeSwapReceipt runtimeReceipt =
                _runtimeHost.Commit(plan.RuntimePlan);
            plan.Consume();

            TevInstalledUpdateRecord target =
                TevInstalledUpdateRecord.FromPackage(plan.Package);

            try
            {
                _store.Save(target);
            }
            catch (Exception exception)
            {
                try
                {
                    _runtimeHost.RollbackLastCommit();
                }
                catch
                {
                    throw new TevContractException(
                        "TEVS_CS_UPDATE_STORE_ROLLBACK",
                        "Durable commit failed and runtime rollback also failed.");
                }

                throw new TevContractException(
                    "TEVS_CS_UPDATE_STORE_COMMIT",
                    "Durable commit failed closed: " +
                    exception.GetType().Name + ".");
            }

            return new TevScriptUpdateReceipt(
                runtimeReceipt.Generation,
                plan.Package.PackageSha256,
                plan.Package.Epoch,
                plan.Package.Sequence,
                false);
        }

        public bool TryRestoreInstalled(out TevScriptUpdateReceipt receipt)
        {
            TevInstalledUpdateRecord record = _store.Load(_channelId);
            if (record == null)
            {
                receipt = null;
                return false;
            }

            TevScriptSignedUpdatePackage package =
                TevScriptSignedUpdatePackage.Parse(record.PackageJson);
            package.VerifySignature(_signatureVerifier);

            if (!string.Equals(
                    package.ChannelId,
                    _channelId,
                    StringComparison.Ordinal) ||
                package.Epoch != record.Epoch ||
                package.Sequence != record.Sequence ||
                !string.Equals(
                    package.PackageSha256,
                    record.PackageSha256,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_RESTORE_INTEGRITY",
                    "Durable state does not match installed package.");
            }

            TevScriptRuntimeSwapReceipt runtimeReceipt =
                _runtimeHost.Commit(
                    _runtimeHost.PrepareSwap(package.ProgramJson));

            receipt = new TevScriptUpdateReceipt(
                runtimeReceipt.Generation,
                package.PackageSha256,
                package.Epoch,
                package.Sequence,
                true);
            return true;
        }

        private static bool SameRecord(
            TevInstalledUpdateRecord left,
            TevInstalledUpdateRecord right)
        {
            if (left == null || right == null)
                return left == null && right == null;
            return left.SameAuthorityState(right);
        }

        private static void ValidateReplay(
            TevInstalledUpdateRecord current,
            TevScriptSignedUpdatePackage package)
        {
            if (current == null)
            {
                if (package.Epoch != 1 || package.Sequence != 1)
                {
                    throw new TevContractException(
                        "TEVS_CS_UPDATE_BOOTSTRAP_SEQUENCE",
                        "First update must be epoch=1 sequence=1.");
                }
                return;
            }

            if (package.Epoch < current.Epoch)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_EPOCH_ROLLBACK",
                    "Package epoch is older than durable state.");
            }

            if (package.Epoch == current.Epoch)
            {
                if (package.Sequence <= current.Sequence)
                {
                    throw new TevContractException(
                        "TEVS_CS_UPDATE_REPLAY",
                        "Package sequence is not newer than durable state.");
                }
                return;
            }

            if (package.Epoch != current.Epoch + 1)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_EPOCH_JUMP",
                    "Epoch may advance by exactly one.");
            }

            if (package.Sequence != 1)
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_EPOCH_SEQUENCE",
                    "A new epoch must begin at sequence 1.");
            }
        }
    }
}
