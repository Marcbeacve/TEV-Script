using System;
using System.Numerics;

namespace Marcbeacve.TevScript.Core
{
    public sealed class TevDiagnostic
    {
        public TevDiagnostic(string code, string message, string path = "")
        {
            Code = Require(code, nameof(code));
            Message = Require(message, nameof(message));
            Path = path == null ? string.Empty : path.Trim();
        }

        public string Code { get; }
        public string Message { get; }
        public string Path { get; }

        public override string ToString()
        {
            return Path.Length == 0
                ? Code + ": " + Message
                : Code + " at " + Path + ": " + Message;
        }

        private static string Require(string value, string name)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                throw new ArgumentException("A non-empty value is required.", name);
            }
            return value.Trim();
        }
    }

    public sealed class TevContractException : Exception
    {
        public TevContractException(string code, string message, string path = "")
            : base(new TevDiagnostic(code, message, path).ToString())
        {
            Diagnostic = new TevDiagnostic(code, message, path);
        }

        public TevDiagnostic Diagnostic { get; }
    }

    public readonly struct TevRational :
        IComparable<TevRational>,
        IEquatable<TevRational>
    {
        public static readonly TevRational Zero =
            new TevRational(BigInteger.Zero, BigInteger.One);
        public static readonly TevRational One =
            new TevRational(BigInteger.One, BigInteger.One);

        public TevRational(BigInteger numerator, BigInteger denominator)
        {
            if (denominator.IsZero)
            {
                throw new DivideByZeroException(
                    "A TEV rational denominator cannot be zero.");
            }
            if (denominator.Sign < 0)
            {
                numerator = BigInteger.Negate(numerator);
                denominator = BigInteger.Negate(denominator);
            }
            BigInteger divisor = BigInteger.GreatestCommonDivisor(
                BigInteger.Abs(numerator), denominator);
            Numerator = numerator / divisor;
            Denominator = denominator / divisor;
        }

        public BigInteger Numerator { get; }
        public BigInteger Denominator { get; }

        public static TevRational FromInteger(BigInteger value)
        {
            return new TevRational(value, BigInteger.One);
        }

        public int CompareTo(TevRational other)
        {
            return (Numerator * other.Denominator)
                .CompareTo(other.Numerator * Denominator);
        }

        public bool Equals(TevRational other)
        {
            return Numerator.Equals(other.Numerator) &&
                   Denominator.Equals(other.Denominator);
        }

        public override bool Equals(object obj)
        {
            return obj is TevRational && Equals((TevRational)obj);
        }

        public override int GetHashCode()
        {
            unchecked
            {
                return (Numerator.GetHashCode() * 397) ^
                       Denominator.GetHashCode();
            }
        }

        public override string ToString()
        {
            return Denominator.IsOne
                ? Numerator.ToString()
                : Numerator + "/" + Denominator;
        }

        public static TevRational operator +(
            TevRational left,
            TevRational right)
        {
            return new TevRational(
                left.Numerator * right.Denominator +
                right.Numerator * left.Denominator,
                left.Denominator * right.Denominator);
        }

        public static TevRational operator -(
            TevRational left,
            TevRational right)
        {
            return new TevRational(
                left.Numerator * right.Denominator -
                right.Numerator * left.Denominator,
                left.Denominator * right.Denominator);
        }

        public static TevRational operator -(TevRational value)
        {
            return new TevRational(
                BigInteger.Negate(value.Numerator),
                value.Denominator);
        }

        public static TevRational operator *(
            TevRational left,
            TevRational right)
        {
            return new TevRational(
                left.Numerator * right.Numerator,
                left.Denominator * right.Denominator);
        }

        public static TevRational operator /(
            TevRational left,
            TevRational right)
        {
            if (right.Numerator.IsZero)
            {
                throw new DivideByZeroException();
            }
            return new TevRational(
                left.Numerator * right.Denominator,
                left.Denominator * right.Numerator);
        }

        public static bool operator ==(TevRational left, TevRational right)
        {
            return left.Equals(right);
        }

        public static bool operator !=(TevRational left, TevRational right)
        {
            return !left.Equals(right);
        }

        public static bool operator <(TevRational left, TevRational right)
        {
            return left.CompareTo(right) < 0;
        }

        public static bool operator <=(TevRational left, TevRational right)
        {
            return left.CompareTo(right) <= 0;
        }

        public static bool operator >(TevRational left, TevRational right)
        {
            return left.CompareTo(right) > 0;
        }

        public static bool operator >=(TevRational left, TevRational right)
        {
            return left.CompareTo(right) >= 0;
        }
    }
}
