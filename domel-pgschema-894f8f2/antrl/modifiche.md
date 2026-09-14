# Report modifiche — SchemaLink (supporto PG-Schema)

Riepilogo delle funzionalità aggiunte all'editor SchemaLink (`schemalink-webapp`, app `arrows-ts`) per supportare i costrutti PG-Schema. Tutti i percorsi sono relativi a `schemalink-webapp/`.

---

## 1. Bottoni Import/Export PG-Schema (placeholder)

Aggiunta una tab "PG-Schema" nell'export e un'opzione "PG-Schema" nell'import, entrambe con messaggio "coming soon" (nessuna logica di conversione ancora implementata).

**File:**
- `apps/arrows-ts/src/components/ExportPgSchemaPanel.tsx` *(nuovo)* — pannello placeholder
- `apps/arrows-ts/src/components/ExportModal.tsx` — nuova tab "PG-Schema"
- `apps/arrows-ts/src/components/ImportModal.tsx` — nuova opzione radio "PG-Schema"

---

## 2. Clausola OPEN

Due toggle per nodo: se la classe ammette label/proprietà aggiuntive non dichiarate nello schema.

- **"Open Class"** — sotto "Abstract"
- **"Open attributes"** — sotto la sezione "Attributes"

**JSON:**
```json
"open": { "class": true, "properties": true }
```

**File:**
- `libs/model/src/lib/Node.ts` — campo `open?: NodeOpen`
- `libs/model/src/lib/Graph.ts` — fix diff-check per il re-render (vedi nota bug §11)
- `apps/arrows-ts/src/actions/graph.ts`, `reducers/graph.ts`, `containers/InspectorContainer.ts` — azione/reducer `SET_NODE_OPEN`
- `apps/arrows-ts/src/components/DetailInspector.tsx` — UI dei due toggle

---

## 3. Clausola STRICT (Schema Type)

Toggle Loose/Strict nella sidebar dello schema (sezione Description/NER/RE Guidelines/License).

**JSON:**
```json
"graphTypeMode": "Strict"
```

**File:**
- `libs/model/src/lib/Graph.ts` — campo `graphTypeMode?: 'Strict' | 'Loose'` su `SchemaProperties`
- `apps/arrows-ts/src/components/GeneralInspector.tsx` — toggle "Schema Type" (riusa il dispatch generico `SET_SCHEMA_PROPERTIES` già esistente)

---

## 4. Ereditarietà opzionale (INHERITANCE `required`)

Toggle "Required" nella sidebar della relazione, visibile solo per relazioni di tipo INHERITANCE. Default `true`.

**JSON:**
```json
"required": false
```

**Grafica:** frecce di ereditarietà con `required: false` → tratto **tratteggiato** (stessa convenzione già usata per il bordo dei nodi astratti), triangolo vuoto invariato.

**File:**
- `libs/model/src/lib/Relationship.ts` — campo `required?: boolean`
- `apps/arrows-ts/src/actions/graph.ts`, `reducers/graph.ts`, `containers/InspectorContainer.ts` — azione/reducer `SET_INHERITANCE_REQUIRED`
- `apps/arrows-ts/src/components/DetailInspector.tsx` — toggle "Required"
- `libs/graphics/src/lib/arrowDimensions.ts`, `StraightArrow.ts`, `BalloonArrow.ts`, `ParallelArrow.ts` — rendering tratteggiato dello shaft

---

## 5. EXCLUSIVE INHERITANCE (vincolo XOR)

Terzo tipo di relazione, per gruppi di generalizzazione mutuamente esclusivi (un'istanza del genitore può appartenere a una sola sottoclasse).

**Vincolo:** servono **almeno 2** relazioni EXCLUSIVE INHERITANCE verso lo stesso genitore; altrimenti warning non bloccante in rosso ("Exclusive inheritance requires at least two child relationships pointing to the same parent"), stile identico agli avvisi di duplicato già presenti in app.

**JSON:**
```json
"relationshipType": "EXCLUSIVE INHERITANCE"
```

**Grafica (non prevista da UML, scelta di design):** stesso stile dell'ereditarietà semplice (shaft sottile, triangolo vuoto), ma con il **contorno del triangolo tratteggiato**, per distinguerla a colpo d'occhio sia dall'ereditarietà normale che da quella opzionale.

| Tipo | Shaft | Punta della freccia |
|---|---|---|
| INHERITANCE (required) | continuo | triangolo vuoto continuo |
| INHERITANCE (optional) | tratteggiato | triangolo vuoto continuo |
| EXCLUSIVE INHERITANCE | continuo | triangolo vuoto tratteggiato |

**File:**
- `libs/model/src/lib/Relationship.ts` — nuovo valore enum `EXCLUSIVE_INHERITANCE`
- `apps/arrows-ts/src/reducers/graph.ts` — generalizzato il blocco anti-duplicato (un solo arco strutturale per coppia di nodi) a entrambi i tipi
- `apps/arrows-ts/src/components/DetailInspector.tsx` — opzione nel menu "Relationship type", warning XOR, fix dropdown (usava le *keys* dell'enum invece dei *values*)
- `apps/arrows-ts/src/components/ContextMenu.tsx`, `utils/sanitizeGraph.js`, `components/ExportJsonPanel.tsx`, `actions/export.ts` — estese le esclusioni già esistenti per INHERITANCE
- `libs/graphics/src/lib/arrowDimensions.ts` + le tre classi freccia — dashing del contorno della punta

**Nota di scope:** LinkML PG import/export (`libs/linkml`), l'helper GPT (`GptModal.tsx`) e l'adattatore Google Drive riconoscono ancora solo `INHERITANCE`; se serve estenderli, è lavoro a parte.

---

## 6. Value Constraints (per attributo)

Nella sidebar dell'attributo (Description/Range/Collection Type/Required), sezione "Value Constraints": lista di vincoli, ciascuno con operatore e valore.

- **Operatori:** `=`, `!=`, `>`, `<`, `>=`, `<=`
- **Più vincoli per attributo** ammessi (nessuna validazione di coerenza tra loro — a carico dell'utente)
- **Ogni riga può essere letterale (int/string) o un riferimento** a un attributo di un'altra classe/relazione (menu a tendina con `Classe.attributo`, per le relazioni include sempre `fromId`/`toId`)
- Disponibile sia per attributi di **nodi** che di **relazioni ASSOCIATION**

**JSON — valore letterale:**
```json
"constraints": [
  { "on": "salary", "type": "property_value", "operator": ">=", "value": 1000 }
]
```

**JSON — riferimento (un "type" per operatore):**
```json
"constraints": [
  { "on": "source", "type": "equal", "target": "Friend.fromId" }
]
```

| Operatore | `type` di riferimento |
|---|---|
| `=` | `equal` |
| `!=` | `not_equal` |
| `>` | `greater_than` |
| `<` | `less_than` |
| `>=` | `greater_than_or_equal` |
| `<=` | `less_than_or_equal` |

**File:**
- `libs/model/src/lib/Id.ts` — tipi `PropertyValueConstraint`, `PropertyReferenceConstraint`, `PropertyConstraint`, `PropertyConstraintDraft`
- `apps/arrows-ts/src/actions/graph.ts`, `reducers/graph.ts`, `containers/InspectorContainer.ts` — azione/reducer `SET_PROPERTY_CONSTRAINTS`, sincronizzazione su rinomina/rimozione attributo
- `apps/arrows-ts/src/components/DetailInspector.tsx` — calcolo delle opzioni `Classe.attributo` disponibili nel grafo
- `apps/arrows-ts/src/components/PropertyTable.tsx`, `PropertyRow.tsx` — UI della lista di vincoli

---

## 7. Attributo Unique

Toggle "Unique" nell'attributo, subito dopo "Required".

**JSON:**
```json
"properties": {
  "email": { "requiredType": "optional", "range": "string", "unique": true }
}
```

**File:**
- `libs/model/src/lib/Id.ts` — campo `unique?: boolean` su `Attribute`
- `apps/arrows-ts/src/components/PropertyRow.tsx` — toggle (riusa il salvataggio generico dell'attributo già esistente, nessuna nuova azione/reducer)

---

## 8. Vincolo Disjoint tra classi sorelle

Nella sidebar del nodo, sezione "Disjoint" — **visibile solo se il nodo ha almeno un "fratello"** (altro nodo che eredita dallo stesso genitore diretto). Switch che abilita un menu a tendina con l'elenco dei fratelli (se ce n'è uno solo, è selezionato di default).

**JSON:**
```json
"constraints": [ { "type": "disjoint", "node": "Employee" } ]
```

**File:**
- `libs/model/src/lib/Id.ts` — tipo `DisjointConstraint`, unione `NodeConstraintEntry` (`constraints` dei nodi ora può contenere sia vincoli di proprietà sia vincoli di classe)
- `apps/arrows-ts/src/actions/graph.ts`, `reducers/graph.ts`, `containers/InspectorContainer.ts` — azione/reducer `SET_DISJOINT_CONSTRAINT`; la rinomina di un nodo aggiorna automaticamente i riferimenti "disjoint" che lo citano
- `apps/arrows-ts/src/components/DetailInspector.tsx` — calcolo dei fratelli e UI switch + dropdown

---

## 9. Indicatori "solo PG-Schema"

Icona informativa (ⓘ, hover) accanto a ogni funzionalità introdotta in questo thread, per chiarire che non è disponibile nell'export LinkML. Riusa il pattern già presente in app (icona `question circle outline` + `Popup`).

Applicata a: Schema Type, Open Class, Open attributes, Required (ereditarietà), Relationship type (solo quando è selezionato EXCLUSIVE INHERITANCE), Unique, Value Constraints, Disjoint.

**File:**
- `apps/arrows-ts/src/components/GeneralInspector.tsx`
- `apps/arrows-ts/src/components/DetailInspector.tsx`
- `apps/arrows-ts/src/components/PropertyRow.tsx`

---

## 10. Rifiniture grafiche

- Rinominato "Graph Type Mode" → "Schema Type"
- Rinominato "Open classes"/"Open properties" → "Open Class"/"Open attributes", spostati sotto "Abstract" e sotto "Attributes" rispettivamente
- Label "Unique" in grassetto
- Spaziatura aggiunta sopra "Open attributes"

---

## 11. Bug corretto durante lo sviluppo

`nodesDifferInMoreThanPositions` (`libs/model/src/lib/Graph.ts`) confrontava solo un elenco fisso di campi per decidere se ridisegnare la sidebar del nodo. Il campo `open` (poi anche `constraints`) non c'era: il salvataggio funzionava, ma la UI non si aggiornava finché non si deselezionava/riselezionava il nodo. Corretto aggiungendo i nuovi campi al confronto.

---

## Elenco completo dei file toccati

```
apps/arrows-ts/src/actions/export.ts
apps/arrows-ts/src/actions/graph.ts
apps/arrows-ts/src/components/ContextMenu.tsx
apps/arrows-ts/src/components/DetailInspector.tsx
apps/arrows-ts/src/components/ExportJsonPanel.tsx
apps/arrows-ts/src/components/ExportModal.tsx
apps/arrows-ts/src/components/ExportPgSchemaPanel.tsx   (nuovo)
apps/arrows-ts/src/components/GeneralInspector.tsx
apps/arrows-ts/src/components/ImportModal.tsx
apps/arrows-ts/src/components/PropertyRow.tsx
apps/arrows-ts/src/components/PropertyTable.tsx
apps/arrows-ts/src/containers/InspectorContainer.ts
apps/arrows-ts/src/reducers/graph.ts
apps/arrows-ts/src/utils/sanitizeGraph.js
libs/graphics/src/lib/arrowDimensions.ts
libs/graphics/src/lib/BalloonArrow.ts
libs/graphics/src/lib/ParallelArrow.ts
libs/graphics/src/lib/StraightArrow.ts
libs/model/src/lib/Graph.ts
libs/model/src/lib/Id.ts
libs/model/src/lib/Node.ts
libs/model/src/lib/Relationship.ts