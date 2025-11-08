import os
import re

RELATIONSHIPS = {
    '@OneToOne': '"1"--"1"',
    '@OneToMany': '"1"--"*"',
    '@ManyToOne': '"*"--"1"',
    '@ManyToMany': '"*"--"*"'
}

# 👇 Hardcoded path here
input_directory = r"C:\Users\user\Documents\erp-ayoub\erp\src\main\java\it\solutions\erp"  # Change this to your Java directory

def parse_enum(content, package_name):
    enums = []
    matches = re.finditer(r'public\s+enum\s+(\w+)\s*{([^}]*)}', content, re.DOTALL)
    for match in matches:
        name = match.group(1)
        values = [val.strip() for val in match.group(2).split(",") if val.strip()]
        enums.append({"name": name, "values": values, "package": package_name})
    return enums

def parse_java_file(file_path):
    print(f"Processing file: {file_path}")  
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return None, [], None

    # Extract the package name from the `package` declaration in the Java file
    package_match = re.search(r'^\s*package\s+([\w.]+);', content, re.MULTILINE)
    full_package_name = package_match.group(1) if package_match else "default"
    package_name = full_package_name.split('.')[-2] if '.' in full_package_name else full_package_name
    print(f"Detected simplified package: {package_name}")

    # Parse enums and associate them with the package
    enums = parse_enum(content, package_name)

    class_match = re.search(r'@Entity\b[\s\S]*?public\s+class\s+(\w+)', content, re.IGNORECASE)
    if class_match:
        print("Detected @Entity annotation: This file is considered an entity class.")
    else:
        print("No @Entity annotation found: This file is not considered an entity class.")
        return None, enums, package_name  

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
    }, enums, package_name

def parse_directory(directory):
    packages = {}
    enums = []

    for root, dirs, files in os.walk(directory):
        print(f"Processing directory: {root}")
        
        for file in files:
            if file.endswith(".java"):
                path = os.path.join(root, file)
                class_def, found_enums, package_name = parse_java_file(path)
                if class_def:
                    if package_name not in packages:
                        packages[package_name] = []
                    packages[package_name].append(class_def)
                enums.extend(found_enums)

    return packages, enums

def generate_plantuml(packages, enums):
    lines = ["@startuml \n !theme spacelab", ""]

    relations = set()  

    for package_name, classes in packages.items():
        lines.append(f"package {package_name} {{")
        for cls in classes:
            lines.append(f"  class {cls['class']} {{")
            for field_type, field_name in cls['fields']:
                lines.append(f"    {field_type} {field_name}")
            lines.append("  }\n")
        # Add enums belonging to this package
        for enum in [e for e in enums if e["package"] == package_name]:
            lines.append(f"  enum {enum['name']} {{")
            for val in enum['values']:
                lines.append(f"    {val}")
            lines.append("  }\n")
        lines.append("}\n")

    # Add relationships
    for package_name, classes in packages.items():
        for cls in classes:
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

    lines.extend(relations)
    lines.append("@enduml")
    return "\n".join(lines)

def compare_and_output_differences(file1, file2, output_diff_file):
    print(f"\nComparing {file1} with {file2}...")
    try:
        with open(file1, 'r', encoding='utf-8') as f1, open(file2, 'r', encoding='utf-8') as f2:
            file1_lines = f1.readlines()  # Reference file
            file2_lines = f2.readlines()  # Newly generated file

        # Parse the files into blocks (packages and their contents)
        def parse_blocks(lines):
            blocks = {}
            current_package = None
            current_block = []
            for line in lines:
                line = line.strip()
                if line.startswith("package"):
                    if current_package and current_block:
                        blocks[current_package] = current_block
                    current_package = line
                    current_block = []
                elif line == "}":
                    if current_package and current_block:
                        blocks[current_package] = current_block
                    current_package = None
                    current_block = []
                elif current_package:
                    current_block.append(line)
            # Ensure the last package is added
            if current_package and current_block:
                blocks[current_package] = current_block
            return blocks

        reference_blocks = parse_blocks(file1_lines)
        new_file_blocks = parse_blocks(file2_lines)

        # Find differences: Only include blocks present in the reference but not in the new file
        differences = {}
        for package, block in reference_blocks.items():
            if package not in new_file_blocks or new_file_blocks[package] != block:
                differences[package] = block

        # Write differences to a new PlantUML file
        with open(output_diff_file, "w", encoding="utf-8") as diff_file:
            diff_file.write("@startuml\n")
            for package, block in differences.items():
                diff_file.write(f"{package}\n")
                diff_file.write("\n".join(block))
                diff_file.write("\n}\n")  # Properly close the package block
            diff_file.write("@enduml\n")

        print(f"Differences have been written to {output_diff_file}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An error occurred while comparing files: {e}")

if __name__ == "__main__":
    if not os.path.isdir(input_directory):
        print("That directory doesn't exist. Please check the path.")
    else:
        packages, enums = parse_directory(input_directory)
        print(f"Found {sum(len(classes) for classes in packages.values())} entity classes.")
        diagram = generate_plantuml(packages, enums)
        
        output_file = "output.pu"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(diagram)
        
        print(f"\nGenerated PlantUML diagram has been written to {output_file}")

        # Compare the generated file with a reference file and output differences
        reference_file = "diag.pu"  # Replace with the path to your reference file
        output_diff_file = "differences.pu"
      #  compare_and_output_differences(output_file, reference_file, output_diff_file)
