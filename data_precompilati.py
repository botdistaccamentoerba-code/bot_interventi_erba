# data_precompilati.py

# Elenco precompilato personale VVF
PERSONALE_PRECOMPILATO = [
    {
        'nome': 'Mario Rossi',
        'qualifica': 'VV',
        'patente': 'IIIE',
        'nautica': True,
        'saf': True,
        'tpss': False,
        'squadra_notturna': 'A',
        'squadra_serale': 'B', 
        'squadra_domenicale': 'C'
    },
    {
        'nome': 'Luca Bianchi',
        'qualifica': 'VV',
        'patente': 'III',
        'nautica': False,
        'saf': False,
        'tpss': True,
        'squadra_notturna': 'B',
        'squadra_serale': 'C',
        'squadra_domenicale': 'A'
    },
    {
        'nome': 'Giuseppe Verdi',
        'qualifica': 'CSV',
        'patente': 'II',
        'nautica': True,
        'saf': True,
        'tpss': True,
        'squadra_notturna': 'C',
        'squadra_serale': 'A',
        'squadra_domenicale': 'B'
    },
    {
        'nome': 'Andrea Romano',
        'qualifica': 'VV',
        'patente': 'I',
        'nautica': False,
        'saf': False,
        'tpss': False,
        'squadra_notturna': 'A',
        'squadra_serale': 'B',
        'squadra_domenicale': 'C'
    },
    {
        'nome': 'Francesco Esposito',
        'qualifica': 'CSV',
        'patente': 'IIIE',
        'nautica': True,
        'saf': True,
        'tpss': False,
        'squadra_notturna': 'B',
        'squadra_serale': 'C',
        'squadra_domenicale': 'A'
    },
    # Aggiungi altri vigili secondo le tue esigenze
]

# Elenco precompilato mezzi VVF
MEZZI_PRECOMPILATI = [
    {'targa': '26613', 'modello': 'APS 160E4'},
    {'targa': '24674', 'modello': 'ABP Daf'},
    {'targa': '26690', 'modello': 'A/TRID ML120E'},
    {'targa': '23377', 'modello': 'CA/PU Defender'},
    {'targa': '29471', 'modello': 'CA/PU Ranger'},
    {'targa': '04901', 'modello': 'RI Humbaur'},
    {'targa': '04020', 'modello': 'FB Arimar'},
    # Aggiungi altri mezzi secondo le tue esigenze
]

# Tipologie intervento predefinite
TIPOLOGIE_INTERVENTO = [
    "Incendio abitazione",
    "Incendio boschivo", 
    "Incendio autovettura",
    "Incidente stradale",
    "Soccorso persona",
    "Esercitazione",
    "Allagamento",
    "Fuoriuscita gas",
    "Recupero animali",
    "Ricerca persona",
    "Incendio capannone",
    "Albero pericolante",
    "Soccorso in acqua",
    "Altro"
]
