from datetime import datetime, timedelta
import pandas as pd


class SimwellScheduler:
    def __init__(self,df_orders, start_date, rotations):
        self.df_initial = df_orders
        self.current_time = start_date
        self.rotations = rotations
        self.setup_time = 12
        self.last_family = None
        self.last_order_id = None
        self.last_maintenance_date = start_date
        self.all_orders = df_orders.to_dict('records')
        self.schedule = []
        
        ## Initialisation des compteurs
        # Au lieu de commencer à 00h00, on commence à 12h00 pour simuler le setup de démarrage
        self.current_time = start_date + timedelta(hours=12)
        self.total_setup_hours = 0
        self.total_setup_hours += 12

        self.total_delay_days = 0
        self.total_idle_hours = 0
        self.maintenance_count = 0
    
    def solution(self):
        """
        Transforme la liste des résultats en DataFrame Pandas et calcule les metrics finaux.
        """
        if not self.schedule:
            return pd.DataFrame()
            
        return pd.DataFrame(self.schedule)

    def metrics(self):
        nb_commandes = len(self.schedule)
        retard_moyen = round(self.total_delay_days / nb_commandes, 2) if nb_commandes > 0 else 0
        borne_inf_heures = self.calculate_lower_bound()
        return {
            "Date de fin totale (j)": self.current_time,
            "Nombre de commandes traitées": nb_commandes,
            "Retard total (j)": round(self.total_delay_days, 2),
            "Date de fin minimale (j)": round(borne_inf_heures, 2),
            "Nombre de setups effectués": self.total_setup_hours // self.setup_time,
            "Temps de setup total (h)": self.total_setup_hours,
            "Nombre de maintenances": self.maintenance_count,
            "Retard Moyenne par commande (j)": retard_moyen
        }
    
    def calculate_lower_bound(self):
        df = self.df_initial
        # LB = Date de début + Somme(Temps de production) + Nbr Setups minimums (9 famille = 9 setups et temps de setup min 9 * 12h = 108h)
        # 1. Somme pure de la production
        total_processing_time_hours = sum((df['QTY'] / df['Average per Day']) * 24)
        
        # 2. Minimum de setups (un par famille présente dans les données)
        num_families = df['Family'].nunique()
        min_setup_hours = num_families * self.setup_time
        
        # 3. Borne inférieure Cmax (en heures depuis le début)
        lb_hours = total_processing_time_hours + min_setup_hours
        return lb_hours

    def _find_next_order(self, pending_orders):
        while True:
            # 1. Déterminer les familles autorisées
            if self.last_family is None:
                allowed = list(self.rotations)
            else:
                allowed = self.rotations.get(self.last_family, [])

            #liste des commandes en attente
            confirmed = [o for o in pending_orders if o['Order Confirmed Date'] <= self.current_time]

            # 2. Filtrer les commandes prêtes ET autorisées
            ready = [o for o in confirmed if o['Family'] in allowed]


            if ready:
                # On trie par EDD (Date de livraison prévue)
                ready.sort(key=lambda x: x['Expected Delivery Date'])
                # On retourne l'index original dans pending_orders
                #chosen = ready[0]
                #print(f"---[SÉLECTION] Commande ID: {chosen['Order ID']} ({chosen['Family']}) choisie.")
                #print(f"(Raison : Autorisée par {self.last_family} et EDD la plus proche)")
                target_id = ready[0]['Order ID']
                return next(i for i, o in enumerate(pending_orders) if o['Order ID'] == target_id)

            if confirmed:
                print(f"\n ---[BLOCAGE ROTATION]")
                print(f"   Dernière commande terminée : ID {self.last_order_id} (Famille: {self.last_family})")
                print(f"Familles autorisées ensuite : {allowed}")
                
                # On affiche les familles qui attendent mais sont interdites
                waiting_families = set(o['Family'] for o in confirmed)
                print(f"Commandes en attente (INTERDITES) : {list(waiting_families)}")
                
                # Détail des premières commandes bloquées pour le debug
                for o in confirmed:
                    print(f"- ID: {o['Order ID']} (Famille: {o['Family']})")
                print(" La machine reste à l'arrêt pour respecter la rotation...")

            # 3. Si rien n'est prêt, on cherche la date de la PROCHAINE commande autorisée
            future = [o for o in pending_orders if o['Family'] in allowed]
            
            if not future:
                # Cas critique : aucune des commandes restantes n'est autorisée par la rotation !
                print(f"---[FIN DE ROTATION]: Plus aucune commande possible pour les familles {allowed} dans tout le fichier.")
                self.last_family = None # On reset car c'est la fin de vie des commandes autorisées
                continue

            # On trouve la commande précise qui arrive le plus tôt
            next_order = min(future, key=lambda x: x['Order Confirmed Date'])
            next_event = next_order['Order Confirmed Date']
            wait_duration = (next_event - self.current_time).total_seconds() / 3600
            # Avancer le temps au prochain événement possible
            print(f"---[ATTENTE] La machine s'arrête")
            print(f"Prochain événement : Arrivée de l'ID {next_order['Order ID']} (Famille: {next_order['Family']}) prévue le {next_event}")            
            self._advance_time(next_event)
            # La boucle 'while True' va maintenant recommencer avec le nouveau self.current_time
        
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
        duration_hours = (order['QTY'] / order['Average per Day']) * 24
        
        self.current_time += timedelta(hours=duration_hours)
        end_prod = self.current_time
        
        # Calcul du retard en jours
        delay = max(0, (end_prod - order['Expected Delivery Date']).total_seconds() / 86400)
        self.total_delay_days += delay
        self.last_order_id = order['Order ID']

        self.schedule.append({
            'OrderID': order['Order ID'],
            'Family': order['Family'],
            'Start': start_prod,
            'End': end_prod,
            'Due_Date': order['Expected Delivery Date'],
            'Delay_Days': round(delay, 2)
        })

    # Approche de resolution 1: EDD pur     
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

        return self.metrics()

 