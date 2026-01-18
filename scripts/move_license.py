import os

readme_path = "/Users/rehanvishwanath/bikeshare-tui/README.md"

with open(readme_path, "r") as f:
    lines = f.readlines()

# Locate License section
license_start = -1
for i, line in enumerate(lines):
    if line.strip() == "## License":
        license_start = i
        break

if license_start != -1:
    # Extract License section (Assuming 2 lines + header)
    # Based on Read output:
    # 99: ## License
    # 100: MIT License. Data provided by Toronto Open Data.
    # 101: 
    
    license_content = lines[license_start:license_start+2]
    
    # Remove from middle (including the newline after it)
    del lines[license_start:license_start+3]
    
    # Append to end
    lines.append("\n\n")
    lines.extend(license_content)
    
    with open(readme_path, "w") as f:
        f.writelines(lines)
    print("Moved License to end.")
else:
    print("License section not found.")
