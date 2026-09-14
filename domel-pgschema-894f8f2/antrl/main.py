import sys
import os
import json
import re
from antlr4 import *

from pgsLexer import pgsLexer
from pgsParser import pgsParser

from translatorDefRev import PGSchemaToJsonVisitor
from exportDefRev import convert_internal_representation_to_pgschema_dict, dump_pgschema

def main():
    input_file = "input.pgs"

    if len(sys.argv) < 2:
        print("Error: Unspecified file")
        return
    
    input_file = sys.argv[1]

    if not os.path.exists(input_file):
        print("Error: No such file")
        return
    
    #logica di ANTLR - preprocessing
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    def auto_fix_graph_name(match):
        safe_name = match.group(1).strip().replace(" ", "_")
        return f"CREATE GRAPH TYPE {safe_name} {match.group(2)}"
    
    # Cerca "CREATE GRAPH TYPE <qualsiasi_cosa> STRICT/LOOSE" e applica la funzione
    raw_text = re.sub(r'(?i)CREATE\s+GRAPH\s+TYPE\s+(.*?)\s+(STRICT|LOOSE)', auto_fix_graph_name, raw_text)

    pattern = r'([a-zA-Z0-9_]+)\s*\\\/\s*([a-zA-Z0-9_]+)'
    replacement = r'\1 | \2 | (\1 & \2)'
    processed_text = re.sub(pattern, replacement, raw_text)

    #taglio dei vincoli
    clean_code, constraints_str = extract_constraints(processed_text)
    #print(f"{clean_code}")
    input_stream = InputStream(clean_code)

    #input_stream = InputStream(processed_text) # Sostituito FileStream con InputStream che legge il testo elaborato
    # --------------------------------------
    
    lexer = pgsLexer(input_stream) #definisce i token e applica le regole di base (Es. eliminare spazi)
    stream = CommonTokenStream(lexer) #crea un "buffer" con i token definiti dal lexer

    parser = pgsParser(stream) #inizializza il parser
    tree = parser.pgs() #parser: legge i token e inizia a costruire l'albero dalla radice (pgs)

    if parser.getNumberOfSyntaxErrors() > 0:
        print("Found syntax errors.")
        return


    #print("\n------------ALBERO SINTATTICO------------\n")
    #print(tree.toStringTree(recog=parser))
    #print("\n------------------------------------------------\n")

    visitor = PGSchemaToJsonVisitor() #creo il visitor
    visitor.visit(tree)

    #riaggiunta dei vincoli
    if constraints_str:
        #print("\n---- VINCOLI----")
        #print(constraints_str)
        #print("------------------\n")

        parsed_constraints = parse_constraints_to_json(constraints_str)
        #visitor.json_schema["globalConstraints"] = parsed_constraints

        apply_property_constraints(visitor.json_schema, parsed_constraints, visitor.alias_table)
        apply_semantic_constraints(visitor.json_schema, parsed_constraints)

        #print("\n---- VINCOLI IN JSON----")
        #print(json.dumps(parsed_constraints, indent=4))
        #print("--------------------------\n")

    output = "output.json"
    with open(output, "w", encoding="utf-8") as file_json:
        json.dump(visitor.json_schema, file_json, indent=4)

    
    schema_dict = convert_internal_representation_to_pgschema_dict(visitor.json_schema)
    pg_schema_text = dump_pgschema(schema_dict)
    print(pg_schema_text)
    print("--------------------------\n")

    
    # Salvataggio del risultato in un nuovo file .pgs
    #output_exported_file = "output_exported.pgs"
    #with open(output_exported_file, "w", encoding="utf-8") as file_pgs:
     #   file_pgs.write(pg_schema_text)

    #print(json.dumps(visitor.json_schema, indent=4))


def extract_constraints(input_pgs_code):
    """
    Estrae i vincoli dal codice PGS inserito in input e restituisce il codice "pulito" per ANTLR.
    Restituisce: (clean_pgs_code, constraints_section)
    """

    #cerca in input_pgs_code, la prima occorrenza che corrisponde al pattern
    found_constraints = re.search(r'(,\s*)?(\bFOR\s+\(.*)', input_pgs_code, re.IGNORECASE | re.DOTALL)

    if found_constraints:
        constraints_block = found_constraints.group(2)

        last_brace = constraints_block.rfind('}') #rimuovo la graffa
        if last_brace != -1:
            constraints_block = constraints_block[:last_brace].strip()
        
        clean_pgs_code = input_pgs_code[:found_constraints.start()] + "\n}" #aggiungo la graffa di chiusura
        return clean_pgs_code, constraints_block
    
    return input_pgs_code, ""

def parse_constraints_to_json(constraints_block):

    constraints_list = []

    #separo i diversi blocchi FOR
    pattern = r'\bFOR\s*\(([^)]+)\)\s*(.*?)(?=\s*(?:,\s*)?\bFOR|$)'
    matches = re.finditer(pattern, constraints_block, re.IGNORECASE | re.DOTALL)

    for m in matches:
        context = m.group(1).strip() #es: x:persontype
        rule_str = m.group(2).strip() #es: EXCLUSIVE MANDATORY SINGLETON x.id


        #estraggo qualificatori
        qualifiers = []
        for q in ["EXCLUSIVE", "MANDATORY", "SINGLETON"]:
            if q in rule_str:
                qualifiers.append(q)
                rule_str = rule_str.replace(q, "").strip()
        
        #estraggo clausole
        target = ""
        within_clause = None
        where_clause = None
        
        if "WHERE" in rule_str:
            rule_str, where_str = rule_str.split("WHERE", 1)
            where_clause = where_str.strip()
            
        if "WITHIN" in rule_str:
            rule_str, within_str = rule_str.split("WITHIN", 1)
            within_clause = within_str.strip()
            
        target = rule_str.strip()
        if target.endswith(','): 
            target = target[:-1].strip()
            
        constraint_obj = {
            "context": context,
            "qualifiers": qualifiers,
            "target": target
        }
        if within_clause: constraint_obj["within"] = within_clause
        if where_clause: constraint_obj["where"] = where_clause
        
        constraints_list.append(constraint_obj)        
    return constraints_list 

def apply_property_constraints(json_schema, parsed_constraints, alias_table):
    """
    Applica i vincoli (identificatori, unicità e confronti di valori) alle proprietà dei nodi,
    leggendoli dalla lista dei vincoli parsati.
    """
    for constraint in parsed_constraints:
        quals = set(constraint.get("qualifiers", []))
        context = constraint.get("context", "")
        target_string = constraint.get("target", "")
        within_clause = constraint.get("within")
        
        # Se non c'è il contesto base (es. x:personType), saltiamo
        if not context or ":" not in context:
            continue
            
        ctx_var, raw_type = [part.strip() for part in context.split(":", 1)]
        clean_type = raw_type.lower().replace("type", "")

        # 1. Controlliamo se raw_type esiste come alias (es. "customertype")
        target_node_id = alias_table.get(raw_type.lower())
        def find_target_entity(schema, entity_id, entity_name):
            # 1. Cerca nei nodi
            for n in schema.get("nodes", []):
                if entity_id and n.get("id") == entity_id:
                    return n
                elif not entity_id and n.get("caption", "").lower() == entity_name:
                    return n
                    
            # 2. Cerca nelle relazioni
            for r in schema.get("relationships", []):
                if entity_id and r.get("id") == entity_id:
                    return r
                elif not entity_id and (r.get("type", "").lower() == entity_name or r.get("original_type_name", "").lower().replace("type", "") == entity_name):
                    return r
            return None
            
        target_node = find_target_entity(json_schema, target_node_id, clean_type)
        
        if not target_node:
            continue

        # =========================================================
        # CASO 1: Confronto matematico (es. x.salary >= 0)
        # =========================================================
        if not within_clause and any(op in target_string for op in ['>=', '<=', '>', '<', '=', '!=']):

            conditions = re.split(r'\s+AND\s+', target_string, flags=re.IGNORECASE)

            for condition in conditions:
                comp_match = re.search(r'^\s*(\w+)\.(\w+)\s*(>=|<=|>|<|=|!=)\s*(.+?)\s*$', condition)

                if comp_match:
                    tgt_var, prop_name, operator, value_str = comp_match.groups()

                    if ctx_var == tgt_var:
                        try:
                            parsed_value = float(value_str) if '.' in value_str else int(value_str)
                        except ValueError:
                            parsed_value = value_str.strip("'\"")

                        constraint_obj = {
                            "on": prop_name,
                            "type": "property_value",
                            "operator": operator,
                            "value": parsed_value
                        }
                        
                        if "constraints" not in target_node:
                            target_node["constraints"] = []
                        target_node["constraints"].append(constraint_obj)
                        
                        if "MANDATORY" in quals and prop_name in target_node.get("properties", {}):
                            target_node["properties"][prop_name]["requiredType"] = "required"
                            
        # =========================================================
        # CASO 2: Proprietà semplice (es. EXCLUSIVE x.id)
        # =========================================================
        elif "." in target_string and not within_clause:
            tgt_var, prop_name = [part.strip() for part in target_string.split(".", 1)]

            if ctx_var == tgt_var:
                is_exclusive = "EXCLUSIVE" in quals
                is_mandatory = "MANDATORY" in quals
                is_singleton = "SINGLETON" in quals
                
                properties = target_node.get("properties", {})
                if prop_name in properties:
                    if is_exclusive and is_mandatory and is_singleton:
                        properties[prop_name]["requiredType"] = "identifier"
                    elif is_exclusive:
                        properties[prop_name]["unique"] = True

        # =========================================================
        # CASO 3: È un vincolo senza punto (es. DISJOINT FROM)
        # =========================================================
        else:
            disjoint_match = re.search(r'\((\w+):\s*!(\w+)\)', target_string)

            if disjoint_match:
                tgt_var = disjoint_match.group(1)       # 'x'
                raw_disjoint_type = disjoint_match.group(2) # 'employeeType'
                
                if ctx_var == tgt_var and "MANDATORY" in quals:
                    clean_disjoint_type = raw_disjoint_type.lower().replace("type", "")
                    
                    # Usa la alias_table per trovare il nodo disgiunto
                    disjoint_node_id = alias_table.get(raw_disjoint_type.lower())
                    disjoint_node = find_target_entity(json_schema, disjoint_node_id, clean_disjoint_type)
                    
                    final_disjoint_caption = disjoint_node.get("caption") if disjoint_node else clean_disjoint_type.capitalize()
                    final_target_caption = target_node.get("caption", clean_type.capitalize())

                    constraint_obj = {
                        "type": "disjoint",
                        "node": final_disjoint_caption
                    }
                    
                    # 1. Aggiungiamo il vincolo al nodo
                    if "constraints" not in target_node:
                        target_node["constraints"] = []
                    if constraint_obj not in target_node["constraints"]:
                        target_node["constraints"].append(constraint_obj)
                        
                    # 2. Aggiungiamo il vincolo al nodo reciproco
                    if disjoint_node:
                        reciprocal_constraint = {
                            "type": "disjoint",
                            "node": final_target_caption
                        }
                        if "constraints" not in disjoint_node:
                            disjoint_node["constraints"] = []
                        if reciprocal_constraint not in disjoint_node["constraints"]:
                            disjoint_node["constraints"].append(reciprocal_constraint)

def apply_semantic_constraints(json_schema, parsed_constraints):
    for constraint in parsed_constraints:
        context_raw = constraint.get("context", "")
        
        if ":" not in context_raw:
            continue

        # nodo source
        ctx_var, raw_type = [p.strip() for p in context_raw.split(":", 1)]
        clean_source_type = raw_type.lower().replace("type", "")

        quals = constraint.get("qualifiers", [])
        within = constraint.get("within", "")
        where = constraint.get("where", "")

        # =======================
        # CASO 1: Uguaglianza
        # =======================
        if "MANDATORY" in quals and within and where and "=" in where:
            target_match = re.search(r'(\w+):\s*(\w+)', within)
            where_match = re.search(r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', where)
            
            if target_match and where_match:
                raw_target = target_match.group(2)
                v1, p1, v2, p2 = where_match.groups()
                
                source_prop = p1 if v1 == ctx_var else p2
                target_prop = p2 if v1 == ctx_var else p1
                
                # 1. Recuperiamo le caption REALI dal JSON per evitare errori con i nodi composti
                real_source_caption = raw_type.replace("type", "").capitalize() # Fallback
                real_target_caption = raw_target.replace("type", "").capitalize() # Fallback
                
                for node in json_schema.get("nodes", []):
                    orig_name = node.get("original_type_name", "").lower()
                    if orig_name == raw_type.lower():
                        real_source_caption = node.get("caption", "")
                    elif orig_name == raw_target.lower():
                        real_target_caption = node.get("caption", "")
                
                # 2. Costruiamo i vincoli usando le caption esatte
                constraint_obj_source = {
                    "on": source_prop,
                    "type": "equal",
                    "target": f"{real_target_caption}.{target_prop}"
                }

                constraint_obj_target = {
                    "on": target_prop,
                    "type": "equal",
                    "target": f"{real_source_caption}.{source_prop}"
                }
                
                # 3. Assegniamo i vincoli speculari ai nodi corretti
                for node in json_schema.get("nodes", []):
                    orig_name = node.get("original_type_name", "").lower()
                    
                    # Applichiamo al nodo source
                    if orig_name == raw_type.lower():
                        if "constraints" not in node:
                            node["constraints"] = []
                        if constraint_obj_source not in node["constraints"]:
                            node["constraints"].append(constraint_obj_source)
                            
                    # Applichiamo al nodo target speculare
                    elif orig_name == raw_target.lower():
                        if "constraints" not in node:
                            node["constraints"] = []
                        if constraint_obj_target not in node["constraints"]:
                            node["constraints"].append(constraint_obj_target)
                            
        # ==========================================
        # CASO 2: Cardinalità
        # ==========================================
        elif within and not where:
            rel_match = re.search(r'\[(?:\w+\s*)?:\s*([^\]]+)\]', within)            
            if rel_match:
                raw_rel_content = rel_match.group(1).strip() # Es: "friendType & Bestie?" o "responsibleType"
                
                if "&" in raw_rel_content:
                    parts = [p.strip() for p in raw_rel_content.split("&")]
                    base_rel = parts[0].lower().replace("type", "").capitalize()
                    target_prop = parts[1].replace("?", "").lower()
                else:
                    base_rel = raw_rel_content.lower().replace("type", "").capitalize()
                    target_prop = None
                
                if not target_prop:
                    # CASO A: Relazione Semplice
                    for rel in json_schema.get("relationships", []):
                        if rel.get("type", "").lower() == base_rel.lower():
                            if "SINGLETON" in quals:
                                rel["target_maximum_cardinality"] = 1
                            if "MANDATORY" in quals:
                                rel["target_minimum_cardinality"] = 1
                else:
                    # CASO B: Relazione Reificata
                    new_constraints = []
                    
                    if "SINGLETON" in quals:
                        new_constraints.append({
                            "type": "max_cardinality",
                            "limit": 1,
                            "attributes": ["source"]
                        })
                        
                    if "MANDATORY" in quals:
                        new_constraints.append({
                            "type": "min_cardinality",
                            "limit": 1,
                            "attributes": ["source"]
                        })
                        
                    if "EXCLUSIVE" in quals:
                        new_constraints.append({
                            "type": "max_cardinality",
                            "limit": 1,
                            "attributes": ["target"]
                        })

                    reified_node_caption = target_prop.capitalize()
                    
                    for c in new_constraints:
                        for node in json_schema.get("nodes", []):
                            if node.get("caption", "") == reified_node_caption:
                                if "constraints" not in node:
                                    node["constraints"] = []
                                if c not in node["constraints"]:
                                    node["constraints"].append(c)               
    return


if __name__ == '__main__':
    main()