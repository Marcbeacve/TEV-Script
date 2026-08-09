using System;
using System.Collections.Generic;
using System.Linq;

namespace Marcbeacve.TevScript.Core
{
    public sealed class TevScriptRuntimeCheckpoint
    {
        public const string Schema = "TEV_SCRIPT_RUNTIME_CHECKPOINT_V1";

        private readonly Dictionary<
            string,
            IReadOnlyDictionary<string, TevScriptValue>> _entities;

        private TevScriptRuntimeCheckpoint(
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

        public string CheckpointHash
        {
            get { return TevJson.Sha256(ToCanonicalJson()); }
        }

        public static TevScriptRuntimeCheckpoint Capture(
            TevScriptRuntime runtime)
        {
            if (runtime == null)
                throw new ArgumentNullException(nameof(runtime));
            return Capture(runtime.CaptureSnapshot());
        }

        public static TevScriptRuntimeCheckpoint Capture(
            TevScriptRuntimeSnapshot snapshot)
        {
            if (snapshot == null)
                throw new ArgumentNullException(nameof(snapshot));

            var entities = new Dictionary<
                string,
                IReadOnlyDictionary<string, TevScriptValue>>(
                    StringComparer.Ordinal);

            foreach (KeyValuePair<
                         string,
                         IReadOnlyDictionary<string, TevScriptValue>>
                     entity in snapshot.Entities.OrderBy(
                         item => item.Key,
                         StringComparer.Ordinal))
            {
                entities.Add(
                    entity.Key,
                    new Dictionary<string, TevScriptValue>(
                        entity.Value,
                        StringComparer.Ordinal));
            }

            return new TevScriptRuntimeCheckpoint(
                snapshot.ProgramId,
                snapshot.SemanticHash,
                entities);
        }

        public string ToCanonicalJson()
        {
            var entities = new List<object>();

            foreach (KeyValuePair<
                         string,
                         IReadOnlyDictionary<string, TevScriptValue>>
                     entity in _entities.OrderBy(
                         item => item.Key,
                         StringComparer.Ordinal))
            {
                var state = new Dictionary<string, object>(
                    StringComparer.Ordinal);

                foreach (KeyValuePair<string, TevScriptValue> item
                         in entity.Value.OrderBy(
                             value => value.Key,
                             StringComparer.Ordinal))
                {
                    state.Add(
                        item.Key,
                        new Dictionary<string, object>(
                            StringComparer.Ordinal)
                        {
                            [ "type" ] = item.Value.TypeName,
                            [ "value" ] = item.Value.ToCanonicalObject()
                        });
                }

                entities.Add(
                    new Dictionary<string, object>(StringComparer.Ordinal)
                    {
                        [ "entity_id" ] = entity.Key,
                        [ "state" ] = state
                    });
            }

            var root = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                [ "schema" ] = Schema,
                [ "program_id" ] = ProgramId,
                [ "semantic_hash" ] = SemanticHash,
                [ "entities" ] = entities
            };

            return TevJson.Canonicalize(root);
        }

        public static TevScriptRuntimeCheckpoint Parse(string json)
        {
            if (json == null) throw new ArgumentNullException(nameof(json));

            object parsed = TevJson.Parse(json);
            string canonical = TevJson.Canonicalize(parsed);
            if (!string.Equals(json, canonical, StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_CHECKPOINT_CANONICAL",
                    "Runtime checkpoint must use exact canonical JSON.");
            }

            Dictionary<string, object> root =
                TevJson.RequireObject(parsed, "$");
            TevJson.RequireExactKeys(
                root,
                "$",
                "schema",
                "program_id",
                "semantic_hash",
                "entities");

            if (!string.Equals(
                    TevJson.RequireString(root, "schema"),
                    Schema,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_CHECKPOINT_SCHEMA",
                    "Unexpected runtime checkpoint schema.");
            }

            string programId =
                RequireIdentifier(
                    TevJson.RequireString(root, "program_id"),
                    "$.program_id");
            string semanticHash =
                RequireSha256(
                    TevJson.RequireString(root, "semantic_hash"),
                    "$.semantic_hash");

            List<object> rawEntities =
                TevJson.RequireArray(root, "entities");
            var entities = new Dictionary<
                string,
                IReadOnlyDictionary<string, TevScriptValue>>(
                    StringComparer.Ordinal);

            string previousEntityId = null;
            for (int entityIndex = 0;
                entityIndex < rawEntities.Count;
                entityIndex++)
            {
                string path = "$.entities[" + entityIndex + "]";
                Dictionary<string, object> rawEntity =
                    TevJson.RequireObject(rawEntities[entityIndex], path);
                TevJson.RequireExactKeys(
                    rawEntity,
                    path,
                    "entity_id",
                    "state");

                string entityId = RequireIdentifier(
                    TevJson.RequireString(rawEntity, "entity_id"),
                    path + ".entity_id");

                if (previousEntityId != null &&
                    string.CompareOrdinal(previousEntityId, entityId) >= 0)
                {
                    throw new TevContractException(
                        "TEVS_CS_CHECKPOINT_ENTITY_ORDER",
                        "Checkpoint entities must be strictly ordered.",
                        path + ".entity_id");
                }
                previousEntityId = entityId;

                Dictionary<string, object> rawState =
                    TevJson.RequireObject(rawEntity, "state");
                var state = new Dictionary<string, TevScriptValue>(
                    StringComparer.Ordinal);

                foreach (string stateName in rawState.Keys.OrderBy(
                             item => item,
                             StringComparer.Ordinal))
                {
                    RequireIdentifier(
                        stateName,
                        path + ".state." + stateName);

                    Dictionary<string, object> typed =
                        TevJson.RequireObject(
                            rawState[stateName],
                            path + ".state." + stateName);
                    TevJson.RequireExactKeys(
                        typed,
                        path + ".state." + stateName,
                        "type",
                        "value");

                    string typeName =
                        TevJson.RequireString(typed, "type");
                    state.Add(
                        stateName,
                        TevScriptValue.Decode(
                            typeName,
                            typed["value"]));
                }

                entities.Add(entityId, state);
            }

            return new TevScriptRuntimeCheckpoint(
                programId,
                semanticHash,
                entities);
        }

        public TevScriptRuntime RestoreExact(
            TevScriptProgram program,
            IEnumerable<ITevScriptCapability> capabilities = null)
        {
            if (program == null)
                throw new ArgumentNullException(nameof(program));

            ValidateExactProgram(program);

            var runtime = new TevScriptRuntime(program, capabilities);
            runtime.RestoreCompatibleSnapshot(ToSnapshot());
            return runtime;
        }

        private TevScriptRuntimeSnapshot ToSnapshot()
        {
            var entities = new Dictionary<
                string,
                IReadOnlyDictionary<string, TevScriptValue>>(
                    StringComparer.Ordinal);

            foreach (KeyValuePair<
                         string,
                         IReadOnlyDictionary<string, TevScriptValue>>
                     entity in _entities)
            {
                entities.Add(
                    entity.Key,
                    new Dictionary<string, TevScriptValue>(
                        entity.Value,
                        StringComparer.Ordinal));
            }

            return new TevScriptRuntimeSnapshot(
                ProgramId,
                SemanticHash,
                entities);
        }

        private void ValidateExactProgram(TevScriptProgram program)
        {
            if (!string.Equals(
                    ProgramId,
                    program.ProgramId,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_CHECKPOINT_PROGRAM_ID",
                    "Checkpoint program id does not match the runtime.");
            }

            if (!string.Equals(
                    SemanticHash,
                    program.SemanticHash,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_CHECKPOINT_SEMANTIC_HASH",
                    "Checkpoint semantic hash does not match the runtime.");
            }

            if (_entities.Count != program.Entities.Count)
            {
                throw new TevContractException(
                    "TEVS_CS_CHECKPOINT_ENTITY_SET",
                    "Checkpoint entity set does not exactly match the runtime.");
            }

            foreach (TevScriptEntityDefinition definition
                     in program.Entities)
            {
                IReadOnlyDictionary<string, TevScriptValue> state;
                if (!_entities.TryGetValue(
                        definition.EntityId,
                        out state))
                {
                    throw new TevContractException(
                        "TEVS_CS_CHECKPOINT_ENTITY_SET",
                        "Checkpoint is missing entity " +
                        definition.EntityId + ".");
                }

                if (state.Count != definition.States.Count)
                {
                    throw new TevContractException(
                        "TEVS_CS_CHECKPOINT_STATE_SET",
                        "Checkpoint state set does not exactly match entity " +
                        definition.EntityId + ".");
                }

                foreach (TevScriptStateDefinition stateDefinition
                         in definition.States)
                {
                    TevScriptValue value;
                    if (!state.TryGetValue(
                            stateDefinition.Name,
                            out value))
                    {
                        throw new TevContractException(
                            "TEVS_CS_CHECKPOINT_STATE_SET",
                            "Checkpoint is missing state " +
                            definition.EntityId + "." +
                            stateDefinition.Name + ".");
                    }

                    if (!string.Equals(
                            stateDefinition.TypeName,
                            value.TypeName,
                            StringComparison.Ordinal))
                    {
                        throw new TevContractException(
                            "TEVS_CS_CHECKPOINT_STATE_TYPE",
                            "Checkpoint state type mismatch for " +
                            definition.EntityId + "." +
                            stateDefinition.Name + ".");
                    }
                }
            }
        }

        private static string RequireSha256(string value, string path)
        {
            if (value == null || value.Length != 64)
            {
                throw new TevContractException(
                    "TEVS_CS_CHECKPOINT_SHA256",
                    "Expected lowercase SHA-256 hexadecimal.",
                    path);
            }

            for (int index = 0; index < value.Length; index++)
            {
                char c = value[index];
                if (!((c >= '0' && c <= '9') ||
                      (c >= 'a' && c <= 'f')))
                {
                    throw new TevContractException(
                        "TEVS_CS_CHECKPOINT_SHA256",
                        "Expected lowercase SHA-256 hexadecimal.",
                        path);
                }
            }

            return value;
        }

        private static string RequireIdentifier(
            string value,
            string path)
        {
            if (string.IsNullOrEmpty(value) ||
                !IsIdentifierStart(value[0]))
            {
                throw new TevContractException(
                    "TEVS_CS_CHECKPOINT_IDENTIFIER",
                    "Expected identifier.",
                    path);
            }

            for (int index = 1; index < value.Length; index++)
            {
                if (!IsIdentifierContinue(value[index]))
                {
                    throw new TevContractException(
                        "TEVS_CS_CHECKPOINT_IDENTIFIER",
                        "Expected identifier.",
                        path);
                }
            }

            return value;
        }

        private static bool IsIdentifierStart(char value)
        {
            return (value >= 'A' && value <= 'Z') ||
                (value >= 'a' && value <= 'z') ||
                value == '_';
        }

        private static bool IsIdentifierContinue(char value)
        {
            return IsIdentifierStart(value) ||
                (value >= '0' && value <= '9');
        }
    }
}
