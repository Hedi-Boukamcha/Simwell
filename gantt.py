import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def plot_gantt(scheduler, title="Gantt"):
    df = scheduler.solution()
    families = df['Family'].unique()
    colors = plt.cm.Set3.colors
    color_map = {f: colors[i % len(colors)] for i, f in enumerate(families)}

    fig, ax = plt.subplots(figsize=(16, 6))
    for _, row in df.iterrows():
        start = row['Start']
        end = row['End']
        ax.barh(row['Family'], 
                (end - start).total_seconds() / 3600,
                left=(start - df['Start'].min()).total_seconds() / 3600,
                color=color_map[row['Family']],
                edgecolor='white', linewidth=0.3)
        if row['Delay_Days'] > 0:
            ax.barh(row['Family'],
                    0.5,
                    left=(end - df['Start'].min()).total_seconds() / 3600,
                    color='red', alpha=0.7)
    patches = [mpatches.Patch(color=color_map[f], label=f) for f in families]
    patches.append(mpatches.Patch(color='red', alpha=0.7, label='Retard'))
    ax.legend(handles=patches, loc='upper right', fontsize=9)

    ax.set_xlabel("Heures depuis le début")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(f"results/gantt_{title}.png", dpi=150)
    plt.show()



def plot_courbes(scheduler, title="Gantt"):
    df = scheduler.solution()

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f"Courbes — {title}", fontsize=14, fontweight='bold')

    t0 = df['Start'].min()
    df_s = df.sort_values('End')

    # ── 1. Retard cumulé dans le temps ───────────────────────
    ax = axes[0, 0]
    ax.plot(
        [(e - t0).total_seconds() / 3600 for e in df_s['End']],
        df_s['Delay_Days'].cumsum(),
        color='steelblue'
    )
    ax.set_title("Retard cumulé dans le temps")
    ax.set_xlabel("Heures depuis le début")
    ax.set_ylabel("Retard cumulé (j)")
    ax.grid(alpha=0.3)

    # ── 2. Nb commandes en retard cumulé ─────────────────────
    ax = axes[0, 1]
    ax.plot(
        [(e - t0).total_seconds() / 3600 for e in df_s['End']],
        (df_s['Delay_Days'] > 0).cumsum(),
        color='coral'
    )
    ax.set_title("Nb commandes en retard cumulé")
    ax.set_xlabel("Heures depuis le début")
    ax.set_ylabel("Nb commandes")
    ax.grid(alpha=0.3)

    # ── 3. Retard par commande (trié croissant) ───────────────
    ax = axes[1, 0]
    ax.plot(df['Delay_Days'], color='steelblue')
    ax.set_title("Retard par commande")
    ax.set_xlabel("Commande")
    ax.set_ylabel("Retard (j)")
    ax.grid(alpha=0.3)

    # ── 4. Nb commandes terminées dans le temps ───────────────
    ax = axes[1, 1]
    ax.plot(
        [(e - t0).total_seconds() / 3600 for e in df_s['End']],
        range(1, len(df_s) + 1),
        color='coral'
    )
    ax.set_title("Nb commandes terminées dans le temps")
    ax.set_xlabel("Heures depuis le début")
    ax.set_ylabel("Nb commandes")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"results/courbes_{title}.png", dpi=150, bbox_inches='tight')
    print(f"Courbes sauvegardées : results/courbes_{title}.png")
    plt.close()