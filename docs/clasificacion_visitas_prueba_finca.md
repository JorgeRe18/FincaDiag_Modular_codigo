# Clasificacion de visitas - Prueba_Finca

Este documento resume, a nivel practico, para que sirve cada visita del arbol
`C:\PROYECTO_TFG\Prueba_Finca`.

La clasificacion no intenta decir si una visita es "buena" o "mala" en
terminos absolutos. La idea es indicar el uso principal de cada una dentro del
proyecto:

- descubrimiento de protocolo serial
- transicion operativa
- analisis de red maduro
- referencia estructural o baseline
- ajuste del motor operativo nuevo

## Leyenda

- `Exploratoria`: util para entender patrones, pero no ideal para correlacion fuerte.
- `Transicion`: mezcla de artefactos o cobertura parcial, util para robustez.
- `Madura`: visita apta para analisis fuerte de red y comparacion entre sesiones.
- `Referencia`: util como patron, control o baseline.

## Matriz

| Visita | Capturas | Baselines | Serial | Antena | PCAP | Grupo | Uso principal | Prioridad | Comentario |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| `Visita_23_02_2026` | 0 | 1 | 0 | 0 | 0 | Referencia | baseline puro | Media | Sirve como referencia temprana de contexto, sin valor para correlacion serial-red. |
| `Visita_25_02_2026` | 6 | 4 | 3 | 0 | 0 | Exploratoria | descubrimiento serial temprano | Alta | Buena para estudiar estructura inicial del serial y primeros patrones de fragmentacion. |
| `Visita_03_03_2026` | 2 | 1 | 1 | 0 | 0 | Exploratoria | arranque de parser serial | Media | Visita corta, util para pruebas rapidas de parseo y normalizacion. |
| `Visita_05_03_2026` | 6 | 2 | 4 | 0 | 0 | Exploratoria | descubrimiento de protocolo serial | Alta | Aporta varios registros seriales sin interferencia de PCAP, utiles para semantica del bus. |
| `Visita_09_03_2026` | 4 | 2 | 2 | 0 | 0 | Exploratoria | patron serial temprano | Media | Util para comparar continuidad y consistencia de marcadores entre sesiones. |
| `Visita_11_03_2026` | 6 | 3 | 3 | 0 | 0 | Exploratoria | descubrimiento serial | Alta | Buena para ver repeticion de patrones y variantes del bus en etapa temprana. |
| `Visita_12_03_2026` | 2 | 3 | 1 | 0 | 0 | Exploratoria | apoyo a parser y baseline | Media | Mezcla corta de baseline con algo de serial; aporta poco para correlacion pero si para consistencia. |
| `Visita_13_03_2026` | 2 | 1 | 0 | 0 | 0 | Referencia | estructura minima | Baja | Sirve mas como contexto de organizacion del arbol que como evidencia fuerte de protocolo. |
| `Visita_14_03_2026` | 3 | 2 | 0 | 1 | 0 | Transicion | aparicion de canal antena | Media | Marca transicion hacia capturas con evidencia de antena, aunque aun sin PCAP. |
| `Visita_16_03_2026` | 6 | 3 | 1 | 3 | 0 | Transicion | mezcla serial-antena | Alta | Buena para ver convivencia parcial de canales antes de la fase madura con red. |
| `Visita_18_03_2026` | 7 | 5 | 2 | 2 | 0 | Transicion | robustez de parser con mezcla parcial | Alta | Util para probar el motor con sesiones heterogeneas y cobertura incompleta. |
| `Visita_19_03_2026` | 5 | 3 | 1 | 2 | 0 | Transicion | continuidad operativa | Media | Aporta una transicion previa al ingreso de PCAP como artefacto habitual. |
| `Visita_20_03_2026` | 10 | 10 | 1 | 5 | 10 | Madura | inicio de fase de red madura | Alta | Primera visita claramente util para baseline, antena, PCAP y comparacion longitudinal. |
| `Visita_21_03_2026` | 15 | 12 | 1 | 6 | 15 | Madura | comparacion de cobertura | Alta | Buena para revisar consistencia estructural de sesiones con PCAP. |
| `Visita_22_03_2026` | 16 | 16 | 0 | 8 | 16 | Referencia | patron de red sin serial | Media | Muy util como referencia de red y de canal antena cuando no hay serial que complique la lectura. |
| `Visita_23_03_2026` | 17 | 16 | 1 | 9 | 17 | Madura | comparacion longitudinal | Alta | Buena como visita de rutina dentro de la etapa madura del esquema de captura. |
| `Visita_24_03_2026` | 16 | 16 | 0 | 8 | 16 | Referencia | patron de red sin serial | Media | Similar a 22/03, sirve como control de entorno y telemetria de antena. |
| `Visita_25_03_2026` | 17 | 16 | 1 | 8 | 16 | Madura | seguimiento longitudinal | Alta | Buena para comparar estabilidad operativa con dias vecinos. |
| `Visita_26_03_2026` | 18 | 17 | 1 | 8 | 18 | Madura | seguimiento longitudinal | Alta | Muestra estructura consolidada y sirve para comparaciones entre visitas maduras. |
| `Visita_27_03_2026` | 16 | 15 | 1 | 8 | 16 | Madura | visita rutinaria de comparacion | Alta | Util para dashboard, metricas globales y lectura por visita. |
| `Visita_28_03_2026` | 17 | 16 | 1 | 9 | 17 | Madura | comparacion de red y antena | Alta | Buena cobertura de red, util para comparar talkers, firma 56 D1 00 y regularidad de antena. |
| `Visita_29_03_2026` | 17 | 16 | 1 | 8 | 17 | Madura | referencia semanal | Alta | Buen punto de arranque para lectura global del lote semanal. |
| `Visita_30_03_2026` | 17 | 16 | 1 | 8 | 17 | Madura | robustez del parser serial | Alta | Interesa por huecos largos y por su utilidad para medir continuidad y cobertura. |
| `Visita_31_03_2026` | 22 | 18 | 4 | 8 | 22 | Madura | incidencia de red y casos ricos | Muy alta | Visita muy valiosa: mas serial que el promedio y baseline con perdida notable en una ventana. |
| `Visita_01_04_2026` | 17 | 16 | 1 | 8 | 17 | Referencia | visita patron | Muy alta | La mas ordenada de la fase madura; ideal como ejemplo de estructura normal. |
| `Visita_02_04_2026` | 18 | 15 | 3 | 8 | 18 | Madura | variantes raras del serial | Muy alta | Muy util para descubrir modos distintos del bus y refinar clasificacion. |
| `Visita_03_04_2026` | 16 | 16 | 2 | 8 | 16 | Madura | mejor visita para eventos de vaca | Muy alta | Es la visita mas valiosa para afinar el motor operativo nuevo. |
| `Visita_04_04_2026` | 14 | 14 | 2 | 7 | 14 | Madura | validacion mixta operativa y red | Muy alta | Combina serial util con una anomalia clara de baseline; excelente para casos mixtos. |

## Resumen ejecutivo

- `Febrero e inicios de marzo`: fase exploratoria del serial.
- `Mitad de marzo`: fase de transicion, util para robustez y mezcla parcial de artefactos.
- `Desde 20 de marzo de 2026`: fase madura de captura con valor fuerte para analisis de red.
- `Mejor visita patron`: `Visita_01_04_2026`.
- `Mejor visita para afinar eventos de vaca`: `Visita_03_04_2026`.
- `Mejor visita para variantes del protocolo serial`: `Visita_02_04_2026`.
- `Mejor visita para anomalias mixtas de red + operacion`: `Visita_04_04_2026`.
- `Visita mas rica para incidencia y seguimiento`: `Visita_31_03_2026`.

## Recomendacion de uso en el proyecto

1. Usar `03/04` y `02/04` para afinar el parser y la maquina de estados de vaca.
2. Usar `01/04` como ejemplo de visita regular o patron.
3. Usar `31/03` y `04/04` para documentar degradacion de red y su impacto analitico.
4. Usar `20/03` a `30/03` para comparacion longitudinal y consolidado global.
