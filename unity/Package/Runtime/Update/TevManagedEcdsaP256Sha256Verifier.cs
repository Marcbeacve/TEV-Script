using System;
using System.Numerics;
using System.Text;
using Marcbeacve.TevScript.Core;

namespace Marcbeacve.TevScript.Update
{
    public sealed class TevManagedEcdsaP256Sha256Verifier : ITevUpdateSignatureVerifier
    {
        private readonly BigInteger _qx;
        private readonly BigInteger _qy;

        public TevManagedEcdsaP256Sha256Verifier(
            string keyId,
            string xBase64,
            string yBase64)
        {
            if (string.IsNullOrWhiteSpace(keyId))
                throw new ArgumentException("A key id is required.", nameof(keyId));

            KeyId = keyId.Trim();
            AlgorithmId = "ES256";

            byte[] x = DecodeCoordinate(xBase64, nameof(xBase64));
            byte[] y = DecodeCoordinate(yBase64, nameof(yBase64));
            _qx = FromUnsignedBigEndian(x);
            _qy = FromUnsignedBigEndian(y);

            if (!P256.IsOnCurve(_qx, _qy))
                throw new ArgumentException("P-256 public key is not on the curve.");
        }

        public string KeyId { get; }
        public string AlgorithmId { get; }

        public bool Verify(byte[] data, byte[] signature)
        {
            if (data == null) throw new ArgumentNullException(nameof(data));
            if (signature == null) throw new ArgumentNullException(nameof(signature));
            if (signature.Length != 64) return false;

            BigInteger r = FromUnsignedBigEndian(signature, 0, 32);
            BigInteger s = FromUnsignedBigEndian(signature, 32, 32);
            if (r <= BigInteger.Zero || r >= P256.N ||
                s <= BigInteger.Zero || s >= P256.N)
                return false;

            byte[] digest = Sha256.Compute(data);
            BigInteger z = FromUnsignedBigEndian(digest);
            BigInteger w = P256.ModInverse(s, P256.N);
            BigInteger u1 = P256.Mod(z * w, P256.N);
            BigInteger u2 = P256.Mod(r * w, P256.N);

            P256.JacobianPoint p1 = P256.Multiply(P256.Gx, P256.Gy, u1);
            P256.JacobianPoint p2 = P256.Multiply(_qx, _qy, u2);
            P256.JacobianPoint sum = P256.Add(p1, p2);
            if (sum.IsInfinity) return false;

            BigInteger x = P256.ToAffineX(sum);
            return P256.Mod(x, P256.N) == r;
        }

        private static byte[] DecodeCoordinate(string value, string name)
        {
            if (string.IsNullOrWhiteSpace(value))
                throw new ArgumentException("A Base64 coordinate is required.", name);

            byte[] decoded;
            try { decoded = Convert.FromBase64String(value); }
            catch (FormatException)
            {
                throw new ArgumentException("Coordinate is not valid Base64.", name);
            }

            if (decoded.Length != 32 ||
                !string.Equals(Convert.ToBase64String(decoded), value, StringComparison.Ordinal))
                throw new ArgumentException(
                    "P-256 coordinate must be canonical 32-byte Base64.", name);
            return decoded;
        }

        private static BigInteger FromUnsignedBigEndian(byte[] bytes)
        {
            return FromUnsignedBigEndian(bytes, 0, bytes.Length);
        }

        private static BigInteger FromUnsignedBigEndian(byte[] bytes, int offset, int count)
        {
            byte[] little = new byte[count + 1];
            for (int i = 0; i < count; i++)
                little[i] = bytes[offset + count - 1 - i];
            return new BigInteger(little);
        }

        private static class P256
        {
            internal static readonly BigInteger P = Hex(
                "FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF");
            internal static readonly BigInteger A = P - 3;
            internal static readonly BigInteger B = Hex(
                "5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B");
            internal static readonly BigInteger Gx = Hex(
                "6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296");
            internal static readonly BigInteger Gy = Hex(
                "4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5");
            internal static readonly BigInteger N = Hex(
                "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551");

            internal struct JacobianPoint
            {
                internal BigInteger X;
                internal BigInteger Y;
                internal BigInteger Z;
                internal bool IsInfinity { get { return Z.IsZero; } }
            }

            internal static bool IsOnCurve(BigInteger x, BigInteger y)
            {
                if (x.Sign < 0 || x >= P || y.Sign < 0 || y >= P) return false;
                BigInteger left = Mod(y * y, P);
                BigInteger right = Mod(x * x * x + A * x + B, P);
                return left == right;
            }

            internal static JacobianPoint Multiply(BigInteger x, BigInteger y, BigInteger k)
            {
                JacobianPoint result = Infinity();
                JacobianPoint addend = new JacobianPoint { X = x, Y = y, Z = BigInteger.One };
                while (k.Sign > 0)
                {
                    if (!k.IsEven) result = Add(result, addend);
                    addend = Double(addend);
                    k >>= 1;
                }
                return result;
            }

            internal static JacobianPoint Add(JacobianPoint p1, JacobianPoint p2)
            {
                if (p1.IsInfinity) return p2;
                if (p2.IsInfinity) return p1;

                BigInteger z1z1 = Mod(p1.Z * p1.Z, P);
                BigInteger z2z2 = Mod(p2.Z * p2.Z, P);
                BigInteger u1 = Mod(p1.X * z2z2, P);
                BigInteger u2 = Mod(p2.X * z1z1, P);
                BigInteger s1 = Mod(p1.Y * p2.Z * z2z2, P);
                BigInteger s2 = Mod(p2.Y * p1.Z * z1z1, P);

                if (u1 == u2)
                {
                    if (s1 != s2) return Infinity();
                    return Double(p1);
                }

                BigInteger h = Mod(u2 - u1, P);
                BigInteger r = Mod(s2 - s1, P);
                BigInteger hh = Mod(h * h, P);
                BigInteger hhh = Mod(h * hh, P);
                BigInteger u1hh = Mod(u1 * hh, P);
                BigInteger x3 = Mod(r * r - hhh - 2 * u1hh, P);
                BigInteger y3 = Mod(r * (u1hh - x3) - s1 * hhh, P);
                BigInteger z3 = Mod(h * p1.Z * p2.Z, P);
                return new JacobianPoint { X = x3, Y = y3, Z = z3 };
            }

            private static JacobianPoint Double(JacobianPoint point)
            {
                if (point.IsInfinity || point.Y.IsZero) return Infinity();

                BigInteger delta = Mod(point.Z * point.Z, P);
                BigInteger gamma = Mod(point.Y * point.Y, P);
                BigInteger beta = Mod(point.X * gamma, P);
                BigInteger alpha = Mod(3 * (point.X - delta) * (point.X + delta), P);
                BigInteger x3 = Mod(alpha * alpha - 8 * beta, P);
                BigInteger z3 = Mod((point.Y + point.Z) * (point.Y + point.Z) - gamma - delta, P);
                BigInteger y3 = Mod(alpha * (4 * beta - x3) - 8 * gamma * gamma, P);
                return new JacobianPoint { X = x3, Y = y3, Z = z3 };
            }

            internal static BigInteger ToAffineX(JacobianPoint point)
            {
                if (point.IsInfinity) throw new InvalidOperationException("Point at infinity.");
                BigInteger zInv = ModInverse(point.Z, P);
                return Mod(point.X * zInv * zInv, P);
            }

            internal static BigInteger ModInverse(BigInteger value, BigInteger modulus)
            {
                value = Mod(value, modulus);
                if (value.IsZero) throw new ArithmeticException("Inverse does not exist.");

                BigInteger oldR = modulus;
                BigInteger r = value;
                BigInteger oldT = BigInteger.Zero;
                BigInteger t = BigInteger.One;
                while (!r.IsZero)
                {
                    BigInteger q = oldR / r;
                    BigInteger nextR = oldR - q * r;
                    oldR = r;
                    r = nextR;
                    BigInteger nextT = oldT - q * t;
                    oldT = t;
                    t = nextT;
                }
                if (oldR != BigInteger.One) throw new ArithmeticException("Inverse does not exist.");
                return Mod(oldT, modulus);
            }

            internal static BigInteger Mod(BigInteger value, BigInteger modulus)
            {
                BigInteger result = value % modulus;
                return result.Sign < 0 ? result + modulus : result;
            }

            private static JacobianPoint Infinity()
            {
                return new JacobianPoint { X = BigInteger.Zero, Y = BigInteger.One, Z = BigInteger.Zero };
            }

            private static BigInteger Hex(string hex)
            {
                byte[] bytes = new byte[hex.Length / 2];
                for (int i = 0; i < bytes.Length; i++)
                    bytes[i] = Convert.ToByte(hex.Substring(i * 2, 2), 16);
                byte[] little = new byte[bytes.Length + 1];
                for (int i = 0; i < bytes.Length; i++)
                    little[i] = bytes[bytes.Length - 1 - i];
                return new BigInteger(little);
            }
        }

        private static class Sha256
        {
            private static readonly uint[] K = new uint[]
            {
                0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
                0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
                0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
                0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
                0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
                0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
                0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
                0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
            };

            internal static byte[] Compute(byte[] data)
            {
                ulong bitLength = checked((ulong)data.Length * 8UL);
                int pad = (56 - ((data.Length + 1) % 64) + 64) % 64;
                byte[] msg = new byte[data.Length + 1 + pad + 8];
                Buffer.BlockCopy(data, 0, msg, 0, data.Length);
                msg[data.Length] = 0x80;
                for (int i = 0; i < 8; i++)
                    msg[msg.Length - 1 - i] = (byte)(bitLength >> (i * 8));

                uint h0=0x6a09e667u,h1=0xbb67ae85u,h2=0x3c6ef372u,h3=0xa54ff53au,
                     h4=0x510e527fu,h5=0x9b05688cu,h6=0x1f83d9abu,h7=0x5be0cd19u;
                uint[] w = new uint[64];
                for (int off = 0; off < msg.Length; off += 64)
                {
                    for (int i = 0; i < 16; i++)
                    {
                        int j = off + i * 4;
                        w[i] = ((uint)msg[j] << 24) | ((uint)msg[j+1] << 16) |
                               ((uint)msg[j+2] << 8) | msg[j+3];
                    }
                    for (int i = 16; i < 64; i++)
                    {
                        uint s0 = Ror(w[i-15],7) ^ Ror(w[i-15],18) ^ (w[i-15] >> 3);
                        uint s1 = Ror(w[i-2],17) ^ Ror(w[i-2],19) ^ (w[i-2] >> 10);
                        w[i] = unchecked(w[i-16] + s0 + w[i-7] + s1);
                    }
                    uint a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
                    for (int i = 0; i < 64; i++)
                    {
                        uint s1=Ror(e,6)^Ror(e,11)^Ror(e,25);
                        uint ch=(e&f)^((~e)&g);
                        uint t1=unchecked(h+s1+ch+K[i]+w[i]);
                        uint s0=Ror(a,2)^Ror(a,13)^Ror(a,22);
                        uint maj=(a&b)^(a&c)^(b&c);
                        uint t2=unchecked(s0+maj);
                        h=g; g=f; f=e; e=unchecked(d+t1); d=c; c=b; b=a; a=unchecked(t1+t2);
                    }
                    h0=unchecked(h0+a);h1=unchecked(h1+b);h2=unchecked(h2+c);h3=unchecked(h3+d);
                    h4=unchecked(h4+e);h5=unchecked(h5+f);h6=unchecked(h6+g);h7=unchecked(h7+h);
                }
                uint[] hs={h0,h1,h2,h3,h4,h5,h6,h7};
                byte[] result=new byte[32];
                for(int i=0;i<8;i++){
                    result[i*4]=(byte)(hs[i]>>24); result[i*4+1]=(byte)(hs[i]>>16);
                    result[i*4+2]=(byte)(hs[i]>>8); result[i*4+3]=(byte)hs[i];
                }
                return result;
            }

            private static uint Ror(uint x, int n) { return (x >> n) | (x << (32 - n)); }
        }
    }
}
