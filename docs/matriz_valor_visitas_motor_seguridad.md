# Matriz de Valor de Visitas y Estado del Motor

## Criterio

La valoracion se separa en dos ejes:

- `valor operativo`: que tan util es la visita para reconstruir tandas, tiempos de ordeño, identificacion del tag Allflex y eventos de vaca.
- `valor de seguridad`: que tan util es la visita para documentar exposicion de red, cadena de custodia, activos de LAN y evidencia forense.

Escala usada:

- `muy alto`
- `alto`
- `medio`
- `bajo`

El `nivel de confianza` no describe la calidad del sistema, sino la confianza actual para usar esa visita como evidencia dentro del proyecto.

## Matriz recomendada

| Visita | Valor operativo | Valor de seguridad | Nivel de confianza | Uso recomendado |
|---|---|---|---|---|
| `Visita_06_04_2026` PM | muy alto | alto | muy alto | visita maestra para calibrar el motor con validacion de campo completa |
| `Visita_09_04_2026` PM | muy alto | alto | alto | contraste de casos problematicos: fotocelda, controller retenido, evento CELO |
| `Visita_05_04_2026` AM | alto | alto | medio | descubrir cadencia, concurrencia y tandas operativas con captura simultanea real |
| `Visita_05_04_2026` PM | alto | alto | medio | contraste de ordeño completo con estructura menos fragmentada que `05/04 AM` |
| `Visita_03_04_2026` | alto | medio | medio | exploracion historica del protocolo serial y de la mezcla de canales |
| `Visita_04_04_2026` | medio | alto | alto | anomalia de baseline/red y soporte para impacto de entorno sobre la medicion |
| `Visita_31_03_2026` | medio | alto | alto | evidencia de degradacion de red y alertas de baseline |
| `Visita_01_04_2026` | medio | medio | alto | visita patron para comparar contra dias ruidosos o anomalias |
| `Visita_02_04_2026` | alto | medio | medio | variantes raras del serial y modos distintos del protocolo |
| `Visitas 20/03 a 30/03` | medio | medio | medio | comparacion longitudinal y estabilidad del baseline/red |
| `Visitas tempranas de febrero e inicios de marzo` | medio | bajo | medio | descubrimiento inicial del serial y fase exploratoria del proyecto |

## Lectura practica

### 1. Visitas principales para el motor

- `Visita_06_04_2026` PM es hoy la referencia principal.
  - Tiene validacion de campo estructurada.
  - La captura cubre el ordeño observado en campo.
  - El motor reconstruyo `18` eventos frente a `19` vacas observadas dentro de ventana.
  - Sirve para ajustar `C2`, `E2`, `C3`, `E0`, lectura rapida del tag y duracion por vaca.

- `Visita_09_04_2026` PM es la segunda referencia principal.
  - Tambien tiene validacion de campo.
  - La captura cubre solo una parte del ordeño validado, lo cual es util para no sobreinterpretar.
  - Sirve para probar comportamiento bajo fotocelda fallida, intervencion del controller y lectura retenida.

- `Visita_05_04_2026` AM y PM son el mejor puente entre captura y modelado.
  - Son las primeras sesiones con `serial + antena_udp + pcap + pcap_6001 + manifest`.
  - Son muy valiosas para estructura temporal, pero todavia no tienen la misma fuerza que `06/04` y `09/04` porque no hubo validacion presencial equivalente.

### 2. Visitas principales para seguridad

- `Visita_04_04_2026` y `Visita_31_03_2026` son las mejores para justificar impacto de la red.
  - Tienen degradacion visible en baseline.
  - Son buenas para hablar de perdida, jitter y condicion de la LAN durante la medicion.

- `Visita_05_04_2026`, `Visita_06_04_2026` y `Visita_09_04_2026` son las mejores para seguridad aplicada al TFG.
  - Ya usan el esquema de captura combinado.
  - Permiten pensar de verdad en cadena de custodia serial-red.
  - Son las mejores candidatas para los cuatro numeros ejecutivos del resumen de seguridad.

## Valoracion del motor hasta ahora

## Lo que ya esta fuerte

- El motor ya no trata el serial como flujo uniforme.
- Distingue `ordeno_completo` de `telemetria_collar`.
- Reconstuye frames, muestras de flujo, eventos de vaca, tandas crudas y tandas operativas.
- Usa una heuristica de preparacion temporal y una cadencia observada cercana a `127 s`.
- Ya incorpora validacion de campo real por sesion.
- La identidad visible del sistema ya se modela correctamente como `tag Allflex del collar`, no como bolo.

## Lo que sigue siendo heuristico

- La semantica exacta de `C2 / E2 / C3 / E0` todavia es inferida.
- La asignacion de `E4` por vaca sigue siendo la parte mas debil por concurrencia de `6` jaulas.
- La lectura de `tag Allflex` no se decodifica aun directamente desde el canal; por ahora se contrasta temporalmente con campo.
- La deteccion de tandas operativas funciona mejor en visitas recientes y peor en datasets historicos ruidosos.

## Lo que hoy no esta cerrado

- La cadena de custodia completa serial-red-servidor.
- El inventario fiable de activos de LAN por visita.
- La confirmacion fuerte de descarte silencioso con evidencia de PCAP procesado.
- La atribucion individual de flujo E4 por jaula.

## Juicio tecnico actual

- Como `motor operativo`, el sistema ya es util y defendible.
- Como `motor de investigacion`, ya produce evidencia valiosa y trazable.
- Como `motor de seguridad completo`, todavia esta en etapa intermedia: la arquitectura conceptual es correcta, pero el cierre depende del analisis de PCAP y de la correlacion serial-red.

## Encaje con la lectura de seguridad del TFG

La hipotesis de fondo sigue siendo solida: el entorno observado opera, en la practica, sin controles visibles equivalentes a `SL-1`, con exposicion de telemetria en claro y sin autenticacion observable en la capa capturada.

Con los datos actuales, el motor ya puede sostener bien:

- exposicion del trafico biotico en claro
- separacion entre telemetria de collar y ordeño completo
- presencia de fallos operativos de identificacion
- necesidad de una pasarela perimetral que aporte aislamiento y trazabilidad

Lo que conviene formular todavia como objetivo en curso y no como cierre total:

- deteccion concluyente de inyeccion activa
- atribucion causal de bytes anomalos como perturbacion maliciosa
- no repudio completo evento fisico -> serial -> red -> servidor

## Recomendacion de uso en el TFG

### Nucleo del capitulo operativo

- `Visita_06_04_2026` PM
- `Visita_09_04_2026` PM
- `Visita_05_04_2026` AM/PM

### Soporte del capitulo de seguridad

- `Visita_04_04_2026`
- `Visita_31_03_2026`
- `Visita_05_04_2026`
- `Visita_06_04_2026`
- `Visita_09_04_2026`

### Soporte historico / descubrimiento de protocolo

- `Visita_03_04_2026`
- `Visita_02_04_2026`
- `Visita_01_04_2026`

## Siguiente paso recomendado

1. Usar `06/04 PM` como patron para recalibrar `C2/E2/C3/E0`.
2. Usar `09/04 PM` como banco de prueba para errores de fotocelda y controller.
3. Rehabilitar el parseo de PCAP para cerrar la capa de seguridad.
4. A partir de ahi, emitir los cuatro numeros ejecutivos del resumen de seguridad:
   - porcentaje de trafico biotico en claro
   - numero de dispositivos no identificados en LAN
   - eventos de vaca sin confirmacion en red
   - tiempo promedio de exposicion de datos de salud animal
