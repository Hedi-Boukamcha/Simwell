import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

STRATEGY_COLORS = {
    'EDD':      {'main': '#4C72B0', 'second': '#4C72B0'},
    'Batching-EDD-1L': {'main': '#DD8452', 'second': '#DD8452'},
    'Batching-EDD-2PL': {'main': '#DD1452', 'second': '#DD1452'}
}

ALPHA_COLORS = {
    'Batching-EDD-2PL (α=0.2)': '#2ca02c',
    'Batching-EDD-2PL (α=0.5)': "#DD6B14",
    'Batching-EDD-2PL (α=0.8)': "#7c67bd",
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


def plot_courbes(scheduler, title="Courbes", colors=None):
    df = scheduler.solution()
    
    color = STRATEGY_COLORS.get(title, {'main': 'steelblue'})['main']


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

    
def plot_courbes_all(schedulers_dict, title="Courbes comparatives"):

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(title, fontsize=14, fontweight='bold')

    for strategy_name, scheduler in schedulers_dict.items():
        df = scheduler.solution()
        color = STRATEGY_COLORS.get(strategy_name, {'main': 'steelblue'})['main']

        t0 = df['Start'].min()
        df_s = df.sort_values('End')
        x_time = [(e - t0).total_seconds() / 86400 for e in df_s['End']]

        # ── 1. Retard cumulé dans le temps ───────────────────────
        axes[0, 0].plot(x_time, df_s['Delay_Days'].cumsum(),
                        color=color, label=strategy_name)
        axes[0, 0].set_title("Retard cumulé par jour")
        axes[0, 0].set_xlabel("Jours")
        axes[0, 0].set_ylabel("Retard cumulé")
        axes[0, 0].grid(alpha=0.3)

        # ── 2. Nb commandes en retard cumulé ─────────────────────
        axes[0, 1].plot(x_time, (df_s['Delay_Days'] > 0).cumsum(),
                        color=color, label=strategy_name)
        axes[0, 1].set_title("Nb commandes en retard cumulé")
        axes[0, 1].set_xlabel("Jours")
        axes[0, 1].set_ylabel("Nb commandes")
        axes[0, 1].grid(alpha=0.3)

        # ── 3. Retard par commande ────────────────────────────────
        axes[1, 0].plot(df['Delay_Days'].values,
                        color=color, label=strategy_name)
        axes[1, 0].set_title("Retard par commande")
        axes[1, 0].set_xlabel("Commande")
        axes[1, 0].set_ylabel("Retard (j)")
        axes[1, 0].grid(alpha=0.3)

        # ── 4. Nb commandes terminées dans le temps ───────────────
        axes[1, 1].plot(x_time, range(1, len(df_s) + 1),
                        color=color, label=strategy_name)
        axes[1, 1].set_title("Nb commandes terminées dans le temps")
        axes[1, 1].set_xlabel("Jours")
        axes[1, 1].set_ylabel("Nb commandes")
        axes[1, 1].grid(alpha=0.3)

    # ── Légende sur chaque sous-graphe ───────────────────────────
    for ax in axes.flat:
        ax.legend(loc='upper left', fontsize=9)

    plt.tight_layout()
    plt.savefig(f"results/courbes_comparatives.png", dpi=150, bbox_inches='tight')
    print("Courbes comparatives sauvegardées : results/courbes_comparatives.png")
    plt.close()

def plot_courbes_alpha(schedulers_alpha, title="Analyse de sensibilité — Alpha"):

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(title, fontsize=14, fontweight='bold')

    for label, scheduler in schedulers_alpha.items():
        df = scheduler.solution()
        color = ALPHA_COLORS.get(label, 'steelblue')

        t0 = df['Start'].min()
        df_s = df.sort_values('End')
        x_time = [(e - t0).total_seconds() / 86400 for e in df_s['End']]

        # ── 1. Retard cumulé dans le temps ───────────────────────
        axes[0, 0].plot(x_time, df_s['Delay_Days'].cumsum(), color=color, label=label)
        axes[0, 0].set_title("Retard cumulé par jour")
        axes[0, 0].set_xlabel("Jours")
        axes[0, 0].set_ylabel("Retard cumulé")
        axes[0, 0].grid(alpha=0.3)

        # ── 2. Nb commandes en retard cumulé ─────────────────────
        axes[0, 1].plot(x_time, (df_s['Delay_Days'] > 0).cumsum(), color=color, label=label)
        axes[0, 1].set_title("Nb commandes en retard cumulé")
        axes[0, 1].set_xlabel("Jours")
        axes[0, 1].set_ylabel("Nb commandes")
        axes[0, 1].grid(alpha=0.3)

        # ── 3. Retard par commande ────────────────────────────────
        axes[1, 0].plot(df['Delay_Days'].values, color=color, label=label)
        axes[1, 0].set_title("Retard par commande")
        axes[1, 0].set_xlabel("Commande")
        axes[1, 0].set_ylabel("Retard (j)")
        axes[1, 0].grid(alpha=0.3)

        # ── 4. Nb commandes terminées dans le temps ───────────────
        axes[1, 1].plot(x_time, range(1, len(df_s) + 1), color=color, label=label)
        axes[1, 1].set_title("Nb commandes terminées dans le temps")
        axes[1, 1].set_xlabel("Jours")
        axes[1, 1].set_ylabel("Nb commandes")
        axes[1, 1].grid(alpha=0.3)

    for ax in axes.flat:
        ax.legend(loc='upper left', fontsize=9)

    plt.tight_layout()
    plt.savefig("results/courbes_alpha.png", dpi=150, bbox_inches='tight')
    print("Courbes alpha sauvegardées : results/courbes_alpha.png")
    plt.close()