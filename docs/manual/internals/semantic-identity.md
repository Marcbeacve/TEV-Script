# Identidad semántica y canónica

TEVScript distingue identidad de fuente, identidad de IR, identidad de unidad, identidad de programa, estado y recibo. Los hashes se calculan sobre estructuras canónicas, no sobre direcciones de objetos ni orden incidental del host.

En 3.1, `source_semantic_hash` combina semántica V3, semánticas de unidades y tabla de `invoke_v4`. `program_hash` cubre el programa V5 construido. Un checkpoint añade `program_hash`, Field, PC, epoch/continuación y `checkpoint_hash`.

La igualdad de hash sólo tiene la autoridad del esquema/validador que lo define; no sustituye una prueba externa.