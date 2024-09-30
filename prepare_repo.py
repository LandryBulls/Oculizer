import os

def is_relevant_file(filename):
    relevant_extensions = ('.py', '.json', '.md')
    irrelevant_patterns = ('__pycache__', '.vscode', '.DS_Store', '.gitignore')
    return filename.endswith(relevant_extensions) and not any(pattern in filename for pattern in irrelevant_patterns)

def generate_repo_overview(root_dir):
    overview = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Remove hidden directories and files from the walk
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and 'song_data' not in d]
        filenames = [f for f in filenames if not f.startswith('.') and is_relevant_file(f)]
        
        if not filenames:  # Skip empty directories
            continue
        
        level = dirpath.replace(root_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        overview.append(f'{indent}{os.path.basename(dirpath)}/')
        sub_indent = ' ' * 4 * (level + 1)
        for f in filenames:
            overview.append(f'{sub_indent}{f}')
            file_path = os.path.join(dirpath, f)
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                overview.append(f'\n{sub_indent}Content of {f}:')
                overview.append(f'{sub_indent}' + '-' * 40)
                overview.append(content)
                overview.append(f'{sub_indent}' + '-' * 40 + '\n')
    
    return '\n'.join(overview)

def main():
    root_dir = os.getcwd()  # Get the current working directory
    output_file = 'repo_overview.txt'
    
    repo_overview = generate_repo_overview(root_dir)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(repo_overview)
    
    print(f"Repository overview has been generated and saved to {output_file}")

if __name__ == "__main__":
    main()