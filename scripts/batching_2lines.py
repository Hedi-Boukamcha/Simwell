from datetime import datetime, timedelta
from collections import Counter
from scripts.solve import SimwellScheduler

TRANSIT_PATH = ['A', 'H', 'F']
VMENC        = {'V', 'M', 'E', 'N', 'C'}
URGENCY_THRESHOLD = 14

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

    def __init__(self, df_orders, start_date, rotations, alpha=0.5):
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
        self.alpha = alpha

        self.last_produced_family_1 = None
        self.last_produced_family_2 = None

        # Setup initial compté pour les 2 lignes
        self.total_setup_hours = 24

        # Redéfinir la stratégie sur la nouvelle méthode
        self._find_next_order = self.batching_2lines



 #------------------------------------------------------------------
    # Transit fixe : trouver la prochaine étape du chemin A→H→F
    # ------------------------------------------------------------------
 
    def _next_transit_step(self, last_family, pending_orders, current_time, line):
        """
        Retourne la prochaine famille cible selon le chemin fixe :
        X → A → (P → A) → H → F → VMENC
 
        Règles :
        - Si on est sur A : vérifier P disponible → switcher vers P
          Quitter A vers H seulement si P vide ET pas de A urgentes
        - Si on est sur P : retourner vers A obligatoirement
        - Si on est sur H : aller vers F
        - Si on est sur F : aller vers VMENC (batch le plus grand + EDD)
        - Sinon (V/M/E/N/C/autre) : aller vers A (début du chemin)
        """
        pending_families = {o['Family'] for o in pending_orders}
 
        if last_family == 'A':
            # Vérifier si P disponible/confirmé
            p_orders = [o for o in pending_orders
                        if o['Family'] == 'P' and o['Order Confirmed Date'] <= current_time]
            if p_orders:
                return 'P'
 
            # Vérifier si des A urgentes restent
            a_remaining = [o for o in pending_orders if o['Family'] == 'A']
            urgent_a = [o for o in a_remaining
                        if (o['Expected Delivery Date'] - current_time).days <= URGENCY_THRESHOLD]
            if urgent_a:
                return 'A'  # rester sur A pour finir les urgentes
 
            # Plus de P ni de A urgentes → avancer vers H
            if 'H' in pending_families:
                return 'H'
            return 'F' if 'F' in pending_families else self._any_available(pending_orders)
 
        elif last_family == 'P':
            # Après P → retour A obligatoire
            if 'A' in pending_families:
                return 'A'
            return 'H' if 'H' in pending_families else 'F'
 
        elif last_family == 'H':
            return 'F' if 'F' in pending_families else self._any_available(pending_orders)
 
        elif last_family == 'F':
            # Après F → forcer VMENC (famille la plus représentée + EDD)
            vmenc_orders = [o for o in pending_orders if o['Family'] in VMENC]
            if vmenc_orders:
                family_counts = Counter(o['Family'] for o in vmenc_orders)
                best = max(family_counts, key=lambda f: (
                    family_counts[f],
                    -min(o['Expected Delivery Date'].timestamp()
                         for o in vmenc_orders if o['Family'] == f)
                ))
                return best
            return self._any_available(pending_orders)
 
        else:
            # Famille quelconque (V/M/E/N/C) → retour vers A
            return 'A' if 'A' in pending_families else 'H'
 
    def _any_available(self, pending_orders):
        """Retourne n'importe quelle famille encore disponible (dernier recours)."""
        families = {o['Family'] for o in pending_orders}
        # Priorité : A > H > F > reste
        for f in ['A', 'H', 'F']:
            if f in families:
                return f
        return next(iter(families), None)

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

    # Dans _apply_setup
    def _apply_setup(self, line, new_family=None):
        last_produced = self.last_produced_family_1 if line == 1 else self.last_produced_family_2
        
        if last_produced is not None and new_family != last_produced:
            if line == 1:
                self.current_time_1 += timedelta(hours=12)
            else:
                self.current_time_2 += timedelta(hours=12)
            self.total_setup_hours += 12

        # Mettre à jour les deux variables
        if line == 1:
            self.last_family_1 = new_family
            self.last_produced_family_1 = new_family
        else:
            self.last_family_2 = new_family
            self.last_produced_family_2 = new_family

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
        processing_time_hour = (order['QTY'] / order['Average per Day']) * 24
        duration_hours = processing_time_hour if line == 1 else processing_time_hour * self.alpha
        end_prod       = current_time + timedelta(hours=processing_time_hour)
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
                # ── Règle 1 : après F → forcer VMENC (batch + EDD) ──
                if last_family == 'F':
                    vmenc_ready = [o for o in ready if o['Family'] in VMENC]
                    if vmenc_ready:
                        family_counts = Counter(o['Family'] for o in vmenc_ready)
                        vmenc_ready.sort(key=lambda x: (-family_counts[x['Family']], x['Expected Delivery Date']))
                        target_id = vmenc_ready[0]['Order ID']
                        return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)
                    # Aucune VMENC confirmée → logique normale
  
                # ── Règle 2 : sur A → vérifier P urgent ──
                if last_family == 'A':
                    p_ready = [o for o in ready if o['Family'] == 'P']
                    if p_ready:
                        p_ready.sort(key=lambda x: x['Expected Delivery Date'])
                        target_id = p_ready[0]['Order ID']
                        return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)

                same_family = [o for o in ready if o['Family'] == last_family]
                if same_family:
                    same_family.sort(key=lambda x: x['Expected Delivery Date'])
                    target_id = same_family[0]['Order ID']
                    return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)

                family_counts = Counter(o['Family'] for o in ready)
                ready.sort(key=lambda x: (-family_counts[x['Family']], x['Expected Delivery Date']))
                target_id = ready[0]['Order ID']
                return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)

            # Aucune commande prête → avancer jusqu'à la prochaine confirmation
            future = [o for o in pending_orders if o['Family'] in allowed]
            if not future:
                # Chemin de transit fixe : trouver la prochaine étape
                next_step = self._next_transit_step(last_family, pending_orders, current_time, line)
                if next_step is None:
                    return None  # plus rien à faire
                if line == 1:
                    self.last_family_1 = next_step
                else:
                    self.last_family_2 = next_step
                last_family = next_step
                # Attendre la prochaine confirmation de next_step
                step_orders = [o for o in pending_orders if o['Family'] == next_step]
                if step_orders:
                    next_confirm = min(step_orders, key=lambda x: x['Order Confirmed Date'])['Order Confirmed Date']
                    if next_confirm > current_time:
                        self._advance_time(line, next_confirm)
                        current_time = self.current_time_1 if line == 1 else self.current_time_2
                continue

            # Des commandes existent mais pas encore confirmées → avancer le temps
            next_confirm = min(future, key=lambda x: x['Order Confirmed Date'])['Order Confirmed Date']
            if next_confirm <= current_time:
                # Sécurité anti-boucle : forcer le transit
                next_step = self._next_transit_step(last_family, pending_orders, current_time, line)
                if next_step and next_step != last_family:
                    if line == 1:
                        self.last_family_1 = next_step
                    else:
                        self.last_family_2 = next_step
                    last_family = next_step
                else:
                    # Vraiment bloqué → idle jusqu'à next_confirm
                    self._advance_time(line, next_confirm + timedelta(seconds=1))
                    current_time = self.current_time_1 if line == 1 else self.current_time_2
                continue

            self._advance_time(line, next_confirm)
            current_time = self.current_time_1 if line == 1 else self.current_time_2