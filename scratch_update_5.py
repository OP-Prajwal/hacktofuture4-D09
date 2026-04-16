import sys

file_path = 'frontend/src/pages/Onboarding/Onboarding.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace(
'''value={ind.name} onChange={e => setInd({...ind, name: e.target.value})} />''',
'''value={ind.name} onChange={e => setInd({...ind, name: e.target.value.replace(/\\//g, '')})} />'''
)

code = code.replace(
'''value={ent.company} onChange={e => setEnt({...ent, company: e.target.value})} />''',
'''value={ent.company} onChange={e => setEnt({...ent, company: e.target.value.replace(/\\//g, '')})} />'''
)

code = code.replace(
'''value={ent.name} onChange={e => setEnt({...ent, name: e.target.value})} />''',
'''value={ent.name} onChange={e => setEnt({...ent, name: e.target.value.replace(/\\//g, '')})} />'''
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated Onboarding.tsx input validation')
