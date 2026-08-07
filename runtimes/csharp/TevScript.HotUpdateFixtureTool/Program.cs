using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Marcbeacve.TevScript.Core;

internal static class Program
{
    private const string PrimaryKeyId = "tev-test-update-key-v1";

    private const string PrimaryD =
        "g0kw8dI0adSQ84SNEj4r4MlmShUK/CnXjJmL6NstPrQ=";
    private const string PrimaryX =
        "JV8YUahvnNr8TZouyW7ek7jgGLnGW59062dKKDrsozM=";
    private const string PrimaryY =
        "lelmvUQzVnJKnfQKqXWHEchkUySpSZFcxfLskTG52rA=";

    private const string WrongD =
        "UBz6if6UKesaHkhIGJZLpVkqj8n/Mpx5ugMSgD9cCpE=";
    private const string WrongX =
        "JvPvStpd0Hq28YmV062oeDH0q/lhQ9Z26hnQ7Ynd3JE=";
    private const string WrongY =
        "9c3qEf7+j3veHo9Qv0jIitT9swzwv4o5mfMPW8aWeWg=";

    private static int Main(string[] args)
    {
        try
        {
            string basePath = RequireArg(args, "--base");
            string output = RequireArg(args, "--out");
            Directory.CreateDirectory(output);

            string baseText = File.ReadAllText(basePath);
            string baseCanonical =
                TevScriptCanonicalJson.Canonicalize(baseText);
            TevScriptProgram.Parse(baseCanonical);

            string p1 = CreateCandidate(baseCanonical, 0);
            string p2 = CreateCandidate(baseCanonical, 1);
            string e2 = CreateCandidate(baseCanonical, 2);
            string e1High = CreateCandidate(baseCanonical, 3);
            string e3Bad = CreateCandidate(baseCanonical, 4);
            string e2s2 = CreateCandidate(baseCanonical, 5);
            string e2s3 = CreateCandidate(baseCanonical, 6);

            using (ECDsa primary = CreateKey(
                PrimaryD, PrimaryX, PrimaryY))
            using (ECDsa wrong = CreateKey(
                WrongD, WrongX, WrongY))
            {
                string package1 = CreatePackage(
                    p1, primary, PrimaryKeyId, "ES256", 1, 1);
                string package2 = CreatePackage(
                    p2, primary, PrimaryKeyId, "ES256", 1, 2);
                string packageEpoch2 = CreatePackage(
                    e2, primary, PrimaryKeyId, "ES256", 2, 1);
                string packageEpoch1High = CreatePackage(
                    e1High, primary, PrimaryKeyId, "ES256", 1, 99);
                string packageEpoch3Bad = CreatePackage(
                    e3Bad, primary, PrimaryKeyId, "ES256", 3, 2);
                string packageEpoch2Seq2 = CreatePackage(
                    e2s2, primary, PrimaryKeyId, "ES256", 2, 2);
                string packageEpoch2Seq3 = CreatePackage(
                    e2s3, primary, PrimaryKeyId, "ES256", 2, 3);

                Write(output, "base.json", baseCanonical);
                Write(output, "package1.json", package1);
                Write(output, "package2.json", package2);
                Write(output, "package_epoch2.json", packageEpoch2);
                Write(output, "package_epoch1_high.json", packageEpoch1High);
                Write(output, "package_epoch3_badseq.json", packageEpoch3Bad);
                Write(output, "package_epoch2_seq2.json", packageEpoch2Seq2);
                Write(output, "package_epoch2_seq3.json", packageEpoch2Seq3);

                string tampered = TamperSequence(package1, 2);
                Write(output, "package_tampered.json", tampered);

                string wrongKeyPackage = CreatePackage(
                    p1, wrong, PrimaryKeyId, "ES256", 1, 1);
                Write(output, "package_wrong_key.json", wrongKeyPackage);

                string unknownAlgorithm =
                    RewriteAlgorithm(package1, "ES999");
                Write(
                    output,
                    "package_unknown_algorithm.json",
                    unknownAlgorithm);

                File.WriteAllText(
                    Path.Combine(output, "package_noncanonical.json"),
                    " " + package1,
                    new UTF8Encoding(false));

                string authority = CanonicalizeNode(
                    new JsonObject
                    {
                        ["schema"] =
                            "TEV_SCRIPT_UPDATE_KEY_AUTHORITY_V1",
                        ["algorithm"] = "ES256",
                        ["key_id"] = PrimaryKeyId,
                        ["x"] = PrimaryX,
                        ["y"] = PrimaryY
                    });
                string wrongAuthority = CanonicalizeNode(
                    new JsonObject
                    {
                        ["schema"] =
                            "TEV_SCRIPT_UPDATE_KEY_AUTHORITY_V1",
                        ["algorithm"] = "ES256",
                        ["key_id"] = "tev-wrong-update-key-v1",
                        ["x"] = WrongX,
                        ["y"] = WrongY
                    });
                Write(output, "authority.json", authority);
                Write(output, "wrong_authority.json", wrongAuthority);

                Console.WriteLine(
                    "GATE5C_FIXTURE_ES256_P256_SHA256=PASS");
                Console.WriteLine(
                    "GATE5C_SIGNATURE_FORMAT=IEEE_P1363_FIXED_64");
                Console.WriteLine(
                    "GATE5C_TEST_PRIVATE_KEY_SCOPE=FIXTURE_TOOL_ONLY");
                Console.WriteLine(
                    "GATE5D_MONOTONIC_FIXTURE_SET=PASS");
                Console.WriteLine(
                    "GATE5E_REMOTE_FIXTURE_SET=PASS");
                Console.WriteLine(
                    "PACKAGE1_SHA256=" +
                    TevScriptCanonicalJson.Hash(package1));
                Console.WriteLine(
                    "PACKAGE2_SHA256=" +
                    TevScriptCanonicalJson.Hash(package2));
                Console.WriteLine(
                    "PACKAGE_EPOCH2_SHA256=" +
                    TevScriptCanonicalJson.Hash(packageEpoch2));
            }

            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            return 81;
        }
    }

    private static string CreateCandidate(
        string baseCanonical,
        int damageAmount)
    {
        JsonObject root =
            (JsonObject)JsonNode.Parse(baseCanonical);

        JsonArray entities = (JsonArray)root["entities"];
        JsonObject player = null;
        for (int index = 0; index < entities.Count; index++)
        {
            JsonObject entity = (JsonObject)entities[index];
            if (entity["entity_id"].GetValue<string>() == "Player")
            {
                player = entity;
                break;
            }
        }
        if (player == null)
            throw new InvalidOperationException("Player entity missing.");

        JsonArray states = (JsonArray)player["states"];
        bool hasAdded = false;
        for (int index = 0; index < states.Count; index++)
        {
            JsonObject state = (JsonObject)states[index];
            if (state["name"].GetValue<string>() == "__hot_update_added")
                hasAdded = true;
        }
        if (!hasAdded)
        {
            JsonObject added =
                (JsonObject)JsonNode.Parse(states[0].ToJsonString());
            added["name"] = "__hot_update_added";
            states.Add(added);
        }

        JsonArray handlers = (JsonArray)player["handlers"];
        JsonObject damage = null;
        for (int index = 0; index < handlers.Count; index++)
        {
            JsonObject handler = (JsonObject)handlers[index];
            if (handler["event_id"].GetValue<string>() == "damage")
            {
                damage = handler;
                break;
            }
        }
        if (damage == null)
            throw new InvalidOperationException("damage handler missing.");

        JsonArray instructions = (JsonArray)damage["instructions"];
        bool replaced = false;
        for (int index = 0; index < instructions.Count; index++)
        {
            JsonObject instruction = (JsonObject)instructions[index];
            if (instruction["op"].GetValue<string>() == "LOAD_PARAM" &&
                instruction["name"].GetValue<string>() == "amount")
            {
                instructions[index] = new JsonObject
                {
                    ["op"] = "CONST",
                    ["type"] = "Int",
                    ["value"] = new JsonObject
                    {
                        ["$int"] = damageAmount.ToString(
                            System.Globalization.CultureInfo.InvariantCulture)
                    }
                };
                replaced = true;
                break;
            }
        }
        if (!replaced)
            throw new InvalidOperationException(
                "damage amount operand not replaced.");

        JsonObject semantic =
            (JsonObject)JsonNode.Parse(root.ToJsonString());
        semantic.Remove("semantic_hash");
        semantic.Remove("debug");
        semantic.Remove("debug_hash");

        root["semantic_hash"] =
            TevScriptCanonicalJson.Hash(semantic.ToJsonString());

        string canonical = CanonicalizeNode(root);
        TevScriptProgram.Parse(canonical);
        return canonical;
    }

    private static string CreatePackage(
        string programJson,
        ECDsa key,
        string keyId,
        string algorithm,
        long epoch,
        long sequence)
    {
        TevScriptProgram program =
            TevScriptProgram.Parse(programJson);

        JsonObject body = new JsonObject
        {
            ["schema"] = "TEV_SCRIPT_UPDATE_BODY_V1",
            ["channel_id"] = "stable",
            ["program_id"] = program.ProgramId,
            ["epoch"] = epoch,
            ["sequence"] = sequence,
            ["program_semantic_hash"] = program.SemanticHash,
            ["ir_sha256"] =
                TevScriptCanonicalJson.Hash(programJson),
            ["ir"] = JsonNode.Parse(programJson)
        };

        string bodyCanonical = CanonicalizeNode(body);
        byte[] signature = key.SignData(
            Encoding.UTF8.GetBytes(bodyCanonical),
            HashAlgorithmName.SHA256,
            DSASignatureFormat.IeeeP1363FixedFieldConcatenation);

        if (signature.Length != 64)
            throw new InvalidOperationException(
                "Expected fixed 64-byte P-256 signature.");

        JsonObject package = new JsonObject
        {
            ["schema"] =
                "TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V1",
            ["body"] = JsonNode.Parse(bodyCanonical),
            ["signature"] = new JsonObject
            {
                ["algorithm"] = algorithm,
                ["key_id"] = keyId,
                ["value"] = Convert.ToBase64String(signature)
            }
        };

        string result = CanonicalizeNode(package);
        TevScriptSignedUpdatePackage parsed =
            TevScriptSignedUpdatePackage.Parse(result);
        if (parsed.Signature.Length != 64)
            throw new InvalidOperationException(
                "Signed package signature length drift.");
        return result;
    }

    private static string TamperSequence(
        string packageJson,
        long newSequence)
    {
        JsonObject package =
            (JsonObject)JsonNode.Parse(packageJson);
        JsonObject body = (JsonObject)package["body"];
        body["sequence"] = newSequence;
        return CanonicalizeNode(package);
    }

    private static string RewriteAlgorithm(
        string packageJson,
        string algorithm)
    {
        JsonObject package =
            (JsonObject)JsonNode.Parse(packageJson);
        JsonObject signature =
            (JsonObject)package["signature"];
        signature["algorithm"] = algorithm;
        return CanonicalizeNode(package);
    }

    private static ECDsa CreateKey(
        string d,
        string x,
        string y)
    {
        var parameters = new ECParameters
        {
            Curve = ECCurve.NamedCurves.nistP256,
            D = Convert.FromBase64String(d),
            Q = new ECPoint
            {
                X = Convert.FromBase64String(x),
                Y = Convert.FromBase64String(y)
            }
        };
        return ECDsa.Create(parameters);
    }

    private static string CanonicalizeNode(JsonNode node)
    {
        return TevScriptCanonicalJson.Canonicalize(
            node.ToJsonString());
    }

    private static void Write(
        string directory,
        string name,
        string content)
    {
        File.WriteAllText(
            Path.Combine(directory, name),
            content,
            new UTF8Encoding(false));
    }

    private static string RequireArg(
        string[] args,
        string name)
    {
        for (int index = 0; index + 1 < args.Length; index++)
        {
            if (args[index] == name)
                return args[index + 1];
        }
        throw new ArgumentException("Missing " + name + ".");
    }
}
