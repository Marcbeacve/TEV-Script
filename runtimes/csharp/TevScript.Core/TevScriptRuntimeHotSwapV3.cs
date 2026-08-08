using System.Text.Json;

namespace TevScript.Core.V3;

public sealed record TevScriptCapabilityContractV3(
    string CapabilityId,
    IReadOnlyList<string> Parameters,
    string ReturnType,
    string Kind)
{
    internal bool SameSignature(TevScriptCapabilityContractV3 other) =>
        other is not null
        && StringComparer.Ordinal.Equals(CapabilityId, other.CapabilityId)
        && StringComparer.Ordinal.Equals(ReturnType, other.ReturnType)
        && StringComparer.Ordinal.Equals(Kind, other.Kind)
        && Parameters.SequenceEqual(other.Parameters, StringComparer.Ordinal);
}

public sealed class TevScriptRuntimeSnapshotV3
{
    internal TevScriptRuntimeSnapshotV3(
        string programId,
        string semanticHash,
        string sourceSemanticHash,
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, TevScriptValueV3>> entities)
    {
        ProgramId = programId;
        SemanticHash = semanticHash;
        SourceSemanticHash = sourceSemanticHash;
        Entities = entities;
    }

    public string ProgramId { get; }
    public string SemanticHash { get; }
    public string SourceSemanticHash { get; }
    public IReadOnlyDictionary<string, IReadOnlyDictionary<string, TevScriptValueV3>> Entities { get; }
}

public sealed partial class TevScriptRuntimeV3
{
    public TevScriptRuntimeSnapshotV3 CaptureSnapshot()
    {
        var entities = new Dictionary<string, IReadOnlyDictionary<string, TevScriptValueV3>>(StringComparer.Ordinal);
        foreach (var pair in _entities.OrderBy(item => item.Key, StringComparer.Ordinal))
        {
            entities.Add(
                pair.Key,
                new Dictionary<string, TevScriptValueV3>(pair.Value.State, StringComparer.Ordinal));
        }
        return new TevScriptRuntimeSnapshotV3(
            ProgramId,
            SemanticHash,
            SourceSemanticHash,
            entities);
    }

    internal void RestoreCompatibleSnapshot(TevScriptRuntimeSnapshotV3 snapshot)
    {
        if (snapshot is null) throw new ArgumentNullException(nameof(snapshot));
        if (!StringComparer.Ordinal.Equals(snapshot.ProgramId, ProgramId))
            throw new TevScriptV3Exception(
                "TEVS_IR_V3_SWAP_PROGRAM_ID",
                "snapshot program id does not match candidate program");

        if (snapshot.Entities.Count != _entities.Count
            || snapshot.Entities.Keys.Any(entityId => !_entities.ContainsKey(entityId)))
            throw new TevScriptV3Exception(
                "TEVS_IR_V3_SWAP_ENTITY_SET",
                "candidate entity identity set differs from snapshot");

        var restored = new Dictionary<string, Dictionary<string, TevScriptValueV3>>(StringComparer.Ordinal);
        foreach (var entitySnapshot in snapshot.Entities)
        {
            var candidate = _entities[entitySnapshot.Key];
            var values = new Dictionary<string, TevScriptValueV3>(StringComparer.Ordinal);
            foreach (var state in entitySnapshot.Value)
            {
                if (!candidate.StateTypes.TryGetValue(state.Key, out var expectedType))
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_SWAP_STATE_REMOVED",
                        $"candidate removed state {entitySnapshot.Key}.{state.Key}");
                if (!StringComparer.Ordinal.Equals(state.Value.TypeId, expectedType))
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_SWAP_STATE_TYPE",
                        $"candidate changed state type for {entitySnapshot.Key}.{state.Key}");
                values.Add(
                    state.Key,
                    Normalize(
                        expectedType,
                        state.Value,
                        $"swap {entitySnapshot.Key}.{state.Key}"));
            }
            restored.Add(entitySnapshot.Key, values);
        }

        foreach (var pair in restored)
        {
            var candidate = _entities[pair.Key];
            foreach (var state in pair.Value)
                candidate.State[state.Key] = state.Value;
        }
    }
}

public sealed class TevScriptRuntimeSwapPlanV3
{
    private bool _consumed;

    internal TevScriptRuntimeSwapPlanV3(
        object owner,
        long sourceGeneration,
        string sourceSemanticHash,
        JsonElement candidateIr,
        TevScriptRuntimeV3 candidateRuntime)
    {
        Owner = owner;
        SourceGeneration = sourceGeneration;
        SourceSemanticHash = sourceSemanticHash;
        CandidateIr = candidateIr.Clone();
        CandidateRuntime = candidateRuntime;
    }

    internal object Owner { get; }
    internal long SourceGeneration { get; }
    internal string SourceSemanticHash { get; }
    internal JsonElement CandidateIr { get; }
    internal TevScriptRuntimeV3 CandidateRuntime { get; }
    public string CandidateProgramId => CandidateRuntime.ProgramId;
    public string CandidateSemanticHash => CandidateRuntime.SemanticHash;
    public string CandidateSourceSemanticHash => CandidateRuntime.SourceSemanticHash;
    public bool IsConsumed => _consumed;

    internal void Consume()
    {
        if (_consumed)
            throw new TevScriptV3Exception(
                "TEVS_IR_V3_SWAP_PLAN_CONSUMED",
                "swap plan has already been consumed");
        _consumed = true;
    }
}

public sealed record TevScriptRuntimeSwapReceiptV3(
    long Generation,
    string SourceSemanticHash,
    string TargetSemanticHash,
    bool Rollback);

public sealed class TevScriptRuntimeHostV3
{
    private readonly object _sync = new();
    private readonly object _planOwner = new();
    private readonly IReadOnlyDictionary<string, TevScriptCapabilityV3> _capabilities;
    private readonly Dictionary<string, TevScriptCapabilityContractV3> _capabilityCeiling;
    private TevScriptRuntimeV3 _active;
    private TevScriptRuntimeV3? _rollbackRuntime;
    private long _generation;

    public TevScriptRuntimeHostV3(
        JsonElement initialProgram,
        IReadOnlyDictionary<string, TevScriptCapabilityV3>? capabilities,
        IEnumerable<TevScriptCapabilityContractV3> capabilityCeiling)
    {
        if (capabilityCeiling is null) throw new ArgumentNullException(nameof(capabilityCeiling));
        _capabilities = capabilities is null
            ? new Dictionary<string, TevScriptCapabilityV3>(StringComparer.Ordinal)
            : new Dictionary<string, TevScriptCapabilityV3>(capabilities, StringComparer.Ordinal);
        _capabilityCeiling = new Dictionary<string, TevScriptCapabilityContractV3>(StringComparer.Ordinal);
        foreach (var contract in capabilityCeiling)
        {
            if (contract is null)
                throw new ArgumentException("capability ceiling cannot contain null", nameof(capabilityCeiling));
            if (_capabilityCeiling.ContainsKey(contract.CapabilityId))
                throw new ArgumentException(
                    "capability ceiling contains duplicate " + contract.CapabilityId,
                    nameof(capabilityCeiling));
            _capabilityCeiling.Add(contract.CapabilityId, contract);
        }

        var validated = initialProgram.Clone();
        TevScriptProgramValidatorV3.Validate(validated);
        ValidateCapabilityCeiling(validated);
        _active = new TevScriptRuntimeV3(validated, _capabilities);
    }

    public string ActiveProgramId
    {
        get { lock (_sync) return _active.ProgramId; }
    }

    public string ActiveSemanticHash
    {
        get { lock (_sync) return _active.SemanticHash; }
    }

    public string ActiveSourceSemanticHash
    {
        get { lock (_sync) return _active.SourceSemanticHash; }
    }

    public long Generation
    {
        get { lock (_sync) return _generation; }
    }

    public IReadOnlyList<TevScriptEmittedEventV3> Invoke(
        string entityId,
        string eventId,
        params TevScriptValueV3[] arguments)
    {
        lock (_sync)
            return _active.Invoke(entityId, eventId, arguments);
    }

    public IReadOnlyDictionary<string, TevScriptValueV3> State(string entityId)
    {
        lock (_sync)
            return _active.State(entityId);
    }

    public TevScriptRuntimeSnapshotV3 CaptureSnapshot()
    {
        lock (_sync)
            return _active.CaptureSnapshot();
    }

    public TevScriptRuntimeSwapPlanV3 PrepareSwap(string candidateProgramJson)
    {
        if (candidateProgramJson is null)
            throw new ArgumentNullException(nameof(candidateProgramJson));
        var candidate = TevScriptStrictJsonV3.ParseElement(candidateProgramJson);
        TevScriptProgramValidatorV3.Validate(candidate);

        lock (_sync)
        {
            ValidateProgramContinuity(_active.IrForCheckpoint, candidate);
            ValidateCapabilityCeiling(candidate);
            var snapshot = _active.CaptureSnapshot();
            var candidateRuntime = new TevScriptRuntimeV3(candidate, _capabilities);
            candidateRuntime.RestoreCompatibleSnapshot(snapshot);
            return new TevScriptRuntimeSwapPlanV3(
                _planOwner,
                _generation,
                _active.SemanticHash,
                candidate,
                candidateRuntime);
        }
    }

    public TevScriptRuntimeSwapReceiptV3 Commit(TevScriptRuntimeSwapPlanV3 plan)
    {
        if (plan is null) throw new ArgumentNullException(nameof(plan));
        lock (_sync)
        {
            if (!ReferenceEquals(plan.Owner, _planOwner))
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_SWAP_PLAN_OWNER",
                    "swap plan belongs to a different runtime host");
            if (plan.IsConsumed)
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_SWAP_PLAN_CONSUMED",
                    "swap plan has already been committed");
            if (plan.SourceGeneration != _generation
                || !StringComparer.Ordinal.Equals(plan.SourceSemanticHash, _active.SemanticHash))
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_SWAP_PLAN_STALE",
                    "swap plan was prepared against stale runtime state");

            var source = _active.SemanticHash;
            _rollbackRuntime = _active;
            _active = plan.CandidateRuntime;
            checked { ++_generation; }
            plan.Consume();
            return new TevScriptRuntimeSwapReceiptV3(
                _generation,
                source,
                _active.SemanticHash,
                false);
        }
    }

    public TevScriptRuntimeSwapReceiptV3 RollbackLastCommit()
    {
        lock (_sync)
        {
            if (_rollbackRuntime is null)
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_SWAP_ROLLBACK_NONE",
                    "no committed runtime is available for rollback");
            var source = _active.SemanticHash;
            var target = _rollbackRuntime;
            _rollbackRuntime = null;
            _active = target;
            checked { ++_generation; }
            return new TevScriptRuntimeSwapReceiptV3(
                _generation,
                source,
                _active.SemanticHash,
                true);
        }
    }

    internal static IReadOnlyDictionary<string, TevScriptCapabilityContractV3> CapabilityContracts(JsonElement program)
    {
        var result = new Dictionary<string, TevScriptCapabilityContractV3>(StringComparer.Ordinal);
        foreach (var entity in program.GetProperty("entities").EnumerateArray())
        {
            foreach (var raw in entity.GetProperty("capabilities").EnumerateArray())
            {
                var contract = new TevScriptCapabilityContractV3(
                    raw.GetProperty("capability_id").GetString()!,
                    raw.GetProperty("parameters").EnumerateArray().Select(item => item.GetString()!).ToArray(),
                    raw.GetProperty("return_type").GetString()!,
                    raw.GetProperty("kind").GetString()!);
                if (result.TryGetValue(contract.CapabilityId, out var previous)
                    && !previous.SameSignature(contract))
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_SWAP_CAPABILITY_CONFLICT",
                        "program contains conflicting contracts for capability " + contract.CapabilityId);
                result[contract.CapabilityId] = contract;
            }
        }
        return result;
    }

    private void ValidateCapabilityCeiling(JsonElement program)
    {
        foreach (var contract in CapabilityContracts(program).Values)
        {
            if (!_capabilityCeiling.TryGetValue(contract.CapabilityId, out var allowed))
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_SWAP_CAPABILITY_CEILING",
                    "program requests capability outside host ceiling: " + contract.CapabilityId);
            if (!allowed.SameSignature(contract))
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_SWAP_CAPABILITY_SIGNATURE_CEILING",
                    "program changes capability ABI outside host ceiling: " + contract.CapabilityId);
        }
    }

    private static void ValidateProgramContinuity(JsonElement current, JsonElement candidate)
    {
        if (!StringComparer.Ordinal.Equals(
                current.GetProperty("program_id").GetString(),
                candidate.GetProperty("program_id").GetString()))
            throw new TevScriptV3Exception(
                "TEVS_IR_V3_SWAP_PROGRAM_ID",
                "candidate program id differs from active program");

        var currentEntities = current.GetProperty("entities").EnumerateArray().ToDictionary(
            item => item.GetProperty("entity_id").GetString()!,
            item => item,
            StringComparer.Ordinal);
        var candidateEntities = candidate.GetProperty("entities").EnumerateArray().ToDictionary(
            item => item.GetProperty("entity_id").GetString()!,
            item => item,
            StringComparer.Ordinal);
        if (currentEntities.Count != candidateEntities.Count
            || currentEntities.Keys.Any(entityId => !candidateEntities.ContainsKey(entityId)))
            throw new TevScriptV3Exception(
                "TEVS_IR_V3_SWAP_ENTITY_SET",
                "transactional V3 swap requires unchanged entity identity set");

        foreach (var pair in currentEntities)
        {
            var candidateStates = candidateEntities[pair.Key].GetProperty("states").EnumerateArray().ToDictionary(
                item => item.GetProperty("name").GetString()!,
                item => item.GetProperty("type").GetString()!,
                StringComparer.Ordinal);
            foreach (var state in pair.Value.GetProperty("states").EnumerateArray())
            {
                var name = state.GetProperty("name").GetString()!;
                var type = state.GetProperty("type").GetString()!;
                if (!candidateStates.TryGetValue(name, out var targetType))
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_SWAP_STATE_REMOVED",
                        $"candidate removed state {pair.Key}.{name}");
                if (!StringComparer.Ordinal.Equals(type, targetType))
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_SWAP_STATE_TYPE",
                        $"candidate changed state type for {pair.Key}.{name}");
            }
        }
    }
}
