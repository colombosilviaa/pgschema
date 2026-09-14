import os
import subprocess
import shutil

# Definiamo le cartelle
INPUT_DIR = "test_schemas"
OUTPUT_DIR = "test_results"

# Assicuriamoci che la cartella di output esista
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Trova tutti i file .pgs nella cartella di input
test_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".pgs")]

print(f"🚀 Trovati {len(test_files)} schemi da testare. Inizio elaborazione...\n")

for file_name in test_files:
    print(f"🔍--- Testando: {file_name} ---")
    input_path = os.path.join(INPUT_DIR, file_name)
    
    # Nomi dei file finali per questo specifico test
    base_name = file_name.replace(".pgs", "")
    json_output_path = os.path.join(OUTPUT_DIR, f"{base_name}_schema.json")
    pgs_output_path = os.path.join(OUTPUT_DIR, f"{base_name}_export.pgs")

    # 1. Esegui il traduttore (main.py)
    subprocess.run(["python", "main.py", input_path])
    
    generated_json = "output.json" 
    
    if os.path.exists(generated_json):
        # 2. Esegui l'esportatore passandogli come argomento il nome del JSON
        result = subprocess.run(["python", "exportDefRev.py", generated_json], capture_output=True, text=True)
        
        # 3. Salviamo l'output testuale dell'export in un file
        with open(pgs_output_path, "w") as f:
            f.write(result.stdout)
            
        # 4. Sposta e rinomina il JSON nella cartella dei risultati per non sovrascriverlo al prossimo giro
        shutil.move(generated_json, json_output_path)
            
        print(f"✔ JSON pronto per SchemaLink: {json_output_path}")
        print(f"✔ Export testuale salvato in: {pgs_output_path}\n")
    else:
        print(f"❌ ERRORE: Il file {generated_json} non è stato trovato!")

print("✅ Tutti i test completati! Vai nella cartella 'test_results' per vedere i file.")