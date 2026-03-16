import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

STRATEGY_COLORS = {
    'edd':      {'main': '#4C72B0', 'second': '#4C72B0'},
    'batching': {'main': '#DD8452', 'second': '#DD8452'},
}


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
                (end - start).total_seconds() / 86400,
                left=(start - df['Start'].min()).total_seconds() / 86400,
                color=color_map[row['Family']],
                edgecolor='white', linewidth=0.3)
        if row['Delay_Days'] > 0:
            ax.barh(row['Family'],
                    0.5,
                    left=(end - df['Start'].min()).total_seconds() / 86400,
                    color='red', alpha=0.7)
    patches = [mpatches.Patch(color=color_map[f], label=f) for f in families]
    patches.append(mpatches.Patch(color='red', alpha=0.7, label='Retard'))

    ax.set_xlabel("Jours")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(f"results/gantt_{title}.png", dpi=150)
    plt.close()


def plot_courbes(scheduler, title="Courbes"):
    df = scheduler.solution()
    
    strategy = title.lower()
    color = STRATEGY_COLORS.get(strategy, {'main': 'steelblue', 'second': 'coral'})['main']

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f"Courbes — {title}", fontsize=14, fontweight='bold')

    t0 = df['Start'].min()
    df_s = df.sort_values('End')

    # ── 1. Retard cumulé dans le temps ───────────────────────
    ax = axes[0, 0]
    ax.plot(
        [(e - t0).total_seconds() / 86400 for e in df_s['End']],
        df_s['Delay_Days'].cumsum(),
        color=color
    )
    ax.set_title("Retard cumulé par jour")
    ax.set_xlabel("Jours")
    ax.set_ylabel("Retard cumulé")
    ax.grid(alpha=0.3)

    # ── 2. Nb commandes en retard cumulé ─────────────────────
    ax = axes[0, 1]
    ax.plot(
        [(e - t0).total_seconds() / 86400 for e in df_s['End']],
        (df_s['Delay_Days'] > 0).cumsum(),
        color=color
    )
    ax.set_title("Nb commandes en retard cumulé")
    ax.set_xlabel("Jours")
    ax.set_ylabel("Nb commandes")
    ax.grid(alpha=0.3)

    # ── 3. Retard par commande ────────────────────────────────
    ax = axes[1, 0]
    ax.plot(df['Delay_Days'], color=color)
    ax.set_title("Retard par commande")
    ax.set_xlabel("Commande")
    ax.set_ylabel("Retard (j)")
    ax.grid(alpha=0.3)

    # ── 4. Nb commandes terminées dans le temps ───────────────
    ax = axes[1, 1]
    ax.plot(
        [(e - t0).total_seconds() / 86400 for e in df_s['End']],
        range(1, len(df_s) + 1),
        color=color
    )
    ax.set_title("Nb commandes terminées dans le temps")
    ax.set_xlabel("Jours")
    ax.set_ylabel("Nb commandes")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"results/courbes_{title}.png", dpi=150, bbox_inches='tight')
    print(f"Courbes sauvegardées : results/courbes_{title}.png")
    plt.close()

    