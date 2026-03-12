import pandas as pd
import datetime
import os

from scripts.data_loader import load_simwell_data
from scripts.approach import SimwellScheduler

def main():
    # --- 1. CONFIGURATION ---
    data_path = "data/Données_Ordonnancement_2026.xlsx"
    start_date = datetime.datetime(2025, 1, 6, 0, 0)
    
    # La rotation cyclique simple telle que définie au début
    ROTATION_LOGIC = {
        'A': ['A', 'P'],
        'P': ['P', 'H'],
        'H': ['H', 'A'],
        None: ['A', 'P', 'H']
    }
    
    # Création du dossier de résultats si nécessaire
    if not os.path.exists('results'):
        os.makedirs('results')

    print("="*50)
    print("SYSTÈME D'ORDONNANCEMENT - VERSION HEURISTIQUE")
    print("="*50)

    # --- 2. CHARGEMENT DES DONNÉES ---
    print("\n[1/3] Chargement des données Excel...")
    df_orders, _ = load_simwell_data(data_path)
    
    if df_orders is None or df_orders.empty:
        print(" Erreur : Impossible de charger les données.")
        return
    print(f"  {len(df_orders)} commandes chargées.")

    # --- 3. EXÉCUTION DE L'ALGORITHME ---
    print("\n[2/3] Lancement de l'ordonnancement (Simwell)...")
    start_time = datetime.time()
    
    # Initialisation du scheduler
    scheduler = SimwellScheduler(df_orders.copy(), start_date, ROTATION_LOGIC)
    
    # Calcul du planning et des métriques
    metrics = scheduler.process_scheduling(df_orders.copy())
    
    execution_time = datetime.time.time() - start_time
    print(f"    Terminé en {execution_time:.2f} secondes.")

    # --- 4. EXPORT ET RÉSULTATS ---
    print("\n[3/3]  Génération des résultats...")
    
    # Récupération du DataFrame final ordonnancé
    df_final = scheduler.solution()
    df_final.to_csv("results/results_approach.csv", index=False, sep=';')

    # Affichage des métriques clés dans la console
    print("\n" + "-"*30)
    print(" PERFORMANCE DU PLANNING")
    print("-"*30)
    for key, value in metrics.items():
        print(f"{key:.<25}: {value}")
    print("-"*30)
    
    print(f"\n Fichier sauvegardé : results/results_approach.csv")

if __name__ == "__main__":
    main()