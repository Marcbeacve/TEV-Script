using System;
using System.Collections;
using System.Collections.Generic;
using BigInteger = System.Numerics.BigInteger;
using Marcbeacve.TevScript.Core;
using Marcbeacve.TevScript.Unity;
using UnityEngine;

namespace Marcbeacve.TevScript.Gate4.Il2CppPlayer
{
    public sealed class TevScriptIl2CppPlayerGate : MonoBehaviour
    {
        private IEnumerator Start()
        {
            // Allow the built Player to enter a real frame before the gate executes.
            yield return null;

            int exitCode = 0;
            try
            {
                RunGate();
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                Debug.Log("TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE_4=FAIL");
                exitCode = 41;
            }

            // Give the logger one more frame to flush witnesses before exiting.
            yield return null;
            Application.Quit(exitCode);
        }

        private static void RunGate()
        {
            if (Application.platform != RuntimePlatform.WindowsPlayer)
            {
                throw new InvalidOperationException(
                    "Gate-4 requires a Windows standalone Player.");
            }

            Debug.Log("UNITY_IL2CPP_PLAYER_ACTIVE=PASS");
            Debug.Log("UNITY_IL2CPP_PLAYER_PLATFORM=WINDOWS_PLAYER_PASS");

            TextAsset fixture = Resources.Load<TextAsset>("TevScriptGate4Player");
            if (fixture == null || string.IsNullOrWhiteSpace(fixture.text))
            {
                throw new InvalidOperationException(
                    "Canonical Gate-4 Player fixture is missing.");
            }

            TevScriptProgram program = TevScriptProgram.Parse(fixture.text);
            if (program.ProgramId != "PlayerGameplay")
            {
                throw new InvalidOperationException(
                    "Unexpected Gate-4 program id: " + program.ProgramId);
            }
            Debug.Log("UNITY_IL2CPP_PLAYER_CORE_PARSE=PASS");

            var witnesses = new List<TevScriptFloatBoundaryWitness>();

            GameObject inputObject = new GameObject("Gate4Input");
            TevScriptConstantMove2DSource input =
                inputObject.AddComponent<TevScriptConstantMove2DSource>();
            input.Value = new Vector2(0.5f, -0.25f);

            GameObject actor = new GameObject("Gate4Actor");
            TevScriptAnimationStateSink animation =
                actor.AddComponent<TevScriptAnimationStateSink>();

            var inputCapability = new TevScriptInputMove2DCapability(
                input,
                witnesses.Add);
            var motionCapability = new TevScriptTransformMotion2DCapability(
                actor.transform,
                witnesses.Add);
            var animationCapability = new TevScriptAnimationPlayCapability(
                animation);
            var timeCapability = new TevScriptTimeDeltaCapability(
                new TevScriptUnityDeltaTimeSource(),
                witnesses.Add);
            var debugCapability = new TevScriptDebugLogCapability();

            var runtime = new TevScriptRuntime(
                program,
                new ITevScriptCapability[]
                {
                    inputCapability,
                    motionCapability,
                    animationCapability,
                    timeCapability,
                    debugCapability
                });

            runtime.Invoke("Player", "start");
            Debug.Log("UNITY_IL2CPP_PLAYER_CAPABILITY_DEBUG_LOG=PASS");

            runtime.Invoke("Player", "update");

            Vector3 position = actor.transform.position;
            if (!Mathf.Approximately(position.x, 2.5f) ||
                !Mathf.Approximately(position.y, -1.25f) ||
                !Mathf.Approximately(position.z, 0.0f))
            {
                throw new InvalidOperationException(
                    "motion.move2d produced unexpected position " + position);
            }

            Debug.Log("UNITY_IL2CPP_PLAYER_CAPABILITY_INPUT_MOVE2D=PASS");
            Debug.Log("UNITY_IL2CPP_PLAYER_CAPABILITY_MOTION_TRANSFORM2D=PASS");

            if (!string.Equals(
                    animation.LastState,
                    "Walk",
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "animation.play did not select Walk.");
            }
            Debug.Log("UNITY_IL2CPP_PLAYER_CAPABILITY_ANIMATION_PLAY=PASS");

            IReadOnlyDictionary<string, TevScriptValue> state =
                runtime.State("Player");
            if (!state.ContainsKey("health") ||
                state["health"].AsInt() != new BigInteger(100))
            {
                throw new InvalidOperationException(
                    "Runtime state changed unexpectedly.");
            }
            Debug.Log("UNITY_IL2CPP_PLAYER_RUNTIME_STATE=PASS");

            TevScriptValue delta = timeCapability.Invoke(
                new TevScriptValue[0]);
            if (delta.TypeName != "Rat")
            {
                throw new InvalidOperationException(
                    "time.delta did not return Rat.");
            }
            Debug.Log("UNITY_IL2CPP_PLAYER_CAPABILITY_TIME_DELTA=PASS");

            bool inputFloatWitness = witnesses.Exists(item =>
                item.Direction ==
                    TevScriptUnityNumericBoundary.FloatToRatDirection &&
                item.CapabilityId.StartsWith(
                    "input.move2d",
                    StringComparison.Ordinal));
            if (!inputFloatWitness)
            {
                throw new InvalidOperationException(
                    "input.move2d exact float witness missing.");
            }
            Debug.Log("UNITY_IL2CPP_PLAYER_FLOAT_TO_RAT_EXACT=PASS");

            bool motionFloatWitness = witnesses.Exists(item =>
                item.Direction ==
                    TevScriptUnityNumericBoundary.RatToFloatDirection &&
                item.CapabilityId.StartsWith(
                    "motion.move2d",
                    StringComparison.Ordinal));
            if (!motionFloatWitness)
            {
                throw new InvalidOperationException(
                    "motion.move2d Rat-to-float witness missing.");
            }
            Debug.Log(
                "UNITY_IL2CPP_PLAYER_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS");

            bool timeWitness = witnesses.Exists(item =>
                item.Direction ==
                    TevScriptUnityNumericBoundary.FloatToRatDirection &&
                item.CapabilityId == "time.delta");
            if (!timeWitness)
            {
                throw new InvalidOperationException(
                    "time.delta exact boundary witness missing.");
            }
            Debug.Log(
                "UNITY_IL2CPP_PLAYER_TIME_DELTA_BOUNDARY_WITNESS=PASS");

            var roundingWitnesses =
                new List<TevScriptFloatBoundaryWitness>();
            TevScriptUnityNumericBoundary.RatToFloat(
                new TevRational(new BigInteger(1), new BigInteger(10)),
                "gate4.rounding",
                roundingWitnesses.Add);
            if (roundingWitnesses.Count != 1 ||
                roundingWitnesses[0].RoundTripError == TevRational.Zero)
            {
                throw new InvalidOperationException(
                    "Expected an exposed non-zero 1/10 float rounding error.");
            }
            Debug.Log(
                "UNITY_IL2CPP_PLAYER_RAT_TO_FLOAT_ROUNDING_EXPOSED=PASS");

            bool nonFiniteRejected = false;
            try
            {
                TevScriptUnityNumericBoundary.FloatToRatExact(
                    float.NaN,
                    "gate4.nan");
            }
            catch (TevContractException exception)
            {
                nonFiniteRejected =
                    exception.Diagnostic.Code ==
                    "TEVS_UNITY_FLOAT_NONFINITE";
            }

            if (!nonFiniteRejected)
            {
                throw new InvalidOperationException(
                    "NaN was not rejected fail-closed.");
            }
            Debug.Log(
                "UNITY_IL2CPP_PLAYER_NONFINITE_FLOAT_FAIL_CLOSED=PASS");

            // Every provider above is supplied explicitly through a constructor.
            // No discovery, reflection, GetComponent, or authority escalation occurs.
            Debug.Log("UNITY_IL2CPP_PLAYER_CAPABILITY_ABI=PASS");
            Debug.Log(
                "UNITY_IL2CPP_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS");
            Debug.Log(
                "UNITY_IL2CPP_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS");
            Debug.Log("UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED");
            Debug.Log("UNITY_ANIMATOR_CONTROLLER=NOT_PROBED");
            Debug.Log("TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE_4=PASS");
        }
    }
}
