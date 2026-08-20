# Field, Transformation y Apply

`Field` es un conjunto semántico canónico de hechos. `Transformation` describe eliminaciones/adiciones, precondición `required_before_hash`, perfil de resultado, efectos/recursos y requisitos de prueba. `Apply` valida la transformación contra el Field y produce Field sucesor + recibo.

Estos objetos son la base semántica reutilizada por Total-Core. La instrucción `apply` referencia una transformación por hash; `branch_fact` consulta un hecho por hash. Una `invoke_v4` ejecuta la unidad y construye una transformación puente derivada que añade el recibo como hecho.

Si una Transformation tiene `proof_requirement_hashes`, el programa debe contener admisiones verificadas exactas. El runtime crea una derivada local sin requisitos sólo después de validar esas admisiones; la transformación canónica original no se muta.

Autoridad: `spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md`, `tev_script/runtime_v5_total.py`.