using System;
using System.Collections.Generic;
using Marcbeacve.TevScript.Core;
using UnityEngine;

namespace Marcbeacve.TevScript.Unity
{
    public interface ITevScriptMove2DSource
    {
        Vector2 ReadMove2D();
    }

    public interface ITevScriptAnimationSink
    {
        void Play(string stateName);
    }

    public interface ITevScriptDeltaTimeSource
    {
        float ReadDeltaTime();
    }

    public sealed class TevScriptConstantMove2DSource : MonoBehaviour, ITevScriptMove2DSource
    {
        [SerializeField] private Vector2 value;

        public Vector2 Value
        {
            get { return value; }
            set { this.value = value; }
        }

        public Vector2 ReadMove2D()
        {
            return value;
        }
    }

    public sealed class TevScriptAnimationStateSink : MonoBehaviour, ITevScriptAnimationSink
    {
        public string LastState { get; private set; } = string.Empty;

        public void Play(string stateName)
        {
            if (string.IsNullOrWhiteSpace(stateName))
            {
                throw new TevContractException(
                    "TEVS_UNITY_ANIMATION_STATE",
                    "animation.play requires a non-empty state name.");
            }
            LastState = stateName;
        }
    }

    public sealed class TevScriptUnityDeltaTimeSource : ITevScriptDeltaTimeSource
    {
        public float LastValue { get; private set; }

        public float ReadDeltaTime()
        {
            LastValue = Time.deltaTime;
            return LastValue;
        }
    }

    public sealed class TevScriptInputMove2DCapability : ITevScriptCapability
    {
        private readonly ITevScriptMove2DSource source;
        private readonly Action<TevScriptFloatBoundaryWitness> observer;

        public TevScriptInputMove2DCapability(
            ITevScriptMove2DSource source,
            Action<TevScriptFloatBoundaryWitness> observer = null)
        {
            this.source = source ?? throw new ArgumentNullException(nameof(source));
            this.observer = observer;
        }

        public string CapabilityId => "input.move2d";

        public TevScriptValue Invoke(IReadOnlyList<TevScriptValue> arguments)
        {
            RequireArity(arguments, 0, CapabilityId);
            Vector2 value = source.ReadMove2D();
            TevRational x = TevScriptUnityNumericBoundary.FloatToRatExact(
                value.x, CapabilityId + ".x", observer);
            TevRational y = TevScriptUnityNumericBoundary.FloatToRatExact(
                value.y, CapabilityId + ".y", observer);
            return TevScriptValue.Vec2(x, y);
        }

        internal static void RequireArity(
            IReadOnlyList<TevScriptValue> arguments,
            int expected,
            string capabilityId)
        {
            if (arguments == null)
            {
                throw new ArgumentNullException(nameof(arguments));
            }
            if (arguments.Count != expected)
            {
                throw new TevContractException(
                    "TEVS_UNITY_CAPABILITY_ARITY",
                    "Capability " + capabilityId + " expects " + expected + " arguments.");
            }
        }
    }

    public sealed class TevScriptTransformMotion2DCapability : ITevScriptCapability
    {
        private readonly Transform target;
        private readonly Action<TevScriptFloatBoundaryWitness> observer;

        public TevScriptTransformMotion2DCapability(
            Transform target,
            Action<TevScriptFloatBoundaryWitness> observer = null)
        {
            this.target = target ?? throw new ArgumentNullException(nameof(target));
            this.observer = observer;
        }

        public string CapabilityId => "motion.move2d";

        public TevScriptValue Invoke(IReadOnlyList<TevScriptValue> arguments)
        {
            TevScriptInputMove2DCapability.RequireArity(arguments, 1, CapabilityId);
            IReadOnlyList<TevRational> vector = arguments[0].AsVector();
            if (arguments[0].TypeName != "Vec2" || vector.Count != 2)
            {
                throw new TevContractException(
                    "TEVS_UNITY_MOTION_TYPE",
                    "motion.move2d requires Vec2.");
            }

            float x = TevScriptUnityNumericBoundary.RatToFloat(
                vector[0], CapabilityId + ".x", observer);
            float y = TevScriptUnityNumericBoundary.RatToFloat(
                vector[1], CapabilityId + ".y", observer);
            Vector3 position = target.position;
            target.position = new Vector3(position.x + x, position.y + y, position.z);
            return TevScriptValue.Unit();
        }
    }

    public sealed class TevScriptAnimationPlayCapability : ITevScriptCapability
    {
        private readonly ITevScriptAnimationSink sink;

        public TevScriptAnimationPlayCapability(ITevScriptAnimationSink sink)
        {
            this.sink = sink ?? throw new ArgumentNullException(nameof(sink));
        }

        public string CapabilityId => "animation.play";

        public TevScriptValue Invoke(IReadOnlyList<TevScriptValue> arguments)
        {
            TevScriptInputMove2DCapability.RequireArity(arguments, 1, CapabilityId);
            sink.Play(arguments[0].AsText());
            return TevScriptValue.Unit();
        }
    }

    public sealed class TevScriptTimeDeltaCapability : ITevScriptCapability
    {
        private readonly ITevScriptDeltaTimeSource source;
        private readonly Action<TevScriptFloatBoundaryWitness> observer;

        public TevScriptTimeDeltaCapability(
            ITevScriptDeltaTimeSource source,
            Action<TevScriptFloatBoundaryWitness> observer = null)
        {
            this.source = source ?? throw new ArgumentNullException(nameof(source));
            this.observer = observer;
        }

        public string CapabilityId => "time.delta";

        public TevScriptValue Invoke(IReadOnlyList<TevScriptValue> arguments)
        {
            TevScriptInputMove2DCapability.RequireArity(arguments, 0, CapabilityId);
            float delta = source.ReadDeltaTime();
            TevRational exact = TevScriptUnityNumericBoundary.FloatToRatExact(
                delta, CapabilityId, observer);
            return TevScriptValue.Rat(exact);
        }
    }

    public sealed class TevScriptDebugLogCapability : ITevScriptCapability
    {
        public string CapabilityId => "debug.log";

        public TevScriptValue Invoke(IReadOnlyList<TevScriptValue> arguments)
        {
            TevScriptInputMove2DCapability.RequireArity(arguments, 1, CapabilityId);
            Debug.Log(arguments[0].AsText());
            return TevScriptValue.Unit();
        }
    }
}
