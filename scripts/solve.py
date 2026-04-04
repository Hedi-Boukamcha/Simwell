from datetime import datetime, timedelta
import pandas as pd
from collections import Counter


class SimwellScheduler:
    def __init__(self, df_orders, start_date, rotations, strategy="EDD"):
        self.df_initial = df_orders
        self.rotations = rotations
        self.setup_time = 12
        self.last_family = None
        self.last_order_id = None
        self.last_maintenance_date = start_date
        self.all_orders = df_orders.to_dict('records')
        self.schedule = []

        ## Initialisation des compteurs
        self.current_time = start_date + timedelta(hours=12)
        self.total_setup_hours = 12
        self.total_delay_days = 0
        self.total_idle_hours = 0
        self.maintenance_count = 0
        self.late_orders_count = 0
        self.cmax = 0
        self.gap = 0

        # Les approches
        strategies = {
            "EDD":       self.EDD,
            "Batching-EDD-1L":  self.batching_EDD_1l,
        }
        if strategy not in strategies:
            raise ValueError(f"Stratégie inconnue: {strategy}. Choisir parmi {list(strategies.keys())}")
        self._find_next_order = strategies[strategy]

    def solution(self):
        if not self.schedule:
            return pd.DataFrame()
        return pd.DataFrame(self.schedule)

    def metrics(self):
        nb_commandes = len(self.schedule)
        retard_moyen = round(self.total_delay_days / self.late_orders_count, 2) if nb_commandes > 0 else 0
        borne_inf_jours = self.calculate_lower_bound()
        self.gap = round((self.cmax - borne_inf_jours) / borne_inf_jours * 100, 1) if borne_inf_jours > 0 else 0
        return {
            "Date de fin totale (j)": self.current_time,
            "Nombre de commandes traitées": nb_commandes,
            "Retard total (j)": round(self.total_delay_days, 2),
            "Borne inferieure (j)": round(borne_inf_jours, 2),
            "Nombre de setups effectués": self.total_setup_hours // self.setup_time,
            "Temps de setup total (h)": self.total_setup_hours,
            "Nombre de maintenances": self.maintenance_count,
            "Retard Moyenne par commande (j)": retard_moyen,
            "Nb commandes en retard": self.late_orders_count,
            "Cmax (j)": round(self.cmax, 2),
            "GAP (%)": round(self.gap, 2),
        }
    
    def calculate_lower_bound(self):
        df = self.df_initial.copy()
        
        total_prod_hours = sum((df['QTY'] / df['Average per Day']) * 24)
        num_families = df['Family'].nunique()
        min_setup_hours = (num_families - 1) * 12
        
        earliest_start = df['Order Confirmed Date'].min()
        lb_end = earliest_start + timedelta(hours=total_prod_hours + min_setup_hours)
        lb_cmax_days = (lb_end - earliest_start).total_seconds() / 86400

        print(f"Temps total production   : {total_prod_hours/24:.1f} jours")
        print(f"Nb familles              : {num_families}")
        print(f"Setups minimaux          : {num_families-1} × 12h = {min_setup_hours/24:.1f} jours")
        print(f"LB Cmax                  : {lb_cmax_days:.1f} jours")
    
        return round(lb_cmax_days, 2)

    def _advance_time(self, new_date):
        if new_date > self.current_time:
            idle_delta = (new_date - self.current_time).total_seconds() / 3600
            self.total_idle_hours += idle_delta
            self.current_time = new_date

    def _apply_setup(self, new_family):
        if self.last_family is not None and new_family != self.last_family:
            self.current_time += timedelta(hours=12)
            self.total_setup_hours += 12
        self.last_family = new_family

    def _check_maintenance(self):
        if (self.current_time - self.last_maintenance_date).days >= 84:
            self.current_time += timedelta(hours=24)
            self.last_maintenance_date = self.current_time
            self.maintenance_count += 1
    
    def process_scheduling(self, orders_df):
        pending_orders = orders_df.to_dict('records')
        while pending_orders:
            self._check_maintenance()
            idx = self._find_next_order(pending_orders)  # appel dynamique
            if idx is None:
                break
            order = pending_orders.pop(idx)
            self._apply_setup(order['Family'])
            self._produce(order)
        return self.metrics()

    def _produce(self, order):
        start_prod = self.current_time
        duration_hours = (order['QTY'] / order['Average per Day']) * 24
        self.current_time += timedelta(hours=duration_hours)
        end_prod = self.current_time
        delay = max(0, (end_prod - order['Expected Delivery Date']).total_seconds() / 86400)
        self.cmax = (self.current_time - datetime(2025, 1, 7, 0, 0)).total_seconds() / 86400
        
        self.total_delay_days += delay
        if delay > 0:
            self.late_orders_count += 1
        self.last_order_id = order['Order ID']
        self.schedule.append({
            'OrderID': order['Order ID'],
            'Family': order['Family'],
            'Start': start_prod,
            'End': end_prod,
            'Due_Date': order['Expected Delivery Date'],
            'Delay_Days': round(delay, 2)
        })
    
    # EDD
    def EDD(self, pending_orders):
        while True:
            allowed = list(self.rotations) if self.last_family is None else self.rotations.get(self.last_family, [])
            confirmed = [o for o in pending_orders if o['Order Confirmed Date'] <= self.current_time]
            ready = [o for o in confirmed if o['Family'] in allowed]

            if ready:
                ready.sort(key=lambda x: x['Expected Delivery Date'])
                target_id = ready[0]['Order ID']
                return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)

            future = [o for o in pending_orders if o['Family'] in allowed]
            if not future:
                self.last_family = None
                continue
            self._advance_time(min(future, key=lambda x: x['Order Confirmed Date'])['Order Confirmed Date'])

    # Batching + EDD
    def batching_EDD_1l(self, pending_orders):
        while True:
            if not pending_orders:
                return None
            
            allowed = list(self.rotations) if self.last_family is None else self.rotations.get(self.last_family, [])
            confirmed = [o for o in pending_orders if o['Order Confirmed Date'] <= self.current_time]
            ready = [o for o in confirmed if o['Family'] in allowed]

            if ready:
                same_family = [o for o in ready if o['Family'] == self.last_family]
                if same_family:
                    same_family.sort(key=lambda x: x['Expected Delivery Date'])
                    target_id = same_family[0]['Order ID']
                    chosen = same_family[0]
                    '''print(f"[BATCH] Continuation famille '{chosen['Family']}' "
                      f"— ID {chosen['Order ID']} | "
                      f"{len(same_family)} commande(s) restantes dans ce batch | "
                      f"Setup évité")'''
                else:
                    family_counts = Counter(o['Family'] for o in ready)
                    ready.sort(key=lambda x: (-family_counts[x['Family']], x['Expected Delivery Date']))
                    target_id = ready[0]['Order ID']
                    chosen = ready[0]
                return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)

            future = [o for o in pending_orders if o['Family'] in allowed]
            if not future:
                self.last_family = None
                continue
            self._advance_time(min(future, key=lambda x: x['Order Confirmed Date'])['Order Confirmed Date'])

