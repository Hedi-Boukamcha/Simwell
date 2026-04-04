from datetime import datetime, timedelta
from collections import Counter, deque
from scripts.solve import SimwellScheduler

TRANSIT_PATH = ['A', 'H', 'F']
VMENC        = {'V', 'M', 'E', 'N', 'C'}
URGENCY_THRESHOLD = 5

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

    def __init__(self, df_orders, start_date, rotations, alpha):
        # Initialise toutes les variables communes via le parent
        super().__init__(df_orders, start_date, rotations, strategy="EDD")

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
 
            """# Vérifier si des A urgentes restent
            a_remaining = [o for o in pending_orders if o['Family'] == 'A']
            urgent_a = [o for o in a_remaining
                        if (o['Expected Delivery Date'] - current_time).days <= URGENCY_THRESHOLD]
            if urgent_a:
                return 'A'  # rester sur A pour finir les urgentes"""
 
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
            if 'H' in pending_families:
                return 'H'
            if 'F' in pending_families:
                return 'F'
            # Dernier recours : famille autorisée par la rotation
            allowed = self.rotations.get(last_family, [])
            for f in allowed:
                if f in pending_families:
                    return f
            return None
 
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

    
    def compute_setup_steps(self, from_family, to_family):
        """
        Retourne le nombre de setups nécessaires pour aller de from_family à to_family
        en respectant le graphe de rotation.
        """
        if from_family is None or from_family == to_family:
            return 0

        path = self.find_shortest_path(from_family, to_family)

        if not path:
            return 1  # fallback (sécurité)

        # nombre de transitions = nombre de setups
        return len(path) - 1
    
    def _apply_setup(self, line, new_family):
        if line == 1:
            last_family = self.last_produced_family_1
            current_time = self.current_time_1
        else:
            last_family = self.last_produced_family_2
            current_time = self.current_time_2

        # 🔥 calcul du nombre de setups nécessaires
        n_setups = self.compute_setup_steps(last_family, new_family)

        if n_setups > 0:
            setup_time = timedelta(hours=12 * n_setups)

            if line == 1:
                self.current_time_1 += setup_time
            else:
                self.current_time_2 += setup_time

            self.total_setup_hours += 12 * n_setups

        # mise à jour famille
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

        # Ligne 2 plus rapide grâce à alpha
        effective_l2 = total_prod_hours / 2 * self.alpha
        effective_l1 = total_prod_hours / 2
        lb_hours     = max(effective_l1, effective_l2) + min_setup_hours
 
        earliest_start = df['Order Confirmed Date'].min()
        lb_end         = earliest_start + timedelta(hours=lb_hours)
        lb_cmax_days   = (lb_end - earliest_start).total_seconds() / 86400
 
        print(f"Temps total production   : {total_prod_hours/24:.1f} j")
        print(f"Alpha ligne 2            : {self.alpha}")
        print(f"Nb familles              : {num_families}")
        print(f"Setups minimaux          : {num_families-1} × 12h = {min_setup_hours/24:.1f} j")
        print(f"LB Cmax (2 lignes)       : {lb_cmax_days:.1f} jours")
 
        return round(lb_cmax_days, 2)

    # ------------------------------------------------------------------
    # Override de process_scheduling pour gérer 2 lignes
    # ------------------------------------------------------------------
    
    def _select_line(self, family):
        """
        Sélectionne la ligne pour produire une commande de famille donnée.
        Priorité :
        1. Ligne qui produit déjà cette famille (complémentarité, pas de setup)
        2. Ligne qui autorise cette famille dans sa rotation
           → si les deux autorisent : celle qui finit le plus tôt
        3. Ligne la plus tôt disponible (fallback)
        """
        lf1 = self.last_produced_family_1
        lf2 = self.last_produced_family_2
 
        # Règle 1 : complémentarité — même famille en cours
        if lf1 == family and lf2 == family:
            return 1 if self.current_time_1 <= self.current_time_2 else 2
        if lf1 == family:
            return 1
        if lf2 == family:
            return 2
 
        # Règle 2 : rotation autorisée
        l1_allows = family in self.rotations.get(lf1, list(self.rotations)) if lf1 else True
        l2_allows = family in self.rotations.get(lf2, list(self.rotations)) if lf2 else True
 
        if l1_allows and l2_allows:
            return 1 if self.current_time_1 <= self.current_time_2 else 2
        if l1_allows:
            return 1
        if l2_allows:
            return 2
 
        # Règle 3 : fallback — ligne la plus tôt
        return 1 if self.current_time_1 <= self.current_time_2 else 2


    def process_scheduling(self, orders_df):
        pending_orders = orders_df.to_dict('records')

        # 🔥 Batch en cours par ligne
        self.current_batch_family_1 = None
        self.current_batch_family_2 = None

        while pending_orders:

            now = min(self.current_time_1, self.current_time_2)

            # ===========================================================
            # PRIORITÉ 0 — Continuer batch MAIS PAS BLOQUER L'AUTRE LIGNE
            # ===========================================================

            l1_batch = self.current_batch_family_1
            l2_batch = self.current_batch_family_2

            l1_ready = [
                o for o in pending_orders
                if l1_batch is not None
                and o["Family"] == l1_batch
                and o["Order Confirmed Date"] <= self.current_time_1
            ]

            l2_ready = [
                o for o in pending_orders
                if l2_batch is not None
                and o["Family"] == l2_batch
                and o["Order Confirmed Date"] <= self.current_time_2
            ]

            # 🔥 CAS 1 : les deux lignes ont un batch actif
            if l1_ready and l2_ready:
                line = 1 if self.current_time_1 <= self.current_time_2 else 2

            # 🔥 CAS 2 : une seule ligne a un batch actif
            elif l1_ready:
                # 👉 vérifier si l'autre ligne peut démarrer autre chose
                other_available = [
                    o for o in pending_orders
                    if o["Order Confirmed Date"] <= self.current_time_2
                    and o["Family"] != l1_batch
                ]

                if other_available:
                    line = 2  # 🔥 on utilise la 2ème ligne !
                else:
                    line = 1

            elif l2_ready:
                other_available = [
                    o for o in pending_orders
                    if o["Order Confirmed Date"] <= self.current_time_1
                    and o["Family"] != l2_batch
                ]

                if other_available:
                    line = 1
                else:
                    line = 2

            else:
                line = None  # → passer à logique normale

            # ===========================================================
            # 🔥 SINON → logique normale
            # ===========================================================
            if line is None:

                confirmed = [o for o in pending_orders if o["Order Confirmed Date"] <= now]

                if confirmed:
                    confirmed.sort(key=lambda x: x["Expected Delivery Date"])
                    family = confirmed[0]["Family"]

                    l1_family = self.last_produced_family_1
                    l2_family = self.last_produced_family_2

                    # Continuité
                    if l1_family == family and l2_family != family:
                        line = 1
                    elif l2_family == family and l1_family != family:
                        line = 2
                    elif l1_family == family and l2_family == family:
                        line = 1 if self.current_time_1 <= self.current_time_2 else 2
                    else:
                        # 🔥 nouvelle famille → UNE seule ligne
                        line = 1 if self.current_time_1 <= self.current_time_2 else 2

                else:
                    line = 1 if self.current_time_1 <= self.current_time_2 else 2

            # ===========================================================
            # Maintenance
            # ===========================================================
            self._check_maintenance(line)

            # ===========================================================
            # Sélection de la commande
            # ===========================================================
            idx = self._find_next_order(pending_orders, line)

            if idx is None:
                break

            order = pending_orders.pop(idx)

            # ===========================================================
            # 🔥 MAJ batch
            # ===========================================================
            if line == 1:
                if self.current_batch_family_1 is None:
                    self.current_batch_family_1 = order["Family"]
            else:
                if self.current_batch_family_2 is None:
                    self.current_batch_family_2 = order["Family"]

            # ===========================================================
            # Setup
            # ===========================================================
            self._apply_setup(line, order["Family"])

            # ===========================================================
            # Production
            # ===========================================================
            self._produce(order, line)

            # ===========================================================
            # 🔥 FIN DE BATCH
            # ===========================================================
            if line == 1:
                remaining = [o for o in pending_orders if o["Family"] == self.current_batch_family_1]
                if not remaining:
                    self.current_batch_family_1 = None
            else:
                remaining = [o for o in pending_orders if o["Family"] == self.current_batch_family_2]
                if not remaining:
                    self.current_batch_family_2 = None

        return self.metrics()



    # ------------------------------------------------------------------
    # Override de _produce pour gérer 2 lignes
    # ------------------------------------------------------------------

    def _produce(self, order, line=1):
        current_time   = self.current_time_1 if line == 1 else self.current_time_2
        start_prod     = current_time
        #processing_time_hour = (order['QTY'] / order['Average per Day']) * 24
        #duration_hours = processing_time_hour if line == 1 else processing_time_hour * self.alpha
        #end_prod = current_time + timedelta(hours=duration_hours)
        processing_time_hour = (order['QTY'] / order['Average per Day']) * 24

        duration_hours = processing_time_hour if line == 1 else processing_time_hour * self.alpha

        end_prod = current_time + timedelta(hours=duration_hours)
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
 
                # ── Règle 3 : continuer même famille (batch, pas de setup) ──
                same_family = [o for o in ready if o['Family'] == last_family]
                if same_family:
                    same_family.sort(key=lambda x: x['Expected Delivery Date'])
                    target_id = same_family[0]['Order ID']
                    return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)
 
                # ── Règle 4 : famille la plus représentée + EDD ──
                family_counts = Counter(o['Family'] for o in ready)
                ready.sort(key=lambda x: (-family_counts[x['Family']], x['Expected Delivery Date']))
                target_id = ready[0]['Order ID']
                return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)
 
            # ── Aucune commande prête dans les familles autorisées ──
            future = [o for o in pending_orders if o['Family'] in allowed]
 
            if not future:
                # ── Coordination inter-lignes : déblocage rotation ──
                # Comparer les familles des 2 lignes pour choisir
                # laquelle peut débloquer vers une famille disponible
                other_lf       = self.last_produced_family_2 if line == 1 else self.last_produced_family_1
                other_time     = self.current_time_2          if line == 1 else self.current_time_1
                pending_fam    = {o['Family'] for o in pending_orders}
 
                # Familles atteignables depuis chaque ligne (hors même famille)
                self_reach  = [f for f in self.rotations.get(last_family, []) if f in pending_fam and f != last_family]
                other_reach = [f for f in self.rotations.get(other_lf, list(self.rotations)) if f in pending_fam and f != other_lf] if other_lf else []
                target_family = self._next_transit_step(last_family, pending_orders, current_time, line)

                if self_reach:
                    # Ligne courante peut se débloquer seule → transit fixe
                    #next_step = self._next_transit_step(last_family, pending_orders, current_time, line)
                    next_step = self.get_next_family_via_path(last_family, target_family)
 
                elif other_reach and not self_reach:
                    # Seule l'autre ligne peut débloquer
                    # → les deux lignes autorisent ? → celle qui finit le plus tôt
                    # → sinon attendre que l'autre finisse et réessayer
                    if other_time > current_time:
                        self._advance_time(line, other_time)
                        current_time = self.current_time_1 if line == 1 else self.current_time_2
                    #next_step = self._next_transit_step(last_family, pending_orders, current_time, line)
                    next_step = self.get_next_family_via_path(last_family, target_family)
 
                else:
                    # Aucune ligne ne peut débloquer → transit fixe forcé
                    #next_step = self._next_transit_step(last_family, pending_orders, current_time, line)
                    next_step = self.get_next_family_via_path(last_family, target_family)
 
                if next_step is None:
                    return None
 
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
    
    def find_shortest_path(self, start, target):
        if start == target:
            return [start]
        visited = set()
        queue = deque([(start, [start])])
        while queue:
            current, path = queue.popleft()
            for neighbor in self.rotations.get(current, []):
                if neighbor == target:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None
    
    def get_next_family_via_path(self, last_family, target_family):
        """
        Retourne la prochaine famille à prendre pour aller vers target_family
        en respectant la rotation (sans produire les intermédiaires).
        """
        if last_family is None:
            return target_family
        path = self.find_shortest_path(last_family, target_family)
        if path and len(path) > 1:
            return path[1]  # prochaine étape seulement
        return target_family