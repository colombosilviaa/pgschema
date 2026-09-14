from typing import Dict, Any, List

PG_TYPES_MAP = {
    "string": "STRING", "integer": "INT", "int": "INT",
    "boolean": "BOOLEAN", "bool": "BOOLEAN", 
    "float": "FLOAT", "double": "DOUBLE", "date": "DATE"
}

def convert_internal_representation_to_pgschema_dict(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Trasforma il JSON interno in un dizionario strutturato per PG-Schema."""
    pg_schema_dict = {
        "name": graph.get("name", "UntitledGraph"),
        "mode": graph.get("graphTypeMode", "strict").upper(),
        "nodes": [], 
        "relationships": [],
        "constraints": []
    }
    
    nodes = graph.get("nodes", [])
    relationships = graph.get("relationships", [])

    id_to_node = {n["id"]: n for n in nodes if "id" in n}
    id_to_typename = {}

    for n in nodes:
        node_id = n.get("id")
        if not node_id: 
            continue
            
        caption = n.get("caption", "Unknown")
        orig_var = n.get("original_type_name")

        if not orig_var or orig_var == caption:
            id_to_typename[node_id] = caption
        else:
            id_to_typename[node_id] = orig_var

    node_parents = {} # id -> op, parents
    all_from_ids = set()
    all_to_ids = set()

    for rel in relationships:
        rel_type = rel.get("relationshipType")
        if rel_type in ("INHERITANCE", "EXCLUSIVE INHERITANCE"):
            from_id = rel.get("fromId") 
            to_id = rel.get("toId")     
            
            if from_id in id_to_node and to_id in id_to_node:
                all_from_ids.add(from_id)
                all_to_ids.add(to_id)

                if from_id not in node_parents:
                    op = "|" if rel_type == "EXCLUSIVE INHERITANCE" else "&"
                    node_parents[from_id] = {"operator": op, "targets": []}

                is_required = rel.get("required", True)
                node_parents[from_id]["targets"].append({"id": to_id, "required": is_required})

    seen_type_names = set()
    roots = [n for n in nodes if n.get("id") in all_from_ids and n.get("id") not in all_to_ids]
    others = [n for n in nodes if n not in roots]

    # NODES
    for node in roots + others:
        node_id = node.get("id")
        if not node_id or node.get("note") == "reified":
            continue

        type_name = id_to_typename.get(node_id, "Unknown")
        if type_name in seen_type_names:
            continue
            
        seen_type_names.add(type_name)
        caption_str = _resolve_inheritance(node_id, node_parents, id_to_typename, id_to_node)
        formatted_node = _format_single_node(node, caption_str, type_name)

        if formatted_node:
            pg_schema_dict["nodes"].append(formatted_node)

    # RELATIONSHIPS
    formatted_associations = _format_associations(relationships, nodes, id_to_typename)
    if formatted_associations:
        pg_schema_dict["relationships"].extend(formatted_associations)

    # CONSTRAINTS
    pg_schema_dict["constraints"] = _extract_constraints(nodes)

    return pg_schema_dict


def _format_single_node(node, caption_str: str, type_name: str):
    open_config = node.get("open")
    is_class_open = False
    is_props_open = False
    
    if isinstance(open_config, dict):
        is_class_open = open_config.get("class", False)
        is_props_open = open_config.get("properties", False)
        
    class_open = " OPEN" if is_class_open else ""
    props_str = _format_properties(node.get("properties", {}), is_props_open)
    
    return f"({type_name}: {caption_str}{class_open}{props_str})"

def _format_properties(properties_data: Dict[str, Any], is_props_open: bool = False):
    """Formatta le proprietà e i tipi di dato, gestendo clausola OPEN e OPTIONAL."""
    if not properties_data and not is_props_open:
        return ""
    
    props_list = []
    if properties_data:
        for k, v in properties_data.items():
            prop_type = v.get("range", "STRING").upper()
            mapped_type = PG_TYPES_MAP.get(prop_type.lower(), prop_type)
            
            opt_str = "OPTIONAL " if v.get("requiredType") == "optional" else ""
            props_list.append(f"{opt_str}{k} {mapped_type}")

    if is_props_open:
        props_list.append("OPEN")
        
    return " {" + ", ".join(props_list) + "}"

def _format_associations(relationships: list, nodes: list, id_to_typename: dict) -> list:
    grouped_assocs = {}
    formatted_rels = []

    # Archi semplici e provenienti da associazioni reificate
    for rel in relationships:
        if rel.get("relationshipType") != "ASSOCIATION":
            continue
            
        source_var = id_to_typename.get(rel.get("fromId"))
        target_var = id_to_typename.get(rel.get("toId"))
        
        if not source_var or not target_var:
            continue

        rel_type_name = rel.get("type", "unknown")
        current_props = rel.get("properties", {})
        
        # 1. Firma delle proprietà
        props_signature = tuple(sorted((k, v.get("range", "").lower(), v.get("requiredType", "optional"))
            for k, v in current_props.items()
        ))
        
        # 2. CHIAVE RIGIDA: separiamo ogni direttrice 1 a 1
        group_key = (source_var, target_var, rel_type_name, props_signature)
        if group_key not in grouped_assocs:
            grouped_assocs[group_key] = {
                "rel_typename": f"{rel_type_name.lower()}Type",
                "properties": {}, 
                "source": source_var,
                "target": target_var
            }
        
        if current_props:
            grouped_assocs[group_key]["properties"].update(current_props)

    for group_key, data in grouped_assocs.items():
        # 3. Estraiamo la sorgente e la destinazione specifiche dalla chiave
        source_var, target_var, rel_type_name, _ = group_key 
        properties = data["properties"]
        reified_types = []
        primitive_props = [] 
        
        if properties:
            for prop_name, prop_details in properties.items():
                range_val = prop_details.get("range", "").lower()
                is_optional = prop_details.get("requiredType") == "optional"
                
                if range_val not in PG_TYPES_MAP:
                    reified_types.append(f"{prop_name}?" if is_optional else prop_name)
                else:
                    pg_type = PG_TYPES_MAP[range_val]
                    opt_flag = "OPTIONAL" if is_optional else ""
                    primitive_props.append(f"{opt_flag} {prop_name} {pg_type}".strip())
        
        rel_label = " & ".join(reified_types) if reified_types else rel_type_name 
        props_str = f" {{{', '.join(primitive_props)}}}" if primitive_props else ""
        
        # 4. Stampiamo la singola relazione lineare senza |
        formatted_rels.append(f"(:{source_var})-[{data['rel_typename']}: {rel_label}{props_str}]->(:{target_var})")
        
    # Reified nodes
    node_map = {n["id"]: n for n in nodes}
    for node in nodes:
        if node.get("note") == "reified":
            node_id = node["id"]
            props = node.get("properties", {})
            
            source_range = props.get("source", {}).get("range")
            target_range = props.get("target", {}).get("range")
                
            source_var = next((n.get("original_type_name") for n in nodes if n.get("caption") == source_range), None)
            target_var = next((n.get("original_type_name") for n in nodes if n.get("caption") == target_range), None)
            if not source_var or not target_var:
                print(f"WARN: Missing source or target. Association skipped")
                continue
            rel_typename = node.get("original_type_name", f"{node.get('caption', 'unknown').lower()}Type")

            inh_parents = [r for r in relationships if r.get("relationshipType") == "INHERITANCE" and r.get("fromId") == node_id]
            inh_children = [r for r in relationships if r.get("relationshipType") == "INHERITANCE" and r.get("toId") == node_id]
            excl_children = [r for r in relationships if r.get("relationshipType") == "EXCLUSIVE INHERITANCE" and r.get("toId") == node_id]
            
            """primitive_props = []
            for p_key, p_val in props.items():
                if p_key in ["source", "target"]:
                    continue

                is_opt = p_val.get("requiredType") == "optional"
                pg_t = PG_TYPES_MAP.get(p_val.get("range", "").lower(), "STRING")
                opt_flag = "OPTIONAL " if is_opt else ""
                primitive_props.append(f"{opt_flag}{p_key} {pg_t}".strip())
                
            props_str = f" {{{', '.join(primitive_props)}}}" if primitive_props else ""

            # CASO A: XOR association (es: Activity -> Deposits|Withdraws)
            if len(excl_children) >= 2:
                children_labels = [node_map[r["fromId"]].get("caption", "") for r in excl_children if r["fromId"] in node_map]
                if len(children_labels) >= 2:
                    label = "|".join(sorted(children_labels))
                    formatted_rels.append(f"(:{source_var})-[{rel_typename}: {label}{props_str}]->(:{target_var})")
                continue
                
            # CASO B: Figlio in Ereditarietà (es: buddyType: friendType)
            if inh_parents:
                parent_node = node_map.get(inh_parents[0]["toId"])
                if parent_node:
                    rel_label = parent_node.get("original_type_name", f"{parent_node.get('caption', 'unknown').lower()}Type")
                    formatted_rels.append(f"(:{source_var})-[{rel_typename}: {rel_label}{props_str}]->(:{target_var})")
                continue
                
            # CASO C: Padre Base Reificato (es: friendType: Friend)
            if inh_children and not inh_parents:
                rel_label = node.get("caption", "Unknown")
                formatted_rels.append(f"(:{source_var})-[{rel_typename}: {rel_label}{props_str}]->(:{target_var})")
                continue
            """

            primitive_props = []
            reified_labels = [] # <--- 1. Aggiungiamo questa lista per salvare Knows e Likes
            
            for p_key, p_val in props.items():
                if p_key in ["source", "target"]:
                    continue

                range_val = p_val.get("range", "").lower()
                is_opt = p_val.get("requiredType") == "optional"
                
                # 2. Se il tipo non è nei primitivi, lo trattiamo come Label dell'AND!
                if range_val not in PG_TYPES_MAP:
                    reified_labels.append(f"{p_key}?" if is_opt else p_key)
                else:
                    pg_t = PG_TYPES_MAP.get(range_val, "STRING")
                    opt_flag = "OPTIONAL " if is_opt else ""
                    primitive_props.append(f"{opt_flag}{p_key} {pg_t}".strip())
                
            props_str = f" {{{', '.join(primitive_props)}}}" if primitive_props else ""

            # CASO A: XOR association (es: Activity -> Deposits|Withdraws)
            if len(excl_children) >= 2:
                children_labels = [node_map[r["fromId"]].get("caption", "") for r in excl_children if r["fromId"] in node_map]
                if len(children_labels) >= 2:
                    label = "|".join(sorted(children_labels))
                    formatted_rels.append(f"(:{source_var})-[{rel_typename}: {label}{props_str}]->(:{target_var})")
                continue
                
            # CASO B: Figlio in Ereditarietà (es: buddyType: friendType)
            if inh_parents:
                parent_node = node_map.get(inh_parents[0]["toId"])
                if parent_node:
                    rel_label = parent_node.get("original_type_name", f"{parent_node.get('caption', 'unknown').lower()}Type")
                    formatted_rels.append(f"(:{source_var})-[{rel_typename}: {rel_label}{props_str}]->(:{target_var})")
                continue
                
            # CASO C: Padre Base Reificato (es: friendType: Friend)
            if inh_children and not inh_parents:
                # 3. Assembliamo le label logiche se ci sono, altrimenti usiamo la caption!
                rel_label = " & ".join(reified_labels) if reified_labels else node.get("caption", "Unknown")
                formatted_rels.append(f"(:{source_var})-[{rel_typename}: {rel_label}{props_str}]->(:{target_var})")
                continue
    return formatted_rels

def _resolve_inheritance(node_id, node_parents, id_to_typename, id_to_node):
    """
    Risolve le espressioni di ereditarietà per un nodo.
    """
    if node_id in node_parents:
        op = node_parents[node_id]["operator"]
        targets = node_parents[node_id]["targets"]
        
        # Se l'operatore è "|", minimo due frecce se no ritorno nodo base
        if op == "|" and len(targets) < 2:
            return id_to_node.get(node_id, {}).get("caption", "Unknown")
        
        resolved_targets = []
        for target in targets:
            target_str = id_to_typename.get(target["id"], "Unknown")
            if not target["required"]:
                target_str += " ?"
            resolved_targets.append(target_str) 
        return f" {op} ".join(resolved_targets)
    else:
        # nodo base
        return id_to_node.get(node_id, {}).get("caption", "Unknown")

def _extract_constraints(nodes: List[Dict[str, Any]]) -> List[str]:
    generated_constraints = []
    for node in nodes:
        for prop_name, prop_data in node.get("properties", {}).items():
            if prop_data.get("requiredType") == "identifier":
                node_var = node.get("original_type_name", f"{node.get('caption', 'unknown').lower()}Type")
                
                alias = "x" #----> capire come gestirlo
                generated_constraints.append(f"FOR ({alias}:{node_var}) EXCLUSIVE MANDATORY SINGLETON {alias}.{prop_name}")       
    return generated_constraints


def dump_pgschema(pgs_schema: Dict[str, Any]) -> str:
    name = pgs_schema.get("name", "UntitledGraph")
    mode = pgs_schema.get("mode", "STRICT")

    nodes = pgs_schema.get("nodes", [])
    relationships = pgs_schema.get("relationships", [])
    constraints = pgs_schema.get("constraints", [])

    all_items = nodes + relationships + constraints
    
    output = []
    output.append(f"CREATE GRAPH TYPE {name} {mode} {{")
    
    if all_items:
        indented_elements = [f"    {e}" for e in all_items]
        output.append(",\n".join(indented_elements))
        
    output.append("}")
    return "\n".join(output)