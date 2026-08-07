using System;
using System.Collections;
using System.Collections.Generic;
using BigInteger = System.Numerics.BigInteger;
using Marcbeacve.TevScript.Core;
using Marcbeacve.TevScript.Unity;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace Marcbeacve.TevScript.Tests.PlayMode
{
    public sealed class TevScriptUnityPlayModeGateTests
    {
        [UnityTest]
        public IEnumerator PlayerProgramDrivesExplicitUnityCapabilities()
        {
            Assert.IsTrue(Application.isPlaying);
            TextAsset playerAsset = Resources.Load<TextAsset>("TevScriptGate2Player");
            Assert.IsNotNull(playerAsset, "Player IR fixture was not imported as a TextAsset.");

            var target = new GameObject("TEV Script Gate2 Target");
            var sourceObject = new GameObject("TEV Script Gate2 Input");
            var source = sourceObject.AddComponent<TevScriptConstantMove2DSource>();
            var animation = target.AddComponent<TevScriptAnimationStateSink>();
            source.Value = new Vector2(1f, 0f);

            var witnesses = new List<TevScriptFloatBoundaryWitness>();
            var runtime = new TevScriptRuntime(
                TevScriptProgram.Parse(playerAsset.text),
                new ITevScriptCapability[]
                {
                    new TevScriptInputMove2DCapability(source, witnesses.Add),
                    new TevScriptTransformMotion2DCapability(target.transform, witnesses.Add),
                    new TevScriptAnimationPlayCapability(animation),
                    new TevScriptDebugLogCapability()
                });

            LogAssert.Expect(LogType.Log, "Player ready");
            runtime.Invoke("Player", "start");
            runtime.Invoke("Player", "update");

            Assert.AreEqual(5f, target.transform.position.x);
            Assert.AreEqual(0f, target.transform.position.y);
            Assert.AreEqual(0f, target.transform.position.z);
            Assert.AreEqual("Walk", animation.LastState);
            Assert.AreEqual(4, witnesses.Count);
            Assert.AreEqual(TevScriptUnityNumericBoundary.FloatToRatDirection, witnesses[0].Direction);
            Assert.AreEqual(TevScriptUnityNumericBoundary.FloatToRatDirection, witnesses[1].Direction);
            Assert.AreEqual(TevScriptUnityNumericBoundary.RatToFloatDirection, witnesses[2].Direction);
            Assert.AreEqual(TevScriptUnityNumericBoundary.RatToFloatDirection, witnesses[3].Direction);
            Assert.AreEqual(TevRational.Zero, witnesses[2].RoundTripError);
            Assert.AreEqual(TevRational.Zero, witnesses[3].RoundTripError);

            source.Value = Vector2.zero;
            runtime.Invoke("Player", "update");
            Assert.AreEqual(5f, target.transform.position.x);
            Assert.AreEqual("Idle", animation.LastState);

            Debug.Log("UNITY_PLAYMODE_ACTIVE=PASS");
            Debug.Log("UNITY_CAPABILITY_INPUT_MOVE2D=PASS");
            Debug.Log("UNITY_CAPABILITY_MOTION_TRANSFORM2D=PASS");
            Debug.Log("UNITY_CAPABILITY_ANIMATION_PLAY=PASS");
            Debug.Log("UNITY_CAPABILITY_DEBUG_LOG=PASS");
            Debug.Log("UNITY_FLOAT_TO_RAT_EXACT=PASS");
            Debug.Log("UNITY_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS");

            UnityEngine.Object.Destroy(sourceObject);
            UnityEngine.Object.Destroy(target);
            yield return null;
        }

        [UnityTest]
        public IEnumerator UnityDeltaTimeIsExposedAsExactObservedFloatRational()
        {
            Assert.IsTrue(Application.isPlaying);
            yield return null;

            var source = new TevScriptUnityDeltaTimeSource();
            var witnesses = new List<TevScriptFloatBoundaryWitness>();
            var capability = new TevScriptTimeDeltaCapability(source, witnesses.Add);
            TevScriptValue result = capability.Invoke(Array.Empty<TevScriptValue>());

            Assert.AreEqual("Rat", result.TypeName);
            Assert.IsFalse(float.IsNaN(source.LastValue));
            Assert.IsFalse(float.IsInfinity(source.LastValue));
            Assert.AreEqual(
                TevScriptUnityNumericBoundary.FloatToRatExact(source.LastValue),
                result.AsRat());
            Assert.AreEqual(1, witnesses.Count);
            Assert.AreEqual(TevScriptUnityNumericBoundary.FloatToRatDirection, witnesses[0].Direction);
            Assert.AreEqual(TevRational.Zero, witnesses[0].RoundTripError);

            Debug.Log("UNITY_CAPABILITY_TIME_DELTA=PASS");
            Debug.Log("UNITY_TIME_DELTA_FLOAT_TO_RAT_EXACT=PASS");
        }

        [UnityTest]
        public IEnumerator NumericBoundaryMakesRoundingVisibleAndRejectsNonFiniteValues()
        {
            var witnesses = new List<TevScriptFloatBoundaryWitness>();
            TevRational tenth = new TevRational(BigInteger.One, new BigInteger(10));
            float projected = TevScriptUnityNumericBoundary.RatToFloat(
                tenth,
                "gate2.rounding",
                witnesses.Add);

            Assert.AreEqual(1, witnesses.Count);
            Assert.AreEqual(
                TevScriptUnityNumericBoundary.FloatToRatExact(projected),
                witnesses[0].RationalValue + witnesses[0].RoundTripError);
            Assert.AreNotEqual(TevRational.Zero, witnesses[0].RoundTripError);

            TevContractException nan = Assert.Throws<TevContractException>(
                () => TevScriptUnityNumericBoundary.FloatToRatExact(float.NaN));
            Assert.AreEqual("TEVS_UNITY_FLOAT_NONFINITE", nan.Diagnostic.Code);

            TevContractException infinity = Assert.Throws<TevContractException>(
                () => TevScriptUnityNumericBoundary.FloatToRatExact(float.PositiveInfinity));
            Assert.AreEqual("TEVS_UNITY_FLOAT_NONFINITE", infinity.Diagnostic.Code);

            var huge = new TevRational(BigInteger.Pow(new BigInteger(10), 1000), BigInteger.One);
            TevContractException overflow = Assert.Throws<TevContractException>(
                () => TevScriptUnityNumericBoundary.RatToFloat(huge, "gate2.overflow"));
            Assert.AreEqual("TEVS_UNITY_RAT_FLOAT_RANGE", overflow.Diagnostic.Code);

            Debug.Log("UNITY_RAT_TO_FLOAT_ROUNDING_EXPOSED=PASS");
            Debug.Log("UNITY_NONFINITE_FLOAT_FAIL_CLOSED=PASS");
            Debug.Log("TEV_SCRIPT_UNITY_PLAYMODE_GATE_2=PASS");
            yield return null;
        }
    }
}
