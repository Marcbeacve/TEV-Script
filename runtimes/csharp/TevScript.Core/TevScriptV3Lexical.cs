namespace TevScript.Core.V3;

internal static class TevScriptLexicalV3
{
    internal static bool IsLowercaseSha256(string value)
    {
        if (value.Length != 64) return false;
        foreach (var character in value)
            if (character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f'))
                return false;
        return true;
    }

    internal static bool IsLocalIdentifier(string value) =>
        IsLocalSegment(value, 0, value.Length);

    internal static bool IsStableIdentifier(string value)
    {
        if (value.Length == 0 || !IsIdentifierStart(value[0])) return false;
        for (var index = 1; index < value.Length; ++index)
        {
            var character = value[index];
            if (!IsIdentifierPart(character) && character is not ('.' or ':' or '/' or '-'))
                return false;
        }
        return true;
    }

    internal static bool IsQualifiedNominalIdentifier(string value)
    {
        var segmentStart = 0;
        var separators = 0;
        for (var index = 0; index <= value.Length; ++index)
        {
            if (index < value.Length && value[index] != '.') continue;
            if (!IsLocalSegment(value, segmentStart, index - segmentStart)) return false;
            if (index < value.Length) ++separators;
            segmentStart = index + 1;
        }
        return separators > 0;
    }

    internal static bool IsCanonicalInteger(string value)
    {
        if (value.Length == 0) return false;
        var firstDigit = value[0] == '-' ? 1 : 0;
        if (firstDigit == value.Length) return false;
        if (value[firstDigit] == '0') return firstDigit + 1 == value.Length;
        if (value[firstDigit] is not (>= '1' and <= '9')) return false;
        for (var index = firstDigit + 1; index < value.Length; ++index)
            if (value[index] is not (>= '0' and <= '9')) return false;
        return true;
    }

    internal static bool IsPositiveCanonicalInteger(string value)
    {
        if (value.Length == 0 || value[0] is not (>= '1' and <= '9')) return false;
        for (var index = 1; index < value.Length; ++index)
            if (value[index] is not (>= '0' and <= '9')) return false;
        return true;
    }

    private static bool IsLocalSegment(string value, int start, int length)
    {
        if (length == 0 || !IsIdentifierStart(value[start])) return false;
        var end = start + length;
        for (var index = start + 1; index < end; ++index)
            if (!IsIdentifierPart(value[index])) return false;
        return true;
    }

    private static bool IsIdentifierStart(char value) =>
        value == '_' || value is >= 'A' and <= 'Z' || value is >= 'a' and <= 'z';

    private static bool IsIdentifierPart(char value) =>
        IsIdentifierStart(value) || value is >= '0' and <= '9';
}
