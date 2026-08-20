# HOWTO — Proyecto con varias unidades

Declara cada unidad una vez en el proceso y suministra exactamente una fuente por nombre. Los perfiles pueden mezclarse: `pure`, `recursive` y `effects` son fronteras diferentes dentro del mismo Total-Core.

Orden recomendado: estabiliza cada unidad de forma aislada; declara `unit`; enlaza con `invoke_v4`; elige una relación de resultado estable; comprueba que cada target label exista; compila el conjunto. La tabla final se ordena canónicamente, por lo que el orden del mapping del host no debe usarse como semántica.

Véase `tutorial/15-complete-application.md`.