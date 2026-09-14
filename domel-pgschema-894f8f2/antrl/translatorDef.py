from pgsVisitor import pgsVisitor
import random

class PGSchemaToJsonVisitor(pgsVisitor):
    def __init__(self):
        super().__init__()
        self.node_counter = 0 
        self.rel_counter = 0

        self.json_schema = {
            "name": "Untitled schema",
            "graphTypeMode": "strict",
            "nodes": [],
            "relationships": [],
            "globalConstraints": [], 
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
                self.json_schema["graphTypeMode"] = "loose"
        
        self.visitChildren(ctx) 
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
            
        self.temp_abstract = False
        self.ignore_label_spec = True
        self.visitChildren(ctx)
        self.ignore_label_spec = False
        
        lbl_prop = ctx.labelPropertySpec()
        if lbl_prop and lbl_prop.labelSpec():
            
            def get_names_with_opt(label_spec):
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
            
            right_nodes_info, is_xor = get_names_with_opt(lbl_prop.labelSpec())
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
                            is_used = any(r["fromId"] == current_id or r["toId"] == current_id for r in self.json_schema["relationships"])
                            if not is_used: node["kind"] = "GHOST"
                    else:
                        if node: node["caption"] = clean_caption
            
            # BASE CASE            
            else:
                raw_spec_text = lbl_prop.labelSpec().getText()
                is_complex_logic = '|' in raw_spec_text or '&' in raw_spec_text
                
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

    def _get_or_create_elem(self, name, ignore_id=None):
        clean_name = name.lower().replace("type", "").replace("?", "").strip()
        
        for key, data in self.elem_table.items():
            if ignore_id and data["id"] == ignore_id: continue 
            if key.lower().replace("type", "").replace("?", "").strip() == clean_name:
                return data["id"]
            if data["caption"].lower() == clean_name:
                return data["id"]
        
        new_id = self._generate_node_id()
        # Generiamo la caption pulita
        final_caption, _, _ = self._parse_label(name)
        
        # Usiamo il nome pulito come chiave
        self.elem_table[clean_name] = {
            "id": new_id, "kind": "NODE", "caption": final_caption, "abstract": False,
            "properties": {}, "open_class": False, "open_properties": False
        }
        return new_id
    
    def _parse_label(self, raw_label):
        is_optional = "?" in raw_label

        base_str = raw_label.replace("?", "").replace("type", "").replace("Type", "").strip().lower()        
        clean_caption = base_str.capitalize()
        return clean_caption, base_str, is_optional
    
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
        type_mapping = {
            "int": "integer", "int32": "integer", "int64": "integer", "integer": "integer",
            "bool": "boolean", "boolean": "boolean",
            "float": "float", "double": "float", "decimal": "float",
            "date": "date", "datetime": "datetime",
            "varchar": "string", "string": "string"
        }

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

        self.current_rel = {
            "entityType" : "relationship", "id": "", "type": "",
            "relationshipType": "ASSOCIATION", "style": {}, "properties": {},
            "fromId": "", "toId": "", "description": "", "required": False,
            "source_minimum_cardinality": 0,
            "source_maximum_cardinality": "N",
            "target_minimum_cardinality": 0,
            "target_maximum_cardinality": "N",
            "navigation": "None"
        }

        right_nodes_info = []
        handler_function = None
        is_xor = False
        is_and = False

        if ctx.middleType():
            middle = ctx.middleType()
            if middle.typeName():
                raw_rel_name = middle.typeName().getText().strip()
                self.current_rel["type"] = raw_rel_name.lower().replace("type", "").capitalize()
            
            lbl_prop = middle.labelPropertySpec()
            if lbl_prop and lbl_prop.labelSpec():                
                def get_names_with_opt_and_ops(label_spec):
                    tokens = []
                    def flatten(node):
                        if node.getChildCount() == 0: 
                            txt = node.getText().strip()
                            if txt: tokens.append(txt)
                        else:
                            for i in range(node.getChildCount()):
                                flatten(node.getChild(i))
                    flatten(label_spec)
                    
                    bracket_stack = [] #stack per posizione di '(' di apertura
                    optional_bracket = set() #per opzionali
                    for i, t in enumerate(tokens):
                        if t == '(': bracket_stack.append(i)
                        elif t == ')':
                            if bracket_stack:
                                start_idx = bracket_stack.pop() #elimina dallo stack
                                if i + 1 < len(tokens) and tokens[i+1] == '?': #controlla se dopo c'è opt
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
                            if any(idx in optional_bracket for idx in current_bracket_groups): is_opt = True #controlla se siamo in una parentesi opzionale
                            
                            val = t + " ?" if is_opt else t
                            results.append((val, is_opt))
                    
                    _is_xor = '|' in tokens
                    _is_and = '&' in tokens
                    return results, _is_xor, _is_and

            
            right_nodes_info, is_xor, is_and = get_names_with_opt_and_ops(lbl_prop.labelSpec())
                
            # Salviamo i risultati per i vecchi gestori
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
                rel_name_clean = self.current_rel["type"].lower()

                parent_raw = self.temp_parents[0]
                parent_name_clean = parent_raw.replace("?", "").replace("type", "").replace("Type", "").strip().lower()

                if rel_name_clean == parent_name_clean:
                    # Se i nomi coincidono (es. "buddy" == "buddy"), è una normale relazione!
                    handler_function = None 
                    self.current_rel["type"] = parent_raw.replace("?", "").strip().capitalize()
                else:
                    # Se i nomi sono diversi (es. "buddy" : "friend"), allora è ereditarietà
                    handler_function = self._handle_inheritance_case

            # Leggiamo le proprietà (es. {since DATE, causal BOOL})
            self.ignore_label_spec = True
            self.visit(middle)
            self.ignore_label_spec = False

        saved_type = self.current_rel["type"]
        saved_props = self.current_rel["properties"].copy()


        processed_pairs = set() 
        for s_id in from_nodes:
            for t_id in to_nodes:
                if not s_id or not t_id: continue
                    
                pair_signature = frozenset([s_id, t_id])
                if pair_signature in processed_pairs: continue  
                processed_pairs.add(pair_signature)

                self.current_s_var = s_id
                self.current_t_var = t_id

                self.current_rel = {
                    "entityType" : "relationship", "id": self._generate_rel_id(), "type": saved_type,
                    "relationshipType": "ASSOCIATION", "style": {}, "properties": saved_props.copy(),
                    "fromId": s_id, "toId": t_id, "description": "", "required": False,
                    "source_minimum_cardinality": 0,
                    "source_maximum_cardinality": "N",
                    "target_minimum_cardinality": 0,
                    "target_maximum_cardinality": "N",
                    "navigation": "None"
                }

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
        
    def _handle_xor_case(self, source_caption, target_caption):
        parent_base_name = self.current_rel["type"] if self.current_rel["type"] else "UnknownRel"
        parent_node_id = self._get_or_create_elem(parent_base_name)
        parent_node = self._get_node_by_id(parent_node_id)
        
        if parent_node:
            parent_node["kind"] = "NODE"
            parent_node["note"] = "reified"
            parent_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": source_caption}
            parent_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": target_caption}
            for key, val in self.current_rel["properties"].items():
                parent_node["properties"][key] = val.copy()
        
            for raw_child_label in self.temp_parents:
                child_name, _, _ = self._parse_label(raw_child_label)
                child_node_id = self._get_or_create_elem(child_name)
                
                self.json_schema["relationships"].append({
                    "entityType": "relationship", "id": self._generate_rel_id(), "relationshipType": "EXCLUSIVE INHERITANCE",
                    "style": {}, "properties": {}, "fromId": child_node_id, "toId": parent_node_id, "description": "",
                    "required": True
                })

    def _handle_inheritance_case(self, source_caption, target_caption):
        main_alias_name = self.current_rel["type"] if self.current_rel["type"] else "Unknown"
        main_node_id = self._get_or_create_elem(main_alias_name)
        main_node = self._get_node_by_id(main_node_id)
        
        if main_node:
            main_node["kind"] = "NODE"
            main_node["note"] = "reified"
            main_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": source_caption}
            main_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": target_caption}
            for key, val in self.current_rel["properties"].items():
                main_node["properties"][key] = val.copy()
        
        for raw_parent_label in self.temp_parents:
            node_name, prop_name, is_optional = self._parse_label(raw_parent_label)
            
            if raw_parent_label.replace("?", "").strip().lower().endswith("type"):
                parent_node_id = self._get_or_create_elem(node_name) 
                parent_node = self._get_node_by_id(parent_node_id)
                
                edges_to_remove = []
                for rel in self.json_schema["relationships"]:
                    if rel.get("type", "").upper() == node_name.upper() and rel.get("relationshipType") == "ASSOCIATION":
                        if parent_node:
                            parent_node["kind"] = "NODE"
                            src_node = self._get_node_by_id(rel.get("fromId"))
                            tgt_node = self._get_node_by_id(rel.get("toId"))
                            
                            parent_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": src_node["caption"] if src_node else "Unknown"}
                            parent_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": tgt_node["caption"] if tgt_node else "Unknown"}
                            
                            for k, v in rel.get("properties", {}).items(): parent_node["properties"][k] = v.copy()
                            if "constraints" in rel: parent_node["constraints"] = list(rel["constraints"])
                        edges_to_remove.append(rel)
                
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
                if aux_node:
                    aux_node["kind"] = "NODE"
                    aux_node["note"] = "reified"
                    aux_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": source_caption}
                    aux_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": target_caption}

    def _handle_and_case(self, source_caption, target_caption):
        if "constraints" not in self.current_rel: self.current_rel["constraints"] = []

        for raw_label in self.temp_parents:
            node_name, prop_name, is_optional = self._parse_label(raw_label)
            
            prop_dict = {
                "description": "",
                "requiredType": "optional" if is_optional else "required", 
                "range": node_name, 
            }
            if not is_optional:
                prop_dict["collectionType"] = "list"
            self.current_rel["properties"][prop_name] = prop_dict
            
            self.current_rel["constraints"].extend([f"self.source == self.{prop_name}.source", f"self.target == self.{prop_name}.target"])

            internal_node_name = f"{node_name}_{self.current_s_var}_{self.current_t_var}"
            aux_node_id = self._get_or_create_elem(internal_node_name)
            
            aux_node = self._get_node_by_id(aux_node_id)
            if aux_node:
                aux_node["kind"] = "NODE"
                aux_node["note"] = "reified"
                aux_node["caption"] = self._generate_reified_caption(node_name, source_caption, target_caption)
                aux_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": source_caption}
                aux_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": target_caption}

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
                if node: node["kind"] = "NODE"
                
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
                    if node: node["kind"] = "NODE"
                    
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
        if not lbl_prop or not lbl_prop.labelSpec(): return []

        def get_names(label_spec):
            if not label_spec: return []
            names = []
            if label_spec.typeName(): names.append(label_spec.typeName().getText().strip())
            if label_spec.labelName(): names.append(label_spec.labelName().getText().strip())
            
            sub_specs = label_spec.labelSpec()
            if sub_specs:
                if isinstance(sub_specs, list):
                    for sub in sub_specs: names.extend(get_names(sub))
                else: names.extend(get_names(sub_specs))
            return names
        
        raw_names = get_names(lbl_prop.labelSpec())
        resolved_ids = []
        
        for name in raw_names:
            key = name.lower()
            if key in self.alias_table:
                resolved_ids.append(self.alias_table[key])
            else:
                resolved_ids.append(self._get_or_create_elem(name))
                
        return resolved_ids            

    def _build_final_json(self):
        for var_name, data in self.elem_table.items():
            if data["kind"] == "NODE":
                node_obj = {
                    "entityType": "node", "id": data["id"],
                    "position": {"x": random.randint(100, 1200), "y": random.randint(100, 600)},
                    "caption": data["caption"] if data["caption"] else var_name,
                    "description": "", "ontologies": [], "examples": [],
                    "abstract": data["abstract"],
                    "open": {"class": data["open_class"], "properties": data["open_properties"]},
                    "properties": data["properties"],   
                    "style": {}
                }
                
                if "note" in data:
                    node_obj["note"] = data["note"]
                
                self.json_schema["nodes"].append(node_obj)

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