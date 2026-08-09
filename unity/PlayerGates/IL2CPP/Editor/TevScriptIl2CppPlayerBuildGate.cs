using System;
using System.IO;
using Marcbeacve.TevScript.Gate4.Il2CppPlayer;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Marcbeacve.TevScript.Gate4.Il2CppPlayer.Editor
{
    public static class TevScriptIl2CppPlayerBuildGate
    {
        public static void Build()
        {
            string executable = Environment.GetEnvironmentVariable(
                "TEV_SCRIPT_GATE4_BUILD_EXE");
            if (string.IsNullOrWhiteSpace(executable))
            {
                throw new InvalidOperationException(
                    "TEV_SCRIPT_GATE4_BUILD_EXE is required.");
            }

            executable = Path.GetFullPath(executable);
            Directory.CreateDirectory(
                Path.GetDirectoryName(executable));

            NamedBuildTarget namedTarget = NamedBuildTarget.Standalone;
            PlayerSettings.SetScriptingBackend(
                namedTarget,
                ScriptingImplementation.IL2CPP);

            ScriptingImplementation observed =
                PlayerSettings.GetScriptingBackend(namedTarget);
            if (observed != ScriptingImplementation.IL2CPP)
            {
                throw new InvalidOperationException(
                    "Failed to bind Standalone scripting backend to IL2CPP.");
            }

            PlayerSettings.productName = "TEV Script IL2CPP Gate";
            PlayerSettings.companyName = "Marcbeacve";

            UnityEngine.SceneManagement.Scene scene =
                EditorSceneManager.NewScene(
                    NewSceneSetup.EmptyScene,
                    NewSceneMode.Single);
            var host = new GameObject("TEVScriptGate4Host");
            host.AddComponent<TevScriptIl2CppPlayerGate>();

            const string scenePath = "Assets/TEVScriptGate4.unity";
            if (!EditorSceneManager.SaveScene(scene, scenePath))
            {
                throw new InvalidOperationException(
                    "Failed to save Gate-4 scene.");
            }

            AssetDatabase.SaveAssets();

            var options = new BuildPlayerOptions
            {
                scenes = new[] { scenePath },
                locationPathName = executable,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != BuildResult.Succeeded)
            {
                throw new InvalidOperationException(
                    "IL2CPP build failed: " + report.summary.result);
            }

            Debug.Log("UNITY_IL2CPP_PLAYER_BUILD_BACKEND=IL2CPP");
            Debug.Log(
                "UNITY_IL2CPP_PLAYER_BUILD_TARGET=STANDALONE_WINDOWS64");
            Debug.Log("UNITY_IL2CPP_PLAYER_BUILD_RESULT=PASS");
        }
    }
}
