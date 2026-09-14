import sys
import json
from exportDef2 import convert_internal_representation_to_pgschema_dict, dump_pgschema

# Controlla che sia stato passato il nome del file
if len(sys.argv) < 2:
    print("Uso: python test_export.py <nome_file.json>")
    sys.exit(1)

nome_file_json = sys.argv[1]

try:
    # Legge il file JSON passato da terminale
    with open(nome_file_json, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    # Converte e formatta
    pgschema_dict = convert_internal_representation_to_pgschema_dict(graph_data)
    testo_finale = dump_pgschema(pgschema_dict)

    # Stampa il risultato
    print("=== RISULTATO EXPORT ===")
    print(testo_finale)
    print("========================")

except FileNotFoundError:
    print(f"Errore: Il file '{nome_file_json}' non è stato trovato.")
except json.JSONDecodeError:
    print(f"Errore: Il file '{nome_file_json}' non è un JSON valido.")
except Exception as e:
    print(f"Si è verificato un errore durante l'export: {e}")