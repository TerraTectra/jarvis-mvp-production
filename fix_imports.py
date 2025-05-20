import os
import re

def fix_imports_in_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Исправляем импорты вида 'from module' на 'from .module'
    pattern = r'^(\s*from\s+)(?!(\w+\.|\s*\.))([a-zA-Z0-9_]+)'
    new_content = re.sub(pattern, r'\1.\3', content, flags=re.MULTILINE)
    
    # Записываем изменения, если они есть
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed imports in {file_path}")

def main():
    src_dir = os.path.join(os.path.dirname(__file__), 'src')
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                fix_imports_in_file(file_path)

if __name__ == "__main__":
    main()
