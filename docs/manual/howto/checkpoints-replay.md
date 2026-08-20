# HOWTO — Checkpoint, reanudación y replay

Crea el checkpoint inicial desde el programa validado. Ejecuta un quantum; persiste el `next_checkpoint` canónico y su continuación. Para reanudar, carga el mismo Program IR y valida el checkpoint antes de ejecutar.

Un replay reproducible conserva: `program_hash`, Field/hash, PC, epoch, continuación previa, hashes de observaciones/efectos/recursos y política de host necesaria para reproducir los inputs externos.

Un checkpoint de otro programa, con epoch inconsistente o marcado `halted` cuando el PC no es `halt`, debe fallar cerrado.