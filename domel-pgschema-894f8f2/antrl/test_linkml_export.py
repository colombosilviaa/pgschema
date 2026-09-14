import json
from exportDefRev import convert_internal_representation_to_pgschema_dict, dump_pgschema

def run_test():
    with open("test.json", "r", encoding="utf-8") as f:
        linkml_graph = json.load(f)

    # Convertiamo la rappresentazione LinkML in PG-Schema
    schema_dict = convert_internal_representation_to_pgschema_dict(linkml_graph)
    pg_schema_text = dump_pgschema(schema_dict)

    print("\n==========================================")
    print("   OUTPUT PG-SCHEMA DA LINKML REALE")
    print("==========================================\n")
    print(pg_schema_text)
    print("\n==========================================")

if __name__ == "__main__":
    run_test()