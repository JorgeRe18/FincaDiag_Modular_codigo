"""Generar figuras Cap 6 con datos EXACTOS del Excel."""
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# Datos EXACTOS del Excel (38 sesiones post-intervencion, ventana 250ms)
post_250 = [
    0.0, 24.24, 38.46, 19.05, 18.18, 21.05, 23.53, 0.0, 35.71, 27.91,
    16.67, 33.33, 27.27, 0.0, 25.0, 33.33, 16.67, 37.5, 13.79, 37.5,
    8.33, 0.0, 16.67, 26.67, 100.0, 15.79, 20.83, 16.67, 41.18, 16.67,
    0.0, 58.33, 16.67, 16.67, 16.67, 13.64, 24.0, 8.33
]

post_300 = [
    10.53, 27.27, 38.46, 23.81, 21.21, 21.05, 23.53, 16.67, 35.71, 32.56,
    16.67, 33.33, 27.27, 0.0, 41.67, 50.0, 16.67, 50.0, 17.24, 50.0,
    8.33, 9.09, 16.67, 26.67, 100.0, 26.32, 25.0, 22.22, 41.18, 16.67,
    16.67, 66.67, 16.67, 16.67, 16.67, 18.18, 32.0, 16.67
]

# Datos pre del Cap 6 original (64 sesiones)
pre = [
    0.0,16.67, 9.09,16.67, 6.67, 8.82, 4.35, 4.35, 0.0, 8.7,
    0.0,16.67, 0.0, 0.0, 0.0,16.67, 0.0, 0.0, 0.0,25.0,
    9.52,16.67, 0.0, 0.0, 0.0, 0.0, 3.23, 3.23, 4.76, 4.76,
    0.0, 5.26, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 6.67, 0.0, 0.0, 6.45, 6.67, 8.33,10.34,
    0.0,16.67, 0.0, 4.76, 6.9,14.29, 0.0, 8.33, 0.0,16.67,
    0.0, 0.0, 0.0, 0.0
]

OUT = r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\INFORME\Figuras'

# =========================================
# FIGURA 1: BOXPLOT PRE VS POST
# =========================================
fig, ax = plt.subplots(figsize=(6.5, 5.2))
bp = ax.boxplot([pre, post_250], tick_labels=[f'Pre-intervención\n($n={len(pre)}$)', f'Post-intervención\n($n={len(post_250)}$)'],
                patch_artist=True, widths=0.45,
                boxprops=dict(facecolor='#e8f4f8', color='#2c5f7c', linewidth=1.5),
                whiskerprops=dict(color='#2c5f7c', linewidth=1.5),
                capprops=dict(color='#2c5f7c', linewidth=1.5),
                medianprops=dict(color='#c44e52', linewidth=2.2),
                flierprops=dict(marker='o', markerfacecolor='#c44e52', markersize=5, alpha=0.5))

ax.set_ylabel(r'Eficiencia de extracción $\eta$ (%)', fontsize=11)
ax.set_title(r'Distribución de $\eta$: pre vs. post intervención', fontsize=12, fontweight='bold', pad=12)
ax.yaxis.grid(True, linestyle='--', alpha=0.6)
ax.set_ylim(-5, 115)
ax.axhline(y=0, color='gray', linewidth=0.5)

# Anotaciones de media
m_pre = sum(pre)/len(pre)
m_post = sum(post_250)/len(post_250)
ax.annotate(f'$\\bar{{\\eta}}_{{\\text{{pre}}}}={m_pre:.2f}\\%$',
            xy=(1, m_pre), xytext=(1.15, m_pre+8),
            fontsize=10, color='#2c5f7c', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#2c5f7c', lw=1.2))
ax.annotate(f'$\\bar{{\\eta}}_{{\\text{{post}}}}={m_post:.2f}\\%$',
            xy=(2, m_post), xytext=(2.15, m_post+8),
            fontsize=10, color='#2c5f7c', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#2c5f7c', lw=1.2))

plt.tight_layout()
fig.savefig(f'{OUT}/fig_boxplot_eta_pre_post.png', dpi=300, bbox_inches='tight')
fig.savefig(f'{OUT}/fig_boxplot_eta_pre_post.pdf', bbox_inches='tight')
plt.close()
print("Guardado: fig_boxplot_eta_pre_post")

# =========================================
# FIGURA 2: BARRAS SENSIBILIDAD VENTANA
# =========================================
fig, ax = plt.subplots(figsize=(11, 5.5))
x = range(len(post_250))
width = 0.38

bars1 = ax.bar([i - width/2 for i in x], post_250, width, label='Ventana 250 ms', color='#5a9bd5', edgecolor='#2c5f7c', linewidth=0.8)
bars2 = ax.bar([i + width/2 for i in x], post_300, width, label='Ventana 300 ms', color='#70ad47', edgecolor='#385723', linewidth=0.8)

ax.set_xlabel('Sesión post-intervención (11--27 mayo 2026)', fontsize=10)
ax.set_ylabel(r'Eficiencia de extracción $\eta$ (%)', fontsize=10)
ax.set_title(r'Sensibilidad de ventana de correlación: 250 ms vs. 300 ms ($n=38$ sesiones)', fontsize=11, fontweight='bold', pad=12)
ax.set_xticks(x)
ax.set_xticklabels([f'{i+1}' for i in x], fontsize=7)
ax.legend(loc='upper right', fontsize=10)
ax.yaxis.grid(True, linestyle='--', alpha=0.6)
ax.set_ylim(0, 115)

# Lineas de media
ax.axhline(y=22.80, color='#5a9bd5', linestyle='--', linewidth=1.3, alpha=0.8)
ax.axhline(y=27.53, color='#70ad47', linestyle='--', linewidth=1.3, alpha=0.8)
ax.text(37.5, 24.5, r'$\bar{\eta}_{250}=22.80\%$', fontsize=9, color='#2c5f7c', ha='right')
ax.text(37.5, 29.5, r'$\bar{\eta}_{300}=27.53\%$', fontsize=9, color='#385723', ha='right')

# Flecha de delta
ax.annotate('', xy=(37, 27.53), xytext=(37, 22.80),
            arrowprops=dict(arrowstyle='<->', color='#c44e52', lw=2))
ax.text(37.3, 25.2, '$\\Delta=+4.73$ pp', fontsize=9, color='#c44e52', fontweight='bold', va='center')

plt.tight_layout()
fig.savefig(f'{OUT}/fig_sensibilidad_ventana_barras.png', dpi=300, bbox_inches='tight')
fig.savefig(f'{OUT}/fig_sensibilidad_ventana_barras.pdf', bbox_inches='tight')
plt.close()
print("Guardado: fig_sensibilidad_ventana_barras")

# =========================================
# FIGURA 3: DISPERSION ETA POST (scatter)
# =========================================
fig, ax = plt.subplots(figsize=(9, 4.5))
dias = list(range(1, 39))
ax.scatter(dias, post_250, c='#5a9bd5', s=60, alpha=0.7, edgecolors='#2c5f7c', linewidth=0.8, label=r'$\eta_{250}$ (ventana principal)')
ax.scatter(dias, post_300, c='#70ad47', s=60, alpha=0.7, edgecolors='#385723', linewidth=0.8, marker='D', label=r'$\eta_{300}$ (análisis de sensibilidad)')

ax.axhline(y=22.80, color='#5a9bd5', linestyle='--', linewidth=1, alpha=0.7)
ax.axhline(y=27.53, color='#70ad47', linestyle='--', linewidth=1, alpha=0.7)
ax.set_xlabel('Sesión post-intervención (índice 1--38)', fontsize=10)
ax.set_ylabel(r'Eficiencia de extracción $\eta$ (%)', fontsize=10)
ax.set_title(r'Dispersión de $\eta$ por sesión post-intervención: ventana 250 ms vs. 300 ms', fontsize=11, fontweight='bold', pad=12)
ax.legend(loc='upper right', fontsize=9)
ax.yaxis.grid(True, linestyle='--', alpha=0.6)
ax.set_ylim(-5, 115)

plt.tight_layout()
fig.savefig(f'{OUT}/fig_dispersion_eta_ventanas.png', dpi=300, bbox_inches='tight')
fig.savefig(f'{OUT}/fig_dispersion_eta_ventanas.pdf', bbox_inches='tight')
plt.close()
print("Guardado: fig_dispersion_eta_ventanas")

print(f"\nEstadisticas verificadas:")
print(f"  Pre: n={len(pre)}, media={sum(pre)/len(pre):.2f}%")
print(f"  Post 250ms: n={len(post_250)}, media={sum(post_250)/len(post_250):.2f}%")
print(f"  Post 300ms: n={len(post_300)}, media={sum(post_300)/len(post_300):.2f}%")
print(f"  Delta: {sum(post_300)/len(post_300) - sum(post_250)/len(post_250):.2f} pp")
