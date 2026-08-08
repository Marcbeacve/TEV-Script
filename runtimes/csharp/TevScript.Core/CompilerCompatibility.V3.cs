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
}
