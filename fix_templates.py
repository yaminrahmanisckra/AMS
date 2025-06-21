#!/usr/bin/env python3
"""
Script to fix duplicate template blocks in HTML files
"""

import os
import re
from pathlib import Path

def fix_template_file(file_path):
    """Fix duplicate blocks in a single template file"""
    print(f"Processing: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Fix duplicate {% block content %} ... {% endblock %}
    # Find all content blocks
    content_blocks = re.findall(r'{%\s*block\s+content\s*%}(.*?){%\s*endblock\s*%}', content, re.DOTALL)
    
    if len(content_blocks) > 1:
        print(f"  Found {len(content_blocks)} content blocks, keeping first one")
        # Keep only the first content block
        first_block = content_blocks[0]
        # Remove all content blocks and replace with just the first one
        content = re.sub(r'{%\s*block\s+content\s*%}.*?{%\s*endblock\s*%}', '', content, flags=re.DOTALL)
        # Add back the first block
        content = re.sub(r'{%\s*extends\s+[^}]+%}', f'\\g<0>\n\n{{% block content %}}{first_block}{{% endblock %}}', content)
    
    # Fix duplicate {% endblock %} tags
    endblock_count = content.count('{% endblock %}')
    if endblock_count > 1:
        print(f"  Found {endblock_count} endblock tags")
        # Keep only the last endblock
        content = re.sub(r'{%\s*endblock\s*%}\s*{%\s*endblock\s*%}', '{% endblock %}', content)
    
    # Fix duplicate {% block title %} ... {% endblock %}
    title_blocks = re.findall(r'{%\s*block\s+title\s*%}(.*?){%\s*endblock\s*%}', content, re.DOTALL)
    if len(title_blocks) > 1:
        print(f"  Found {len(title_blocks)} title blocks, keeping first one")
        first_title = title_blocks[0]
        content = re.sub(r'{%\s*block\s+title\s*%}.*?{%\s*endblock\s*%}', '', content, flags=re.DOTALL)
        content = re.sub(r'{%\s*extends\s+[^}]+%}', f'\\g<0>\n{{% block title %}}{first_title}{{% endblock %}}', content)
    
    # Write back if content changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Fixed: {file_path}")
        return True
    else:
        print(f"  No changes needed")
        return False

def find_html_files(directory):
    """Find all HTML files in directory and subdirectories"""
    html_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    return html_files

def main():
    """Main function to fix all template files"""
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # Find all HTML files
    html_files = find_html_files(project_root)
    
    print(f"Found {len(html_files)} HTML files")
    print("=" * 50)
    
    fixed_count = 0
    
    for file_path in html_files:
        try:
            if fix_template_file(file_path):
                fixed_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    print("=" * 50)
    print(f"Fixed {fixed_count} files out of {len(html_files)} total files")

if __name__ == "__main__":
    main() 