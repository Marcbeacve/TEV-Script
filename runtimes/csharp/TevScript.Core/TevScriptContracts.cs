using System;
using System.Collections.Generic;

namespace Marcbeacve.TevScript.Core
{
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
            if (string.IsNullOrWhiteSpace(capabilityId))
            {
                throw new ArgumentException(
                    "A capability id is required.",
                    nameof(capabilityId));
            }
            CapabilityId = capabilityId.Trim();
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
