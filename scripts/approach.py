from datetime import datetime, timedelta
import pandas as pd

class SimwellScheduler:
    def __init__(self, start_date, allowed_transitions):
        self.current_time = start_date
        self.allowed_transitions = allowed_transitions  # Dictionnaire des familles permises
        self.last_family = None
        self.last_maintenance_date = start_date
        self.schedule = []
        
        # Initialisation des compteurs pour le rapport final
        self.total_setup_hours = 0
        self.total_delay_days = 0
        self.maintenance_count = 0
    
    def solution(self):
        """
        Transforme la liste des résultats en DataFrame Pandas 
        et calcule les KPIs finaux.
        """
        if not self.schedule:
            return pd.DataFrame()
            
        return pd.DataFrame(self.schedule)

    def metrics(self):
        """
        Retourne un dictionnaire des indicateurs de performance (KPI).
        """
        return {
            "Date de fin totale": self.current_time,
            "Retard total (jours)": round(self.total_delay_days, 2),
            "Temps de setup total (h)": self.total_setup_hours,
            "Nombre de maintenances": self.maintenance_count,
            "Nombre de commandes traitées": len(self.schedule)
        }

    def process_scheduling(self, orders_df):
        """Boucle principale d'ordonnancement."""
        # On travaille sur une copie pour ne pas modifier l'original
        pending_orders = orders_df.to_dict('records')
        
        while pending_orders:
            # 1. Vérification de la maintenance (tous les 84 jours / 12 semaines)
            self._check_maintenance()
            
            # 2. Trouver la prochaine commande (Logique de réveil incluse)
            idx = self._find_next_order(pending_orders)
            
            if idx is None:
                # Si vraiment plus rien n'est possible (cas théorique)
                break
                
            # Extraire la commande
            order = pending_orders.pop(idx)
            
            # 3. Appliquer le Setup de 12h si changement de famille
            self._apply_setup(order['Family'])
            
            # 4. Produire
            self._produce(order)

        return self.get_summary_metrics()

    def _find_next_order(self, pending_orders):
        """Cherche le meilleur job prêt ou attend le prochain événement."""
        # Déterminer les familles autorisées (Contrainte Dure)
        if self.last_family is None:
            allowed = list(self.rotations.keys())
        else:
            allowed = self.rotations.get(self.last_family, [])

        # --- ÉTAPE 1 : Ce qui est prêt ET autorisé ---
        ready_and_allowed = [o for o in pending_orders 
                             if o['Family'] in allowed 
                             and o['Order Confirmed Date'] <= self.current_time]

        if ready_and_allowed:
            # Tri par urgence (EDD)
            ready_and_allowed.sort(key=lambda x: x['Expected Delivery Date'])
            # Retourner l'index dans la liste originale
            return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == ready_and_allowed[0]['Order ID'])

        # --- ÉTAPE 2 : Mode IDLE (Attente réactive) ---
        future_allowed = [o for o in pending_orders if o['Family'] in allowed]
        
        if not future_allowed:
            # Si aucune commande future n'est possible dans ce cycle, 
            # on doit chercher la toute prochaine commande n'importe où (fin de cycle forcée)
            pending_orders.sort(key=lambda x: x['Order Confirmed Date'])
            next_any = pending_orders[0]
            self._advance_time(next_any['Order Confirmed Date'])
            return self._find_next_order(pending_orders)

        # On avance le temps au moment de la prochaine confirmation autorisée
        next_wakeup = min(o['Order Confirmed Date'] for o in future_allowed)
        self._advance_time(next_wakeup)
        
        # On relance la recherche à la nouvelle heure (Ré-évaluation EDD)
        return self._find_next_order(pending_orders)

    def _advance_time(self, new_date):
        """Avance le temps et comptabilise l'inactivité."""
        if new_date > self.current_time:
            idle_delta = (new_date - self.current_time).total_seconds() / 3600
            self.total_idle_hours += idle_delta
            self.current_time = new_date

    def _apply_setup(self, new_family):
        """Applique 12h de setup si la famille change."""
        if self.last_family is not None and new_family != self.last_family:
            self.current_time += timedelta(hours=12)
            self.total_setup_hours += 12
        self.last_family = new_family

    def _check_maintenance(self):
        """Maintenance de 24h toutes les 12 semaines."""
        if (self.current_time - self.last_maintenance_date).days >= 84:
            self.current_time += timedelta(hours=24)
            self.last_maintenance_date = self.current_time
            self.maintenance_count += 1

    def _produce(self, order):
        """Calcule la fin de production et le retard."""
        start_prod = self.current_time
        duration_hours = (order['QTY'] / order['Average Per Day']) * 24
        
        self.current_time += timedelta(hours=duration_hours)
        end_prod = self.current_time
        
        # Calcul du retard en jours
        delay = max(0, (end_prod - order['Expected Delivery Date']).total_seconds() / 86400)
        self.total_delay_days += delay
        
        self.schedule.append({
            'OrderID': order['Order ID'],
            'Family': order['Family'],
            'Start': start_prod,
            'End': end_prod,
            'Due_Date': order['Expected Delivery Date'],
            'Delay_Days': round(delay, 2)
        })