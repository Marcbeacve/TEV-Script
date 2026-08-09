using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class TevScriptMonoPlayerBuildGate
{
    public static void Build()
    {
        NamedBuildTarget standalone = NamedBuildTarget.Standalone;
        PlayerSettings.SetScriptingBackend(
            standalone,
            ScriptingImplementation.Mono2x);

        ScriptingImplementation observed =
            PlayerSettings.GetScriptingBackend(standalone);
        if (observed != ScriptingImplementation.Mono2x)
        {
            throw new InvalidOperationException(
                "Standalone scripting backend is not Mono2x: " + observed);
        }

        PlayerSettings.productName = "TEVScriptMonoGate";
        PlayerSettings.companyName = "Marcbeacve";
        PlayerSettings.runInBackground = true;
        PlayerSettings.usePlayerLog = true;
        PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
        PlayerSettings.defaultScreenWidth = 320;
        PlayerSettings.defaultScreenHeight = 180;

        const string scenePath = "Assets/TevScriptMonoGate.unity";
        Scene scene = EditorSceneManager.NewScene(
            NewSceneSetup.EmptyScene,
            NewSceneMode.Single);
        if (!EditorSceneManager.SaveScene(scene, scenePath))
        {
            throw new InvalidOperationException("Could not save Gate-3 scene.");
        }

        string buildDirectory = Path.GetFullPath("Build");
        Directory.CreateDirectory(buildDirectory);
        string executable = Path.Combine(buildDirectory, "TEVScriptMonoGate.exe");

        BuildPlayerOptions options = new BuildPlayerOptions
        {
            scenes = new[] { scenePath },
            locationPathName = executable,
            target = BuildTarget.StandaloneWindows64,
            options = BuildOptions.Development | BuildOptions.DetailedBuildReport
        };

        BuildReport report = BuildPipeline.BuildPlayer(options);
        BuildSummary summary = report.summary;
        if (summary.result != BuildResult.Succeeded)
        {
            throw new InvalidOperationException(
                "Mono Player build failed: " + summary.result);
        }

        Debug.Log("UNITY_MONO_PLAYER_BUILD_BACKEND=MONO");
        Debug.Log("UNITY_MONO_PLAYER_BUILD_TARGET=STANDALONE_WINDOWS64");
        Debug.Log("UNITY_MONO_PLAYER_BUILD_RESULT=PASS");
        Debug.Log("UNITY_MONO_PLAYER_BUILD_BYTES=" + summary.totalSize);
        Debug.Log("UNITY_IL2CPP=NOT_PROBED");
    }
}
