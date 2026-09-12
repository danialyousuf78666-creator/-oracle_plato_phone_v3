from __future__ import annotations
import argparse,json
from pathlib import Path
from hunter_engine import analyze_video,save_report,lock_report

def rect(s):
    v=tuple(float(x) for x in s.split(","));
    if len(v)!=4:raise argparse.ArgumentTypeError("use x0,y0,x1,y1")
    return v
p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",default="runs/batch");p.add_argument("--extraction-zone",required=True,type=rect);p.add_argument("--chamber-roi",type=rect);p.add_argument("--cutoff-seconds",type=float);p.add_argument("--radiation-weight",type=float,default=.10);p.add_argument("--specialist-weight",type=float,default=.20);a=p.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=True);rows=[]
for v in sorted([*Path(a.input).glob("*.mp4"),*Path(a.input).glob("*.mov"),*Path(a.input).glob("*.m4v")]):
    r=analyze_video(v,a.extraction_zone,chamber_roi=a.chamber_roi,cutoff_seconds=a.cutoff_seconds,radiation_weight=a.radiation_weight,specialist_weight=a.specialist_weight,recovery_dir="recovery");rp=out/f"{v.stem}.json";save_report(r,rp);lp=lock_report(rp);rows.append({"video":v.name,"report":str(rp),"lock":str(lp),"status":r["top6_status"],"top6":r["top6"]})
(out/"batch_index.json").write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
