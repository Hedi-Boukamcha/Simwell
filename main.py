import pandas as pd
from datetime import datetime
import copy

from config import ROTATION
from plots import plot_courbes, plot_courbes_alpha, plot_gantt, plot_courbes_all, ALPHA_COLORS
from scripts.data_loader import load_simwell_data_exl
from scripts.solve import SimwellScheduler
from scripts.batching_2lines import SimwellScheduler2Lines


def main():
    # 1. Configuration des paramètres
    data_path = "data/Données_Ordonnancement_2026.xlsx"
    start_date = datetime(2025, 1, 6, 0, 0) # Lancement le 06 Janvier 2025 à 00h

    print("--- Chargement des données ---")
    df_orders, rotations_excel = load_simwell_data_exl(data_path)
    if df_orders is None or df_orders.empty:
        print("Erreur : Impossible de charger les données.")
        return
    if not rotations_excel:
        print("Erreur critique : La matrice de rotation est vide ou mal chargée.")
        return
    
    print("--- Lancement de l'ordonnancement ---")
    # Lancement des approches
    strategies = ["EDD", "Batching-EDD-1L", "Batching-EDD-2PL"]
    all_metrics = {}
    schedulers_dict = {}
    alphas = [0.2, 0.5, 0.8]
    schedulers_alpha = {}
    
    for strategy in strategies:
        print(f"\n--- Lancement : {strategy.upper()} ---")
        df_orders_copy = df_orders.copy()
        if strategy == "Batching-EDD-2PL":
            scheduler = SimwellScheduler2Lines(df_orders_copy, start_date, ROTATION, alpha=0.8)
            label = 'Batching-EDD-2PL'
        elif strategy == "EDD":
            scheduler = SimwellScheduler(df_orders_copy, start_date, ROTATION, strategy=strategy)
            label = 'EDD'
        else:
            scheduler = SimwellScheduler(df_orders_copy, start_date, ROTATION, strategy="Batching-EDD-1L")
            label = 'Batching-EDD-1L'
        metrics = scheduler.process_scheduling(df_orders_copy)
        all_metrics[strategy] = metrics
        #plot_gantt(scheduler, strategy)                     
        #plot_courbes(scheduler, strategy) 
        schedulers_dict[label] = scheduler
        #plot_courbes_all(schedulers_dict, title="Comparaison des stratégies")

        # Sauvegarde solution et métriques par stratégie
        df_resultat = scheduler.solution()
        df_resultat.to_csv(f"results/results_{strategy}.csv", index=False)
        #print(f"Solution sauvegardée : results/results_{strategy}.csv")
    

    for alpha in alphas:
        df_orders_copy = df_orders.copy()
        scheduler = SimwellScheduler2Lines(df_orders_copy, start_date, ROTATION, alpha=alpha)
        scheduler.process_scheduling(df_orders_copy)
        label = f'Batching-EDD-2PL (α={alpha})'
        schedulers_alpha[label] = scheduler
    plot_courbes_alpha(schedulers_alpha)
    
    # Sauvegarder les métriques ensemble
    df_all_metrics = pd.DataFrame(all_metrics).T
    df_all_metrics.to_csv("results/metrics_all.csv")
    print("\nMétriques comparatives sauvegardées : results/metrics_all.csv")

    # Affichage comparatif dans le terminal
    print("\n" + "="*65)
    print(f"{'Métrique':<35} {'EDD':>6} {'BATCH':>6} {'BATCH_2lines':>6}")
    print("="*65)
    
    kpis = [
        ("Retard total (j)",               "Retard total (j)"),
        ("Retard moyen/commande (j)",      "Retard Moyenne par commande (j)"),
        ("Nb setups",                     "Nombre de setups effectués"),
        ("Setup total (h)",                "Temps de setup total (h)"),
        ("Nb maintenances",                "Nombre de maintenances"),
        ("Nb commandes traitées",          "Nombre de commandes traitées"),
        ("Nb commandes en retard",         "Nb commandes en retard"),
        ("Cmax (j)",                       "Cmax (j)"),
        ("GAP (%)",                       "GAP (%)")
    ]

    for label, key in kpis:
        vals = [all_metrics[s][key] for s in strategies]
        print(f"{label:<35} {vals[0]:>8} {vals[1]:>8} {vals[2]:>8}")

    print("="*65)

    # Identifier la meilleure stratégie sur le retard total
    best = min(all_metrics, key=lambda s: all_metrics[s]["Retard total (j)"])
    print(f"\nMeilleure stratégie (retard total) : {best.upper()}")
    print(f"  Retard : {all_metrics[best]['Retard total (j)']} jours")
    print(f"  Setups : {all_metrics[best]['Nombre de setups effectués']}")

# executer le code
if __name__ == "__main__":
    main()