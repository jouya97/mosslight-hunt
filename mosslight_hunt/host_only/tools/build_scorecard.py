"""Authoring-only migration from the preserved original manifest/probe archive.

Runtime reads only the generated scorecard, programs and expected tables.
Run from any working directory to regenerate that exact reviewable packet.
"""
import ast, copy, json, pathlib, shutil
root=pathlib.Path(__file__).resolve().parents[2]
data=root/'grader/grader_data'; archive=root/'host_only/probe_archive'; archive.mkdir(exist_ok=True)
files=('probes_ecology_forms.json','probes_persistence.json','probes_specialist.json','probes_irrigation.json')
probes=[]
for name in files:
    source=data/name
    if source.exists(): shutil.move(source,archive/name)
    probes.extend(json.loads((archive/name).read_text()))
programs=data/'probes';programs.mkdir(exist_ok=True)
expected={}; descriptors=[]
for probe in probes:
    bug=probe['id'];program=probe['program']
    if bug=='I02':
        fixtures=ast.literal_eval(ast.parse(program).body[2].value)
        world=fixtures[0]['world']
        assert all(f['world']==world for f in fixtures)
        params=[{k:v for k,v in f.items() if k!='world'} for f in fixtures]
        lines=program.splitlines(); assert lines[2].startswith('fixtures = ')
        cell=world['cells'][0];tile=world['workbench']['tiles'][0]
        assert all(c==cell for c in world['cells']) and all(t==tile for t in world['workbench']['tiles'])
        world_fields={k:v for k,v in world.items() if k not in ('cells','workbench')}
        wb_fields={k:v for k,v in world['workbench'].items() if k!='tiles'}
        lines[2:3]=[
            '# Fixed input world, shared by five scheduling problems. Every fixture gets a copy.',
            f'base_world = {world_fields!r}',
            f'base_world["cells"] = [copy.deepcopy({cell!r}) for _ in range(16)]',
            f'base_world["workbench"] = {wb_fields!r}',
            f'base_world["workbench"]["tiles"] = [copy.deepcopy({tile!r}) for _ in range(16)]',
            'parameters = [', *['    '+repr(p)+',' for p in params],']',
            'fixtures = [dict(world=copy.deepcopy(base_world), **params) for params in parameters]',
        ]
        program='\n'.join(lines)+'\n'
        compact=[]
        for case in probe['expected']:
            schedules={}
            for schedule,report in case['schedules'].items():
                w=report['world']; reconstructed=copy.deepcopy(world)
                reconstructed['day']=w['day'];reconstructed['cells'][:2]=w['cells'][:2]
                assert reconstructed==w, (schedule,'world factoring lost data')
                schedules[schedule]={'score':report['score'],'remaining':report['remaining'],'day':w['day'],'cells':w['cells'][:2]}
                assert set(report)=={'score','remaining','world'}
            compact.append({'best':case['best'],'schedules':schedules})
        packed={'world_template':world,'cases':compact}
        # Compact line per complete schedule keeps data legible and avoids repeated worlds.
        text='{"world_template": '+json.dumps(world,ensure_ascii=False)+',\n "cases": [\n'
        for ci,case in enumerate(compact):
            text+='  {"best": '+json.dumps(case['best'])+', "schedules": {\n'
            text+=',\n'.join('    '+json.dumps(k)+': '+json.dumps(v,ensure_ascii=False) for k,v in case['schedules'].items())
            text+='\n  }}'+(',' if ci+1<len(compact) else '')+'\n'
        text+=' ]\n}\n'
        (data/'irrigation_expected.json').write_text(text)
        assert json.loads(text)==packed
        expected[bug]={'expected_file':'irrigation_expected.json'}
    else: expected[bug]={'expected':probe['expected']}
    if 'comparator' in probe: expected[bug]['comparator']=probe['comparator']
    (programs/(bug+'.py')).write_text(program)
(data/'expected.json').write_text('{\n'+',\n'.join('  '+json.dumps(k)+': '+json.dumps(v,ensure_ascii=False) for k,v in expected.items())+'\n}\n')
manifest=json.loads((data/'manifest.json').read_text())
levels={'normal':1,'hard':5,'extreme':10,'legendary':20}
doc_map={
 'engine':('BEHAVIORS.md#core-ecology',), 'habitat':('BEHAVIORS.md#habitat',),
 'gardening':('BEHAVIORS.md#garden-tools-and-materials',), 'nursery':('BEHAVIORS.md#propagation-bench',),
 'planning':('BEHAVIORS.md#plans-and-rules',), 'analysis':('BEHAVIORS.md#field-measurements',),
 'notebook':('BEHAVIORS.md#notebook',), 'weather':('BEHAVIORS.md#calendar-and-experiments',),
 'experiments':('BEHAVIORS.md#calendar-and-experiments',), 'exchange':('BEHAVIORS.md#interchange-and-artwork',),
 'charts':('BEHAVIORS.md#interchange-and-artwork',), 'model':('BEHAVIORS.md#application-transactions-and-persistence',),
 'state':('BEHAVIORS.md#application-transactions-and-persistence',), 'commands':('BEHAVIORS.md#application-transactions-and-persistence','COMMANDS.md'),
 'server':('BEHAVIORS.md#application-transactions-and-persistence','DESIGN.md#interfaces'),
 '__main__':('BEHAVIORS.md#application-transactions-and-persistence','README.md#cli-workflows'),
 'render':('BEHAVIORS.md#interchange-and-artwork',), 'courier':('COURIER.md',), 'runtime':('DESIGN.md#daily-order',),
 'campaigns':('CAMPAIGNS.md',), 'history':('HISTORY.md',), 'ensembles':('ENSEMBLES.md',),
 'ensemble_reports':('ENSEMBLES.md',), 'ensemble_compute':('ENSEMBLES.md',), 'save_merge':('SAVE_MERGE.md',),
 'history_exchange':('HISTORY_EXCHANGE.md',), 'studies':('STUDIES.md',), 'field_calibration':('FIELD_CALIBRATION.md',),
 'workspace_catalog':('WORKSPACE_CATALOG.md',), 'irrigation_flow':('IRRIGATION.md',), 'irrigation':('IRRIGATION.md',),
}
entries=[]
for e in manifest['entries']:
    bug=e['id']; sources=sorted({x['file'] for x in e.get('locations',[]) } or {e['file']})
    docs=list(doc_map[pathlib.Path(e['file']).stem])
    for doc in docs: assert (root/'host_only/seeded_snapshot'/doc.split('#')[0]).exists()
    ref='grader.py:FinalOracle:N01' if bug=='N01' else 'grader.py:flow_probe+valid_flow:I01' if bug=='I01' else 'grader_data/probes/'+bug+'.py'
    entries.append({'id':bug,'weight':levels[e['level']],'contract':e['contract'],'documentation':docs,'source':sources,'probe':ref})
scorecard={'schema_version':1,'policy':'independent_repair_process_v2','documentation_root':'host_only/seeded_snapshot','entries':entries}
(data/'scorecard.json').write_text('{\n  "schema_version": 1,\n  "policy": "independent_repair_process_v2",\n  "documentation_root": "host_only/seeded_snapshot",\n  "entries": [\n'+',\n'.join('    '+json.dumps(e,ensure_ascii=False) for e in entries)+'\n  ]\n}\n')
print('Generated',len(entries),'scorecard entries,',len(probes),'static programs')
