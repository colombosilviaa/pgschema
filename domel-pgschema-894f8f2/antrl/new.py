from pgsVisitor import pgsVisitor
import random

class PGSchemaToJsonVisitor(pgsVisitor):
    def __init__(self):
        super().__init__()
        # Due contatori rigorosamente separati, prefisso fisso 'n'
        self.node_counter = 0 
        self.rel_counter = 0 

        self.json_schema = {
            "name": "Untitled schema",
            "graphTypeMode": "strict",
            "nodes": [],
            "relationships": [],
            "style": global_style
        }

        self.current_node = None
        self.current_rel = None
        
        # Memoria Centrale per il Forward Referencing (risolve gli Unknown)
        self.var_to_id = {}    # Mappa le variabili (es. 'personType') agli ID ('n0')
        self.id_to_node = {}   # Mappa gli ID ai dizionari dei nodi

    # ====================
    # GESTIONE DEL GRAFO
    # ====================
    
    def visitGraphType(self, ctx):
        if ctx.typeName():
            self.json_schema["name"] = ctx.typeName().getText()

        if ctx.typeForm() and ctx.typeForm().getText().lower() == "loose":
            self.json_schema["graphTypeMode"] = "loose"

        self.visitChildren(ctx)
        return self.json_schema

    # ==================================
    # PARSER AST NATIVO (CORE LOGIC)
    # ==================================

    def _parse_ast_label(self, ctx):
        """
        Naviga l'albero di ANTLR senza manipolare le stringhe.
        Restituisce un dizionario formale della regola labelSpec.
        """
        if not ctx: return None

        # 1. Foglie terminali
        if ctx.labelName():
            return {"type": "leaf", "value": ctx.labelName().getText(), "is_type": False, "optional": False, "children": []}
        if ctx.typeName():
            return {"type": "leaf", "value": ctx.typeName().getText(), "is_type": True, "optional": False, "children": []}

        # 2. Opzionalità (labelSpec '?')
        if ctx.getChildCount() >= 2 and ctx.getChild(ctx.getChildCount()-1).getText().strip() == '?':
            base = self._parse_ast_label(ctx.labelSpec(0))
            if base: base["optional"] = True
            return base

        # 3. Parentesi ('(' labelSpec ')' o '[' labelSpec ']')
        if ctx.getChildCount() >= 3 and ctx.getChild(0).getText().strip() in ['(', '[']:
            return self._parse_ast_label(ctx.labelSpec(0))

        # 4. Operatori Binari ('&' o '|')
        if ctx.getChildCount() >= 3:
            operator = None
            for i in range(ctx.getChildCount()):
                text = ctx.getChild(i).getText().strip()
                if text in ['&', '|']:
                    operator = text
                    break
            
            if operator:
                left = self._parse_ast_label(ctx.labelSpec(0))
                right = self._parse_ast_label(ctx.labelSpec(1))
                return {
                    "type": "AND" if operator == '&' else "XOR", 
                    "value": None, "is_type": False, "optional": False, 
                    "children": [left, right]
                }
        
        return None

    def _extract_leaves(self, ast_node):
        """Estrae tutte le foglie da un albero logico (per loop e rendering)."""
        if not ast_node: return []
        if ast_node["type"] == "leaf": return [ast_node]
        res = []
        for child in ast_node["children"]:
            res.extend(self._extract_leaves(child))
        return res

    # ==================================
    # GESTORE MEMORIA & NODI
    # ==================================

    def _get_or_create_node_by_var(self, var_name):
        """
        Motore di risoluzione degli Unknown.
        Se la variabile esiste, restituisce l'ID. Se non esiste (es. letta da un arco in anticipo),
        crea un nodo placeholder pronto per essere riempito.
        """
        if not var_name: return None
        if var_name in self.var_to_id:
            return self.var_to_id[var_name]
        
        new_id = f"n{self.node_counter}"
        self.node_counter += 1
        
        # Genera una caption di fallback pulita basata sul nome della variabile
        caption = var_name.lower().replace("type", "").capitalize()
        
        new_node = {
            "entityType": "node", "id": new_id,
            "position": {"x": random.randint(100, 800), "y": random.randint(100, 600)},
            "caption": caption, "description": "", "abstract": False,
            "open": {"class": False, "properties": False}, "properties": {}, "style": {}
        }
        
        self.json_schema["nodes"].append(new_node)
        self.id_to_node[new_id] = new_node
        self.var_to_id[var_name] = new_id
        
        return new_id

    # ==================================
    # VISITOR DEI NODI
    # ==================================

    def visitCreateNodeType(self, ctx):
        node_type_ctx = ctx.nodeType()
        if not node_type_ctx: return self.visitChildren(ctx)
        
        var_name = node_type_ctx.typeName().getText() if node_type_ctx.typeName() else None
        if var_name:
            node_id = self._get_or_create_node_by_var(var_name)
            if ctx.ABSTRACT():
                self.id_to_node[node_id]["abstract"] = True
                
        return self.visitChildren(ctx)

    def visitNodeType(self, ctx):
        var_name = ctx.typeName().getText() if ctx.typeName() else None
        if not var_name: return self.visitChildren(ctx)
            
        node_id = self._get_or_create_node_by_var(var_name)
        node_obj = self.id_to_node[node_id]
        self.current_node = node_obj
        
        lbl_prop_ctx = ctx.labelPropertySpec()
        if lbl_prop_ctx:
            if lbl_prop_ctx.OPEN():
                node_obj["open"]["class"] = True
                
            spec_ctx = lbl_prop_ctx.labelSpec()
            if spec_ctx:
                ast_spec = self._parse_ast_label(spec_ctx)
                
                # NODO SEMPLICE / EREDITARIETÀ DIRETTA
                if ast_spec["type"] == "leaf":
                    if ast_spec["is_type"]:
                        # Ereditarietà: (employeeType: personType)
                        parent_id = self._get_or_create_node_by_var(ast_spec["value"])
                        node_obj["caption"] = var_name.lower().replace("type", "").capitalize()
                        
                        rel_id = f"n{self.rel_counter}"
                        self.rel_counter += 1
                        self.json_schema["relationships"].append({
                            "entityType": "relationship", "id": rel_id, "relationshipType": "INHERITANCE",
                            "style": {}, "properties": {}, "fromId": node_id, "toId": parent_id
                        })
                    else:
                        # Etichetta normale: (personType: Person)
                        node_obj["caption"] = ast_spec["value"].replace("\"", "") + (" OPT" if ast_spec["optional"] else "")
                        
                # REIFICAZIONE SU NODI (XOR / AND)
                elif ast_spec["type"] in ["AND", "XOR"]:
                    leaves = self._extract_leaves(ast_spec)
                    captions = []
                    
                    for leaf in leaves:
                        if leaf["is_type"]:
                            parent_id = self._get_or_create_node_by_var(leaf["value"])
                            captions.append(self.id_to_node[parent_id]["caption"])
                            
                            rel_id = f"n{self.rel_counter}"
                            self.rel_counter += 1
                            rel_type = "EXCLUSIVE INHERITANCE" if ast_spec["type"] == "XOR" else "INHERITANCE"
                            self.json_schema["relationships"].append({
                                "entityType": "relationship", "id": rel_id, "relationshipType": rel_type,
                                "style": {}, "properties": {}, "fromId": node_id, "toId": parent_id
                            })
                        else:
                            captions.append(leaf["value"].replace("\"", ""))
                            
                    op_str = " AND " if ast_spec["type"] == "AND" else " XOR "
                    node_obj["caption"] = op_str.join(captions) + (" OPT" if ast_spec["optional"] else "")
                    
            # Visita le proprietà
            prop_spec_ctx = lbl_prop_ctx.propertySpec()
            if prop_spec_ctx:
                self.visit(prop_spec_ctx)
                
        self.current_node = None
        return self.json_schema

    # ==================================
    # VISITOR DELLE PROPRIETA'
    # ==================================

    def visitProperty(self, ctx):
        prop_name = ctx.key().getText()
        prop_range = ctx.propertyType().getText().lower()

        type_mapping = {
            "int": "integer", "int32": "integer", "int64": "integer", "integer": "integer",
            "bool": "boolean", "boolean": "boolean",
            "float": "float", "double": "float", "decimal": "float",
            "date": "date", "datetime": "datetime",
            "varchar": "string", "string": "string"
        }

        prop_range = type_mapping.get(prop_range, "string")
        prop_requiredType = "optional" if ctx.OPTIONAL() else "required"

        prop_data = {"description": "", "requiredType": prop_requiredType, "range": prop_range}

        if self.current_node is not None:
            self.current_node["properties"][prop_name] = prop_data
        elif self.current_rel is not None:
            self.current_rel["properties"][prop_name] = prop_data
            
        return self.visitChildren(ctx)

    # ==================================
    # VISITOR DELLE RELAZIONI (ARCHI)
    # ==================================

    def visitEdgeType(self, ctx):
        if len(ctx.endpointType()) < 2: return self.visitChildren(ctx)
        
        # 1. Estrazione degli Endpoint via AST
        def get_endpoint_var(end_ctx):
            lbl_prop = end_ctx.labelPropertySpec()
            if not lbl_prop or not lbl_prop.labelSpec(): return None
            ast_spec = self._parse_ast_label(lbl_prop.labelSpec())
            leaves = self._extract_leaves(ast_spec)
            return leaves[0]["value"] if leaves else None

        from_var = get_endpoint_var(ctx.endpointType(0))
        to_var = get_endpoint_var(ctx.endpointType(1))
        
        from_id = self._get_or_create_node_by_var(from_var)
        to_id = self._get_or_create_node_by_var(to_var)
        
        from_caption = self.id_to_node[from_id]["caption"] if from_id else "Unknown"
        to_caption = self.id_to_node[to_id]["caption"] if to_id else "Unknown"

        # 2. Configurazione Arco Base
        rel_id = f"n{self.rel_counter}"
        self.rel_counter += 1
        
        middle_ctx = ctx.middleType()
        rel_var = middle_ctx.typeName().getText() if middle_ctx.typeName() else ""
        rel_type_label = rel_var.lower().replace("type", "").capitalize() if rel_var else ""
        
        self.current_rel = {
            "entityType" : "relationship", "id": rel_id, "type": rel_type_label,
            "relationshipType": "ASSOCIATION", "style": {}, "properties": {},
            "fromId": from_id, "toId": to_id, "description": ""
        }
        
        # 3. Analisi del blocco MiddleType e Reificazioni
        lbl_prop_ctx = middle_ctx.labelPropertySpec()
        if lbl_prop_ctx:
            if lbl_prop_ctx.OPEN(): pass 
            
            # Legge prima le proprietà esplicite per non perderle
            prop_spec = lbl_prop_ctx.propertySpec()
            if prop_spec:
                self.visit(prop_spec)
            
            # Applica le regole logiche AST
            spec_ctx = lbl_prop_ctx.labelSpec()
            if spec_ctx:
                ast_spec = self._parse_ast_label(spec_ctx)
                
                if ast_spec["type"] == "leaf":
                    if ast_spec["is_type"]:
                        self._handle_edge_inheritance(ast_spec, from_caption, to_caption)
                    else:
                        self.current_rel["type"] = ast_spec["value"].replace("\"", "")
                elif ast_spec["type"] == "AND":
                    self._handle_edge_and(ast_spec, from_caption, to_caption)
                elif ast_spec["type"] == "XOR":
                    self._handle_edge_xor(ast_spec, from_caption, to_caption)
                    
        self.json_schema["relationships"].append(self.current_rel)
        self.current_rel = None
        
        return self.json_schema

    # ==================================
    # HANDLER DI REIFICAZIONE (LOGICA PURA)
    # ==================================

    def _create_aux_node(self, caption):
        """Genera nodi ausiliari visivi per i vincoli delle reificazioni."""
        aux_id = f"n{self.node_counter}"
        self.node_counter += 1
        aux_node = {
            "entityType": "node", "id": aux_id,
            "position": {"x": random.randint(100, 800), "y": random.randint(100, 600)},
            "caption": caption, "description": "", "abstract": False,
            "open": {"class": False, "properties": False}, "properties": {}, "style": {}
        }
        self.json_schema["nodes"].append(aux_node)
        self.id_to_node[aux_id] = aux_node
        return aux_id

    def _handle_edge_and(self, ast_spec, from_caption, to_caption):
        if "constraints" not in self.current_rel: self.current_rel["constraints"] = []
            
        leaves = self._extract_leaves(ast_spec)
        for leaf in leaves:
            clean_name = leaf["value"].replace("\"", "")
            caption = clean_name.capitalize()
            prop_name = clean_name.lower().replace("type", "")
            
            self.current_rel["properties"][prop_name] = {
                "description": "", "requiredType": "optional" if leaf["optional"] else "required", "range": caption
            }
            
            self.current_rel["constraints"].append(f"self.source == self.{prop_name}.source")
            self.current_rel["constraints"].append(f"self.target == self.{prop_name}.target")
            
            aux_id = self._create_aux_node(caption)
            aux_node = self.id_to_node[aux_id]
            aux_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": from_caption}
            aux_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": to_caption}

    def _handle_edge_xor(self, ast_spec, from_caption, to_caption):
        parent_caption = self.current_rel["type"] if self.current_rel["type"] else "UnknownRel"
        parent_id = self._create_aux_node(parent_caption)
        parent_node = self.id_to_node[parent_id]
        
        parent_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": from_caption}
        parent_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": to_caption}
        for k, v in self.current_rel["properties"].items(): parent_node["properties"][k] = v.copy()
            
        leaves = self._extract_leaves(ast_spec)
        for leaf in leaves:
            child_caption = leaf["value"].replace("\"", "").capitalize()
            child_id = self._create_aux_node(child_caption)
            
            inh_rel_id = f"n{self.rel_counter}"
            self.rel_counter += 1
            self.json_schema["relationships"].append({
                "entityType": "relationship", "id": inh_rel_id, "relationshipType": "INHERITANCE",
                "style": {}, "properties": {}, "fromId": child_id, "toId": parent_id, "description": ""
            })
            
    def _handle_edge_inheritance(self, ast_spec, from_caption, to_caption):
        parent_id = self._get_or_create_node_by_var(ast_spec["value"])
        parent_node = self.id_to_node[parent_id]
        
        main_caption = self.current_rel["type"] if self.current_rel["type"] else "Unknown"
        main_id = self._create_aux_node(main_caption)
        main_node = self.id_to_node[main_id]
        
        main_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": from_caption}
        main_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": to_caption}
        for k, v in self.current_rel["properties"].items(): main_node["properties"][k] = v.copy()
            
        inh_rel_id = f"n{self.rel_counter}"
        self.rel_counter += 1
        self.json_schema["relationships"].append({
            "entityType": "relationship", "id": inh_rel_id, "relationshipType": "INHERITANCE",
            "style": {}, "properties": {}, "fromId": main_id, "toId": parent_id, "description": ""
        })
        
        if "source" not in parent_node["properties"]:
            parent_node["properties"]["source"] = {"description": "", "requiredType": "required", "range": from_caption}
            parent_node["properties"]["target"] = {"description": "", "requiredType": "required", "range": to_caption}

global_style = {
    # (Incolla il tuo global_style qui sotto)
}