using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;
using Marcbeacve.TevScript.Core;

internal static class Program
{
    private static int Main(string[] args)
    {
        if (args.Length != 1 || !File.Exists(args[0]))
        {
            Console.Error.WriteLine(
                "Usage: TevScript.Core.Smoke <Player.tevs.ir.json>");
            return 2;
        }

        TevScriptProgram program = TevScriptProgram.Parse(
            File.ReadAllText(args[0]));
        var trace = new List<string>();
        var capabilities = new ITevScriptCapability[]
        {
            new DelegateTevScriptCapability(
                "debug.log",
                arguments =>
                {
                    trace.Add("log:" + arguments[0].AsText());
                    return TevScriptValue.Unit();
                }),
            new DelegateTevScriptCapability(
                "input.move2d",
                _ => TevScriptValue.Vec2(
                    TevRational.One,
                    TevRational.Zero)),
            new DelegateTevScriptCapability(
                "motion.move2d",
                arguments =>
                {
                    trace.Add("move:" +
                        string.Join(",", arguments[0].AsVector()));
                    return TevScriptValue.Unit();
                }),
            new DelegateTevScriptCapability(
                "animation.play",
                arguments =>
                {
                    trace.Add("animation:" + arguments[0].AsText());
                    return TevScriptValue.Unit();
                })
        };

        var runtime = new TevScriptRuntime(program, capabilities);
        runtime.Invoke("Player", "start");
        runtime.Invoke("Player", "update");
        runtime.Invoke(
            "Player",
            "damage",
            TevScriptValue.Int(new BigInteger(100)));

        if (runtime.State("Player")["health"].AsInt() != BigInteger.Zero)
            throw new InvalidOperationException("health did not reach zero");
        if (!runtime.EmittedEvents.Select(item => item.EventId)
                .SequenceEqual(new[] { "died" }))
            throw new InvalidOperationException("died event missing");
        if (!trace.Contains("animation:Walk"))
            throw new InvalidOperationException("Walk animation missing");

        Console.WriteLine("TEV_SCRIPT_CSHARP_SMOKE=PASS");
        return 0;
    }
}
