import pandas as pd
import os

def load_simwell_data(file_path):
    """
    Charge et fusionne les données du fichier Excel Simwell.
    """
    # 1. Chargement des onglets
    # On utilise les noms exacts mentionnés dans vos directives
    df_demand = pd.read_excel(file_path, sheet_name='Demand')
    df_family = pd.read_excel(file_path, sheet_name='Family')
    df_prod_plan = pd.read_excel(file_path, sheet_name='Production Plan')
    df_rotation = pd.read_excel(file_path, sheet_name='Rotation', index_col=0)

    # 2. Nettoyage et Fusion (Merge)
    # On lie chaque produit à sa famille 
    df_merged = pd.merge(df_demand, df_family, on='Product', how='left')
    
    # On lie chaque famille à son taux de production 
    # Note : Assurez-vous que la colonne de jointure s'appelle 'Family' dans les deux onglets
    df_merged = pd.merge(df_merged, df_prod_plan, on='Family', how='left')

    # 3. Calcul du temps de production théorique
    # Formule : $Time_{hours} = \frac{QTY}{Average\ Per\ Day} \times 24$
    df_merged['Production_Hours'] = (df_merged['QTY'] / df_merged['Average per Day']) * 24

    # 4. Traitement de la Matrice de Rotation [cite: 7, 9]
    # On transforme la matrice 1/0 en dictionnaire de transitions autorisées
    allowed_transitions = {}
    for family in df_rotation.index:
        # On ne garde que les colonnes où la valeur est 1 (transition permise)
        allowed = df_rotation.columns[df_rotation.loc[family] == 1].tolist()
        allowed_transitions[family] = allowed

    return df_merged, allowed_transitions

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_PATH = os.path.join(BASE_DIR, 'data', 'Données_Ordonnancement_2026.xlsx')
    try:
        print(f"Tentative d'ouverture de : {DATA_PATH}")
        df, rotations = load_simwell_data(DATA_PATH)
        print("Succès !")
        print(df.head())
    except Exception as e:
        print(f"Erreur : {e}")