using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using TevScript.Core.V3;

internal static class Program
{
    private const string PrimaryKeyId = "tev-test-update-key-v1";
    private const string PrimaryD = "g0kw8dI0adSQ84SNEj4r4MlmShUK/CnXjJmL6NstPrQ=";
    private const string PrimaryX = "JV8YUahvnNr8TZouyW7ek7jgGLnGW59062dKKDrsozM=";
    private const string PrimaryY = "lelmvUQzVnJKnfQKqXWHEchkUySpSZFcxfLskTG52rA=";
    private const string WrongD = "UBz6if6UKesaHkhIGJZLpVkqj8n/Mpx5ugMSgD9cCpE=";
    private const string WrongX = "JvPvStpd0Hq28YmV062oeDH0q/lhQ9Z26hnQ7Ynd3JE=";
    private const string WrongY = "9c3qEf7+j3veHo9Qv0jIitT9swzwv4o5mfMPW8aWeWg=";

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length != 2 || args[0] != "--dir")
                throw new ArgumentException("usage: TevScript.V3UpdateFixtureTool --dir <program-fixture-dir>");
            var root = Path.GetFullPath(args[1]);
            Directory.CreateDirectory(root);

            var baseIr = Load(root, "base.ir.json");
            var target1 = Load(root, "target1.ir.json");
            var target2 = Load(root, "target2.ir.json");
            var target3 = Load(root, "target3.ir.json");
            var removed = Load(root, "removed_state.ir.json");
            var typeChanged = Load(root, "type_changed.ir.json");
            var capabilityChanged = Load(root, "capability_abi_changed.ir.json");
            var recordChanged = Load(root, "record_abi_changed.ir.json");

            using var primary = CreateKey(PrimaryD, PrimaryX, PrimaryY);
            using var wrong = CreateKey(WrongD, WrongX, WrongY);

            var package1 = CreatePackage(baseIr, target1, primary, PrimaryKeyId, "ES256", 1, 1);
            var package2 = CreatePackage(target1, target2, primary, PrimaryKeyId, "ES256", 1, 2);
            var packageEpoch2 = CreatePackage(target2, target3, primary, PrimaryKeyId, "ES256", 2, 1);
            var packageRemoved = CreatePackage(baseIr, removed, primary, PrimaryKeyId, "ES256", 1, 1);
            var packageTypeChanged = CreatePackage(baseIr, typeChanged, primary, PrimaryKeyId, "ES256", 1, 1);
            var packageCapabilityChanged = CreatePackage(baseIr, capabilityChanged, primary, PrimaryKeyId, "ES256", 1, 1);
            var packageRecordChanged = CreatePackage(baseIr, recordChanged, primary, PrimaryKeyId, "ES256", 1, 1);
            var packageWrongFrom = CreatePackage(target3, target1, primary, PrimaryKeyId, "ES256", 1, 1);
            var packageWrongKey = CreatePackage(baseIr, target1, wrong, PrimaryKeyId, "ES256", 1, 1);
            var packageUnknownAlgorithm = CreatePackage(baseIr, target1, primary, PrimaryKeyId, "ES999", 1, 1);
            var packageTampered = TamperSequence(package1, 2);

            Write(root, "package1.json", package1);
            Write(root, "package2.json", package2);
            Write(root, "package_epoch2.json", packageEpoch2);
            Write(root, "package_removed_state.json", packageRemoved);
            Write(root, "package_type_changed.json", packageTypeChanged);
            Write(root, "package_capability_abi_changed.json", packageCapabilityChanged);
            Write(root, "package_record_abi_changed.json", packageRecordChanged);
            Write(root, "package_wrong_from.json", packageWrongFrom);
            Write(root, "package_wrong_key.json", packageWrongKey);
            Write(root, "package_unknown_algorithm.json", packageUnknownAlgorithm);
            Write(root, "package_tampered.json", packageTampered);
            File.WriteAllText(
                Path.Combine(root, "package_noncanonical.json"),
                " " + package1,
                new UTF8Encoding(false));

            Write(root, "authority.json", CanonicalNode(new JsonObject
            {
                ["schema"] = "TEV_SCRIPT_UPDATE_KEY_AUTHORITY_V1",
                ["algorithm"] = "ES256",
                ["key_id"] = PrimaryKeyId,
                ["x"] = PrimaryX,
                ["y"] = PrimaryY,
            }));
            Write(root, "wrong_authority.json", CanonicalNode(new JsonObject
            {
                ["schema"] = "TEV_SCRIPT_UPDATE_KEY_AUTHORITY_V1",
                ["algorithm"] = "ES256",
                ["key_id"] = "tev-wrong-update-key-v1",
                ["x"] = WrongX,
                ["y"] = WrongY,
            }));

            Console.WriteLine("TEV_SCRIPT_IR_V3_UPDATE_FIXTURE_SIGNER=PASS");
            Console.WriteLine("TEV_SCRIPT_IR_V3_UPDATE_SIGNATURE_FORMAT=IEEE_P1363_FIXED_64");
            Console.WriteLine("TEV_SCRIPT_IR_V3_UPDATE_TEST_PRIVATE_KEY_SCOPE=FIXTURE_TOOL_ONLY");
            Console.WriteLine("TEV_SCRIPT_IR_V3_UPDATE_PACKAGE1_SHA256=" + TevScriptSignedUpdatePackageV3.Parse(package1).PackageSha256);
            Console.WriteLine("TEV_SCRIPT_IR_V3_UPDATE_PACKAGE2_SHA256=" + TevScriptSignedUpdatePackageV3.Parse(package2).PackageSha256);
            Console.WriteLine("TEV_SCRIPT_IR_V3_UPDATE_PACKAGE_EPOCH2_SHA256=" + TevScriptSignedUpdatePackageV3.Parse(packageEpoch2).PackageSha256);
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 81;
        }
    }

    private static string Load(string root, string name)
    {
        var text = File.ReadAllText(Path.Combine(root, name), Encoding.UTF8);
        var ir = TevScriptStrictJsonV3.ParseElement(text);
        TevScriptProgramValidatorV3.Validate(ir);
        var canonical = TevScriptCanonicalV3.Json(ir);
        if (!StringComparer.Ordinal.Equals(text, canonical))
            throw new InvalidOperationException(name + " is not canonical IR V3");
        return canonical;
    }

    private static string CreatePackage(
        string fromProgramJson,
        string targetProgramJson,
        ECDsa key,
        string keyId,
        string algorithm,
        long epoch,
        long sequence)
    {
        var fromIr = TevScriptStrictJsonV3.ParseElement(fromProgramJson);
        var targetIr = TevScriptStrictJsonV3.ParseElement(targetProgramJson);
        TevScriptProgramValidatorV3.Validate(fromIr);
        TevScriptProgramValidatorV3.Validate(targetIr);
        if (fromIr.GetProperty("program_id").GetString() != targetIr.GetProperty("program_id").GetString())
            throw new InvalidOperationException("fixture transition changes program id");

        var body = new JsonObject
        {
            ["schema"] = "TEV_SCRIPT_UPDATE_BODY_V2",
            ["channel_id"] = "stable",
            ["program_id"] = targetIr.GetProperty("program_id").GetString(),
            ["epoch"] = epoch,
            ["sequence"] = sequence,
            ["from_ir_semantic_hash"] = fromIr.GetProperty("semantic_hash").GetString(),
            ["target_ir_semantic_hash"] = targetIr.GetProperty("semantic_hash").GetString(),
            ["target_source_semantic_hash"] = targetIr.GetProperty("source_semantic_hash").GetString(),
            ["ir_sha256"] = TevScriptCanonicalV3.Sha256(targetIr),
            ["ir"] = JsonNode.Parse(targetProgramJson),
        };
        var bodyCanonical = CanonicalNode(body);
        var signature = key.SignData(
            Encoding.UTF8.GetBytes(bodyCanonical),
            HashAlgorithmName.SHA256,
            DSASignatureFormat.IeeeP1363FixedFieldConcatenation);
        if (signature.Length != 64)
            throw new InvalidOperationException("fixture signer did not produce 64-byte P1363 signature");
        var root = new JsonObject
        {
            ["schema"] = "TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V2",
            ["body"] = JsonNode.Parse(bodyCanonical),
            ["signature"] = new JsonObject
            {
                ["algorithm"] = algorithm,
                ["key_id"] = keyId,
                ["value"] = Convert.ToBase64String(signature),
            },
        };
        var canonical = CanonicalNode(root);
        TevScriptSignedUpdatePackageV3.Parse(canonical);
        return canonical;
    }

    private static string TamperSequence(string packageJson, long sequence)
    {
        var root = JsonNode.Parse(packageJson)?.AsObject()
            ?? throw new InvalidOperationException("package JSON parse failed");
        root["body"]!["sequence"] = sequence;
        return CanonicalNode(root);
    }

    private static string CanonicalNode(JsonNode node) =>
        TevScriptCanonicalV3.Json(TevScriptStrictJsonV3.ParseElement(node.ToJsonString()));

    private static void Write(string root, string name, string value) =>
        File.WriteAllText(Path.Combine(root, name), value, new UTF8Encoding(false));

    private static ECDsa CreateKey(string dBase64, string xBase64, string yBase64)
    {
        var key = ECDsa.Create();
        key.ImportParameters(new ECParameters
        {
            Curve = ECCurve.NamedCurves.nistP256,
            D = Convert.FromBase64String(dBase64),
            Q = new ECPoint
            {
                X = Convert.FromBase64String(xBase64),
                Y = Convert.FromBase64String(yBase64),
            },
        });
        return key;
    }
}
