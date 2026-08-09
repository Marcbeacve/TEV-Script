using System;
using System.Numerics;
using Marcbeacve.TevScript.Core;

namespace Marcbeacve.TevScript.Unity
{
    public sealed class TevScriptFloatBoundaryWitness
    {
        public TevScriptFloatBoundaryWitness(
            string capabilityId,
            string direction,
            float floatValue,
            int floatBits,
            TevRational rationalValue,
            TevRational roundTripError)
        {
            CapabilityId = capabilityId ?? throw new ArgumentNullException(nameof(capabilityId));
            Direction = direction ?? throw new ArgumentNullException(nameof(direction));
            FloatValue = floatValue;
            FloatBits = floatBits;
            RationalValue = rationalValue;
            RoundTripError = roundTripError;
        }

        public string CapabilityId { get; }
        public string Direction { get; }
        public float FloatValue { get; }
        public int FloatBits { get; }
        public TevRational RationalValue { get; }
        public TevRational RoundTripError { get; }
    }

    public static class TevScriptUnityNumericBoundary
    {
        public const string FloatToRatDirection = "FLOAT_TO_RAT_EXACT";
        public const string RatToFloatDirection = "RAT_TO_FLOAT_ROUNDED";

        public static TevRational FloatToRatExact(
            float value,
            string capabilityId = "unity.float",
            Action<TevScriptFloatBoundaryWitness> observer = null)
        {
            RequireFinite(value, capabilityId);

            int signedBits = BitConverter.ToInt32(BitConverter.GetBytes(value), 0);
            uint bits = unchecked((uint)signedBits);
            bool negative = (bits & 0x80000000u) != 0;
            int rawExponent = (int)((bits >> 23) & 0xffu);
            uint fraction = bits & 0x007fffffu;

            TevRational rational;
            if (rawExponent == 0 && fraction == 0)
            {
                rational = TevRational.Zero;
            }
            else
            {
                BigInteger significand;
                int exponent;
                if (rawExponent == 0)
                {
                    significand = new BigInteger(fraction);
                    exponent = -149;
                }
                else
                {
                    significand = new BigInteger((1u << 23) | fraction);
                    exponent = rawExponent - 127 - 23;
                }

                BigInteger numerator = significand;
                BigInteger denominator = BigInteger.One;
                if (exponent >= 0)
                {
                    numerator <<= exponent;
                }
                else
                {
                    denominator <<= -exponent;
                }
                if (negative)
                {
                    numerator = BigInteger.Negate(numerator);
                }
                rational = new TevRational(numerator, denominator);
            }

            observer?.Invoke(new TevScriptFloatBoundaryWitness(
                capabilityId,
                FloatToRatDirection,
                value,
                signedBits,
                rational,
                TevRational.Zero));
            return rational;
        }

        public static float RatToFloat(
            TevRational value,
            string capabilityId,
            Action<TevScriptFloatBoundaryWitness> observer = null)
        {
            if (string.IsNullOrWhiteSpace(capabilityId))
            {
                throw new ArgumentException("A capability id is required.", nameof(capabilityId));
            }

            double numerator = (double)value.Numerator;
            double denominator = (double)value.Denominator;
            double projected = numerator / denominator;
            if (double.IsNaN(projected) || double.IsInfinity(projected) ||
                projected > float.MaxValue || projected < -float.MaxValue)
            {
                throw new TevContractException(
                    "TEVS_UNITY_RAT_FLOAT_RANGE",
                    "Rational value cannot be represented as a finite Unity float.");
            }

            float result = (float)projected;
            RequireFinite(result, capabilityId);
            TevRational roundTrip = FloatToRatExact(result, capabilityId);
            TevRational error = roundTrip - value;
            int bits = BitConverter.ToInt32(BitConverter.GetBytes(result), 0);

            observer?.Invoke(new TevScriptFloatBoundaryWitness(
                capabilityId,
                RatToFloatDirection,
                result,
                bits,
                value,
                error));
            return result;
        }

        private static void RequireFinite(float value, string capabilityId)
        {
            if (float.IsNaN(value) || float.IsInfinity(value))
            {
                throw new TevContractException(
                    "TEVS_UNITY_FLOAT_NONFINITE",
                    "Capability " + capabilityId + " produced a non-finite float.");
            }
        }
    }
}
