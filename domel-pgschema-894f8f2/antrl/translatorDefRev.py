from pgsVisitor import pgsVisitor
import random

class PGSchemaToJsonVisitor(pgsVisitor):
    def __init__(self):
        super().__init__()
        self.node_counter = 0 
        self.rel_counter = 0

        self.json_schema = {
            "name": "Untitled schema",
            "graphTypeMode": "Strict",
            "nodes": [],
            "relationships": [],
            "style": global_style              
        }

        self.elem_table = {}
        self.alias_table = {}

        self.current_node_name = None  
        self.temp_abstract = False
        self.ignore_label_spec = False 

    def _generate_node_id(self):
        ident = f"n{self.node_counter}"
        self.node_counter += 1
        return ident

    def _generate_rel_id(self):
        ident = f"n{self.rel_counter}"
        self.rel_counter += 1
        return ident
    
    # ====================
    # GESTIONE DEL GRAFO
    # ====================
    def visitGraphType(self, ctx):
        if ctx.typeName(): 
            self.json_schema["name"] = ctx.typeName().getText().strip()
        
        if ctx.typeForm():
            form_text = ctx.typeForm().getText().strip().lower()
            if form_text == "loose":
                self.json_schema["graphTypeMode"] = "Loose"

        if ctx.graphTypeDefinition() and ctx.graphTypeDefinition().IMPORTS():
            if ctx.graphTypeDefinition().typeName():
                imported_schema = ctx.graphTypeDefinition().typeName().getText().strip()
                self.json_schema["imports"] = [imported_schema]
        
        self.visitChildren(ctx) 
        self._resolve_reified_constraints()
        self._build_final_json() 
            
        return self.json_schema
    
    # ====================
    # GESTIONE DEI NODI
    # ====================
    def visitCreateNodeType(self, ctx):
        if ctx.ABSTRACT():
            self.temp_abstract = True
        return self.visitChildren(ctx)

    def visitNodeType(self, ctx):
        if not ctx.typeName(): return self.visitChildren(ctx)
            
        raw_typename = ctx.typeName().getText().strip()
        clean_caption, clean_base, _ = self._parse_label(raw_typename)
        
        current_id = self._get_or_create_elem(raw_typename)
        self.current_node_id = current_id  
        
        node = self._get_node_by_id(current_id)
        if node:
            node["kind"] = "NODE"
            node["abstract"] = getattr(self, 'temp_abstract', False)

            node["original_type_name"] = raw_typename #TEST
            
        self.temp_abstract = False
        self.ignore_label_spec = True
        self.visitChildren(ctx)
        self.ignore_label_spec = False
        
        lbl_prop = ctx.labelPropertySpec()
        if lbl_prop and lbl_prop.labelSpec():
           
            right_nodes_info, is_xor = self._parse_node_label_spec(lbl_prop.labelSpec())
            right_bases = [self._parse_label(n)[1] for n, opt in right_nodes_info]
            
            # EQUALITY CASE
            if clean_base in right_bases:
                logic_root_id, logic_root_name = self._evaluate_label_spec(lbl_prop.labelSpec()) #nodo radice restituito
                if logic_root_id:
                    self.alias_table[raw_typename.lower()] = logic_root_id
                    logic_node = self._get_node_by_id(logic_root_id)
                    
                    if logic_node:
                        # Assegniamo la caption generata
                        logic_node["caption"] = logic_root_name
                        
                        if "?" in ctx.getText() and not logic_node["caption"].endswith("OPT"):
                            logic_node["caption"] += " OPT"
                            
                        for r_name, is_opt in right_nodes_info:
                            target_id = self._get_or_create_elem(r_name)
                            # Troviamo la freccia corrispondente a questo ramo e applichiamo l'opzionalità corretta
                            for r in self.json_schema["relationships"]:
                                if r["fromId"] == logic_root_id and r["toId"] == target_id:
                                    r["required"] = not is_opt

                    if logic_root_id != current_id:
                        if logic_node:
                            for k, v in node["properties"].items(): logic_node["properties"][k] = v
                            node["properties"] = {}

                            if "original_type_name" in node:
                                logic_node["original_type_name"] = node["original_type_name"]
                                node["original_type_name"] = clean_caption

                            is_used = any(r["fromId"] == current_id or r["toId"] == current_id for r in self.json_schema["relationships"])
                            if not is_used: node["kind"] = "GHOST"
                    else:
                        if node: node["caption"] = clean_caption
            
            # BASE CASE            
            else:
                raw_spec_text = lbl_prop.labelSpec().getText()
                # La logica è complessa SOLO se ci sono sia AND che OR contemporaneamente, 
                # oppure se ci sono delle parentesi che alterano la precedenza logica.
                is_complex_logic = ('|' in raw_spec_text and '&' in raw_spec_text) or ('(' in raw_spec_text)
                
                # Caso con combinazioni di operatori (es. NameType : A | B | (A&B))
                if is_complex_logic:
                    logic_root_id, logic_root_name = self._evaluate_label_spec(lbl_prop.labelSpec())
                    
                    if logic_root_id:
                        self.alias_table[raw_typename.lower()] = logic_root_id
                        logic_node = self._get_node_by_id(logic_root_id)
                        
                        if logic_node:
                            logic_node["caption"] = clean_caption
                            
                            if "?" in ctx.getText() and not logic_node["caption"].endswith("OPT"):
                                logic_node["caption"] += " OPT"
                                
                        if logic_root_id != current_id:
                            if logic_node:
                                for k, v in node["properties"].items(): logic_node["properties"][k] = v
                                node["properties"] = {}

                                if "original_type_name" in node:
                                    logic_node["original_type_name"] = node["original_type_name"]
                                    node["original_type_name"] = clean_caption
                                is_used = any(r["fromId"] == current_id or r["toId"] == current_id for r in self.json_schema["relationships"])
                                if not is_used: node["kind"] = "GHOST"
                        else:
                            if node: node["caption"] = clean_caption

                if node: node["caption"] = clean_caption
                rel_type = "EXCLUSIVE INHERITANCE" if is_xor else "INHERITANCE"
                
                for r_name, is_opt in right_nodes_info:
                    target_id = self._get_or_create_elem(r_name)
                    
                    if current_id != target_id:
                        exists = any(r["fromId"] == current_id and r["toId"] == target_id and r["relationshipType"] == rel_type for r in self.json_schema["relationships"])
                        
                        if not exists:
                            self.json_schema["relationships"].append({
                                "entityType": "relationship", 
                                "id": self._generate_rel_id(),
                                "relationshipType": rel_type, 
                                "fromId": current_id, 
                                "toId": target_id,
                                "required": not is_opt, 
                                "style": {}, 
                                "properties": {}
                            })
        else:
            if node: node["caption"] = clean_caption
            
        self.current_node_id = None

    def _get_or_create_elem(self, name):
        final_caption, clean_name, _ = self._parse_label(name)
        
        for key, data in self.elem_table.items():
            _, key_clean, _ = self._parse_label(key)
            
            if key_clean == clean_name:
                return data["id"]
            if data["caption"].lower() == clean_name:
                return data["id"]
        
        new_id = self._generate_node_id()
        
        self.elem_table[clean_name] = {
            "id": new_id, "kind": "NODE", "caption": final_caption, "abstract": False,
            "properties": {}, "open_class": False, "open_properties": False, "original_type_name": name,
        }
        return new_id
    
    def _parse_label(self, raw_label):
        if not raw_label:
            return "", "", False
        
        is_optional = "?" in raw_label
        base_str = raw_label.replace("?", "").lower().replace("type", "").strip()
        clean_caption = base_str.capitalize()
        
        return clean_caption, base_str, is_optional

    
    def _parse_node_label_spec(self, label_spec):
        """
        Analizza le label spec dei nodi per estrarre i nomi e identificare se sono opzionali (?).
        Restituisce una lista di tuple: (nome_nodo, is_optional)
        """
        tokens = []
        def flatten(node):
            if node.getChildCount() == 0:
                txt = node.getText().strip()
                if txt: tokens.append(txt)
            else:
                for i in range(node.getChildCount()):
                    flatten(node.getChild(i))
        flatten(label_spec)
        
        paren_stack = []
        optional_parens = set()
        
        for i, t in enumerate(tokens):
            if t == '(':
                paren_stack.append(i)
            elif t == ')':
                if paren_stack:
                    start_idx = paren_stack.pop()
                    if i + 1 < len(tokens) and tokens[i+1] == '?':
                        optional_parens.add(start_idx)
                        
        results = []
        current_paren_groups = []
        for i, t in enumerate(tokens):
            if t == '(':
                current_paren_groups.append(i)
            elif t == ')':
                if current_paren_groups:
                    current_paren_groups.pop()
            elif t not in ['&', '|', '?', '[', ']', '{', '}', ':', ',']:
                is_opt = False
                
                if i + 1 < len(tokens) and tokens[i+1] == '?':
                    is_opt = True
                
                if any(idx in optional_parens for idx in current_paren_groups):
                    is_opt = True
                    
                results.append((t, is_opt))
        
        is_xor = '|' in tokens
        return results, is_xor
                    

        
    # ====================================
    # GESTIONE DELLE PROPRIETÀ E LABEL
    # ====================================
    def visitLabelSpec(self, ctx):
        if getattr(self, "ignore_label_spec", False):
            return self.visitChildren(ctx)
        
        if self.current_node_name is not None or self.current_rel is not None:
            has_optional = False
            for i in range(ctx.getChildCount()):
                child = ctx.getChild(i)
                if child.getChildCount() == 0:  
                    operator = child.getText().strip()
                    if operator in ["&", "|"]:
                        self.temp_operator = operator
                        if getattr(self, "temp_parents", None) is None: self.temp_parents = []
                    elif operator == "?":
                        has_optional = True
                        if getattr(self, "temp_operator", None) is None: self.temp_operator = "?"
                        if getattr(self, "temp_parents", None) is None: self.temp_parents = []
  
            clean_text = ""
            if ctx.labelName() is not None: clean_text = ctx.labelName().getText().replace("?", "").strip()
            elif ctx.typeName() is not None: clean_text = ctx.typeName().getText().replace("?", "").strip()

            if clean_text: 
                if getattr(self, "temp_operator", None) is not None:
                    if clean_text not in self.temp_parents: self.temp_parents.append(clean_text)
                else:
                    if self.current_node_name is not None and self.elem_table[self.current_node_name]["caption"] == "":
                        self.elem_table[self.current_node_name]["caption"] = clean_text
                    elif self.current_rel is not None and self.current_rel["type"] == "":
                        self.current_rel["type"] = clean_text.capitalize()

            result = self.visitChildren(ctx)

            if has_optional:
                self.temp_optional = True
                if hasattr(self, "temp_parents") and len(self.temp_parents) > 0:
                    if not self.temp_parents[-1].endswith("?"): self.temp_parents[-1] += " ?" 
            return result
        return self.visitChildren(ctx)
   
    def visitLabelPropertySpec(self, ctx):
        if getattr(self, "current_node_id", None) is not None and ctx.OPEN() is not None:
            node = self._get_node_by_id(self.current_node_id)
            if node: node["open_class"] = True
        return self.visitChildren(ctx)

    def visitPropertySpec(self, ctx):
        if getattr(self, "current_node_id", None) is not None and ctx.OPEN() is not None:
            node = self._get_node_by_id(self.current_node_id)
            if node: node["open_properties"] = True
        return self.visitChildren(ctx)

    def visitProperty(self, ctx):
        prop_name = ctx.key().getText()
        prop_range = type_mapping.get(ctx.propertyType().getText().lower(), "string")

        prop_requiredType = "optional" if ctx.OPTIONAL() else "required"
        prop_data = {"description": "", "requiredType": prop_requiredType, "range": prop_range}

        if getattr(self, "current_node_id", None) is not None:
            node = self._get_node_by_id(self.current_node_id)
            if node: node["properties"][prop_name] = prop_data
        elif getattr(self, "current_rel", None) is not None:
            self.current_rel["properties"][prop_name] = prop_data
            
        return self.visitChildren(ctx)
    
    # ===================================
    # GESTIONE DELLE RELAZIONI (ARCHI)
    # ===================================
    def visitCreateEdgeType(self, ctx):
        if ctx.ABSTRACT():
            self.temp_abstract = True
        return self.visitChildren(ctx)

    def visitEdgeType(self, ctx):
        from_nodes = self._extract_all_endpoints(ctx.endpointType(0))
        to_nodes = self._extract_all_endpoints(ctx.endpointType(1))
        
        if not from_nodes: from_nodes = [""]
        if not to_nodes: to_nodes = [""]

        self.is_multi_endpoint = (len(from_nodes) > 1) or (len(to_nodes) > 1)

        self.current_rel = self._create_base_rel_dict("", "", "", "")

        right_nodes_info = []
        handler_function = None
        is_xor = False
        is_and = False

        if ctx.middleType():
            middle = ctx.middleType()
            if middle.typeName():
                raw_rel_name = middle.typeName().getText().strip()
                self.current_rel["original_type_name"] = raw_rel_name 
                self.current_rel["type"] = raw_rel_name.lower().replace("type", "").capitalize()
            
            lbl_prop = middle.labelPropertySpec()
            if lbl_prop and lbl_prop.labelSpec():                
               right_nodes_info, is_xor, is_and = self._parse_edge_label_spec(lbl_prop.labelSpec())
            self.temp_parents = [r[0] for r in right_nodes_info]

            if is_xor: self.temp_operator = "|"
            elif is_and: self.temp_operator = "&"
            else: self.temp_operator = None

            if is_xor:
                handler_function = self._handle_xor_case
            elif is_and:
                # Se c'è un '&' ma ci stiamo riferendo a nomi di relazioni base ("Knows & Likes") usiamo l'AND
                # Se c'è un '&' ma ci riferiamo a tipi ("friendType & enemyType") usiamo l'ereditarietà
                if any(r[0].replace("?", "").strip().lower().endswith("type") for r in right_nodes_info):
                    handler_function = self._handle_inheritance_case
                else:
                    handler_function = self._handle_and_case
            else:
                # CASO SINGOLO (Es. buddyType : friendType) -> Ereditarietà Diretta!
                rel_name_clean = self.current_rel["type"].lower().replace("_", "")
                
                parent_raw = self.temp_parents[0]
                _, parent_name_clean, _ = self._parse_label(parent_raw)
                parent_name_clean_norm = parent_name_clean.replace("_", "")

                if rel_name_clean == parent_name_clean_norm:
                    # Se i nomi coincidono (es. "buddy" == "buddy" o "takenfrom" == "takenfrom"), è una normale relazione!
                    handler_function = None 
                    self.current_rel["type"] = parent_raw.replace("?", "").strip().capitalize()
                    
                elif parent_raw.replace("?", "").strip().lower().endswith("type"):
                    # Caso 4: (buddyType : friendType) -> Se la label è un "...Type", allora è ereditarietà
                    handler_function = self._handle_inheritance_case
                else:
                    # Caso 2: (friendType : Knows) -> È una reificazione singola! Usiamo la logica dell'AND
                    handler_function = self._handle_and_case

            # Leggiamo le proprietà (es. {since DATE, causal BOOL})
            self.ignore_label_spec = True
            self.visit(middle)
            self.ignore_label_spec = False

        saved_type = self.current_rel["type"]
        saved_props = self.current_rel["properties"].copy()
        saved_original = self.current_rel.get("original_type_name")


        processed_pairs = set() 
        for s_id in from_nodes:
            for t_id in to_nodes:
                if not s_id or not t_id: continue
                    
                pair_signature = (s_id, t_id)
                if pair_signature in processed_pairs: continue  
                processed_pairs.add(pair_signature)

                self.current_s_var = s_id
                self.current_t_var = t_id

                self.current_rel = self._create_base_rel_dict(
                    rel_id=self._generate_rel_id(),
                    rel_type=saved_type,
                    from_id=s_id,
                    to_id=t_id,
                    properties=saved_props.copy()
                )

                if saved_original:
                    self.current_rel["original_type_name"] = saved_original
                source_caption, target_caption = self._get_node_captions()

                if handler_function:
                    handler_function(source_caption, target_caption)
                else:
                    if not self.current_rel["type"]: self.current_rel["type"] = "Association"
                    self.json_schema["relationships"].append(self.current_rel)

        self.current_rel = None
        self.temp_parents = []
        self.temp_operator = None
        self.temp_optional = False
        
        return self.json_schema

    def _parse_edge_label_spec(self, label_spec):
        """
        Analizza le label spec degli archi per estrarre nodi, opzionalità (?) e operatori logici (&, |).
        Restituisce: (results_list, is_xor, is_and)
        """
        tokens = []
        def flatten(node):
            if node.getChildCount() == 0: 
                txt = node.getText().strip()
                if txt: tokens.append(txt)
            else:
                for i in range(node.getChildCount()):
                    flatten(node.getChild(i))
        
        flatten(label_spec)
        
        bracket_stack = [] 
        optional_bracket = set() 
        
        for i, t in enumerate(tokens):
            if t == '(': bracket_stack.append(i)
            elif t == ')':
                if bracket_stack:
                    start_idx = bracket_stack.pop() 
                    if i + 1 < len(tokens) and tokens[i+1] == '?': 
                        optional_bracket.add(start_idx)
                        
        results = []
        current_bracket_groups = []
        for i, t in enumerate(tokens):
            if t == '(': current_bracket_groups.append(i)
            elif t == ')':
                if current_bracket_groups: current_bracket_groups.pop()
            elif t not in ['&', '|', '?', '[', ']', '{', '}', ':', ',']: 
                is_opt = False
                if i + 1 < len(tokens) and tokens[i+1] == '?': is_opt = True
                if any(idx in optional_bracket for idx in current_bracket_groups): is_opt = True 
                
                val = t + " ?" if is_opt else t
                results.append((val, is_opt))
        
        _is_xor = '|' in tokens
        _is_and = '&' in tokens
        return results, _is_xor, _is_and

    def _create_base_rel_dict(self, rel_id, rel_type, from_id, to_id, properties=None):
        return {
            "entityType" : "relationship", 
            "id": rel_id, 
            "type": rel_type,
            "relationshipType": "ASSOCIATION", 
            "style": {}, 
            "properties": properties if properties is not None else {},
            "fromId": from_id, 
            "toId": to_id, 
            "description": "", 
            "required": False,
            "source_minimum_cardinality": 0,
            "source_maximum_cardinality": "N",
            "target_minimum_cardinality": 0,
            "target_maximum_cardinality": "N",
            "navigation": "None"
        }
    
    # --- HELPER LOGICI ---
    def _is_xor_case(self):
        return hasattr(self, "temp_parents") and self.temp_parents and getattr(self, "temp_operator", None) == "|"

    def _is_inheritance_case(self):
        if not hasattr(self, "temp_parents") or not self.temp_parents: return False
        if getattr(self, "temp_operator", None) == "|": return False
        return any(p.replace("?", "").strip().lower().endswith("type") for p in self.temp_parents)

    def _is_and_case(self):
        if not hasattr(self, "temp_parents") or not self.temp_parents: return False
        if getattr(self, "temp_operator", None) == "|": return False
        return not self._is_inheritance_case()

    def _get_node_captions(self):
        source_node = self._get_node_by_id(self.current_rel["fromId"])
        target_node = self._get_node_by_id(self.current_rel["toId"])
        return (source_node["caption"] if source_node else "Unknown", target_node["caption"] if target_node else "Unknown")
        
    def _get_node_by_id(self, target_id):
        return next((v for v in self.elem_table.values() if v["id"] == target_id), None)

    def _generate_reified_caption(self, base_name, source_caption, target_caption):
        if not getattr(self, "is_multi_endpoint", False): return base_name.capitalize()
        src = source_caption if source_caption else "Unknown"
        tgt = target_caption if target_caption else "Unknown"
        return f"{src} {base_name.capitalize()} {tgt}"

    def _build_reified_node(self, node, source_caption, target_caption, extra_properties=None):
        """Centralizza la logica di inizializzazione di un nodo reificato."""
        if not node:
            return
            
        node["kind"] = "NODE"
        node["note"] = "reified"
        
        node["properties"]["source"] = {
            "description": "", 
            "requiredType": "required", 
            "range": source_caption if source_caption else "Unknown"
        }
        node["properties"]["target"] = {
            "description": "", 
            "requiredType": "required", 
            "range": target_caption if target_caption else "Unknown"
        }
        
        if extra_properties:
            for key, val in extra_properties.items():
                node["properties"][key] = val.copy()

    def _handle_xor_case(self, source_caption, target_caption):
        parent_base_name = self.current_rel["type"] if self.current_rel["type"] else "UnknownRel"
        parent_node_id = self._get_or_create_elem(parent_base_name)
        parent_node = self._get_node_by_id(parent_node_id)
        
        if parent_node:
            
            self._build_reified_node(parent_node, source_caption, target_caption, self.current_rel.get("properties"))
        
            for raw_child_label in self.temp_parents:
                child_name, _, _ = self._parse_label(raw_child_label)
                child_node_id = self._get_or_create_elem(child_name)

                child_node = self._get_node_by_id(child_node_id)
                if child_node:
                    child_node["note"] = "reified"
                
                self.json_schema["relationships"].append({
                    "entityType": "relationship", "id": self._generate_rel_id(), "relationshipType": "EXCLUSIVE INHERITANCE",
                    "style": {}, "properties": {}, "fromId": child_node_id, "toId": parent_node_id, "description": "",
                    "required": True
                })

    def _handle_inheritance_case(self, source_caption, target_caption):
        main_alias_name = self.current_rel.get("original_type_name", self.current_rel["type"]) if self.current_rel["type"] else "Unknown"
        main_node_id = self._get_or_create_elem(main_alias_name)
        main_node = self._get_node_by_id(main_node_id)
        
        self._build_reified_node(main_node, source_caption, target_caption, self.current_rel.get("properties"))

        for raw_parent_label in self.temp_parents:
            node_name, prop_name, is_optional = self._parse_label(raw_parent_label)
            
            if raw_parent_label.replace("?", "").strip().lower().endswith("type"):
                parent_raw_clean = raw_parent_label.replace("?", "").strip()
                parent_node_id = self._get_or_create_elem(parent_raw_clean) 
                parent_node = self._get_node_by_id(parent_node_id)
                
                edges_to_remove = []
                already_reified = False
                for rel in self.json_schema["relationships"]:
                    if rel.get("type", "").upper() == node_name.upper() and rel.get("relationshipType") == "ASSOCIATION":
                        if already_reified:
                            # Un nodo reificato ha un solo source/target: una seconda relazione con lo
                            # stesso nome di tipo non puo' essere assorbita senza sovrascrivere la prima.
                            # La lasciamo com'e' (relazione ASSOCIATION separata) invece di eliminarla,
                            # per non perdere silenziosamente i suoi dati.
                            print(f"WARN: Multiple '{node_name}' relationships found while reifying '{parent_raw_clean}'; keeping the extra one as a separate ASSOCIATION.")
                            continue

                        if parent_node:
                            src_node = self._get_node_by_id(rel.get("fromId"))
                            tgt_node = self._get_node_by_id(rel.get("toId"))

                            src_cap = src_node["caption"] if src_node else "Unknown"
                            tgt_cap = tgt_node["caption"] if tgt_node else "Unknown"

                            self._build_reified_node(parent_node, src_cap, tgt_cap, rel.get("properties", {}))
                            if "constraints" in rel: parent_node["constraints"] = list(rel["constraints"])
                        edges_to_remove.append(rel)
                        already_reified = True

                for edge in edges_to_remove: self.json_schema["relationships"].remove(edge)

                self.json_schema["relationships"].append({
                    "entityType": "relationship", "id": self._generate_rel_id(), "relationshipType": "INHERITANCE",
                    "style": {}, "properties": {}, "fromId": main_node_id, "toId": parent_node_id, "description": "",
                    "required": not is_optional
                })
            else: 
                if main_node: main_node["properties"][prop_name] = {"description": "", "requiredType": "optional" if is_optional else "required", "range": node_name}
                aux_node_id = self._get_or_create_elem(node_name)
                aux_node = self._get_node_by_id(aux_node_id)

                self._build_reified_node(aux_node, source_caption, target_caption)

    def _handle_and_case(self, source_caption, target_caption):
        if "constraints" not in self.current_rel: self.current_rel["constraints"] = []

        for raw_label in self.temp_parents:
            node_name, p_name, is_optional = self._parse_label(raw_label)

            prop_name = p_name.capitalize()
            prop_dict = {
                "description": "",
                "requiredType": "optional" if is_optional else "required", 
                "range": node_name, 
            }
            if not is_optional:
                prop_dict["collectionType"] = "list"
            self.current_rel["properties"][prop_name] = prop_dict
            
            current_rel_name = self.current_rel["type"] if self.current_rel.get("type") else "Association"

            # vincoli sulla relazione
            rel_c1 = {
                "on": "fromId",
                "type": "equal",
                "target": f"{prop_name}.source"         
            }
    
            rel_c2 = {
                "on": "toId",
                "type": "equal",
                "target": f"{prop_name}.target"            
            }

            if rel_c1 not in self.current_rel["constraints"]:
                self.current_rel["constraints"].append(rel_c1)
            if rel_c2 not in self.current_rel["constraints"]:
                self.current_rel["constraints"].append(rel_c2)

            internal_node_name = f"{node_name}_{self.current_s_var}_{self.current_t_var}"
            aux_node_id = self._get_or_create_elem(internal_node_name)
            
            aux_node = self._get_node_by_id(aux_node_id)
            if aux_node:
                aux_node["note"] = "reified"
                self._build_reified_node(aux_node, source_caption, target_caption)
                aux_node["caption"] = self._generate_reified_caption(node_name, source_caption, target_caption)

                #vincoli sul nodo reificato
                if "constraints" not in aux_node:
                    aux_node["constraints"] = []

                inverse_c1 = {
                    "on": "source",
                    "type": "equal",
                    "target": f"{current_rel_name}.fromId"            
                }

                inverse_c2 = {
                    "on": "target",
                    "type": "equal",
                    "target": f"{current_rel_name}.toId"            
                }
                
                if inverse_c1 not in aux_node["constraints"]:
                    aux_node["constraints"].append(inverse_c1)
                if inverse_c2 not in aux_node["constraints"]:
                    aux_node["constraints"].append(inverse_c2)

        if not self.current_rel["type"]: self.current_rel["type"] = "Association"
        self.json_schema["relationships"].append(self.current_rel)


    def _evaluate_label_spec(self, label_spec_ctx):
        if not label_spec_ctx: return None, ""
        
        if label_spec_ctx.typeName() or label_spec_ctx.labelName():
            name = label_spec_ctx.typeName().getText().strip() if label_spec_ctx.typeName() else label_spec_ctx.labelName().getText().strip()
            clean_name = self._parse_label(name)[0]
            node_id = self._get_or_create_elem(name)
            node = self._get_node_by_id(node_id)
            if node: node["caption"] = clean_name
            return node_id, clean_name
            
        specs = label_spec_ctx.labelSpec()
        
        if len(specs) == 1:
            child_id, child_name = self._evaluate_label_spec(specs[0])
            if label_spec_ctx.getText().endswith('?'): return child_id, child_name + " OPT"
            return child_id, child_name
            
        if len(specs) == 2:
            op = next((label_spec_ctx.getChild(i).getText() for i in range(label_spec_ctx.getChildCount()) if label_spec_ctx.getChild(i).getText() in ['&', '|']), "")
                    
            if op == '&':
                left_id, left_name = self._evaluate_label_spec(specs[0])
                right_id, right_name = self._evaluate_label_spec(specs[1])
                
                and_name = f"{left_name} AND {right_name}"
                and_id = self._get_or_create_elem(and_name)
                node = self._get_node_by_id(and_id)
                if node: 
                    node["kind"] = "NODE"
                    node["caption"] = and_name
                    node["note"] = "intermediate"
                
                self._create_edge(and_id, left_id, "INHERITANCE")
                self._create_edge(and_id, right_id, "INHERITANCE")
                return and_id, and_name
                
            elif op == '|':
                operands = self._collect_or_operands(label_spec_ctx)
                evaluated = [self._evaluate_label_spec(ctx) for ctx in operands]
                current_id, current_name = evaluated[-1]
                
                for i in range(len(evaluated) - 2, -1, -1):
                    prev_id, prev_name = evaluated[i]
                    xor_name = f"{prev_name} XOR {current_name}"
                    xor_id = self._get_or_create_elem(xor_name)
                    node = self._get_node_by_id(xor_id)
                    if node: 
                        node["kind"] = "NODE"
                        node["caption"] = xor_name
                        node["note"] = "intermediate"
                    
                    self._create_edge(xor_id, prev_id, "EXCLUSIVE INHERITANCE")
                    self._create_edge(xor_id, current_id, "EXCLUSIVE INHERITANCE")
                    current_id, current_name = xor_id, xor_name
                    
                return current_id, current_name
        return None, ""
    
    def _create_edge(self, from_id, to_id, rel_type, required=True):
        if from_id == to_id or any((r["fromId"] == from_id and r["toId"] == to_id) or (r["fromId"] == to_id and r["toId"] == from_id) for r in self.json_schema["relationships"]): return       
        self.json_schema["relationships"].append({
            "entityType": "relationship", "id": self._generate_rel_id(),
            "relationshipType": rel_type, "fromId": from_id, "toId": to_id,
            "required": required, "style": {}, "properties": {}
        })
    
    def _collect_or_operands(self, label_spec_ctx):
        specs = label_spec_ctx.labelSpec()
        if len(specs) == 2:
            op = next((label_spec_ctx.getChild(i).getText() for i in range(label_spec_ctx.getChildCount()) if label_spec_ctx.getChild(i).getText() in ['&', '|']), "")
            if op == '|': return self._collect_or_operands(specs[0]) + self._collect_or_operands(specs[1])
        return [label_spec_ctx]

    def _extract_all_endpoints(self, endpoint_ctx):
        lbl_prop = endpoint_ctx.labelPropertySpec()
        if not lbl_prop or not lbl_prop.labelSpec(): 
            return []

        # Generatore ricorsivo: non crea liste intermedie, molto più efficiente
        def iter_names(label_spec):
            if not label_spec: return
            
            if label_spec.typeName(): yield label_spec.typeName().getText().strip()
            if label_spec.labelName(): yield label_spec.labelName().getText().strip()
            
            sub_specs = label_spec.labelSpec()
            if not sub_specs: return
            
            # Normalizziamo a lista e iteriamo
            sub_list = sub_specs if isinstance(sub_specs, list) else [sub_specs]
            for sub in sub_list:
                yield from iter_names(sub)

        # List comprehension per risolvere gli ID in modo compatto
        return [
            self.alias_table[name.lower()] if name.lower() in self.alias_table else self._get_or_create_elem(name)
            for name in iter_names(lbl_prop.labelSpec())
        ]

    def _resolve_reified_constraints(self):
        """
        Fase di Linking (Pass 2): ripercorre i vincoli dopo che l'intero schema è stato parsato.
        Corregge le referenze (fromId/toId -> source/target) se rileva che un'entità è stata reificata.
        """
        for data in list(self.elem_table.values()):
            is_reified = data.get("note") == "reified"
            
            if "constraints" in data:
                for c in data["constraints"]:
                    # 1. Se questo nodo è reificato, modifichiamo le sue chiavi interne 'on'
                    if is_reified:
                        if c.get("on") == "fromId": c["on"] = "source"
                        if c.get("on") == "toId": c["on"] = "target"
                    
                    # 2. Sistemiamo il 'target' del vincolo incrociato (es. Knows -> Friend.fromId)
                    if "target" in c and isinstance(c["target"], str) and "." in c["target"]:
                        t_entity, t_prop = c["target"].split(".", 1)
                        
                        # [CORREZIONE] Ricerca "safe": guardiamo se esiste senza crearlo!
                        _, clean_t_entity, _ = self._parse_label(t_entity)
                        t_node = None
                        for v in self.elem_table.values():
                            if v.get("caption", "").lower() == clean_t_entity or v.get("original_type_name", "").lower() == clean_t_entity:
                                t_node = v
                                break
                        
                        # Se l'abbiamo trovato ed è reificato, aggiorniamo il vincolo
                        if t_node and t_node.get("note") == "reified":
                            if t_prop == "fromId": c["target"] = f"{t_entity}.source"
                            if t_prop == "toId": c["target"] = f"{t_entity}.target"
                            
    def _build_final_json(self):
        for type_name, data in self.elem_table.items():
            if data["kind"] == "NODE":
                node_obj = {
                    "entityType": "node", "id": data["id"],
                    "position": {"x": random.randint(100, 1200), "y": random.randint(100, 600)},
                    "caption": data["caption"] if data["caption"] else type_name,
                    "original_type_name": data.get("original_type_name", type_name),
                    "abstract": data["abstract"],
                    "description": "",
                    "properties": data["properties"],   
                    "style": {},
                    "open": {"class": data["open_class"], "properties": data["open_properties"]}
                }
                
                if "note" in data:
                    node_obj["note"] = data["note"]

                if "constraints" in data:
                    node_obj["constraints"] = data["constraints"]
                
                self.json_schema["nodes"].append(node_obj)

type_mapping = {
    "int": "integer", "int32": "integer", "int64": "integer", "integer": "integer",
    "bool": "boolean", "boolean": "boolean",
    "float": "float", "double": "float", "decimal": "float",
    "date": "date", "datetime": "datetime",
    "varchar": "string", "string": "string"
}

global_style = {
    "font-family": "sans-serif", "background-color": "#ffffff", "background-image": "", "background-size": "100%",
    "class-color": "#ffffff", "border-width": 4, "border-color": "#000000", "radius": 50, "class-padding": 5, "class-margin": 2,
    "outside-position": "auto", "class-icon-image": "", "class-background-image": "", "icon-position": "inside", "icon-size": 64,
    "class-name-position": "inside", "class-name-max-width": 200, "class-name-color": "#000000", "class-name-font-size": 50,
    "class-name-font-weight": "normal", "label-position": "inside", "label-display": "pill", "label-color": "#000000",
    "label-background-color": "#ffffff", "label-border-color": "#000000", "label-border-width": 4, "label-font-size": 40,
    "label-padding": 5, "label-margin": 4, "detail-position": "inline", "detail-orientation": "parallel", "arrow-width": 5,
    "arrow-color": "#000000", "margin-start": 5, "margin-end": 5, "margin-peer": 20, "attachment-start": "normal",
    "attachment-end": "normal", "relationship-icon-image": "", "type-color": "#000000", "type-background-color": "#ffffff",
    "type-border-color": "#000000", "type-border-width": 0, "type-font-size": 16, "type-padding": 5, "attribute-position": "outside",
    "ontology-position": "outside", "attribute-alignment": "colon", "attribute-color": "#000000", "attribute-font-size": 16,
    "attribute-font-weight": "normal"
}