using System;
using System.Collections.Generic;
using System.Linq;

namespace Marcbeacve.TevScript.Core
{
    public sealed class TevScriptRuntimeSnapshot
    {
        private readonly Dictionary<
            string,
            IReadOnlyDictionary<string, TevScriptValue>> _entities;

        internal TevScriptRuntimeSnapshot(
            string programId,
            string semanticHash,
            Dictionary<
                string,
                IReadOnlyDictionary<string, TevScriptValue>> entities)
        {
            ProgramId = programId ??
                throw new ArgumentNullException(nameof(programId));
            SemanticHash = semanticHash ??
                throw new ArgumentNullException(nameof(semanticHash));
            _entities = entities ??
                throw new ArgumentNullException(nameof(entities));
        }

        public string ProgramId { get; }
        public string SemanticHash { get; }

        public IReadOnlyDictionary<
            string,
            IReadOnlyDictionary<string, TevScriptValue>> Entities
        {
            get { return _entities; }
        }
    }

    public sealed partial class TevScriptRuntime
    {
        internal TevScriptProgram ProgramDefinition
        {
            get { return _program; }
        }

        public string ProgramId
        {
            get { return _program.ProgramId; }
        }

        public string SemanticHash
        {
            get { return _program.SemanticHash; }
        }

        public TevScriptRuntimeSnapshot CaptureSnapshot()
        {
            var entities = new Dictionary<
                string,
                IReadOnlyDictionary<string, TevScriptValue>>(
                    StringComparer.Ordinal);

            foreach (TevScriptEntityDefinition definition in _program.Entities)
            {
                RuntimeEntity entity = _entities[definition.EntityId];
                entities.Add(
                    definition.EntityId,
                    new Dictionary<string, TevScriptValue>(
                        entity.State,
                        StringComparer.Ordinal));
            }

            return new TevScriptRuntimeSnapshot(
                _program.ProgramId,
                _program.SemanticHash,
                entities);
        }

        internal void RestoreCompatibleSnapshot(
            TevScriptRuntimeSnapshot snapshot)
        {
            if (snapshot == null)
            {
                throw new ArgumentNullException(nameof(snapshot));
            }
            if (!string.Equals(
                    snapshot.ProgramId,
                    _program.ProgramId,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_SWAP_PROGRAM_ID",
                    "Snapshot program id does not match candidate program.");
            }

            var definitions = _program.Entities.ToDictionary(
                item => item.EntityId,
                item => item,
                StringComparer.Ordinal);

            foreach (KeyValuePair<
                         string,
                         IReadOnlyDictionary<string, TevScriptValue>>
                     entitySnapshot in snapshot.Entities)
            {
                TevScriptEntityDefinition definition;
                RuntimeEntity runtimeEntity;
                if (!definitions.TryGetValue(
                        entitySnapshot.Key,
                        out definition) ||
                    !_entities.TryGetValue(
                        entitySnapshot.Key,
                        out runtimeEntity))
                {
                    throw new TevContractException(
                        "TEVS_CS_SWAP_ENTITY_SET",
                        "Candidate program removed entity " +
                        entitySnapshot.Key + ".");
                }

                Dictionary<string, TevScriptStateDefinition> stateDefinitions =
                    definition.States.ToDictionary(
                        item => item.Name,
                        item => item,
                        StringComparer.Ordinal);

                foreach (KeyValuePair<string, TevScriptValue> state
                         in entitySnapshot.Value)
                {
                    TevScriptStateDefinition stateDefinition;
                    if (!stateDefinitions.TryGetValue(
                            state.Key,
                            out stateDefinition))
                    {
                        throw new TevContractException(
                            "TEVS_CS_SWAP_STATE_REMOVED",
                            "Candidate program removed state " +
                            entitySnapshot.Key + "." + state.Key + ".");
                    }
                    if (!string.Equals(
                            stateDefinition.TypeName,
                            state.Value.TypeName,
                            StringComparison.Ordinal))
                    {
                        throw new TevContractException(
                            "TEVS_CS_SWAP_STATE_TYPE",
                            "Candidate program changed state type for " +
                            entitySnapshot.Key + "." + state.Key + ".");
                    }
                    runtimeEntity.State[state.Key] = state.Value;
                }
            }
        }
    }

    public sealed class TevScriptRuntimeSwapPlan
    {
        private bool _consumed;

        internal TevScriptRuntimeSwapPlan(
            object owner,
            long sourceGeneration,
            string sourceSemanticHash,
            TevScriptProgram candidateProgram,
            TevScriptRuntime candidateRuntime)
        {
            Owner = owner;
            SourceGeneration = sourceGeneration;
            SourceSemanticHash = sourceSemanticHash;
            CandidateProgram = candidateProgram;
            CandidateRuntime = candidateRuntime;
        }

        internal object Owner { get; }
        internal long SourceGeneration { get; }
        internal string SourceSemanticHash { get; }
        internal TevScriptProgram CandidateProgram { get; }
        internal TevScriptRuntime CandidateRuntime { get; }

        public string CandidateProgramId
        {
            get { return CandidateProgram.ProgramId; }
        }

        public string CandidateSemanticHash
        {
            get { return CandidateProgram.SemanticHash; }
        }

        public bool IsConsumed
        {
            get { return _consumed; }
        }

        internal void Consume()
        {
            if (_consumed)
            {
                throw new TevContractException(
                    "TEVS_CS_SWAP_PLAN_CONSUMED",
                    "Swap plan has already been committed.");
            }
            _consumed = true;
        }
    }

    public sealed class TevScriptRuntimeSwapReceipt
    {
        internal TevScriptRuntimeSwapReceipt(
            long generation,
            string sourceSemanticHash,
            string targetSemanticHash,
            bool rollback)
        {
            Generation = generation;
            SourceSemanticHash = sourceSemanticHash;
            TargetSemanticHash = targetSemanticHash;
            Rollback = rollback;
        }

        public long Generation { get; }
        public string SourceSemanticHash { get; }
        public string TargetSemanticHash { get; }
        public bool Rollback { get; }
    }

    public sealed class TevScriptRuntimeHost
    {
        private readonly object _sync = new object();
        private readonly object _planOwner = new object();
        private readonly ITevScriptCapability[] _capabilities;
        private readonly HashSet<string> _capabilityCeiling;

        private TevScriptRuntime _active;
        private TevScriptRuntime _rollbackRuntime;
        private long _generation;

        public TevScriptRuntimeHost(
            TevScriptProgram initialProgram,
            IEnumerable<ITevScriptCapability> capabilities,
            IEnumerable<string> capabilityCeiling)
        {
            if (initialProgram == null)
            {
                throw new ArgumentNullException(nameof(initialProgram));
            }

            _capabilities = capabilities == null
                ? new ITevScriptCapability[0]
                : capabilities.ToArray();

            _capabilityCeiling = new HashSet<string>(
                StringComparer.Ordinal);
            if (capabilityCeiling != null)
            {
                foreach (string capabilityId in capabilityCeiling)
                {
                    if (string.IsNullOrWhiteSpace(capabilityId))
                    {
                        throw new ArgumentException(
                            "Capability ceiling contains an empty id.",
                            nameof(capabilityCeiling));
                    }
                    if (!_capabilityCeiling.Add(capabilityId))
                    {
                        throw new ArgumentException(
                            "Capability ceiling contains duplicate " +
                            capabilityId + ".",
                            nameof(capabilityCeiling));
                    }
                }
            }

            ValidateCapabilityCeiling(initialProgram);
            _active = new TevScriptRuntime(
                initialProgram,
                _capabilities);
        }

        public string ActiveProgramId
        {
            get
            {
                lock (_sync)
                {
                    return _active.ProgramId;
                }
            }
        }

        public string ActiveSemanticHash
        {
            get
            {
                lock (_sync)
                {
                    return _active.SemanticHash;
                }
            }
        }

        public long Generation
        {
            get
            {
                lock (_sync)
                {
                    return _generation;
                }
            }
        }

        public IReadOnlyList<TevScriptEvent> Invoke(
            string entityId,
            string eventId,
            params TevScriptValue[] arguments)
        {
            lock (_sync)
            {
                return _active.Invoke(
                    entityId,
                    eventId,
                    arguments);
            }
        }

        public IReadOnlyDictionary<string, TevScriptValue> State(
            string entityId)
        {
            lock (_sync)
            {
                return _active.State(entityId);
            }
        }

        public TevScriptRuntimeSnapshot CaptureSnapshot()
        {
            lock (_sync)
            {
                return _active.CaptureSnapshot();
            }
        }

        public TevScriptRuntimeSwapPlan PrepareSwap(
            string candidateProgramJson)
        {
            if (candidateProgramJson == null)
            {
                throw new ArgumentNullException(
                    nameof(candidateProgramJson));
            }

            // Parsing and hash/boundary validation happen before any
            // authoritative host state is touched.
            TevScriptProgram candidate =
                TevScriptProgram.Parse(candidateProgramJson);

            lock (_sync)
            {
                TevScriptProgram current =
                    _active.ProgramDefinition;

                ValidateProgramContinuity(
                    current,
                    candidate);
                ValidateCapabilityCeiling(candidate);

                TevScriptRuntimeSnapshot snapshot =
                    _active.CaptureSnapshot();

                // Candidate runtime is isolated. If construction or state
                // restoration fails, _active remains unchanged.
                var candidateRuntime = new TevScriptRuntime(
                    candidate,
                    _capabilities);
                candidateRuntime.RestoreCompatibleSnapshot(
                    snapshot);

                return new TevScriptRuntimeSwapPlan(
                    _planOwner,
                    _generation,
                    _active.SemanticHash,
                    candidate,
                    candidateRuntime);
            }
        }

        public TevScriptRuntimeSwapReceipt Commit(
            TevScriptRuntimeSwapPlan plan)
        {
            if (plan == null)
            {
                throw new ArgumentNullException(nameof(plan));
            }

            lock (_sync)
            {
                if (!ReferenceEquals(plan.Owner, _planOwner))
                {
                    throw new TevContractException(
                        "TEVS_CS_SWAP_PLAN_OWNER",
                        "Swap plan belongs to a different runtime host.");
                }
                if (plan.IsConsumed)
                {
                    throw new TevContractException(
                        "TEVS_CS_SWAP_PLAN_CONSUMED",
                        "Swap plan has already been committed.");
                }
                if (plan.SourceGeneration != _generation ||
                    !string.Equals(
                        plan.SourceSemanticHash,
                        _active.SemanticHash,
                        StringComparison.Ordinal))
                {
                    throw new TevContractException(
                        "TEVS_CS_SWAP_PLAN_STALE",
                        "Swap plan was prepared against stale runtime state.");
                }

                string sourceHash = _active.SemanticHash;
                _rollbackRuntime = _active;

                // The single authoritative mutation of Gate-5A.
                _active = plan.CandidateRuntime;
                _generation++;
                plan.Consume();

                return new TevScriptRuntimeSwapReceipt(
                    _generation,
                    sourceHash,
                    _active.SemanticHash,
                    false);
            }
        }

        public TevScriptRuntimeSwapReceipt RollbackLastCommit()
        {
            lock (_sync)
            {
                if (_rollbackRuntime == null)
                {
                    throw new TevContractException(
                        "TEVS_CS_SWAP_ROLLBACK_NONE",
                        "No committed runtime is available for rollback.");
                }

                string sourceHash = _active.SemanticHash;
                TevScriptRuntime target = _rollbackRuntime;
                _rollbackRuntime = null;
                _active = target;
                _generation++;

                return new TevScriptRuntimeSwapReceipt(
                    _generation,
                    sourceHash,
                    _active.SemanticHash,
                    true);
            }
        }

        private static void ValidateProgramContinuity(
            TevScriptProgram current,
            TevScriptProgram candidate)
        {
            if (!string.Equals(
                    current.ProgramId,
                    candidate.ProgramId,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_SWAP_PROGRAM_ID",
                    "Candidate program id differs from active program.");
            }

            Dictionary<string, TevScriptEntityDefinition> currentEntities =
                current.Entities.ToDictionary(
                    item => item.EntityId,
                    item => item,
                    StringComparer.Ordinal);
            Dictionary<string, TevScriptEntityDefinition> candidateEntities =
                candidate.Entities.ToDictionary(
                    item => item.EntityId,
                    item => item,
                    StringComparer.Ordinal);

            if (currentEntities.Count != candidateEntities.Count ||
                currentEntities.Keys.Any(
                    item => !candidateEntities.ContainsKey(item)))
            {
                throw new TevContractException(
                    "TEVS_CS_SWAP_ENTITY_SET",
                    "Gate-5A requires an unchanged entity identity set.");
            }

            foreach (KeyValuePair<
                         string,
                         TevScriptEntityDefinition> entity
                     in currentEntities)
            {
                TevScriptEntityDefinition candidateEntity =
                    candidateEntities[entity.Key];

                Dictionary<string, TevScriptStateDefinition> candidateStates =
                    candidateEntity.States.ToDictionary(
                        item => item.Name,
                        item => item,
                        StringComparer.Ordinal);

                foreach (TevScriptStateDefinition state
                         in entity.Value.States)
                {
                    TevScriptStateDefinition candidateState;
                    if (!candidateStates.TryGetValue(
                            state.Name,
                            out candidateState))
                    {
                        throw new TevContractException(
                            "TEVS_CS_SWAP_STATE_REMOVED",
                            "Candidate removed state " +
                            entity.Key + "." + state.Name + ".");
                    }
                    if (!string.Equals(
                            state.TypeName,
                            candidateState.TypeName,
                            StringComparison.Ordinal))
                    {
                        throw new TevContractException(
                            "TEVS_CS_SWAP_STATE_TYPE",
                            "Candidate changed state type for " +
                            entity.Key + "." + state.Name + ".");
                    }
                }
            }
        }

        private void ValidateCapabilityCeiling(
            TevScriptProgram program)
        {
            foreach (TevScriptEntityDefinition entity
                     in program.Entities)
            {
                foreach (string capabilityId
                         in entity.Capabilities.Keys)
                {
                    if (!_capabilityCeiling.Contains(capabilityId))
                    {
                        throw new TevContractException(
                            "TEVS_CS_SWAP_CAPABILITY_CEILING",
                            "Program requests capability outside host ceiling: " +
                            capabilityId + ".");
                    }
                }
            }
        }
    }
}
