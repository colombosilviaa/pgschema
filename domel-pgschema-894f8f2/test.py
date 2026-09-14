import sys
from antlr4 import *
from antrl.pgsLexer import pgsLexer
from antrl.pgsParser import pgsParser

def main():
    # 1. Specifica il file da leggere (usa uno degli esempi)
    input_file = "examples/CatalogGraphType.pgs"
    
    try:
        # 2. Prepara il flusso di caratteri
        input_stream = FileStream(input_file, encoding='utf-8')
        
        # 3. Inizializza Lexer e Parser
        lexer = pgsLexer(input_stream)
        token_stream = CommonTokenStream(lexer)
        parser = pgsParser(token_stream)
        
        # 4. Avvia il parsing (usa la regola principale 'pgs')
        tree = parser.pgs()
        
        # 5. Se arriva qui senza errori, è tutto OK!
        print(f"✅ Analisi di '{input_file}' completata con successo!")
        # Stampa l'albero in formato testuale (opzionale)
        # print(tree.toStringTree(recog=parser))
        
    except Exception as e:
        print(f"❌ Errore durante il parsing: {e}")

if __name__ == '__main__':
    main()