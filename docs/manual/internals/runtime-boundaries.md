# Fronteras del runtime

El runtime V5 Total recibe un `TotalCoreProgramV1` validado y un checkpoint válido. Cada quantum ejecuta como máximo `quantum_step_limit`, acumula receipts V4/Apply y termina `HALTED` o `SUSPENDED`.

`invoke_v4` selecciona una unidad por `unit_hash`, ejecuta su runtime V4 según perfil y proyecta el recibo mediante una transformación puente. `effects` puede producir transcript/transition receipts; el commit físico sigue en el proveedor.

La reanudación valida programa, PC, epoch, continuación, Field y estado halted antes de avanzar.