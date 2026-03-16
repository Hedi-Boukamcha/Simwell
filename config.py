
# Chemins
OUTPUT_PATH = "results/Solution_Ordonnancement.xlsx"

# Paramètres de temps (en heures)
SETUP_TIME = 12
MAINTENANCE_DURATION = 24
MAINTENANCE_INTERVAL_DAYS = 84

# Matrice de rotation
ROTATION = {
'A': ['A', 'P', 'H'],
'P': ['P', 'A'],
'H': ['H', 'F'],
'F': ['F', 'V', 'M', 'N', 'E', 'C', 'A'],
'C': ['C', 'A'],
'E': ['E', 'A'], 
'N': ['N', 'A'], 
'M': ['M', 'A'], 
'V': ['V', 'A']
}