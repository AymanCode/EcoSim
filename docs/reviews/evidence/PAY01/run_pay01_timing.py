import pathlib,subprocess,json,time
r=pathlib.Path(__file__).parent
python="/Users/aymanislam/EcoSim_v_2/EcoSim/.venv/bin/python"
base=pathlib.Path("/Users/aymanislam/EcoSim_v_2/EcoSim")
script=base/"docs/reviews/benchmark_concrete_package.py"
rows=[]
for mode in [False,True]:
 for pair,order in enumerate([["baseline","candidate"],["candidate","baseline"]],1):
  for variant in order:
   source=base if variant=="baseline" else r/"candidate"
   out=r/"timing"/("performance" if mode else "normal")/str(pair)/variant
   cmd=[python,str(script),"--source-root",str(source),"--output-root",str(out),"--repeats","1","--households","1000","--seeds","42","--ticks","100"]
   if mode:cmd.append("--performance-mode")
   p=subprocess.run(cmd,cwd=source,text=True,capture_output=True)
   out.mkdir(parents=True,exist_ok=True);(out/"stdout.txt").write_text(p.stdout);(out/"stderr.txt").write_text(p.stderr)
   row={"mode":"performance" if mode else "normal","pair":pair,"variant":variant,"source":str(source),"exit_code":p.returncode,"output":str(out)};rows.append(row)
   (r/"timing_run_index.json").write_text(json.dumps({"scope":"early 1000-household timing; not full integrated 5-percent acceptance","order":"AB then BA within each mode","ticks":100,"seed":42,"runs":rows},indent=2)+"\n")
   print(json.dumps(row),flush=True)
   if p.returncode:raise SystemExit(p.returncode)
