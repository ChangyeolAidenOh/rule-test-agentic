from pathlib import Path
import re,types,csv
from decimal import Decimal as D
from datetime import date,timedelta
BASE=Path(__file__).parent
mods={}
for sid in ['S1','S2','S3','S4','S5']:
    txt=(BASE/'code'/f'{sid}.txt').read_text()
    lines=[]
    for line in txt.splitlines():
        m=re.match(r'^\s*\d+: ?(.*)$',line)
        if not m:raise ValueError(f'invalid line: {line}')
        lines.append(m.group(1))
    mod=types.ModuleType(sid)
    exec(compile('\n'.join(lines), f'{sid}.py','exec'), mod.__dict__)
    mods[sid]=mod
s1,s2,s3,s4,s5=[mods[k] for k in ('S1','S2','S3','S4','S5')]
rows=[]
def record(sid,cid, case, expected, actual):
    rows.append({'scenario_id':sid,'condition_id':cid,'case':case,'spec_expected':str(expected),'code_actual':str(actual),'match':expected==actual})
# S1
for v in [64,65,66]: record('S1','C1',f'age={v}',v>=65,s1._is_age_surcharge_applicable(v))
for v in [4,5,6]: record('S1','C2',f'claim_free_years={v}',v>=5,s1._is_no_claim_discount_applicable(v))
# S2
for v in [89,90,91]: record('S2','C1',f'days_since_inception={v}',v>90,s2._is_waiting_period_satisfied(v))
for v in [179,180,181]:
  if v<=180: actual=s2._is_annual_limit_available(v)
  else:
    try:s2.apply_rule(91,v,1);actual=True
    except ValueError:actual=False
  record('S2','C2',f'annual_hospitalization_days_used={v}',v<180,actual)
for v in [0,1,2]:
  try:s2.apply_rule(91,0,v);actual=True
  except ValueError:actual=False
  record('S2','C3',f'claimed_hospitalization_days={v}',v>=1,actual)
# S3
for a,b in [('J18.9','J18.9'),('J18.9','J18.8')]:
  actual=s3._is_same_disease(a,b)
  record('S3','C1',f'prior={a},readmission={b}',a==b,actual)
for days in [179,180,181]: record('S3','C2',f'days_between={days}',days<=180,s3._determine_single_hospitalization(True,days))
for prior,combined,lim in [(D('700'),D('300'),D('1000')),(D('700'),D('301'),D('1000')),(D('1000'),D('100'),D('1000'))]:
  result=s3._calculate_cumulative_annual_benefit(prior,combined,lim)
  record('S3','C3',f'prior={prior},add={combined},limit={lim}',True,result<=lim)
# S4
for v in [D('-1'),D('0'),D('1')]:
  try:s4.apply_rule(v,D('0'),D('0'),D('0'));actual=True
  except ValueError:actual=False
  record('S4','C1',f'total_paid_premium={v}',v>0,actual)
for cid,idx in [('C2',1),('C3',2),('C4',3)]:
 for v in [D('-1'),D('0'),D('1')]:
  args=[D('10'),D('0'),D('0'),D('0')];args[idx]=v
  try:s4.apply_rule(*args);actual=True
  except ValueError:actual=False
  record('S4',cid,f'input_{idx}={v}',v>=0,actual)
for paid,risk,expense,deduct in [(D('100'),D('40'),D('30'),D('30')),(D('100'),D('40'),D('30'),D('31')),(D('100'),D('40'),D('30'),D('29'))]:
  res=s4.apply_rule(paid,risk,expense,deduct)
  before=res['surrender_value_before_floor']
  record('S4','C5',f'paid={paid},risk={risk},expense={expense},deduction={deduct}',True,before>=0)
# S5
for v in [89,90,91]:
  res=s5.apply_rule(v,'stroke',D('100'),policy_status='active')
  record('S5','C1',f'days={v}',v>90,res['is_eligible'])
for v in ['cancer','acute_myocardial_infarction','stroke','flu']:
  res=s5._is_covered_disease(v)
  record('S5','C2',f'disease={v}',v in {'cancer','acute_myocardial_infarction','stroke'},res)
for v in ['thyroid_cancer','skin_cancer','lung_cancer']:
  actual=s5._is_minor_cancer('cancer',v)
  record('S5','C3',f'cancer_type={v}',v in {'thyroid_cancer','skin_cancer'},actual)
for v in ['active','lapsed']:
  actual=s5._is_policy_active(v)
  record('S5','C4',f'policy_status={v}',v=='active',actual)
with open(BASE/'boundary_test_evidence.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
for r in rows: print(f"{r['scenario_id']}-{r['condition_id']} {r['case']}: spec={r['spec_expected']} code={r['code_actual']} {'OK' if r['match'] else 'MISMATCH'}")
print('Cases:',len(rows),'Mismatches:',sum(not r['match'] for r in rows))
