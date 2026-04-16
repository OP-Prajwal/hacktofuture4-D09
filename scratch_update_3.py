import sys

file_path = 'backend/main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    orig_code = f.read()

# Replace endpoint parameters and arguments
code = orig_code.replace('{workspace_slug}', '{workspace}')
code = code.replace('workspace_slug: str', 'workspace: str')
code = code.replace('workspace_slug,', 'workspace,')
code = code.replace('!= workspace_slug:', '!= workspace:')
code = code.replace('(workspace_slug)', '(workspace)')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated main.py')
