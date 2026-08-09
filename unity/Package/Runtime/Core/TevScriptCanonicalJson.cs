using System;
using System.Collections.Generic;

namespace Marcbeacve.TevScript.Core
{
    public static class TevScriptCanonicalJson
    {
        public static string Canonicalize(string json)
        {
            if (json == null) throw new ArgumentNullException(nameof(json));
            return TevJson.Canonicalize(TevJson.Parse(json));
        }

        public static string Hash(string json)
        {
            if (json == null) throw new ArgumentNullException(nameof(json));
            return TevJson.Hash(TevJson.Parse(json));
        }

        public static int VerifyVectorSet(string vectorsJson)
        {
            if (vectorsJson == null)
                throw new ArgumentNullException(nameof(vectorsJson));

            Dictionary<string, object> root = TevJson.RequireObject(
                TevJson.Parse(vectorsJson),
                "$");
            TevJson.RequireExactKeys(
                root,
                "$",
                "schema",
                "profile",
                "vectors");
            if (TevJson.RequireString(root, "schema") !=
                "TEV_CANONICAL_JSON_VECTORS_V1")
            {
                throw new TevContractException(
                    "TEVS_CS_CANONICAL_VECTOR_SCHEMA",
                    "Unexpected canonical vector schema.");
            }
            if (TevJson.RequireString(root, "profile") !=
                "TEV_CANONICAL_JSON_V1")
            {
                throw new TevContractException(
                    "TEVS_CS_CANONICAL_VECTOR_PROFILE",
                    "Unexpected canonical JSON profile.");
            }

            List<object> vectors = TevJson.RequireArray(root, "vectors");
            if (vectors.Count == 0)
            {
                throw new TevContractException(
                    "TEVS_CS_CANONICAL_VECTOR_EMPTY",
                    "Canonical vector set must be non-empty.");
            }

            for (int index = 0; index < vectors.Count; index++)
            {
                Dictionary<string, object> vector = TevJson.RequireObject(
                    vectors[index],
                    "vectors[" + index + "]");
                TevJson.RequireExactKeys(
                    vector,
                    "vectors[" + index + "]",
                    "id",
                    "value",
                    "canonical",
                    "sha256");
                string id = TevJson.RequireString(vector, "id");
                string expectedCanonical =
                    TevJson.RequireString(vector, "canonical");
                string expectedHash = TevJson.RequireString(vector, "sha256");
                string observedCanonical = TevJson.Canonicalize(vector["value"]);
                string observedHash = TevJson.Hash(vector["value"]);
                if (!string.Equals(
                        observedCanonical,
                        expectedCanonical,
                        StringComparison.Ordinal))
                {
                    throw new TevContractException(
                        "TEVS_CS_CANONICAL_VECTOR_TEXT",
                        "Canonical JSON mismatch for vector " + id + ".");
                }
                if (!string.Equals(
                        observedHash,
                        expectedHash,
                        StringComparison.Ordinal))
                {
                    throw new TevContractException(
                        "TEVS_CS_CANONICAL_VECTOR_HASH",
                        "SHA-256 mismatch for vector " + id + ".");
                }
            }

            return vectors.Count;
        }
    }
}
