using System;
using System.IO;
using Marcbeacve.TevScript.Gate6A.Web;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Marcbeacve.TevScript.Gate6A.Web.Editor
{
    public static class TevScriptUnityWebBuildGate
    {
        public static void Build()
        {
            string output = Environment.GetEnvironmentVariable(
                "TEV_SCRIPT_GATE6A_BUILD_DIR");
            if (string.IsNullOrWhiteSpace(output))
            {
                throw new InvalidOperationException(
                    "TEV_SCRIPT_GATE6A_BUILD_DIR is required.");
            }

            output = Path.GetFullPath(output);
            Directory.CreateDirectory(output);

            PlayerSettings.productName = "TEV Script Gate 6A Web";
            PlayerSettings.companyName = "Marcbeacve";
            PlayerSettings.WebGL.compressionFormat =
                WebGLCompressionFormat.Disabled;
            PlayerSettings.WebGL.decompressionFallback = false;

            UnityEngine.SceneManagement.Scene scene =
                EditorSceneManager.NewScene(
                    NewSceneSetup.EmptyScene,
                    NewSceneMode.Single);

            var host = new GameObject("TEVScriptGate6AHost");
            host.AddComponent<TevScriptUnityWebGate>();

            const string scenePath = "Assets/TEVScriptGate6A.unity";
            if (!EditorSceneManager.SaveScene(scene, scenePath))
            {
                throw new InvalidOperationException(
                    "Failed to save Gate-6A scene.");
            }

            AssetDatabase.SaveAssets();

            var options = new BuildPlayerOptions
            {
                scenes = new[] { scenePath },
                locationPathName = output,
                target = BuildTarget.WebGL,
                options = BuildOptions.None
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != BuildResult.Succeeded)
            {
                throw new InvalidOperationException(
                    "Gate-6A WebGL build failed: " +
                    report.summary.result);
            }

            Debug.Log("UNITY_GATE6A_BUILD_TARGET=WEBGL");
            Debug.Log("UNITY_GATE6A_BUILD_COMPRESSION=DISABLED");
            Debug.Log("UNITY_GATE6A_BUILD_RESULT=PASS");
        }
    }
}
