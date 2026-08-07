using System;
using System.Collections;
using System.Collections.Generic;
using BigInteger = System.Numerics.BigInteger;
using Marcbeacve.TevScript.Core;
using Marcbeacve.TevScript.Unity;
using UnityEngine;

public sealed class TevScriptMonoPlayerGate : MonoBehaviour
{
    private readonly List<TevScriptFloatBoundaryWitness> witnesses =
        new List<TevScriptFloatBoundaryWitness>();

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (Application.isEditor)
        {
            return;
        }

        GameObject root = new GameObject("TEV Script Mono Player Gate");
        DontDestroyOnLoad(root);
        root.AddComponent<TevScriptMonoPlayerGate>();
    }

    private IEnumerator Start()
    {
        // Wait until one real Player frame has elapsed so Time.deltaTime is a
        // genuine Player observation rather than an Editor/build-time value.
        yield return null;

        int exitCode = 0;
        try
        {
            RunGate();
            Debug.Log("TEV_SCRIPT_UNITY_MONO_PLAYER_GATE_3=PASS");
            Debug.Log("UNITY_IL2CPP=NOT_PROBED");
        }
        catch (Exception exception)
        {
            Debug.LogException(exception);
            Debug.Log("TEV_SCRIPT_UNITY_MONO_PLAYER_GATE_3=FAIL");
            exitCode = 31;
        }

        // C# iterator methods cannot yield from a try block that has catch, or
        // from the catch itself. Yield once after the result is fixed so Unity
        // flushes the Player log, then terminate with the observed gate code.
        yield return null;
        Application.Quit(exitCode);
    }

    private void RunGate()
    {
        Require(Application.platform == RuntimePlatform.WindowsPlayer,
            "Expected WindowsPlayer runtime.");
        Debug.Log("UNITY_MONO_PLAYER_ACTIVE=PASS");
        Debug.Log("UNITY_MONO_PLAYER_PLATFORM=WINDOWS_PLAYER_PASS");

        TextAsset fixture = Resources.Load<TextAsset>("TevScriptGate3Player");
        Require(fixture != null, "Canonical Player IR resource is missing.");

        TevScriptProgram program = TevScriptProgram.Parse(fixture.text);
        Require(program.SemanticHash ==
            "f18d1b2428b96bf8c859463ab62a431c654933e65e23c3d8183335506d5adb5d",
            "Player semantic hash drifted.");
        Debug.Log("UNITY_MONO_PLAYER_CORE_PARSE=PASS");

        GameObject actor = new GameObject("TEV Script Mono Actor");
        TevScriptConstantMove2DSource moveSource =
            actor.AddComponent<TevScriptConstantMove2DSource>();
        TevScriptAnimationStateSink animationSink =
            actor.AddComponent<TevScriptAnimationStateSink>();
        moveSource.Value = new Vector2(0.25f, -0.5f);

        ITevScriptCapability[] capabilities = new ITevScriptCapability[]
        {
            new TevScriptInputMove2DCapability(moveSource, ObserveBoundary),
            new TevScriptTransformMotion2DCapability(actor.transform, ObserveBoundary),
            new TevScriptAnimationPlayCapability(animationSink),
            new TevScriptDebugLogCapability()
        };

        TevScriptRuntime runtime = new TevScriptRuntime(program, capabilities);
        runtime.Invoke("Player", "start");
        Debug.Log("UNITY_MONO_PLAYER_CAPABILITY_DEBUG_LOG=PASS");

        runtime.Invoke("Player", "update");
        Require(Mathf.Approximately(actor.transform.position.x, 1.25f),
            "motion.move2d x effect mismatch.");
        Require(Mathf.Approximately(actor.transform.position.y, -2.5f),
            "motion.move2d y effect mismatch.");
        Require(animationSink.LastState == "Walk",
            "animation.play sink mismatch.");
        Debug.Log("UNITY_MONO_PLAYER_CAPABILITY_INPUT_MOVE2D=PASS");
        Debug.Log("UNITY_MONO_PLAYER_CAPABILITY_MOTION_TRANSFORM2D=PASS");
        Debug.Log("UNITY_MONO_PLAYER_CAPABILITY_ANIMATION_PLAY=PASS");

        runtime.Invoke(
            "Player",
            "damage",
            TevScriptValue.Int(new BigInteger(100)));
        IReadOnlyDictionary<string, TevScriptValue> state = runtime.State("Player");
        Require(state["health"].AsInt() == BigInteger.Zero,
            "Portable runtime state did not survive Player execution.");
        Debug.Log("UNITY_MONO_PLAYER_RUNTIME_STATE=PASS");

        TevScriptUnityDeltaTimeSource deltaSource =
            new TevScriptUnityDeltaTimeSource();
        TevScriptTimeDeltaCapability timeCapability =
            new TevScriptTimeDeltaCapability(deltaSource, ObserveBoundary);
        TevScriptValue delta = timeCapability.Invoke(new TevScriptValue[0]);
        Require(delta.TypeName == "Rat", "time.delta did not return Rat.");
        Require(IsFinite(deltaSource.LastValue),
            "time.delta source returned a non-finite float.");
        Debug.Log("UNITY_MONO_PLAYER_CAPABILITY_TIME_DELTA=PASS");

        TevRational exactPointOne =
            TevScriptUnityNumericBoundary.FloatToRatExact(
                0.1f,
                "gate3.float_to_rat",
                ObserveBoundary);
        Require(exactPointOne != new TevRational(new BigInteger(1), new BigInteger(10)),
            "0.1f was incorrectly treated as exact decimal 1/10.");
        Debug.Log("UNITY_MONO_PLAYER_FLOAT_TO_RAT_EXACT=PASS");

        TevRational oneTenth =
            new TevRational(new BigInteger(1), new BigInteger(10));
        float rounded = TevScriptUnityNumericBoundary.RatToFloat(
            oneTenth,
            "gate3.rat_to_float",
            ObserveBoundary);
        Require(IsFinite(rounded), "Rat to float produced non-finite value.");

        bool sawRoundedWitness = false;
        bool sawTimeWitness = false;
        foreach (TevScriptFloatBoundaryWitness witness in witnesses)
        {
            if (witness.CapabilityId == "gate3.rat_to_float" &&
                witness.Direction == TevScriptUnityNumericBoundary.RatToFloatDirection &&
                witness.RoundTripError != TevRational.Zero)
            {
                sawRoundedWitness = true;
            }
            if (witness.CapabilityId == "time.delta" &&
                witness.Direction == TevScriptUnityNumericBoundary.FloatToRatDirection)
            {
                sawTimeWitness = true;
            }
        }
        Require(sawRoundedWitness,
            "Rat to float rounding witness was not exposed.");
        Require(sawTimeWitness,
            "time.delta float-to-Rat witness was not exposed.");
        Debug.Log("UNITY_MONO_PLAYER_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS");
        Debug.Log("UNITY_MONO_PLAYER_TIME_DELTA_BOUNDARY_WITNESS=PASS");

        bool nonFiniteRejected = false;
        try
        {
            TevScriptUnityNumericBoundary.FloatToRatExact(float.NaN, "gate3.nan");
        }
        catch (TevContractException exception)
        {
            nonFiniteRejected =
                exception.Diagnostic.Code == "TEVS_UNITY_FLOAT_NONFINITE";
        }
        Require(nonFiniteRejected, "Non-finite float did not fail closed.");
        Debug.Log("UNITY_MONO_PLAYER_NONFINITE_FLOAT_FAIL_CLOSED=PASS");

        Debug.Log("UNITY_MONO_PLAYER_CAPABILITY_ABI=PASS");
        Debug.Log("UNITY_MONO_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS");
        Debug.Log("UNITY_MONO_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS");
        Debug.Log("UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED");
        Debug.Log("UNITY_ANIMATOR_CONTROLLER=NOT_PROBED");
    }

    private void ObserveBoundary(TevScriptFloatBoundaryWitness witness)
    {
        if (witness == null)
        {
            throw new ArgumentNullException(nameof(witness));
        }
        witnesses.Add(witness);
    }

    private static bool IsFinite(float value)
    {
        return !float.IsNaN(value) && !float.IsInfinity(value);
    }

    private static void Require(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
