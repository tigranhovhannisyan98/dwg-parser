#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_plan_all_inserts.py

Usage:
python3 extract_plan_all_inserts.py \
  --dxf out/good.dxf \
  --calib '282.14,1169.69:885,588;282.14,513:885,4460;522.14,820.16:2300,2650' \
"""
import argparse, json, math, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont as PILImageFont

import ezdxf
from ezdxf.colors import aci2rgb, int2rgb
from ezdxf.lldxf.const import DXFStructureError

import colorsys
import time

LAYOUTS_X = {
    "F": 468, 
    "F1": 590, 
    "G":  1236,
    "G1": 1886,
    "G2": 2537,
    "G3": 3188,
    "G4": 3843,
    "G5": 4491,
    "G6": 5136,
    "G7": 5790,
    "H":  6440,
    "H1": 7088,
    "H2": 7739,
    "H3": 8390,
    "I":  9044,
    "I1": 9690,
    "I2": 10340,
    "I3": 10990,
    "I4": 11644,
    "I5": 12300
}
LAYOUTS_Y = {
"45":500,
"44":1070,
"43":1730,
"42":2375,
"41":3025,
"40":3680,
"39":4330,
"38":4978,
"37":5620,
"36":6280,
"35":6930,
"34":7580,
"33":8230,
"32":8880,
"31":9530
}

#LAYOUTS_X = {
#    "A": 1907, 
#    "B": 2962, 
#    "C": 3610,
#    "D": 5035,
#    "E": 5643,
#    "F": 6463,
#    "G": 7110,
#    "H": 8165
#}
#LAYOUTS_Y = {
#"10": 1952,
#"9": 3130,
#"8": 4428,
#"7": 4953,
#"6": 5970,
#"5": 6848,
#"4": 7832,
#"3": 8610,
#"2": 9272,
#"1": 10188
#}
# ------------- chessboard ------------
from typing import Dict, List, Tuple, Any, Iterable, Union
import math

CoordMap = Union[Dict[str, float], Iterable[Tuple[str, float]]]

def _sorted_axis(layouts: CoordMap) -> List[Tuple[str, float]]:
    """
    Accepts either a dict {label: coord} or a list of (label, coord) pairs.
    Returns a list sorted by coord ascending.
    """
    if isinstance(layouts, dict):
        items = list(layouts.items())
    else:
        items = list(layouts)
    # ensure float and sort
    cleaned = [(str(k), float(v)) for k, v in items]
    cleaned.sort(key=lambda kv: kv[1])
    return cleaned

def _bounds_for(value: float, axis: List[Tuple[str, float]], clamp: bool = True) -> Tuple[str, str, float, float]:
    """
    Find the two neighboring labels (left/right or upper/lower) that bound 'value'.
    Returns (lo_label, hi_label, lo_coord, hi_coord).
    If outside, either clamp to first/last (when clamp=True) or raise ValueError.
    """
    n = len(axis)
    if n == 0:
        raise ValueError("Axis has no entries.")
    # if before first
    if value <= axis[0][1]:
        if clamp and n >= 2:
            return axis[0][0], axis[1][0], axis[0][1], axis[1][1]
        elif clamp and n == 1:
            return axis[0][0], axis[0][0], axis[0][1], axis[0][1]
        else:
            raise ValueError("Value below axis range.")
    # if after last
    if value >= axis[-1][1]:
        if clamp and n >= 2:
            return axis[-2][0], axis[-1][0], axis[-2][1], axis[-1][1]
        elif clamp and n == 1:
            return axis[0][0], axis[0][0], axis[0][1], axis[0][1]
        else:
            raise ValueError("Value above axis range.")
    # inside: find bracket
    lo_idx = 0
    hi_idx = 1
    for i in range(n - 1):
        c0 = axis[i][1]
        c1 = axis[i + 1][1]
        if c0 <= value <= c1:
            lo_idx = i
            hi_idx = i + 1
            break
    lo_lab, lo_coord = axis[lo_idx]
    hi_lab, hi_coord = axis[hi_idx]
    return lo_lab, hi_lab, lo_coord, hi_coord

def _normalize(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5  # degenerate cell; treat as center
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))

def _describe_position(nx: float, ny: float,) -> str:
    """
    nx, ny in [0..1] within the cell (nx: left→right, ny: upper→lower).
    Priority: center > corners > edges > quadrants. No 'thirds' wording.
    Tweak center_r / corner_box / edge_band to taste.
    """
    if nx < 1/3:
        horiz = "left"
    elif nx > 2/3:
        horiz = "right"
    else:
        horiz = "center"

    # Vertical band: upper / center / lower
    if ny < 1/3:
        vert = "upper"
    elif ny > 2/3:
        vert = "lower"
    else:
        vert = "center"

    # Match JavaScript return strings
    if vert == "center" and horiz == "center":
        return "center"
    if vert == "upper" and horiz == "left":
        return "upper left corner"
    if vert == "upper" and horiz == "right":
        return "upper right corner"
    if vert == "lower" and horiz == "left":
        return "lower left corner"
    if vert == "lower" and horiz == "right":
        return "lower right corner"
    if vert == "upper" and horiz == "center":
        return "upper center"
    if vert == "lower" and horiz == "center":
        return "lower center"
    if vert == "center" and horiz == "left":
        return "center left"
    if vert == "center" and horiz == "right":
        return "center right"


def assign_chessboard_and_position(
    items: List[dict],
    layouts_x: CoordMap,
    layouts_y: CoordMap,
    clamp_to_bounds: bool = True
) -> List[dict]:
    """
    Returns a NEW list with each dict augmented by:
      - 'grid_cols': [left_label, right_label]
      - 'grid_rows': [upper_label, lower_label]   (upper = smaller y)
      - 'chessboard_id': "[left,right],[upper-lower]"  (string)
      - 'position_description': human-friendly location in the cell
    """
    x_axis = _sorted_axis(layouts_x)
    y_axis = _sorted_axis(layouts_y)

    for key,obj in items.items():
        #print('obj: ', obj)
        px, py = obj.get("pos_img", [None, None])[:2]
        if px is None or py is None:
            continue

        try:
            lx, rx, x0, x1 = _bounds_for(float(px), x_axis, clamp=clamp_to_bounds)
            uy, ly, y0, y1 = _bounds_for(float(py), y_axis, clamp=clamp_to_bounds)
        except ValueError:
            # outside and clamp_to_bounds=False
            continue

        nx = _normalize(float(px), x0, x1)
        ny = _normalize(float(py), y0, y1)

        descr = _describe_position(nx, ny)
        # build chessboard_id string exactly like your example
        chessboard_id = f"[{lx},{rx}],[{uy}-{ly}]"

        new_obj = {**obj}
        new_obj["grid_cols"] = [lx, rx]
        new_obj["grid_rows"] = [uy, ly]
        new_obj["chessboard_id"] = chessboard_id
        new_obj["position_description"] = descr
        items[key] = new_obj

    return items
# ---------------------
import re

def clean_txt(txt):
    txt = txt.replace("{", "").replace("}", "")
    txt = re.sub(r"\\[A-Za-z][^;]*;", "", txt)
    txt = txt.replace(",", ".")
    return txt

# ------------- transforms -------------

def parse_calib(s):
    pairs=[]
    for seg in s.split(";"):
        seg=seg.strip()
        if not seg: continue
        L,R=seg.split(":")
        x,y=map(float,L.split(",")); X,Y=map(float,R.split(","))
        pairs.append(((x,y),(X,Y)))
    return pairs

def fit_similarity_from_two(p1,p2,q1,q2):
    v1=np.array([p2[0]-p1[0],p2[1]-p1[1]],float)
    v2=np.array([q2[0]-q1[0],q2[1]-q1[1]],float)
    n1,n2=np.linalg.norm(v1),np.linalg.norm(v2)
    if n1==0 or n2==0: raise ValueError("Degenerate calibration points")
    s=n2/n1
    v1n,v2n=v1/n1,v2/n2
    cos=float(np.clip(np.dot(v1n,v2n),-1,1))
    sin=float(v1n[0]*v2n[1]-v1n[1]*v2n[0])
    R=np.array([[cos,-sin],[sin,cos]],float)
    t=np.array(q1,float)-s*(R@np.array(p1,float))
    return np.array([[s*R[0,0],s*R[0,1],t[0]],[s*R[1,0],s*R[1,1],t[1]]],float)

def fit_affine(pairs):
    A=[]; B=[]
    for (x,y),(X,Y) in pairs:
        A+=([x,y,0,0,1,0],[0,0,x,y,0,1]); B+=[X,Y]
    A=np.asarray(A,float); B=np.asarray(B,float)
    a,b,c,d,tx,ty=np.linalg.lstsq(A,B,rcond=None)[0]
    return np.array([[a,b,tx],[c,d,ty]],float)

def fit_transform(pairs):
    if len(pairs)>=3: return fit_affine(pairs)
    if len(pairs)==2: return fit_similarity_from_two(pairs[0][0],pairs[1][0],pairs[0][1],pairs[1][1])
    raise ValueError("Provide at least 2 calibration pairs.")

def apply_M(M,x,y):
    v=M@np.array([x,y,1.0],float)
    return float(v[0]),float(v[1])

# ------------- color / category -------------

def load_layer_colors(doc):
    table={}
    for layer in doc.layers:
        aci = layer.color
        try: rgb = aci2rgb(aci if aci!=0 else 7)
        except Exception: rgb=(200,200,200)
        table[layer.dxf.name] = rgb
    return table

def get_entity_rgb(e,layer_table):
    aci=getattr(e.dxf,"color",256)
    tc=getattr(e.dxf,"true_color",None)
    if tc:
        return ((tc>>16)&0xFF,(tc>>8)&0xFF,tc&0xFF)
    if aci in (0,256):
        return layer_table.get(e.dxf.layer,(200,200,200))
    try: return aci2rgb(aci if aci!=0 else 7)
    except Exception: return (200,200,200)

# ------------- text cleaning -------------

def clean_text_basic(t):
    if not t: return ""
    # replace AutoCAD paragraph markers with space
    t=t.replace(r"\P"," ").replace("\\\\P"," ")
    # keep payload in {...} by taking last ';' segment
    def repl(m):
        parts=[p.strip() for p in m.group(1).split(";") if p.strip()]
        return parts[-1] if parts else ""
    t=re.sub(r"{([^}]*)}",repl,t)
    t=re.sub(r"\\[A-Za-z]+","",t)
    t=re.sub(r"\s+"," ",t).strip()
    return t

def mtext_to_plain(e):
    if hasattr(e,"plain_text"):
        try:
            s=e.plain_text()
            if s and s.strip(): return clean_text_basic(s)
        except Exception: pass
    try:
        from ezdxf.tools.text import plain_mtext
        raw=getattr(e,"text",getattr(e.dxf,"text","")) or ""
        return clean_text_basic(plain_mtext(raw))
    except Exception:
        raw=getattr(e,"text",getattr(e.dxf,"text","")) or ""
        return clean_text_basic(raw)

# ------------- collectors -------------

def collect_texts(msp,layer_table,M):
    out=[]; tid=0
    for e in msp.query("TEXT"):
        s=clean_text_basic(e.dxf.text)
        if not s: continue
        x,y = float(e.dxf.insert[0]),float(e.dxf.insert[1])
        #change pos to img pos
        X,Y = apply_M(M,x,y)
        rgb = get_entity_rgb(e,layer_table)
        out.append({"id":f"T{tid}","source":"base_text","kind":"TEXT","content":s,
                    "layer":e.dxf.layer,"rgb":rgb,
                    "pos_dxf":[x,y],"pos_img":[X,Y]}); tid+=1
    for e in msp.query("MTEXT"):
        s=mtext_to_plain(e)
        if not s: continue
        x,y = float(e.dxf.insert[0]),float(e.dxf.insert[1])
        X,Y = apply_M(M,x,y)
        rgb = get_entity_rgb(e,layer_table)
        out.append({"id":f"T{tid}","source":"base_mtext","kind":"MTEXT","content":s,
                    "layer":e.dxf.layer,"rgb":rgb,
                    "pos_dxf":[x,y],"pos_img":[X,Y]}); tid+=1
    return out


def collect_items(msp, layer_table, M):
    out=[]
    prev_id = None
    prev_layer = None
    prev_name = None
    prev_pos = None
    prev_color = None
    elements = {}
    
    for e in msp.query("INSERT"):
        txt = ''
        layer = (e.dxf.layer or "").strip()
        name = (e.dxf.name or "").strip()
        iid = (e.dxf.handle or "").strip() 
        x,y = float(e.dxf.insert[0]),float(e.dxf.insert[1])
        X,Y = apply_M(M,x,y)
        rgb = get_entity_rgb(e, layer_table)

        #print(f"ekav: name={name} layer={layer} ins={tuple(e.dxf.insert)}")
#TODO ete inqe ekel mtel a uje txt poxvel a heto vor sxal el lini meje pahum a txt infon
        vents = list(e.virtual_entities())
        for v in vents:
            h = getattr(v.dxf, "handle", None)
            lay = getattr(v.dxf, "layer", None)
            if v.dxftype() == "TEXT":
                x,y = float(v.dxf.insert[0]),float(v.dxf.insert[1])
                X,Y = apply_M(M,x,y)
                txt += clean_txt((v.dxf.text + " "))
                #TODO-fixed bug repetition in txt when the same layer has two virtual layers during printing
                #txt = (v.dxf.text + " ")
                #print(f"  * TEXT  layer={lay} text={v.dxf.text!r} ins={tuple(v.dxf.insert)} img_pos={(X,Y)}")

            elif v.dxftype() == "MTEXT":
                text = mtext_to_plain(v) if 'mtext_to_plain' in globals() else v.dxf.text
                #TODO chishtna txt += (text + " ")
                txt += clean_txt((v.dxf.text + " "))
                x,y = float(v.dxf.insert[0]),float(v.dxf.insert[1])
                X,Y = apply_M(M,x,y)
                #print(f"  * MTEXT layer={lay} text={txt!r} ins={tuple(v.dxf.insert)} img_pos={(X,Y)}")
            #else:
            #    print(f"  * {v.dxftype()} {h} layer={lay}")
        
        #print("prev_layer: ", prev_layer)
        #print("layer: ", layer)
        #print("prev_name: ", prev_name)
        
        #if "Schaltkreis_" in name and prev_layer + "-TXT" == layer:
        if prev_layer and prev_layer + "-TXT" == layer:
            elements[prev_id]['txt'] += txt 
            #print("poxvec: ", elements[prev_id])
        elif "Schaltkreis_" in name and math.dist(prev_pos, [x,y]) < 20: 
            elements[prev_id]['txt'] += txt
        elif prev_layer  == layer and "Schaltkreis_" in name and not "Schaltkreis_" in prev_name:
            elements[prev_id]['txt'] += txt
            #print("poxvec: ", elements[prev_id])
        #elif "-TXT" in layer and math.dist(prev_pos, [x,y]) < 12 :#and prev_rgb == rgb:
        #    elements[prev_id]['txt'] += txt
        #    #print("poxvec: ", elements[prev_id])
        else:
            elements[iid] = {'name': name, 'layer': layer, 'rgb':rgb, 'pos_dxf': [x,y], 'pos_img': [X,Y], 'txt': txt}
            #print("element: ", elements[iid])
            prev_layer = layer
            prev_name = name
            prev_pos = [x,y]
            prev_rgb = rgb
            prev_id = iid
        
        out = elements
    return out

def extract_prefix(input_string):
    # Step 1: take the last segment after '$'
    last_part = input_string.split('$')[-1]

    # Step 2: split by '_' → ["Kabelkanal", "A01KSXVQXE"]
    prefix = last_part.split('_')[0]

    # Step 3: return with trailing underscore
    return prefix 

def extract_layer_suffix(layer_string):
    # Split by '$' and return the last segment
    return layer_string.split('$')[-1]

def remove_last_dash_part(text):
    if '-' not in text:
        return text
    return '-'.join(text.split('-')[:-1])

def clean_data(elements):
    clean_elements = {}
    # Calculate layout boundaries
    min_x = min(LAYOUTS_X.values())
    max_x = max(LAYOUTS_X.values())
    min_y = min(LAYOUTS_Y.values())
    max_y = max(LAYOUTS_Y.values())
    
    for k, element in elements.items():
        if "Polygonsäule" in element["name"] or "XREF" == element["name"][:4] or "*" == element["name"][0] or "_Oblique" in element["name"]:
            continue
        #if "$" in element["name"] or "Legende" in element["name"] or "Text" in element["layer"]:
        if "$" in element["name"] or"Legende" in element["name"] or "text" in element["layer"].lower():# or "TEXT" in element["layer"].lower():
            continue
            #or element["layer"] == "ADE_ET_BEL_Lichtschiene" or element["layer"] == "E-Stromschiene Variante 2":
            #continue
        # Filter out elements outside layout boundaries
        pos_img = element.get("pos_img", [None, None])
        if pos_img[0] is not None and pos_img[1] is not None:
            if pos_img[0] < min_x or pos_img[0] > max_x or pos_img[1] < min_y or pos_img[1] > max_y:
                continue
        
        # Process and add element if it passed all filters
        if "Vorplanung" in element["layer"] or "Vorplanung" in element["name"]:
            element["name"] = extract_prefix(element["name"])
            element["layer"] = remove_last_dash_part(extract_layer_suffix(element["layer"]))
            clean_elements[k] = element
        #elif "-" in element["layer"] and element["layer"] != "E-Stromschiene Variante 2":
        elif element["layer"] != "E-Stromschiene Variante 2":
            #element["layer"] = remove_last_dash_part(element["layer"])
            #element["layer"] = element["layer"]
            clean_elements[k] = element
        clean_elements[k] = element
    return clean_elements


def load_legend_mapping(legend_path: Path) -> List[Tuple[str, str, str]]:
    """
    Parses legend mapping file into ordered list of tuples
    preserving the file order to respect first-match priority.
    """
    entries = []
    if not legend_path.exists():
        return entries

    with legend_path.open(encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if idx == 0 and [p.lower() for p in parts[:3]] == ["layer", "name", "legend_info"]:
                continue  # skip header
            if len(parts) < 3:
                continue
            #layer, name, legend_info = remove_last_dash_part(parts[0]), parts[1], ",".join(parts[2:]).strip()
            layer, name, legend_info = parts[0], parts[1], ",".join(parts[2:]).strip()
            if name[-1] == "_":
                name = name[:-1]
            entries.append((layer, name, legend_info))
    return entries

def assign_group_ids(elements: Dict[str, dict], legend_entries: List[Tuple[str, str, str]]) -> Dict[str, dict]:
    """
    Adds 'group_id' to each element based on legend mapping.
    - Match requires exact layer equality and legend name contained in element name (case-insensitive).
    - When multiple legend rows satisfy this, the first occurrence is used.
    - If nothing matches, defaults to the element's name.
    """
    fields = ["16A", "32A", "63A", "Typ 1", "Typ 2", "Typ 3", "Typ 4"]
    for key, element in elements.items():
        interesting_field = None
        down = None
        ka = False
        candidate = None

        elem_layer = (element.get("layer") or "").strip()
        elem_name = (element.get("name") or "").strip()
        elem_txt = (element.get("txt") or "").strip()
        elem_name_lower = elem_name.lower()
        
        if elem_layer == "E-Stromschiene Variante 2":
            group_id = elem_name
        else:
            #FOR SAMSON
            group_id = extract_prefix(elem_name)  # fallback
            #group_id = elem_name  # fallback

        if elem_layer in ["ADE_ET_NSHV_Verteiler", "ADE_ET_NSV_Anschluss", "ADE_ET_NSV_Steckdose"]:
            for f in fields:
                if f in elem_txt:
                    if "1xAP-SD_ SchuKo" in elem_name:
                        elem_name = "1xAP-SD_ SchuKo_"+f
                        elem_name_lower = elem_name.lower()
                        down = True 
                    group_id = group_id + " " + f
                    interesting_field = f
                    break
                    
        # Check if legend name matches as prefix of element name with word boundary
        # This prevents "b3" from matching "b30" but allows "1xap-sd_ schuko" to match "1xap-sd_ schuko_a01u1f8ykh"
        def matches_legend_name(elem_name_lower, legend_name_clean):
            """Check if legend name matches element name with proper word boundary.
            Legend name must be followed by underscore, end of string, or non-alphanumeric char."""
            if not elem_name_lower.startswith(legend_name_clean):
                return False
            # Check what comes after the legend name
            remaining = elem_name_lower[len(legend_name_clean):]
            if not remaining:  # End of string - perfect match
                return True
            # Must be followed by underscore or non-alphanumeric character
            return remaining[0] == '_' or not remaining[0].isalnum()
        
        for layer, legend_name, legend_info in legend_entries:
            legend_name_clean = legend_name.strip().lower()
            if not legend_name_clean:
                continue
                
            if elem_layer == layer.strip():
                if matches_legend_name(elem_name_lower, legend_name_clean):
                    #FOR SAMSON
                    group_id = legend_info.strip() or extract_prefix(elem_name)
                    #group_id = legend_info.strip() or elem_name
                    if down:
                        group_id = "CEE-Steckdose 230V AP"
                    if interesting_field:
                        group_id = group_id + " " + f
                    ka = True
                    break
            elif matches_legend_name(elem_name_lower, legend_name_clean):
                    #FOR SAMSON
                    #group_id = legend_info.strip() or extract_prefix(elem_name)
                    candidate = legend_info.strip() or elem_name
                    if down:
                        candidate = "CEE-Steckdose 230V AP"
                    if interesting_field:
                        candidate = group_id + " " + f
        if not ka and not candidate:
            #print("group_id: ", group_id, "element: ", element)
            pass
        if not ka and candidate:
            group_id = candidate
        
        element["group_id"] = group_id
        elements[key] = element
    return elements

def merge_data(elements):
    items = []
    new_elements = {} 
    for iid, element in elements.items():
        if "Schaltkreis" in element["name"]:
            items.append(iid)
        else:
            new_elements[iid] = elements[iid]
    print("len: ", len(items))

    potential_candidate = {}
    for iid, element in elements.items():
        if "Schaltkreis" in element["name"]:
            continue
        for i in items:
            candidate = elements[i]
            if element["layer"] in candidate["layer"] and math.dist(element["pos_dxf"], candidate["pos_dxf"]) < 20:
                if i in potential_candidate:
                    if math.dist(element["pos_dxf"], candidate["pos_dxf"]) < math.dist(candidate["pos_dxf"], elements[potential_candidate[i]]["pos_dxf"]):
                        potential_candidate[i] = iid
                else:
                    potential_candidate[i] = iid
    for i in items:
        if i not in potential_candidate:
            print("CHKA: ", elements[i])
        else:
            new_elements[potential_candidate[i]]["txt"] += elements[i]["txt"]
    return new_elements

# ------------- main -------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dxf",required=True)
    ap.add_argument("--calib",required=True)
    args = ap.parse_args()

    # DXF
    tk = time.time()
    try:
        doc = ezdxf.readfile(args.dxf)
    except (IOError,DXFStructureError) as e:
        print(f"Failed to read DXF: {e}", file=sys.stderr); sys.exit(1)
    
    proned_txt = []
    #legend_file = Path(__file__).resolve().with_name("berlin_legend_element_match.txt")
    legend_file = Path(__file__).resolve().with_name("legend_element_match.txt")
    legend_entries = load_legend_mapping(legend_file)
    #print(legend_entries)
    #exit(0)
    
    print("Loaded: ", time.time() - tk)
    msp = doc.modelspace()

    # Transform depends on values map the values
    M = fit_transform(parse_calib(args.calib))

    # Layers/colors extract layers info from doc
    layer_table = load_layer_colors(doc)
    #print("layer_table: ", layer_table)

    # Collect base
    base_texts = collect_texts(msp, layer_table, M)
    items      = collect_items(msp, layer_table, M)
    #for i, v in items.items():
    #    print('item:', i, v)
    #exit(0)
    clean_items = clean_data(items)
    merged_items = merge_data(clean_items)
    #print("legened_entires: ", legend_entries)
    #exit(0)
    items_with_groups = assign_group_ids(merged_items, legend_entries)
    #exit(0)
    #print('elements do:', elements)
    elements = assign_chessboard_and_position(items_with_groups, LAYOUTS_X,  LAYOUTS_Y)
    #print('elements posle:', elements)
    #print('proned_txt: ', proned_txt)
    with open("extracted_elements_samson.json", "w", encoding="utf-8") as f:
        json.dump(elements, f, ensure_ascii=False, indent=2)
    with open("extracted_txt_samson.json", "w", encoding="utf-8") as f:
        json.dump(base_texts, f, ensure_ascii=False, indent=2)


if __name__=="__main__":
    from PIL import Image  # ensure Pillow is importable
    main()
