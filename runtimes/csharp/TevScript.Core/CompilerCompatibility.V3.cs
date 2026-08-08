#if NETSTANDARD2_1
namespace System.Runtime.CompilerServices
{
    internal static class IsExternalInit
    {
    }

    [System.AttributeUsage(
        System.AttributeTargets.Class |
        System.AttributeTargets.Struct |
        System.AttributeTargets.Field |
        System.AttributeTargets.Property,
        Inherited = false)]
    internal sealed class RequiredMemberAttribute : System.Attribute
    {
    }

    [System.AttributeUsage(System.AttributeTargets.All, AllowMultiple = true, Inherited = false)]
    internal sealed class CompilerFeatureRequiredAttribute : System.Attribute
    {
        public CompilerFeatureRequiredAttribute(string featureName)
        {
            FeatureName = featureName;
        }

        public string FeatureName { get; }
        public bool IsOptional { get; init; }
    }
}

namespace System.Diagnostics.CodeAnalysis
{
    [System.AttributeUsage(System.AttributeTargets.Constructor, Inherited = false)]
    internal sealed class SetsRequiredMembersAttribute : System.Attribute
    {
    }
}

namespace System.Diagnostics
{
    internal sealed class UnreachableException : System.Exception
    {
        public UnreachableException()
            : base("The program executed an instruction that was thought to be unreachable.")
        {
        }

        public UnreachableException(string message)
            : base(message)
        {
        }
    }
}

namespace System.Linq
{
    internal static class TevScriptEnumerableCompatibilityV3
    {
        public static System.Linq.IOrderedEnumerable<T> Order<T>(
            this System.Collections.Generic.IEnumerable<T> source,
            System.Collections.Generic.IComparer<T>? comparer)
        {
            return System.Linq.Enumerable.OrderBy(source, item => item, comparer);
        }
    }
}
#endif

namespace TevScript.Core.V3
{
    // RegexOptions.NonBacktracking is newer than netstandard2.1. V3 only uses
    // short, anchored, bounded identifier/hash expressions, so the portable
    // semantic contract does not depend on that engine selection. Expose the
    // existing options with NonBacktracking as an intentional no-op.
    internal static class RegexOptions
    {
        public const System.Text.RegularExpressions.RegexOptions None =
            System.Text.RegularExpressions.RegexOptions.None;
        public const System.Text.RegularExpressions.RegexOptions CultureInvariant =
            System.Text.RegularExpressions.RegexOptions.CultureInvariant;
        public const System.Text.RegularExpressions.RegexOptions IgnoreCase =
            System.Text.RegularExpressions.RegexOptions.IgnoreCase;
        public const System.Text.RegularExpressions.RegexOptions Multiline =
            System.Text.RegularExpressions.RegexOptions.Multiline;
        public const System.Text.RegularExpressions.RegexOptions ExplicitCapture =
            System.Text.RegularExpressions.RegexOptions.ExplicitCapture;
        public const System.Text.RegularExpressions.RegexOptions Compiled =
            System.Text.RegularExpressions.RegexOptions.Compiled;
        public const System.Text.RegularExpressions.RegexOptions Singleline =
            System.Text.RegularExpressions.RegexOptions.Singleline;
        public const System.Text.RegularExpressions.RegexOptions IgnorePatternWhitespace =
            System.Text.RegularExpressions.RegexOptions.IgnorePatternWhitespace;
        public const System.Text.RegularExpressions.RegexOptions RightToLeft =
            System.Text.RegularExpressions.RegexOptions.RightToLeft;
        public const System.Text.RegularExpressions.RegexOptions ECMAScript =
            System.Text.RegularExpressions.RegexOptions.ECMAScript;
        public const System.Text.RegularExpressions.RegexOptions NonBacktracking =
            System.Text.RegularExpressions.RegexOptions.None;
    }

    // System.Text.Json gained SerializeToElement after the oldest portable
    // target used by TevScript.Core. The canonical semantic result is exactly
    // serialize -> strict parse -> detached JsonElement.
    internal static class JsonSerializer
    {
        public static System.Text.Json.JsonElement SerializeToElement<T>(T value)
        {
            var text = System.Text.Json.JsonSerializer.Serialize(value);
            return TevScriptStrictJsonV3.ParseElement(text);
        }

        public static string Serialize<T>(T value)
        {
            return System.Text.Json.JsonSerializer.Serialize(value);
        }
    }

    // Runtime object GetHashCode is explicitly non-semantic. This helper only
    // removes a BCL-version dependency for value objects; canonical SHA-256 is
    // defined elsewhere and remains the sole portable hash authority.
    internal static class HashCode
    {
        public static int Combine<T1, T2>(T1 first, T2 second)
        {
            unchecked
            {
                var a = first is null ? 0 : System.Collections.Generic.EqualityComparer<T1>.Default.GetHashCode(first);
                var b = second is null ? 0 : System.Collections.Generic.EqualityComparer<T2>.Default.GetHashCode(second);
                return (a * 397) ^ b;
            }
        }
    }
}
