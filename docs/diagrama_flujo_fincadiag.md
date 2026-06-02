# Flujo actualizado de FincaDiag

## Motor de analisis para Objetivo 1

```mermaid
flowchart TD
    A["Descubrimiento por visita"] --> B["Clasificacion de sesion\nBaseline / Collares / Ordeno"]
    B --> C["Parseo baseline"]
    B --> D["Parseo serial"]
    B --> E["Parseo antena UDP"]
    B --> F["Parseo PCAP"]
    D --> G["Demultiplexado y reconstruccion"]
    G --> H["Eventos de vaca y tandas"]
    E --> I["Telemetria de collar"]
    F --> J["Exposicion de red y evidencia PCAP"]
    H --> K["Correlacion y alertas"]
    I --> K
    J --> K
    C --> L["Linea base de red"]
    K --> M["Resumen por sesion"]
    L --> M
    M --> N["Resumen por visita"]
    N --> O["Resumen global"]
    O --> P["Perfiles por fase de Obj. 1"]
    P --> Q["Readiness para gateway"]
```

## Criterio metodologico

- `23/02/2026` a `13/03/2026`: linea base temprana de latencia, jitter y firmas iniciales.
- `14/03/2026` a `31/03/2026`: maduracion de red y mayor cobertura PCAP.
- `01/04/2026` a `05/04/2026`: captura madura para el motor operativo.
- `06/04/2026` a `09/04/2026`: contraste validado con campo.

## Salida esperada

- El motor no reemplaza el gateway.
- El motor entrega la linea base, las reglas de separacion por dominio y los criterios de seguridad para Obj. 3.
