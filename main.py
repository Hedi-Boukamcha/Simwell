import pandas as pd
from datetime import datetime

from config import ROTATION
from scripts.data_loader import load_simwell_data
from scripts.approach import SimwellScheduler

def main():
    # 1. Configuration des paramètres
    data_path = "data/Données_Ordonnancement_2026.xlsx"
    start_date = datetime(2025, 1, 6, 0, 0) # Lancement le 06 Janvier à 00h

    print("--- Chargement des données ---")
    df_orders, rotations_excel = load_simwell_data(data_path)
    
    if df_orders is None or df_orders.empty:
        print("Erreur : Impossible de charger les données.")
        return
    
    if not rotations_excel:
        print("Erreur critique : La matrice de rotation est vide ou mal chargée.")
        return
    
    # 2. Initialisation du moteur d'ordonnancement
    scheduler = SimwellScheduler(df_orders, start_date, ROTATION)

    print("--- Lancement de l'ordonnancement (Logique EDD + Rotation) ---")
    metrics = scheduler.process_scheduling(df_orders)

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
    print(f"Date de fin totale           : {metrics['Date de fin totale (j)']}")
    print(f"Retard total (j)         : {metrics['Retard total (j)']} jours")
    print(f"Temps de setup total (h)     : {metrics['Temps de setup total (h)']} h")
    print(f"Nombre de maintenances       : {metrics['Nombre de maintenances']}")
    print(f"Nombre de commandes traitées : {metrics['Nombre de commandes traitées']}")  

# pyhton main.py
if __name__ == "__main__":
    main()