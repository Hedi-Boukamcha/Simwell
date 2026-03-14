import pandas as pd
from datetime import datetime

from config import ROTATION
from gantt import plot_courbes, plot_gantt
from scripts.data_loader import load_simwell_data_exl
from scripts.approach import SimwellScheduler
from scripts.test import SimwellTest

def main():
    # 1. Configuration des paramètres
    data_path = "data/Données_Ordonnancement_2026.xlsx"
    start_date = datetime(2025, 1, 6, 0, 0) # Lancement le 06 Janvier à 00h

    print("--- Chargement des données ---")
    df_orders, rotations_excel = load_simwell_data_exl(data_path)
    
    if df_orders is None or df_orders.empty:
        print("Erreur : Impossible de charger les données.")
        return
    
    if not rotations_excel:
        print("Erreur critique : La matrice de rotation est vide ou mal chargée.")
        return
    
    # 2. Initialisation du moteur d'ordonnancement
    #scheduler = SimwellScheduler(df_orders, start_date, ROTATION)

    print("--- Lancement de l'ordonnancement ---")
    '''metrics1 = scheduler.process_scheduling(df_orders)

    # 3. Récupération et sauvegarde des résultats
    df_resultat = scheduler.solution()
    # Export vers CSV
    solution_path = "results/results_approach.csv"
    df_resultat.to_csv(solution_path, index=False)
    print(f"--- Solution sauvegardée : {solution_path} ---")

    # 4. Récupération et sauvegarde des KPIs
    stats = scheduler.metrics()
    df_metrics = pd.DataFrame([stats])
    metrics_path = "results/metrics_approach.csv"
    df_metrics.to_csv(metrics_path, index=False)
    print(f"--- Metrics sauvegardées : {metrics_path} ---")

    print("\n--- RÉSULTATS DU TP ---")
    print("\n--- App 1 ---")
    print(f"Date de fin totale           : {metrics1['Date de fin totale (j)']}")
    print(f"Retard total (j)             : {metrics1['Retard total (j)']} jours")
    print(f"Temps de setup total (h)     : {metrics1['Temps de setup total (h)']} h")
    print(f"Nombre de maintenances       : {metrics1['Nombre de maintenances']}")
    print(f"Nombre de commandes traitées : {metrics1['Nombre de commandes traitées']}")'''

        # 2. Lancement des 4 stratégies
    strategies = ["edd", "batching"]
    all_metrics = {}
    
    for strategy in strategies:
        print(f"\n--- Lancement : {strategy.upper()} ---")
        scheduler = SimwellTest(df_orders, start_date, ROTATION, strategy=strategy)
        metrics = scheduler.process_scheduling(df_orders)
        all_metrics[strategy] = metrics
        plot_gantt(scheduler, strategy)  
        plot_courbes(scheduler, strategy)      

        # Sauvegarde solution et métriques par stratégie
        df_resultat = scheduler.solution()
        df_resultat.to_csv(f"results/results_{strategy}.csv", index=False)
        print(f"Solution sauvegardée : results/results_{strategy}.csv")


    # 3. Sauvegarde comparative des métriques
    df_all_metrics = pd.DataFrame(all_metrics).T
    df_all_metrics.to_csv("results/metrics_all.csv")
    print("\nMétriques comparatives sauvegardées : results/metrics_all.csv")

    # 4. Affichage comparatif
    print("\n" + "="*65)
    print(f"{'Métrique':<35} {'EDD':>6} {'BATCH':>6}")
    print("="*65)
    
    kpis = [
        ("Retard total (j)",             "Retard total (j)"),
        ("Retard moyen/commande (j)",     "Retard Moyenne par commande (j)"),
        ("Nb setups",                     "Nombre de setups effectués"),
        ("Setup total (h)",               "Temps de setup total (h)"),
        ("Nb maintenances",               "Nombre de maintenances"),
        ("Nb commandes traitées",         "Nombre de commandes traitées"),
    ]

    for label, key in kpis:
        vals = [all_metrics[s][key] for s in strategies]
        print(f"{label:<35} {vals[0]:>6} {vals[1]:>6}")

    print("="*65)

    # Identifier la meilleure stratégie sur le retard total
    best = min(all_metrics, key=lambda s: all_metrics[s]["Retard total (j)"])
    print(f"\nMeilleure stratégie (retard total) : {best.upper()}")
    print(f"  Retard : {all_metrics[best]['Retard total (j)']} jours")
    print(f"  Setups : {all_metrics[best]['Nombre de setups effectués']}")





# pyhton main.py
if __name__ == "__main__":
    main()