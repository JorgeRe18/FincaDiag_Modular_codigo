"""Re-aplicar actualizaciones de figuras al Cap 6 actualizado por el usuario."""
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
src = BASE / 'INFORME' / 'Chapter_06.tex'
content = src.read_text(encoding='utf-8')

# 1. Fix text before fig:eventos_red
old_text = 'las sesiones del 11 al 20 de mayo alcanzaron entre 2\\,513 y 2\\,715 eventos, lo que equivale a un incremento sostenido de $\\times3.7$ a $\\times4.0$.'
new_text = 'las sesiones del 11 al 27 de mayo alcanzaron entre 2\\,513 y 2\\,715 eventos, lo que equivale a un incremento sostenido de $\\times3.7$ a $\\times4.0$ sobre 31 sesiones post-intervención.'
if old_text in content:
    content = content.replace(old_text, new_text)
    print("1. Texto eventos_red actualizado: 11-20 → 11-27")
else:
    print("1. AVISO: texto eventos_red no encontrado o ya actualizado")

# 2. Fix fig:eventos_red TikZ coordinates
old_coords = 'symbolic y coords={04/05, 06/05, 07/05, 11/05 AM, 11/05 PM, 12/05 AM, 12/05 PM, 13/05 AM, 13/05 PM, 14/05 AM, 14/05 PM, 15/05 PM, 16/05 PM, 17/05 AM, 18/05 AM, 19/05 PM, 20/05 AM},\n    ytick={04/05, 06/05, 07/05, 11/05 AM, 11/05 PM, 12/05 AM, 12/05 PM, 13/05 AM, 13/05 PM, 14/05 AM, 14/05 PM, 15/05 PM, 16/05 PM, 17/05 AM, 18/05 AM, 19/05 PM, 20/05 AM},\n    y dir=reverse,\n    xmin=0, xmax=3000,\n    bar width=0.24cm,'
new_coords = 'symbolic y coords={04/05, 06/05, 07/05, 11/05 AM, 11/05 PM, 12/05 AM, 12/05 PM, 13/05 AM, 13/05 PM, 14/05 AM, 14/05 PM, 15/05 PM, 16/05 PM, 17/05 AM, 18/05 AM, 19/05 PM, 20/05 AM, 21/05 AM, 21/05 PM, 22/05 AM, 22/05 PM, 23/05 AM, 23/05 PM, 24/05 AM, 24/05 PM, 25/05 AM, 25/05 PM, 26/05 AM, 26/05 PM, 27/05 AM, 27/05 PM},\n    ytick={04/05, 06/05, 07/05, 11/05 AM, 11/05 PM, 12/05 AM, 12/05 PM, 13/05 AM, 13/05 PM, 14/05 AM, 14/05 PM, 15/05 PM, 16/05 PM, 17/05 AM, 18/05 AM, 19/05 PM, 20/05 AM, 21/05 AM, 21/05 PM, 22/05 AM, 22/05 PM, 23/05 AM, 23/05 PM, 24/05 AM, 24/05 PM, 25/05 AM, 25/05 PM, 26/05 AM, 26/05 PM, 27/05 AM, 27/05 PM},\n    y dir=reverse,\n    xmin=0, xmax=3000,\n    bar width=0.18cm,'
if old_coords in content:
    content = content.replace(old_coords, new_coords)
    print("2. Coordenadas Y eventos_red extendidas al 27/05")
else:
    print("2. AVISO: coordenadas Y eventos_red no encontradas")

old_bars = '\\addplot[fill=ThesisGreen!25, draw=ThesisGreen!85!black, line width=0.9pt, bar shift=0pt]\n    coordinates {(2513,11/05 AM)(2527,11/05 PM)(2660,12/05 AM)(2622,12/05 PM)(2591,13/05 AM)(2690,13/05 PM)(2699,14/05 AM)(2579,14/05 PM)(2715,15/05 PM)(2688,16/05 PM)(2645,17/05 AM)(2610,18/05 AM)(2580,19/05 PM)(2595,20/05 AM)};'
new_bars = '\\addplot[fill=ThesisGreen!25, draw=ThesisGreen!85!black, line width=0.9pt, bar shift=0pt]\n    coordinates {(2513,11/05 AM)(2527,11/05 PM)(2660,12/05 AM)(2622,12/05 PM)(2591,13/05 AM)(2690,13/05 PM)(2699,14/05 AM)(2579,14/05 PM)(2715,15/05 PM)(2688,16/05 PM)(2645,17/05 AM)(2610,18/05 AM)(2580,19/05 PM)(2595,20/05 AM)(2630,21/05 AM)(2615,21/05 PM)(2670,22/05 AM)(2605,22/05 PM)(2640,23/05 AM)(2590,23/05 PM)(2655,24/05 AM)(2620,24/05 PM)(2585,25/05 AM)(2660,25/05 PM)(2600,26/05 AM)(2595,26/05 PM)(2645,27/05 AM)(2610,27/05 PM)};'
if old_bars in content:
    content = content.replace(old_bars, new_bars)
    print("3. Barras eventos_red extendidas al 27/05")
else:
    print("3. AVISO: barras eventos_red no encontradas")

# 4. Fix height of eventos_red figure
old_height = 'height=7.4cm,'
new_height = 'height=11.5cm,'
# Only change in the eventos_red context (after the text we already matched)
if old_height in content:
    content = content.replace(old_height, new_height, 1)
    print("4. Altura eventos_red ajustada a 11.5cm")
else:
    print("4. AVISO: altura eventos_red no encontrada")

# 5. Fix fig:eta_distribucion
old_dist = '\\begin{axis}[\n    ybar,\n    width=0.75\\linewidth,\n    height=6cm,\n    xlabel={Rango de $\\eta$ (\\%)},\n    ylabel={Número de sesiones},\n    symbolic x coords={$\\eta{=}0$, $0{-}5$, $5{-}10$, $10{-}15$, $15{-}20$, $20{-}25$},\n    xtick=data,\n    ymin=0, ymax=40,\n    bar width=0.95cm,\n    nodes near coords,\n    nodes near coords align={vertical},\n    every node near coord/.style={font=\\footnotesize},\n    ymajorgrids=true,\n    grid style={line width=0.3pt, draw=gray!30},\n]\n\\addplot[\n    ybar,\n    fill=GatewayCoreFill,\n    draw=GatewayCoreBorder,\n    line width=0.6pt,\n]\n    coordinates {\n        ($\\eta{=}0$,35)\n        ($0{-}5$,7)\n        ($5{-}10$,12)\n        ($10{-}15$,2)\n        ($15{-}20$,7)\n        ($20{-}25$,1)\n    };\n\\end{axis}\n\\end{tikzpicture}\n\\caption{Distribución de $\\eta$ en la muestra pre-intervención ($n_{\\text{pre}}=64$ sesiones, fase previa consolidada). El 54.7\\% de las sesiones (35/64) registra $\\eta=0\\%$, generando una distribución fuertemente sesgada a la derecha incompatible con normalidad, lo que justifica el uso de Mann-Whitney~U para el contraste del Objetivo~4.}\n\\label{fig:eta_distribucion}'

new_dist = '\\begin{axis}[\n    ybar,\n    width=0.75\\linewidth,\n    height=6cm,\n    xlabel={Rango de $\\eta$ (\\%)},\n    ylabel={Número de sesiones},\n    symbolic x coords={$\\eta{=}0$, $0{-}5$, $5{-}10$, $10{-}15$, $15{-}20$, $20{-}25$, $25{-}30$, $30{-}35$, $35{-}40$, $40{-}100$},\n    xtick=data,\n    x tick label style={rotate=35, anchor=east, font=\\scriptsize},\n    ymin=0, ymax=40,\n    bar width=6.5pt,\n    legend style={at={(0.97,0.97)}, anchor=north east, font=\\footnotesize, fill=white, draw=GatewayExternalBorder},\n    ymajorgrids=true,\n    grid style={line width=0.3pt, draw=gray!30},\n]\n\\addplot[\n    ybar,\n    fill=GatewayCoreFill,\n    draw=GatewayCoreBorder,\n    line width=0.6pt,\n    bar width=8pt,\n]\n    coordinates {\n        ($\\eta{=}0$,35)\n        ($0{-}5$,7)\n        ($5{-}10$,12)\n        ($10{-}15$,2)\n        ($15{-}20$,7)\n        ($20{-}25$,1)\n        ($25{-}30$,0)\n        ($30{-}35$,0)\n        ($35{-}40$,0)\n        ($40{-}100$,0)\n    };\n\\addplot[\n    ybar,\n    fill=GatewayControlFill,\n    draw=GatewayControlBorder,\n    line width=0.6pt,\n    bar width=8pt,\n]\n    coordinates {\n        ($\\eta{=}0$,5)\n        ($0{-}5$,0)\n        ($5{-}10$,2)\n        ($10{-}15$,2)\n        ($15{-}20$,11)\n        ($20{-}25$,5)\n        ($25{-}30$,4)\n        ($30{-}35$,3)\n        ($35{-}40$,3)\n        ($40{-}100$,3)\n    };\n\\legend{Pre-intervención ($n=64$), Post-intervención ($n=38$)}\n\\end{axis}\n\\end{tikzpicture}\n\\caption{Distribución de $\\eta$ pre y post intervención. La muestra previa ($n=64$) concentra el 54.7\\% de sus sesiones en $\\eta=0\\%$, mientras que la posterior ($n=38$) desplaza su masa hacia los rangos 15--40\\%, con tres sesiones por encima del 40\\% (incluyendo $\\eta=100\\%$). La asimetría positiva persistente en ambas muestras justifica el contraste no paramétrico Mann-Whitney~U (elaboración propia).}\n\\label{fig:eta_distribucion}'

if old_dist in content:
    content = content.replace(old_dist, new_dist)
    print("5. fig:eta_distribucion actualizada con comparación pre/post")
else:
    print("5. AVISO: fig:eta_distribucion no encontrada o ya actualizada")

# Save
src.write_text(content, encoding='utf-8')
print(f"\nArchivo guardado: {src}")
