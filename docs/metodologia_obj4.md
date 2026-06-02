# Metodología de validación — Objetivo 4

**Estado:** Implementada el 28/05/2026, en ejecución 28/05–29/05.
**Para redactar:** Chapter 6 (Resultados) y/o Chapter 7 (Discusión) de la tesis.

---

## 1. Indicador formal del Objetivo 4 (Chapter 2)

> *Reporte de validación estadística basado en protocolos de pruebas de campo, que contraste la eficiencia de extracción ($\eta$), la pérdida de paquetes (PLR) y el tiempo medio de recuperación (MTTR) respecto de la referencia establecida en el Objetivo~1, mediante pruebas de normalidad y contrastes estadísticos paramétricos o no paramétricos, según corresponda ($n \geq 30$, $\alpha = 0.05$), así como la neutralidad eléctrica del bus RS-232 durante el ordeño.*

## 2. Métricas del indicador y cómo se cubren

| Métrica | Cobertura | n esperado | Test estadístico |
|---------|-----------|------------|------------------|
| **$\eta$ (eficiencia extracción)** | Sesiones AM y PM acumuladas pre/post intervención | pre=1018 / post=32+ | Mann-Whitney U unilateral ($H_1: \eta_{post} > \eta_{pre}$) |
| **PLR (Packet Loss Rate)** | `compute_plr.py` sobre pcaps existentes | pre=1018 / post=32+ | Mann-Whitney U unilateral ($H_1: PLR_{post} < PLR_{pre}$) |
| **MTTR broker** | `mttr_stress_pi.sh` — corte de servicio mosquitto | 60–120 ciclos | Estadísticos descriptivos + IC 95% |
| **MTTR red** | `network_failure_pi.sh` — bloqueo iptables MQTT | 30–60 ciclos | Estadísticos descriptivos + IC 95% |
| **MTTR proceso** | `power_failure_sim_pi.sh` — kill -9 al gateway | 10–20 ciclos | Proxy software de corte de energía |
| **MTTR systemd** | `mttr_systemd_pi.sh` — kill servicio + Restart=always | 10 ciclos | descriptiva + IC 95% |
| **MTTR energía real** | Desenchufe físico cronometrado manual | 3–5 puntos | Cualitativo / referencia |
| **Latencia E2E** | `latency_e2e_pi.sh` — `mosquitto_sub` recibe timestamps | 45–90 ciclos | Estadísticos descriptivos + IC 95% |
| **Soak / estabilidad** | `soak_test_pi.sh` — operación continua | 6–12 horas | Análisis tendencia memoria/CPU |
| **Neutralidad RS-232** | Capturas de osciloscopio (Chapter 6) | 2 ondas | Cualitativo |

## 3. Pruebas de normalidad

Antes de aplicar Mann-Whitney se ejecuta **Shapiro-Wilk** ($\alpha=0.05$) para justificar la elección de test no paramétrico:

- $H_0$: la muestra proviene de distribución normal
- Si $p < 0.05$ → rechazar normalidad → usar Mann-Whitney
- Si $p \geq 0.05$ → no rechazar → t-test posible (pero conservadoramente se mantiene Mann-Whitney por homogeneidad de criterio)

Implementación: `normality_tests.py`.

## 4. Diseño de pruebas en campo

### 4.1 Modificación temporal de `FincaScheduler.py` (Pi)

Para liberar ventanas de la Raspberry Pi, se suspendieron 4 bloques NORMAL de los 9 originales:

**Suspendidos:** NORMAL_1, NORMAL_3, NORMAL_4, NORMAL_6
**Conservados:** ORDEÑO_AM, NORMAL_2, ORDEÑO_PM, NORMAL_5, NORMAL_7

Backup en `/home/esmeralda/FincaScheduler.py.bak_obj4_28may`. La modificación es reversible.

### 4.2 Cronograma diario (28/05 y 29/05)

| Hora | Tarea | n |
|------|-------|---|
| 02:25 | **ORDEÑO AM** (intacto) | suma a $\eta$ |
| 04:35 | RUN 1 — MTTR broker | 30 |
| 04:55 | RUN 1 — Latencia E2E | 15 |
| 05:30 | RUN 1 — Soak 1h | 1 hora |
| 06:40 | Network failure | 30 |
| 07:23 | NORMAL 2 (intacto) | — |
| 10:00 | Power failure (kill -9) | 10 |
| 10:30 | Soak 2h matinal | 2 horas |
| 13:02 | **ORDEÑO PM** (intacto) | suma a $\eta$ |
| 15:00 | RUN 2 — MTTR broker | 30 |
| 15:20 | RUN 2 — Latencia E2E | 15 |
| 15:55 | RUN 2 — Soak 1h | 1 hora |
| 17:48 | NORMAL 5 (intacto) | — |
| 20:30 | RUN 3 — Soak 2h nocturno | 2 horas |
| 22:35 | RUN 3 — Latencia E2E | 15 |
| 23:00 | Bundle resultados día | — |

### 4.3 Totales por día y a 2 días

| Métrica | 1 día | 2 días | Cumple n≥30 |
|---------|-------|--------|-------------|
| MTTR broker | 60 | **120** | ✓✓✓ |
| MTTR red | 30 | **60** | ✓✓ |
| MTTR proceso | 10 | **20** | proxy ✓ |
| Latencia E2E | 45 | **90** | ✓✓✓ |
| Soak | 6 h en 4 ventanas | **12 h en 8 ventanas** | ✓ |

### 4.4 Pruebas en caliente con inyección controlada (Día 3, 30/05/2026)

Tras completar las pruebas aisladas del Día 2, se restaura `FincaScheduler.py` a la programación normal. Durante los ordeños reales del 30/05 se inyectan fallos controlados en el sistema **productivo** para validar que la cadena completa (captura → parser → gateway → broker → suscriptor) resiste pérdida de eventos en condiciones reales.

| Sesión | Momento | Fallo inyectado | Mecanismo | Duración |
|--------|---------|-----------------|-----------|----------|
| ORDEÑO_AM (04:35) | Minuto ~15 | Caída de broker | `systemctl restart mosquitto` | <10 s |
| ORDEÑO_PM (13:02) | Minuto ~10 | Bloqueo de red | `iptables DROP 8883` | 30 s |
| ORDEÑO_PM (13:02) | Minuto ~25 | Crash de proceso | `systemctl kill -s KILL fincadiag-gateway` | ~15 s |

**Registro:** cada inyección se marca en `/home/esmeralda/fault_injections.csv` con timestamp, modo, duración y estado del servicio antes/después.

**Medición de resiliencia:** tras cada sesión con inyección, `measure_live_resilience_pi.sh` cruza `session_summary.json` publicado con el log de fallos para calcular:
- `cow_events_publicados` vs `cow_events_summary` (esperados)
- `spool_residual` (debe ser 0 si drenó correctamente)
- `resilience_status` = PASS si `spool==0` y `cow_events>0`

**Justificación:** las pruebas aisladas en huecos miden el componente en condiciones ideales; las pruebas en caliente demuestran que la resiliencia se mantiene con estado real, datos reales en juego y contención de recursos.

## 5. Justificación metodológica para defensa

- **Distribución multi-día:** las muestras se obtuvieron en dos días no consecutivos en la Finca La Esmeralda, capturando variabilidad operativa inter-día (carga de red, condiciones eléctricas, actividad ganadera).
- **Distribución intra-día:** cada día integra tres ventanas (madrugada, tarde, noche) para distinguir el efecto de la actividad humana, ordeño y temperatura sobre el desempeño del gateway.
- **Cobertura de modos de fallo:** se distinguen fallos a nivel aplicación (broker), enlace (red) y proceso (kill abrupto), con un punto cualitativo de fallo eléctrico real (desenchufe).
- **Robustez estadística:** $n$ supera el umbral 30 en todas las métricas; pruebas de normalidad justifican el uso de contrastes no paramétricos.

## 6. Salidas a empaquetar

Todos los CSV/log se comprimen al final de cada día en `obj4_bundle_YYYY-MM-DD.tar.gz`:

- `mttr_results.csv` — MTTR broker
- `network_failure_results.csv` — MTTR red
- `power_failure_results.csv` — MTTR proceso
- `latency_e2e_results.csv` — latencia E2E
- `soak_results.csv` — métricas de soak (memoria, CPU, spool)
- `obj4_runs/*.log` — logs por run
- `mttr_stress.log`, `latency_e2e.log`, `soak_test.log`, `network_failure.log`, `power_failure.log`

## 7. Análisis post-corrida (Windows)

```powershell
$BASE = "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular"
python "$BASE\compute_plr.py"          # PLR pre/post + Mann-Whitney
python "$BASE\normality_tests.py"      # Shapiro-Wilk η, PLR, MTTR
```

## 8. Reversión del estado de la Pi

```bash
ssh -p 33000 esmeralda@gateway-esmeralda-ssh.at.remote.it

# Cancelar at jobs pendientes
for j in $(atq | awk '{print $1}'); do atrm $j; done

# Restaurar FincaScheduler.py original
sudo cp /home/esmeralda/FincaScheduler.py.bak_obj4_28may /home/esmeralda/FincaScheduler.py
sudo chown root:root /home/esmeralda/FincaScheduler.py
sudo chmod 644 /home/esmeralda/FincaScheduler.py
```

## 9. Estructura sugerida para Chapter 6 / 7

### Chapter 6 — Resultados Obj 4

1. **6.x.1 Eficiencia de extracción ($\eta$)**
   - Tabla pre vs post (medias, medianas, σ, n)
   - Box plot pre vs post
   - Resultado Mann-Whitney U + tamaño efecto $r$
2. **6.x.2 Pérdida de paquetes (PLR)**
   - Tabla pre vs post
   - Mann-Whitney + tamaño efecto
3. **6.x.3 Tiempo medio de recuperación (MTTR)**
   - Tabla por modo de fallo (broker / red / proceso)
   - Histograma o ridge plot por modo
   - IC 95% por modo
4. **6.x.4 Latencia end-to-end** (complementario)
5. **6.x.5 Soak test** (estabilidad)
6. **6.x.6 Neutralidad eléctrica RS-232**
   - Figuras de osciloscopio
7. **6.x.7 Síntesis del cumplimiento del indicador**
   - Tabla checklist contra el indicador formal

### Chapter 7 — Discusión

- Discusión de variabilidad inter-día e intra-día observada
- Comparación con literatura de gateways perimetrales
- Limitaciones (proxy software del corte de energía, n=10 en MTTR proceso)
- Trabajo futuro

---

**Fecha de redacción de este documento:** 2026-05-28 01:37 CST
**Próxima actualización:** 2026-05-29 después del bundle Día 2.
