import sys, json, pathlib, contextlib, io
source=pathlib.Path(sys.argv[1]).resolve();sys.path.insert(0,str(source/"backend"))
from tests_contracts.factories import make_economy
from config import CONFIG
rows=[]
for mode in [False,True]:
 e=make_economy(num_households=60,num_firms_per_category=2,seed=932)
 e.performance_mode=mode
 mismatches=[];earnings_errors=[]
 for _ in range(55):
  earned={}
  original={f.firm_id:f.apply_production_and_costs for f in e.firms}
  for f in e.firms:
   def capture(*a,_f=f,_fn=original[f.firm_id],**kw):
    for hid in _f.employees:earned[hid]=_f.actual_wages.get(hid,_f.wage_offer)
    return _fn(*a,**kw)
   f.apply_production_and_costs=capture
  with contextlib.redirect_stdout(io.StringIO()):e.step()
  for f in e.firms:
   if f.firm_id in original:f.apply_production_and_costs=original[f.firm_id]
  ceos={f.ceo_household_id for f in e.firms if f.ceo_household_id is not None}
  for h in e.households:
   f=e.firm_lookup.get(h.employer_id)
   if f is not None and abs(h.wage-f.actual_wages.get(h.household_id,f.wage_offer))>1e-6:
    mismatches.append([e.current_tick,h.household_id,h.wage,f.actual_wages.get(h.household_id)])
   if h.household_id in earned and h.household_id not in ceos and abs(h.last_wage_income-earned[h.household_id])>1e-6:
    earnings_errors.append([e.current_tick,h.household_id,earned[h.household_id],h.last_wage_income])
 rows.append({"performance_mode":mode,"ticks":55,"mirror_mismatches":len(mismatches),"earned_receipt_mismatches":len(earnings_errors),"mirror_examples":mismatches[:3],"earned_examples":earnings_errors[:3]})
print(json.dumps({"source":str(source),"rows":rows},indent=2))
