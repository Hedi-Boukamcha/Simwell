from datetime import timedelta
import pandas as pd
import openpyxl


def load_simwell_data_exl(file_path):

    wb = openpyxl.load_workbook(file_path, data_only=True)

    def wb_to_df(sheet_name, index_col=None):
        ws = wb[sheet_name]
        data = list(ws.values)
        df = pd.DataFrame(data[1:], columns=data[0])
        if index_col:
            df = df.set_index(index_col)
        return df

    df_demand   = wb_to_df('Demand')
    df_family   = wb_to_df('Family')
    df_prod_plan = wb_to_df('Production Plan')
    df_rotation = wb_to_df('Rotation', index_col='From/To')

    # Convertion de la date de confirmation des commandes 
    df_demand['Order Confirmed Date'] = pd.to_datetime(df_demand['Order Confirmed Date'])

    # Recalculer Expected Delivery Date si manquante (formule = +42 jours)
    mask = df_demand['Expected Delivery Date'].isna() | (df_demand['Expected Delivery Date'] == pd.Timestamp('1969-12-31'))
    df_demand.loc[mask, 'Expected Delivery Date'] = df_demand.loc[mask, 'Order Confirmed Date'] + timedelta(days=42)
    df_demand['Expected Delivery Date'] = pd.to_datetime(df_demand['Expected Delivery Date'])

    # Fusion
    df_merged = pd.merge(df_demand, df_family, on='Product', how='left')
    df_merged = pd.merge(df_merged, df_prod_plan, on='Family', how='left')

    # Convertion des dates
    df_merged['Order Confirmed Date'] = pd.to_datetime(df_merged['Order Confirmed Date'])
    df_merged['Expected Delivery Date'] = pd.to_datetime(df_merged['Expected Delivery Date'])

    # Matrice de rotation
    allowed_transitions = {}
    for family in df_rotation.index:
        allowed = df_rotation.columns[df_rotation.loc[family] == 1].tolist()
        allowed_transitions[family] = allowed

    return df_merged, allowed_transitions

if __name__ == "__main__":
    DATA_PATH = "data/Données_Ordonnancement_2026.xlsx"
    try:
        orders, allowed_transitions = load_simwell_data_exl(DATA_PATH)
        print("Succès !")
        print(orders.head(10))
        print(orders.dtypes)
    except Exception as e:
        print(f"Erreur : {e}")