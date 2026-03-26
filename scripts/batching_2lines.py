from datetime import datetime, timedelta
from collections import Counter
from scripts.solve import SimwellScheduler


class SimwellScheduler2Lines(SimwellScheduler):
    """
    Heuristique : Batching 2 Lines
    Hérite de SimwellScheduler (solve.py).

    Ajouts :
    - 2 lignes de production en parallèle
    - Chaque ligne a son propre current_time, last_family, last_maintenance_date
    - À chaque itération, on choisit la ligne disponible le plus tôt
    - Sur chaque ligne, logique batching + EDD
    """

    def __init__(self, df_orders, start_date, rotations):
        # Initialise toutes les variables communes via le parent
        super().__init__(df_orders, start_date, rotations, strategy="edd")

        # --- Ligne 1 : réutilise les variables du parent ---
        self.current_time_1          = self.current_time
        self.last_family_1           = self.last_family
        self.last_order_id_1         = self.last_order_id
        self.last_maintenance_date_1 = self.last_maintenance_date

        # --- Ligne 2 : variables dédiées ---
        self.current_time_2          = start_date + timedelta(hours=12)
        self.last_family_2           = None
        self.last_order_id_2         = None
        self.last_maintenance_date_2 = start_date

        # Setup initial compté pour les 2 lignes
        self.total_setup_hours = 24

        # Redéfinir la stratégie sur la nouvelle méthode
        self._find_next_order = self.batching_2lines

    # ------------------------------------------------------------------
    # Overrides des helpers pour prendre `line` en paramètre
    # ------------------------------------------------------------------

    def _advance_time(self, line, new_date=None):
        # Compatibilité avec l'appel parent _advance_time(new_date)
        if new_date is None:
            new_date, line = line, 1

        if line == 1:
            if new_date > self.current_time_1:
                self.total_idle_hours += (new_date - self.current_time_1).total_seconds() / 3600
                self.current_time_1 = new_date
        else:
            if new_date > self.current_time_2:
                self.total_idle_hours += (new_date - self.current_time_2).total_seconds() / 3600
                self.current_time_2 = new_date

    def _apply_setup(self, line, new_family=None):
        # Compatibilité avec l'appel parent _apply_setup(new_family)
        if new_family is None:
            new_family, line = line, 1

        if line == 1:
            if self.last_family_1 is not None and new_family != self.last_family_1:
                self.current_time_1 += timedelta(hours=12)
                self.total_setup_hours += 12
            self.last_family_1 = new_family
        else:
            if self.last_family_2 is not None and new_family != self.last_family_2:
                self.current_time_2 += timedelta(hours=12)
                self.total_setup_hours += 12
            self.last_family_2 = new_family

    def _check_maintenance(self, line=1):
        if line == 1:
            if (self.current_time_1 - self.last_maintenance_date_1).days >= 84:
                self.current_time_1 += timedelta(hours=24)
                self.last_maintenance_date_1 = self.current_time_1
                self.maintenance_count += 1
        else:
            if (self.current_time_2 - self.last_maintenance_date_2).days >= 84:
                self.current_time_2 += timedelta(hours=24)
                self.last_maintenance_date_2 = self.current_time_2
                self.maintenance_count += 1

    # ------------------------------------------------------------------
    # Override de metrics et calculate_lower_bound
    # ------------------------------------------------------------------

    def metrics(self):
        # Synchronise current_time du parent avec le max des 2 lignes
        self.current_time = max(self.current_time_1, self.current_time_2)
        return super().metrics()

    def calculate_lower_bound(self):
        df = self.df_initial.copy()

        total_prod_hours = sum((df['QTY'] / df['Average per Day']) * 24)
        num_families     = df['Family'].nunique()
        min_setup_hours  = (num_families - 1) * 12

        earliest_start = df['Order Confirmed Date'].min()
        lb_end         = earliest_start + timedelta(hours=(total_prod_hours / 2) + min_setup_hours)
        lb_cmax_days   = (lb_end - earliest_start).total_seconds() / 86400

        print(f"Temps total production   : {total_prod_hours/24:.1f} j (÷2 lignes = {total_prod_hours/2/24:.1f} j)")
        print(f"Nb familles              : {num_families}")
        print(f"Setups minimaux          : {num_families-1} × 12h = {min_setup_hours/24:.1f} jours")
        print(f"LB Cmax (2 lignes)       : {lb_cmax_days:.1f} jours")

        return round(lb_cmax_days, 2)

    # ------------------------------------------------------------------
    # Override de process_scheduling pour gérer 2 lignes
    # ------------------------------------------------------------------

    def process_scheduling(self, orders_df):
        pending_orders = orders_df.to_dict('records')
        while pending_orders:
            # Ligne disponible le plus tôt
            line = 1 if self.current_time_1 <= self.current_time_2 else 2

            self._check_maintenance(line)
            idx = self._find_next_order(pending_orders, line)
            if idx is None:
                break
            order = pending_orders.pop(idx)
            self._apply_setup(line, order['Family'])
            self._produce(order, line)
        return self.metrics()

    # ------------------------------------------------------------------
    # Override de _produce pour gérer 2 lignes
    # ------------------------------------------------------------------

    def _produce(self, order, line=1):
        current_time   = self.current_time_1 if line == 1 else self.current_time_2
        start_prod     = current_time
        duration_hours = (order['QTY'] / order['Average per Day']) * 24
        end_prod       = current_time + timedelta(hours=duration_hours)
        delay          = max(0, (end_prod - order['Expected Delivery Date']).total_seconds() / 86400)

        if line == 1:
            self.current_time_1  = end_prod
            self.last_order_id_1 = order['Order ID']
        else:
            self.current_time_2  = end_prod
            self.last_order_id_2 = order['Order ID']

        self.cmax = max(
            (self.current_time_1 - datetime(2025, 1, 7, 0, 0)).total_seconds() / 86400,
            (self.current_time_2 - datetime(2025, 1, 7, 0, 0)).total_seconds() / 86400,
        )

        self.total_delay_days += delay
        if delay > 0:
            self.late_orders_count += 1
        self.last_order_id = order['Order ID']

        self.schedule.append({
            'OrderID':    order['Order ID'],
            'Family':     order['Family'],
            'Line':       line,
            'Start':      start_prod,
            'End':        end_prod,
            'Due_Date':   order['Expected Delivery Date'],
            'Delay_Days': round(delay, 2),
        })

    # ------------------------------------------------------------------
    # Heuristique : Batching 2 Lines
    # ------------------------------------------------------------------

    def batching_2lines(self, pending_orders, line):
        last_family  = self.last_family_1  if line == 1 else self.last_family_2
        current_time = self.current_time_1 if line == 1 else self.current_time_2

        while True:
            if not pending_orders:
                return None

            allowed   = list(self.rotations) if last_family is None else self.rotations.get(last_family, [])
            confirmed = [o for o in pending_orders if o['Order Confirmed Date'] <= current_time]
            ready     = [o for o in confirmed if o['Family'] in allowed]

            if ready:
                same_family = [o for o in ready if o['Family'] == last_family]
                if same_family:
                    same_family.sort(key=lambda x: x['Expected Delivery Date'])
                    target_id = same_family[0]['Order ID']
                else:
                    family_counts = Counter(o['Family'] for o in ready)
                    ready.sort(key=lambda x: (-family_counts[x['Family']], x['Expected Delivery Date']))
                    target_id = ready[0]['Order ID']

                return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)

            # Aucune commande prête → avancer jusqu'à la prochaine confirmation
            future = [o for o in pending_orders if o['Family'] in allowed]
            if not future:
                if line == 1:
                    self.last_family_1 = None
                else:
                    self.last_family_2 = None
                last_family = None
                continue

            next_confirm = min(future, key=lambda x: x['Order Confirmed Date'])['Order Confirmed Date']
            if next_confirm <= current_time:
                # Sécurité anti-boucle infinie
                if line == 1:
                    self.last_family_1 = None
                else:
                    self.last_family_2 = None
                last_family = None
                continue

            self._advance_time(line, next_confirm)
            current_time = self.current_time_1 if line == 1 else self.current_time_2