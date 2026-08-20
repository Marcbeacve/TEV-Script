# Control, recursión y cotas

TEVScript distingue control local de unidad y control del proceso. Las funciones recursivas V2 son **INHERITED_COMPATIBILITY** y deben satisfacer sus contratos de descenso/cota. El proceso semántico dispone de labels e instrucciones `apply`, `branch_fact`, `jump` y `halt` heredadas de V3.

Total-Core añade `invoke_v4` y conserva un `quantum_step_limit`. Un programa V5 Total-Core admite entre 1 y 65.536 instrucciones y un límite de quantum entre 1 y 1.000.000 pasos. La computación abierta se representa como sucesión de quanta finitos ligados por continuaciones.

Una cota de quantum no es una prueba de terminación global; es una garantía de que cada tramo ejecutable es finito y reanudable.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, `tev_script/program_ir_v5_total.py`.