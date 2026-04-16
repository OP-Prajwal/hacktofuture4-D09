import sys

file_path = 'frontend/src/pages/Dashboard/Dashboard.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    orig_code = f.read()

# Replace the input onChange for project name
code = orig_code.replace('''e.target.value''', '''e.target.value.replace(/\//g, '')''')
# But wait, that replaces ALL e.target.values! We ONLY want the newProj ones!
code = orig_code.replace(
'''value={newProj.name} onChange={e => setNewProj({ ...newProj, name: e.target.value })} />''',
'''value={newProj.name} onChange={e => setNewProj({ ...newProj, name: e.target.value.replace(/\\//g, '') })} />'''
)

# And if there are any other inputs that need sanitization, maybe we just use that one.
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated Dashboard.tsx input validation')
