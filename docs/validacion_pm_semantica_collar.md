# Validacion PM y Semantica de Identificacion

## Punto fijo

- La identidad observada en campo se corresponde con el `tag del collar Allflex`.
- Con lo que hay hoy, el motor no debe asumir que el `bolo` aparezca en la lectura del ordeño.
- Si en el futuro se obtiene un ejemplo de bolo, debe contrastarse como un dominio distinto y no mezclarse automaticamente con el `tag_allflex`.

## Archivos estructurados

- Registro de tags: [allflex_tag_registry.csv](/C:/Users/jorge/OneDrive/Documentos/FincaDiag_Modular/data/field_validation/allflex_tag_registry.csv)
- Validaciones PM: [pm_validations_2026_04_06_2026_04_09.csv](/C:/Users/jorge/OneDrive/Documentos/FincaDiag_Modular/data/field_validation/pm_validations_2026_04_06_2026_04_09.csv)

## Hallazgos de campo que impactan el motor

- La mayoria de lecturas buenas de identificacion ocurre muy rapido tras la entrada, normalmente `1 a 3 s`.
- Existen casos de lectura tardia por falla de fotocelda o por intervencion manual en la jaula/controlador.
- Existen casos donde el controlador mantiene la lectura aunque la vaca ya salio.
- El flujo visible puede ser `dudoso` aunque exista identificacion, por lo que `identificacion` y `flujo` no deben colapsarse en una sola señal.
- Las vacas con mastitis pueden agruparse al final del bloque y producir tandas operativas especiales.
- Aparecen eventos operativos del controlador (`CELO`, `E56`, `E59`) que conviene conservar como contexto y no descartar como ruido.

## Implicaciones para el motor

1. `E2` debe interpretarse provisionalmente como `identificacion de collar/tag`.
2. El lenguaje visible del sistema debe evitar presentar esa lectura como `bolo`.
3. Los casos con fotocelda fallida o lectura retenida deben quedar como categoria propia de validacion.
4. El dataset de campo debe usarse para contrastar:
   - `entrada -> identificacion`
   - `entrada -> salida`
   - identificacion rapida vs identificacion tardia
   - persistencia indebida del controller tras la salida
5. Si aparece un ejemplo real de bolo, debe abrirse una tabla aparte:
   - `bolo_code`
   - `tag_allflex`
   - `animal_number`
   - `source_channel`
   - `confidence`

## Observaciones de calidad de datos

- En la validacion del `2026-04-06 PM` aparece una fila duplicada de la vaca `758`; en el CSV estructurado se deduplico y se dejo nota.
- En la misma validacion aparece `636`, pero ese numero no figura en el registro Allflex entregado. Se preservo como `not_found` y se dejo la nota de posible typo.
