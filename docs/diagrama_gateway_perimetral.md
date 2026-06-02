# Esqueleto del gateway perimetral

## Flujo de referencia

```mermaid
flowchart TD
    A["Sesion procesada / captura viva"] --> B["Clasificador de dominio\nOrdeno / Collar / Baseline"]
    B --> C["Politica allowlist\nIP / puerto / protocolo"]
    C --> D["Normalizador JSON"]
    D --> E["Cola store-and-forward\nJSONL spool"]
    E --> F["Publicador MQTT"]
    F --> G["Broker Mosquitto con TLS"]
    G --> H["Consumidor local / dashboard / export"]
    C --> I["Alertas y evidencia forense"]
    D --> I
    E --> I
```

## Componentes creados

- `src/fincadiag/gateway/config.py`
- `src/fincadiag/gateway/policy.py`
- `src/fincadiag/gateway/normalizer.py`
- `src/fincadiag/gateway/store.py`
- `src/fincadiag/gateway/publisher.py`
- `src/fincadiag/gateway/runtime.py`

## Alcance de esta iteracion

- Ya existe normalizacion de eventos a topicos MQTT.
- Ya existe cola local para `store-and-forward`.
- Ya existe politica base de allowlist para el dominio biotico.
- Ya existe modo `dry-run` para validar el pipeline sin tocar produccion.

## Lo que aun falta para cerrar Obj. 3

- endurecer TLS 1.3 en despliegue real del broker
- validar publicacion sobre captura viva
- congelar el esquema JSON final por dominio
- contrastar `eta`, `PLR` y `MTTR` contra la linea base de Obj. 1
