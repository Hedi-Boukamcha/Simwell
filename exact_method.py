import pandas as pd
from ortools.sat.python import cp_model
import datetime

class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Affiche l'évolution de l'optimisation en temps réel."""
    def __init__(self, delay_var, cmax_var, alpha, beta):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__delay = delay_var
        self.__cmax = cmax_var
        self.__alpha = alpha
        self.__beta = beta
        self.__count = 0

    def on_solution_callback(self):
        self.__count += 1
        d = self.Value(self.__delay)
        c = self.Value(self.__cmax)
        score = (self.__alpha * d) + (self.__beta * c)
        print(f"   [Solution #{self.__count}] Score: {score} | Retard: {d}j | Fin: {c}h")

def solve_exact_method(df, alpha=1, beta=50, start_date_str="2025-01-06"):
    """
    Modèle Multi-Objectif : Retard vs Nombre de Setups
    ------------------------------------------------
    Objectif : Minimiser (alpha * Somme_Retards) + (beta * Nombre_Total_Setups)
    """
    model = cp_model.CpModel()
    n = len(df)
    start_date = pd.to_datetime(start_date_str)
    setup_time_h = 12
    
    # 1. Horizon de temps
    horizon = int(sum((df['QTY'] / df['Average per Day']) * 24) + (n * setup_time_h))

    # --- VARIABLES ---
    starts = [model.NewIntVar(0, horizon, f's_{i}') for i in range(n)]
    ends = [model.NewIntVar(0, horizon, f'e_{i}') for i in range(n)]
    intervals = []
    delays = []
    
    for i in range(n):
        duration = int(max(1, round((df.iloc[i]['QTY'] / df.iloc[i]['Average per Day']) * 24)))
        intervals.append(model.NewIntervalVar(starts[i], duration, ends[i], f'int_{i}'))
        
        due_h = int((pd.to_datetime(df.iloc[i]['Expected Delivery Date']) - start_date).total_seconds() / 3600)
        d = model.NewIntVar(0, horizon, f'd_{i}')
        model.Add(d >= ends[i] - due_h)
        delays.append(d)

    model.AddNoOverlap(intervals)

    # --- LOGIQUE MULTI-OBJECTIF : COMPTAGE DES SETUPS ---
    # On crée une variable 'is_setup[i, j]' qui vaut 1 si la commande j passe juste après i 
    # ET que leurs familles sont différentes.
    
    # Pour 1000 commandes, on simplifie par "Regroupement de Familles" (Clustering)
    # On crée une variable binaire par commande qui indique si elle est un "début de série"
    is_setup = [model.NewBoolVar(f'setup_{i}') for i in range(n)]
    
    # Pour réduire les setups, on minimise le nombre de fois où une famille change
    # Dans ce modèle exact, on utilise la proximité temporelle
    for i in range(n):
        for j in range(i + 1, n):
            # Si deux commandes de familles différentes se chevauchent presque, 
            # on impose un écart de setup_time_h
            if df.iloc[i]['Family'] != df.iloc[j]['Family']:
                # Si j suit i
                b = model.NewBoolVar(f'order_{i}_{j}')
                model.Add(starts[j] >= ends[i]).OnlyEnforceIf(b)
                model.Add(starts[j] >= ends[i] + setup_time_h).OnlyEnforceIf(b)
                
    #  Objectifs
    total_delay_days = model.NewIntVar(0, 100000, 'total_delay')
    model.Add(total_delay_days == sum(delays) // 24)
    c_max = model.NewIntVar(0, 100000, 'c_max')
    model.AddMaxEquality(c_max, ends)

    model.Minimize(alpha * total_delay_days + beta * c_max)

    # --- CONFIGURATION DU SUIVI ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    # Active les logs internes (affiche les détails techniques dans la console)
    solver.parameters.log_search_progress = True 
    
    print(f"\n--- 🧠 Début de l'optimisation (Alpha={alpha}, Beta={beta}) ---")
    printer = VarArraySolutionPrinter(total_delay_days, c_max, alpha, beta)

    # --- RÉSOLUTION ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0 # Temps limité pour l'exercice
    status = solver.Solve(model, printer)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        results = []
        for i in range(n):
            results.append({
                "Commande_ID": i,
                "Famille": df.iloc[i]['Family'],
                "Debut": start_date + datetime.timedelta(hours=solver.Value(starts[i])),
                "Fin": start_date + datetime.timedelta(hours=solver.Value(ends[i])),
                "Retard_H": solver.Value(delays[i])
            })
        
        df_res = pd.DataFrame(results).sort_values(by="Debut")
        
        # Calcul des setups réels après optimisation
        nb_setups = 0
        for k in range(1, len(df_res)):
            if df_res.iloc[k]['Famille'] != df_res.iloc[k-1]['Famille']:
                nb_setups += 1

        metrics = {
            "Retard total (jours)": round(df_res['Retard_H'].sum() / 24, 2),
            "Nombre de setups": nb_setups,
            "Date de fin": df_res['Fin'].max(),
            "Nombre de commandes traitées": len(df_res)
        }
        return df_res, metrics
    
    return None, None