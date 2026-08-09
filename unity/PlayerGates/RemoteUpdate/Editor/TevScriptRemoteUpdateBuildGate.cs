using System;
using System.IO;
using Marcbeacve.TevScript.Gate5E.RemoteUpdate;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Marcbeacve.TevScript.Gate5E.RemoteUpdate.Editor
{
    public static class TevScriptRemoteUpdateBuildGate
    {
        public static void Build()
        {
            string executable = Environment.GetEnvironmentVariable(
                "TEV_SCRIPT_GATE5E_BUILD_EXE");
            if (string.IsNullOrWhiteSpace(executable))
                throw new InvalidOperationException(
                    "TEV_SCRIPT_GATE5E_BUILD_EXE is required.");

            executable = Path.GetFullPath(executable);
            Directory.CreateDirectory(Path.GetDirectoryName(executable));

            NamedBuildTarget target = NamedBuildTarget.Standalone;
            PlayerSettings.SetScriptingBackend(
                target,
                ScriptingImplementation.IL2CPP);

            if (PlayerSettings.GetScriptingBackend(target) !=
                ScriptingImplementation.IL2CPP)
            {
                throw new InvalidOperationException(
                    "Gate-5E failed to bind IL2CPP.");
            }

            PlayerSettings.productName = "TEV Script Remote Update Gate";
            PlayerSettings.companyName = "Marcbeacve";

            UnityEngine.SceneManagement.Scene scene =
                EditorSceneManager.NewScene(
                    NewSceneSetup.EmptyScene,
                    NewSceneMode.Single);
            var host = new GameObject("TEVScriptGate5EHost");
            host.AddComponent<TevScriptRemoteUpdateGate>();

            const string scenePath = "Assets/TEVScriptGate5E.unity";
            if (!EditorSceneManager.SaveScene(scene, scenePath))
                throw new InvalidOperationException(
                    "Failed to save Gate-5E scene.");

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
                throw new InvalidOperationException(
                    "Gate-5E build failed: " + report.summary.result);

            Debug.Log("UNITY_GATE5E_BUILD_BACKEND=IL2CPP");
            Debug.Log(
                "UNITY_GATE5E_BUILD_TARGET=STANDALONE_WINDOWS64");
            Debug.Log("UNITY_GATE5E_BUILD_RESULT=PASS");
        }
    }
}
