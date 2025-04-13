import os
import re

RELATIONSHIPS = {
    '@OneToOne': '"1"--"1"',
    '@OneToMany': '"1"--"*"',
    '@ManyToOne': '"*"--"1"',
    '@ManyToMany': '"*"--"*"'
}

# 👇 Hardcoded path here
input_directory = r"path\to\your\java\directory"  # Change this to your Java directory

def parse_enum(content):
    enums = []
    matches = re.finditer(r'public\s+enum\s+(\w+)\s*{([^}]*)}', content, re.DOTALL)
    for match in matches:
        name = match.group(1)
        values = [val.strip() for val in match.group(2).split(",") if val.strip()]
        enums.append({"name": name, "values": values})
    return enums

def parse_java_file(file_path):
    print(f"Processing file: {file_path}")  
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return None, []

    enums = parse_enum(content)

    class_match = re.search(r'@Entity\b[\s\S]*?public\s+class\s+(\w+)', content, re.IGNORECASE)
    if class_match:
        print("Detected @Entity annotation: This file is considered an entity class.")
    else:
        print("No @Entity annotation found: This file is not considered an entity class.")
        return None, enums  

    class_name = class_match.group(1)
    fields = []
    relations = []
    used_enums = []
    print(f"Found entity class: {class_name}")

    lines = content.splitlines()
    current_relation = None

    for line in lines:
        line = line.strip()

        if any(line.startswith(ann) for ann in RELATIONSHIPS):
            current_relation = line.split('(')[0]
            print(f"Detected relationship annotation: {current_relation}")
            continue

        field_match = re.match(r'(private|protected|public)\s+([\w<>.]+)\s+(\w+);', line)
        if field_match:
            type_, name = field_match.group(2), field_match.group(3)

            type_ = re.sub(r'Set<(\w+)>', r'\1', type_)

            fields.append((type_, name))
            print(f"Found field: {name} of type {type_}")

            if current_relation:
                relations.append((current_relation, type_))
                print(f"Adding relationship: {class_name} {current_relation} {type_}")
                current_relation = None

            if type_:
                used_enums.append(type_)

    return {
        "class": class_name,
        "fields": fields,
        "relations": relations,
        "used_enums": used_enums
    }, enums

def parse_directory(directory):
    class_defs = []
    enums = []

    for root, dirs, files in os.walk(directory):
        print(f"Processing directory: {root}")
        
        for file in files:
            if file.endswith(".java"):
                path = os.path.join(root, file)
                class_def, found_enums = parse_java_file(path)
                if class_def:
                    class_defs.append(class_def)
                enums.extend(found_enums)

    return class_defs, enums

def generate_plantuml(classes, enums):
    lines = ["@startuml", ""]
    relations = set()  

    for cls in classes:
        lines.append(f"class {cls['class']} {{")
        for field_type, field_name in cls['fields']:
            lines.append(f"    {field_type} {field_name}")
        lines.append("}\n")

        for rel_type, target_class in cls['relations']:
            rel_arrow = RELATIONSHIPS.get(rel_type, '--')
            if cls['class'] < target_class:
                relationship = f"{cls['class']} {rel_arrow} {target_class}"
            else:
                reversed_arrow = rel_arrow.replace('"1"', '"TEMP"').replace('"*"', '"1"').replace('"TEMP"', '"*"')
                relationship = f"{target_class} {reversed_arrow} {cls['class']}"
            relations.add(relationship)

        for enum_name in cls['used_enums']:
            if any(e["name"] == enum_name for e in enums):
                relations.add(f"{cls['class']} --> {enum_name}")

    for enum in enums:
        lines.append(f"enum {enum['name']} {{")
        for val in enum['values']:
            lines.append(f"    {val}")
        lines.append("}\n")

    lines.extend(relations)
    lines.append("@enduml")
    return "\n".join(lines)

if __name__ == "__main__":
     if not os.path.isdir(input_directory):
        print("That directory doesn't exist. Please check the path.")
     else:
        class_defs, enums = parse_directory(input_directory)
        print(f"Found {len(class_defs)} entity classes.")
        diagram = generate_plantuml(class_defs, enums)
        
        output_file = "plant.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(diagram)
        
        print(f"\nGenerated PlantUML diagram has been written to {output_file}")
