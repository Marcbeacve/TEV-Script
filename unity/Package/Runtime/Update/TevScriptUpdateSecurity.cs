using System;
using System.IO;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using System.Text;
using Marcbeacve.TevScript.Core;

namespace Marcbeacve.TevScript.Update
{
    public sealed class TevEcdsaP256Sha256Verifier :
        ITevUpdateSignatureVerifier
    {
        private readonly byte[] _x;
        private readonly byte[] _y;

        public TevEcdsaP256Sha256Verifier(
            string keyId,
            string xBase64,
            string yBase64)
        {
            if (string.IsNullOrWhiteSpace(keyId))
                throw new ArgumentException(
                    "A key id is required.", nameof(keyId));
            KeyId = keyId.Trim();
            AlgorithmId = "ES256";
            _x = DecodeCoordinate(xBase64, nameof(xBase64));
            _y = DecodeCoordinate(yBase64, nameof(yBase64));
        }

        public string KeyId { get; }
        public string AlgorithmId { get; }

        public bool Verify(byte[] data, byte[] signature)
        {
            if (data == null) throw new ArgumentNullException(nameof(data));
            if (signature == null)
                throw new ArgumentNullException(nameof(signature));
            if (signature.Length != 64) return false;

            var parameters = new ECParameters
            {
                Curve = ECCurve.NamedCurves.nistP256,
                Q = new ECPoint
                {
                    X = (byte[])_x.Clone(),
                    Y = (byte[])_y.Clone()
                }
            };

            using (ECDsa ecdsa = ECDsa.Create(parameters))
            {
                // The netstandard2.1 product surface uses the legacy/default
                // ECDSA signature representation, which is fixed-field P1363.
                // P-256 is additionally constrained to exactly 64 bytes.
                return ecdsa.VerifyData(
                    data,
                    signature,
                    HashAlgorithmName.SHA256);
            }
        }

        private static byte[] DecodeCoordinate(string value, string name)
        {
            if (string.IsNullOrWhiteSpace(value))
                throw new ArgumentException(
                    "A Base64 coordinate is required.", name);

            byte[] decoded;
            try
            {
                decoded = Convert.FromBase64String(value);
            }
            catch (FormatException)
            {
                throw new ArgumentException(
                    "Coordinate is not valid Base64.", name);
            }

            if (decoded.Length != 32 ||
                !string.Equals(
                    Convert.ToBase64String(decoded),
                    value,
                    StringComparison.Ordinal))
            {
                throw new ArgumentException(
                    "P-256 coordinate must be canonical 32-byte Base64.",
                    name);
            }
            return decoded;
        }
    }


    public sealed class TevWindowsCngEcdsaP256Sha256Verifier :
        ITevUpdateSignatureVerifier
    {
        private const string AlgorithmProvider = "ECDSA_P256";
        private const string EccPublicBlob = "ECCPUBLICBLOB";

        private readonly byte[] _x;
        private readonly byte[] _y;

        public TevWindowsCngEcdsaP256Sha256Verifier(
            string keyId,
            string xBase64,
            string yBase64)
        {
            if (string.IsNullOrWhiteSpace(keyId))
                throw new ArgumentException(
                    "A key id is required.", nameof(keyId));

            KeyId = keyId.Trim();
            AlgorithmId = "ES256";
            _x = DecodeCoordinate(xBase64, nameof(xBase64));
            _y = DecodeCoordinate(yBase64, nameof(yBase64));
        }

        public string KeyId { get; }
        public string AlgorithmId { get; }

        public bool Verify(byte[] data, byte[] signature)
        {
            if (data == null)
                throw new ArgumentNullException(nameof(data));
            if (signature == null)
                throw new ArgumentNullException(nameof(signature));
            if (signature.Length != 64)
                return false;

            byte[] digest;
            using (SHA256 sha = SHA256.Create())
            {
                digest = sha.ComputeHash(data);
            }

            byte[] blob = BuildPublicBlob(_x, _y);

            IntPtr algorithm = IntPtr.Zero;
            IntPtr key = IntPtr.Zero;
            try
            {
                int status = BCryptOpenAlgorithmProvider(
                    out algorithm,
                    AlgorithmProvider,
                    null,
                    0);
                ThrowIfFailed(status, "BCryptOpenAlgorithmProvider");

                status = BCryptImportKeyPair(
                    algorithm,
                    IntPtr.Zero,
                    EccPublicBlob,
                    out key,
                    blob,
                    blob.Length,
                    0);
                ThrowIfFailed(status, "BCryptImportKeyPair");

                status = BCryptVerifySignature(
                    key,
                    IntPtr.Zero,
                    digest,
                    digest.Length,
                    signature,
                    signature.Length,
                    0);

                return status == 0;
            }
            finally
            {
                if (key != IntPtr.Zero)
                    BCryptDestroyKey(key);

                if (algorithm != IntPtr.Zero)
                    BCryptCloseAlgorithmProvider(algorithm, 0);
            }
        }

        private static byte[] BuildPublicBlob(
            byte[] x,
            byte[] y)
        {
            if (x == null || y == null ||
                x.Length != 32 || y.Length != 32)
            {
                throw new ArgumentException(
                    "P-256 coordinates must be exactly 32 bytes.");
            }

            // BCRYPT_ECCKEY_BLOB header:
            // BCRYPT_ECDSA_PUBLIC_P256_MAGIC serializes as ASCII "ECS1"
            // in little-endian DWORD form; cbKey is 32.
            // X and Y then follow as 32-byte big-endian coordinates.
            byte[] blob = new byte[72];
            blob[0] = (byte)'E';
            blob[1] = (byte)'C';
            blob[2] = (byte)'S';
            blob[3] = (byte)'1';
            blob[4] = 32;
            blob[5] = 0;
            blob[6] = 0;
            blob[7] = 0;
            Buffer.BlockCopy(x, 0, blob, 8, 32);
            Buffer.BlockCopy(y, 0, blob, 40, 32);
            return blob;
        }

        private static byte[] DecodeCoordinate(
            string value,
            string name)
        {
            if (string.IsNullOrWhiteSpace(value))
                throw new ArgumentException(
                    "A Base64 coordinate is required.", name);

            byte[] decoded;
            try
            {
                decoded = Convert.FromBase64String(value);
            }
            catch (FormatException)
            {
                throw new ArgumentException(
                    "Coordinate is not valid Base64.", name);
            }

            if (decoded.Length != 32 ||
                !string.Equals(
                    Convert.ToBase64String(decoded),
                    value,
                    StringComparison.Ordinal))
            {
                throw new ArgumentException(
                    "P-256 coordinate must be canonical 32-byte Base64.",
                    name);
            }

            return decoded;
        }

        private static void ThrowIfFailed(
            int status,
            string operation)
        {
            if (status != 0)
            {
                throw new InvalidOperationException(
                    operation +
                    " failed with NTSTATUS=0x" +
                    unchecked((uint)status).ToString("x8") +
                    ".");
            }
        }

        [DllImport(
            "bcrypt.dll",
            ExactSpelling = true,
            CharSet = CharSet.Unicode)]
        private static extern int BCryptOpenAlgorithmProvider(
            out IntPtr phAlgorithm,
            string pszAlgId,
            string pszImplementation,
            uint dwFlags);

        [DllImport(
            "bcrypt.dll",
            ExactSpelling = true,
            CharSet = CharSet.Unicode)]
        private static extern int BCryptImportKeyPair(
            IntPtr hAlgorithm,
            IntPtr hImportKey,
            string pszBlobType,
            out IntPtr phKey,
            byte[] pbInput,
            int cbInput,
            uint dwFlags);

        [DllImport(
            "bcrypt.dll",
            ExactSpelling = true)]
        private static extern int BCryptVerifySignature(
            IntPtr hKey,
            IntPtr pPaddingInfo,
            byte[] pbHash,
            int cbHash,
            byte[] pbSignature,
            int cbSignature,
            uint dwFlags);

        [DllImport(
            "bcrypt.dll",
            ExactSpelling = true)]
        private static extern int BCryptDestroyKey(
            IntPtr hKey);

        [DllImport(
            "bcrypt.dll",
            ExactSpelling = true)]
        private static extern int BCryptCloseAlgorithmProvider(
            IntPtr hAlgorithm,
            uint dwFlags);
    }

    public sealed class TevFileInstalledUpdateStore :
        ITevInstalledUpdateStore
    {
        private readonly string _path;

        public TevFileInstalledUpdateStore(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
                throw new ArgumentException(
                    "A store path is required.", nameof(path));
            _path = Path.GetFullPath(path);
        }

        public TevInstalledUpdateRecord Load(string channelId)
        {
            if (!File.Exists(_path)) return null;

            string json = File.ReadAllText(
                _path,
                new UTF8Encoding(false, true));
            TevInstalledUpdateRecord record =
                TevInstalledUpdateRecord.Parse(json);

            if (!string.Equals(
                    record.ChannelId,
                    channelId,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_UPDATE_STORE_CHANNEL",
                    "Durable record belongs to another channel.");
            }
            return record;
        }

        public void Save(TevInstalledUpdateRecord record)
        {
            if (record == null) throw new ArgumentNullException(nameof(record));

            string directory = Path.GetDirectoryName(_path);
            if (string.IsNullOrEmpty(directory))
                throw new InvalidOperationException(
                    "Installed-update path has no parent directory.");
            Directory.CreateDirectory(directory);

            string temporary =
                _path + ".tmp." + Guid.NewGuid().ToString("N");
            byte[] bytes = new UTF8Encoding(false, true).GetBytes(
                record.ToCanonicalJson());

            try
            {
                using (var stream = new FileStream(
                    temporary,
                    FileMode.CreateNew,
                    FileAccess.Write,
                    FileShare.None))
                {
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }

                if (File.Exists(_path))
                    File.Replace(temporary, _path, null);
                else
                    File.Move(temporary, _path);
            }
            finally
            {
                if (File.Exists(temporary))
                    File.Delete(temporary);
            }
        }
    }
}
