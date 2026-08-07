using System;
using System.Collections.Generic;

namespace Marcbeacve.TevScript.Core
{
    internal static class TevScriptId
    {
        public static string RequireIdentifier(string value, string code)
        {
            if (!IsIdentifier(value))
                throw new TevContractException(code, "Non-canonical identifier.");
            return value;
        }

        public static string RequireStableId(string value, string code)
        {
            if (string.IsNullOrEmpty(value) || !IsAsciiStart(value[0]))
                throw new TevContractException(code, "Non-canonical stable identifier.");
            for (int index = 1; index < value.Length; index++)
            {
                char c = value[index];
                if (!IsAsciiContinue(c) && c != '.' && c != ':' && c != '/' && c != '-')
                    throw new TevContractException(code, "Non-canonical stable identifier.");
            }
            return value;
        }

        private static bool IsIdentifier(string value)
        {
            if (string.IsNullOrEmpty(value) || !IsAsciiStart(value[0])) return false;
            for (int index = 1; index < value.Length; index++)
                if (!IsAsciiContinue(value[index])) return false;
            return true;
        }

        private static bool IsAsciiStart(char value)
        {
            return (value >= 'A' && value <= 'Z') ||
                (value >= 'a' && value <= 'z') || value == '_';
        }

        private static bool IsAsciiContinue(char value)
        {
            return IsAsciiStart(value) || (value >= '0' && value <= '9');
        }
    }

    public interface ITevScriptCapability
    {
        string CapabilityId { get; }
        TevScriptValue Invoke(IReadOnlyList<TevScriptValue> arguments);
    }

    public sealed class DelegateTevScriptCapability : ITevScriptCapability
    {
        private readonly Func<
            IReadOnlyList<TevScriptValue>,
            TevScriptValue> _handler;

        public DelegateTevScriptCapability(
            string capabilityId,
            Func<IReadOnlyList<TevScriptValue>, TevScriptValue> handler)
        {
            CapabilityId = TevScriptId.RequireStableId(
                capabilityId,
                "TEVS_RUNTIME_CAPABILITY_BINDING_ID");
            _handler = handler ?? throw new ArgumentNullException(nameof(handler));
        }

        public string CapabilityId { get; }

        public TevScriptValue Invoke(
            IReadOnlyList<TevScriptValue> arguments)
        {
            return _handler(arguments ?? throw new ArgumentNullException(
                nameof(arguments)));
        }
    }

    public sealed class TevScriptEvent
    {
        public TevScriptEvent(
            string entityId,
            string eventId,
            IReadOnlyList<TevScriptValue> arguments)
        {
            EntityId = entityId ?? throw new ArgumentNullException(nameof(entityId));
            EventId = eventId ?? throw new ArgumentNullException(nameof(eventId));
            Arguments = arguments ?? throw new ArgumentNullException(nameof(arguments));
        }

        public string EntityId { get; }
        public string EventId { get; }
        public IReadOnlyList<TevScriptValue> Arguments { get; }
    }
}
