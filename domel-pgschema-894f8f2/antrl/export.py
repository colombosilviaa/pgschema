from typing import Dict, Any, List

def convert_internal_representation_to_pgschema_dict(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Fase 1: Genero un dizionario."""

    pg_schema_dict = {
        "name": graph.get("name", "UntitledGraph"),
        "mode": graph.get("graphTypeMode", "strict").upper(),
        "elements": [] 
    }
    
    nodes = graph.get("nodes", [])
    relationships = graph.get("relationships", [])

    id_to_node = {n["id"]: n for n in nodes if "id" in n}
    #id_to_varname = {n["id"]: f"{n.get('caption', 'Unknown').lower()}Type" for n in nodes if "id" in n}
    id_to_varname = {n["id"]: n.get("original_var_name", f"{n.get('caption', 'Unknown').lower()}Type") for n in nodes if "id" in n}
    print(id_to_varname)

    parents = {}
    for rel in relationships:
        rel_type = rel.get("relationshipType")
        if rel_type in ("INHERITANCE", "EXCLUSIVE INHERITANCE"):
            from_id = rel.get("fromId") 
            to_id = rel.get("toId")     
            
            if from_id in id_to_node and to_id in id_to_node:
                if from_id not in parents:
                    op = "|" if rel_type == "EXCLUSIVE INHERITANCE" else "&"
                    parents[from_id] = {"parents": [], "operator": op}

                #salvo caption dei genitori
                parent_caption = id_to_node[to_id].get("caption", "")

                is_required = rel.get("required", True)
                if not is_required:
                    parent_caption += " ?"

                parents[from_id]["parents"].append(parent_caption)

    # Elaborazione Nodi: NESSUN FILTRO, stampiamo tutto!
    for node in nodes:
        node_id = node.get("id")
        parents_info = parents.get(node_id)
        formatted_node = _format_single_node(node, parents_info)
        if formatted_node:
            pg_schema_dict["elements"].append(formatted_node)

    # Elaborazione Relazioni: le INHERITANCE vengono comunque saltate
    for rel in relationships:
        if rel.get("relationshipType") in ("INHERITANCE", "EXCLUSIVE INHERITANCE"):
            continue
            
        formatted_rel = _format_single_rel(rel, id_to_varname)
        if formatted_rel:
            pg_schema_dict["elements"].append(formatted_rel)
                
    return pg_schema_dict

def _format_single_node(node, parents_info=None):
    """Formatta la riga del nodo base, ripristinando l'input originale"""
    if parents_info is None:
        parents_info = {"parents": [], "operator": "&"}

    caption = node.get("caption", "Unknown")
    original_var_name = node.get("original_var_name", "errore")

    parents = parents_info.get("parents", [])
    operator = parents_info.get("operator", "&")

    # Se ci sono label ereditate, ignoriamo la caption "Customer" creata 
    # dall'importatore e usiamo solo "Person & Athlete"
    if parents:
        join_str = f" {operator} "
        caption_str = join_str.join(parents)
    else:
        caption_str = caption

    open_config = node.get("open", {})
    is_class_open = open_config.get("class", False)
    is_props_open = open_config.get("properties", False)
    open_prop = " OPEN" if is_class_open else ""
    
    properties_dict = node.get("properties", {})
    props_str = _format_properties(properties_dict, is_props_open)
    
    return f"({original_var_name}: {caption_str}{open_prop}{props_str})"



def _format_properties(properties_data: Dict[str, Any], is_props_open: bool = False):
    """Mappa i tipi e gestisce OPTIONAL"""
    if not properties_data and not is_props_open:
        return ""
        
    type_mapping = {
        "string": "STRING", "integer": "INT", "int": "INT",
        "boolean": "BOOLEAN", "bool": "BOOLEAN", "float": "FLOAT", "double": "DOUBLE"
    }
    
    props_list = []
    if properties_data:
        for k, v in properties_data.items():
            prop_type = v.get("range", "STRING").upper()
            mapped_type = type_mapping.get(prop_type.lower(), prop_type)
            
            is_optional = v.get("requiredType") == "optional"
            opt_str = "OPTIONAL " if is_optional else ""
            
            props_list.append(f"{opt_str}{k} {mapped_type}")

    if is_props_open:
        props_list.append("OPEN")
        
    return " {" + ", ".join(props_list) + "}"


def _format_single_rel(rel, id_to_varname):
    rel_type = rel.get("type", "Unknown")

    var_name = f"{rel_type.lower()}Type"

    source_id = rel.get("fromId")
    target_id = rel.get("toId")

    source_var = id_to_varname.get(source_id, "unknownType")
    target_var = id_to_varname.get(target_id, "unknownType")

    properties_dict = rel.get("properties", {})
    props_str = _format_properties(properties_dict, False) # Di default gli archi non sono OPEN
    
    return f"(:{source_var})-[{var_name}: {rel_type}{props_str}]->(:{target_var})"



def dump_pgschema(pgs_schema: Dict[str, Any]) -> str:
    """Fase 2: Formatta l'output testuale."""
    name = pgs_schema.get("name", "UntitledGraph")
    mode = pgs_schema.get("mode", "STRICT")
    elements = pgs_schema.get("elements", [])
    
    output = []
    output.append(f"CREATE GRAPH TYPE {name} {mode} {{")
    
    if elements:
        indented_elements = [f"    {e}" for e in elements]
        output.append(",\n".join(indented_elements))
        
    output.append("}")
    return "\n".join(output)