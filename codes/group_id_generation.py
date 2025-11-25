#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reads a JSON file of elements and adds an empty 'group_id' field to each element
if it doesn't already exist. Useful for manual grouping later.

✅ Example input:
{
  "180B1": {"name": "RJ-45-Datendose 1-fach_ AP_A01U1HGKKH", "layer": "..."},
  "162E5": {"name": "RJ45-Steckdose_ AP_A01U1GO5KH", "layer": "..."}
}

✅ Example output:
{
  "180B1": {"name": "...", "layer": "...", "group_id": ""},
  "162E5": {"name": "...", "layer": "...", "group_id": ""}
}

Usage:
  python3 add_group_field.py --json input.json --out grouped.json
"""

import argparse
import json
import re


def clean_txt(text: str) -> str:
    if not isinstance(text, str):
        return text
    # 1. Remove patterns like 12F04
    cleaned = re.sub(r"\b\d{2}F\d{2}\b", "", text)
    # 2. Normalize spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    # 3. Sort words alphabetically
    parts = cleaned.split(" ")
    parts = sorted(p for p in parts if p)  # filter empty
    return " ".join(parts)

def clean_type(text: str) -> str:
    if not isinstance(text, str):
        return text
    # 1. Remove patterns like 12F04
    cleaned = re.sub(r"\b\d{1}F\d{1}\b", "", text)
    # 2. Normalize spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    # 3. Sort words alphabetically
    parts = cleaned.split(" ")
    parts = sorted(p for p in parts if p)  # filter empty
    return " ".join(parts)

def clean_slash(text: str) -> str:
    if not isinstance(text, str):
        return text
    cleaned = re.sub(r"\b\d{2}/\d{3}\b", "", text).strip()
    # 2. Normalize spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    # 3. Sort words alphabetically
    parts = cleaned.split(" ")
    parts = sorted(p for p in parts if p)  # filter empty
    return " ".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="Path to input JSON")
    parser.add_argument("--out", required=True, help="Path to output JSON")
    args = parser.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Input JSON must be a dictionary mapping IDs to element objects")

    for key, value in data.items():
        if isinstance(value, dict):
            # add empty group_id if not already there
            if "Staplerladestation" in value["txt"]:
                txt_id = clean_txt(value["txt"]) 
                if "16A" in txt_id:
                    group_id = "Steckdose_CEE_230V_AP"
                else:
                    group_id = "Steckdose_1_fach_AP"
                value.setdefault("group_id", group_id)
                continue

            if value["name"] == "_Oblique":
                value.setdefault("group_id", "")
            elif value["name"][0] == "*" or value["name"][:4] == "XREF":
                value.setdefault("group_id", "")
            elif "002 Sirene" in value["name"]:
                group_id = value["name"].rsplit("_", 1)[0]
                value.setdefault("group_id", group_id)
            elif "069 Multisensormelder (Kombination" in value["name"]:
                group_id = value["name"].rsplit("_", 1)[0]
                txt_id = value["txt"].rsplit(" ")[0]
                if txt_id:
                    value.setdefault("group_id", group_id+ "-" +txt_id)
                else:
                    value.setdefault("group_id", group_id)

            elif "1xAP-SD_ SchuKo" in value["name"]:
                txt_id = clean_txt(value["txt"]) 
                if "16A" in txt_id:
                    group_id = "Steckdose_CEE_230V_AP"
                else:
                    group_id = "Steckdose_1_fach_AP"
                value.setdefault("group_id", group_id)
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "1xUP-SD_ SchuKo" in value["name"]:
                group_id = "Steckdose_1_fach_UP"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            elif "2xAP-SD_ SchuKo" in value["name"]:
                group_id = "Steckdose_2_fach_AP"
                value.setdefault("group_id", group_id)
                #group_id = "Steckdose_NSV_2_fach_AP_SchuKo"
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "2xRJ45-Steckdose_ AP_" in value["name"] or "RJ-45-Datendose 2-fach_ AP_" in value["name"]:
                group_id = "RJ_45_Datendose_2_fach_AP"
                value.setdefault("group_id", group_id)

            elif "3xUP-SD_ SchuKo" in value["name"]:
                group_id = "Steckdose_3_fach_UP_Schuko"
                value.setdefault("group_id", group_id)
            
            elif "A1_" in value["name"]:
                group_id = "A1_LED_38_W"
                value.setdefault("group_id", group_id)

            elif "Ableitung_" in value["name"]:
                group_id = "Ableitung_RAS"
                value.setdefault("group_id", group_id)

            elif "Ansaugstutzen RAS_" in value["name"]:
                group_id = "RAS_Ansaugstutzen"
                value.setdefault("group_id", group_id)
                
            elif "AP-SD_ Drehstrom_" in value["name"]:
                group_id = "Anschluss_400V_3_polig"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            elif "Auslass 230 V_" in value["name"]:
                group_id = "Anschluss_230V_1_polig"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Auslass 400 V" in value["name"]:
                group_id = "Anschluss_400V_1_polig"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Auslass RWA-Motor_" in value["name"]:
                group_id = "RWA_Motor_Auslass"
                #value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
                    
            elif "B11_" in value["name"]:
                group_id = "B11-BEL_Decke"
                value.setdefault("group_id", group_id)
            
            elif "B12_" in value["name"]:
                group_id = "B12-BEL_Decke"
                value.setdefault("group_id", group_id)
            
            elif "B13_" in value["name"]:
                group_id = "B13-BEL_Decke"
                value.setdefault("group_id", group_id)
            
            elif "B14_" in value["name"]:
                group_id = "B14-BEL_Decke"
                value.setdefault("group_id", group_id)
            
            elif "B14_" in value["name"]:
                group_id = "B14-BEL_Decke"
                value.setdefault("group_id", group_id)
            
            elif "B16_" in value["name"]:
                group_id = "B16-BEL_Decke"
                value.setdefault("group_id", group_id)
            
            elif "B17_" in value["name"]:
                group_id = "B17-BEL_Decke"
                value.setdefault("group_id", group_id)

            elif "B2_" in value["name"]:
                group_id = "B2-BEL_Decke"
                value.setdefault("group_id", group_id)
            
            elif "B30_" in value["name"]:
                group_id = "B30-BEL_Decke"
                value.setdefault("group_id", group_id)

            elif "Beleuchtungstableau_" in value["name"]:
                group_id = "Lichtbedientableau-NSV_Tableau"
                value.setdefault("group_id", group_id)

            elif "Bus-Steuerkoppler BMA (I_O)" in value["name"]:
                group_id = "Bus_Steuerkoppler_BMA_(I_O)"
                value.setdefault("group_id", group_id)
                #txt_id = clean_slash(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Druckknopfmelder_" in value["name"]:
                group_id = "Druckknopfmelder"
                value.setdefault("group_id", group_id)
                #txt_id = clean_slash(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "E-Verteiler_" in value["name"] and value["layer"] == "ADE_ET_SIBE_Zentrale":
                group_id = "Sicherheitsbeleuchtungszentrale"
                value.setdefault("group_id", group_id)
            
            elif "E-Verteiler_" in value["name"] and value["layer"] == "ADE_ET_NSV_Verteiler":
                group_id = "Elektro_Verteiler_AV"
                value.setdefault("group_id", group_id)
            
            elif "Einspeisestück_" in value["name"]:
                group_id = "Einspeisestück"
                value.setdefault("group_id", group_id)

            elif "Elektromagnetischer Türöffner_" in value["name"]:
                group_id = "Elektromagnetischer_Türöffner"
                value.setdefault("group_id", group_id)
            
            elif "Elektroschloss_" in value["name"]:
                group_id = "Elektroschloss-ZKS_Offline"
                value.setdefault("group_id", group_id)
            
            elif "FIZ" in value["name"]:
                group_id = "Feuerwehr_Informations_Zentrale"
                value.setdefault("group_id", group_id)
            
            elif "Geräteanschluß 230 V_" in value["name"]:
                group_id = "Anschluss_230V_1_polig"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Geräteanschluß 400 V_" in value["name"]:
                group_id = "Anschluss_400V_1_polig"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Kartenleser Zutritt Anlage_" in value["name"]:
                group_id = "ZKS_Kartenleser_Online"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)

            elif "Leitung_" in value["name"]:
                group_id = "Leitung_RAS"
                value.setdefault("group_id", group_id)
            
            elif "Mulitnsensormelder mit integr. Sirene_" in value["name"]:
                group_id = "Mulitnsensormelder_mit_integr_Sirene"
                value.setdefault("group_id", group_id)

            elif "Magnetkontakt_" in value["name"]:
                group_id = "ZKS-Magnetkontakt"
                value.setdefault("group_id", group_id)
                #txt_id = clean_txt(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Netzteil inkl. Akku_" in value["name"]:
                group_id = "Netzteil_inkl_Akku"
                value.setdefault("group_id", group_id)
                #txt_id = clean_slash(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "optisch akustischer Signalgeber_" in value["name"]:
                group_id = "Optisch_akustischer_Signalgeber"
                value.setdefault("group_id", group_id)
                #txt_id = clean_slash(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Steckdosenverteiler_" in value["name"]:
                group_id = "Steckdosenverteiler"
                txt_id = clean_type(value["txt"]) 
                if txt_id:
                    value.setdefault("group_id", group_id + "-" + txt_id)
                else:
                    value.setdefault("group_id", group_id)
            
            elif value["name"].startswith("Polygon") or value["name"].startswith("Polygonsäule"):
                value.setdefault("group_id", "")
            
            elif "Präsenzmelder AP 360" in value["name"]:
                group_id = "Präsenzmelder_Decke_AP_360-DALI"
                value.setdefault("group_id", group_id)
            
            elif "Präsenzmelder UP 360" in value["name"]:
                group_id = "Präsenzmelder_Decke_UP_360"
                value.setdefault("group_id", group_id)
            
            elif "Revisionswolke_" in value["name"]:
                value.setdefault("group_id", "")
            
            elif "Schaltkreis_" in value["name"]:
                value.setdefault("group_id", "")
            
            elif "RJ-45-Datendose 1-fach_ AP_" in value["name"]:
                #TODO DO WE NEED TO HAVE WLAN here or no?
                value.setdefault("group_id", "RJ_45_Datendose_1_fach_AP")
            
            elif "RJ-45-Datendose 2-fach_ UP_" in value["name"]:
                value.setdefault("group_id", "RJ_45_Datendose_2_fach_UP")

            elif "RJ45-Steckdose_ AP_" in value["name"]:
                value.setdefault("group_id", "RJ_45_Datendose_1_fach_AP")
            
            elif "RWA-Taster_" in value["name"]:
                value.setdefault("group_id", "RWA_Taster")
            
            elif "RWA-Zentrale_" in value["name"]:
                value.setdefault("group_id", "RWA_Zentrale")

            elif "S02_" in value["name"]:
                value.setdefault("group_id", "S02")
            
            elif "S04_" in value["name"]:
                value.setdefault("group_id", "S04")
                
            elif "S07_" in value["name"]:
                value.setdefault("group_id", "S07")
            
            elif "S10_" in value["name"]:
                value.setdefault("group_id", "S10")

            elif "S11_" in value["name"]:
                value.setdefault("group_id", "S11")
            
            elif "S12_" in value["name"]:
                value.setdefault("group_id", "S12")
            
            elif "Taster_ AP_ 1S_" in value["name"]:
                value.setdefault("group_id", "Taster_AP_1S")
            
            elif "Taster_ UP_ 1S_" in value["name"]:
                value.setdefault("group_id", "Taster_UP_1S")
            
            elif "Taster_ Zugangskontrolle_" in value["name"]:
                value.setdefault("group_id", "Hauptschalter_AP")
                #txt_id = clean_slash(value["txt"]) 
                #if txt_id:
                #    value.setdefault("group_id", group_id + "-" + txt_id)
                #else:
                #    value.setdefault("group_id", group_id)
            
            elif "Türcontroller_" in value["name"]:
                value.setdefault("group_id", "ZKS_Türsteuereinheit_GAM")
            
            elif "Verteiler AV-SV_" in value["name"]:
                value.setdefault("group_id", "Elektro_Verteiler_SV")
            
            elif "Warnschild_" in value["name"]:
                value.setdefault("group_id", "Warnschild_Brandalarm")
            
            elif "Blitzleuchte_" in value["name"]:
                value.setdefault("group_id", "Feuerwehr_Blitzleuchte")
            
            elif "Zentralbedientableau RWA" in value["name"]:
                value.setdefault("group_id", "Zentralbedientableau_RWA")


    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Added group_id to {len(data)} elements")
    print(f"💾 Saved to: {args.out}")

if __name__ == "__main__":
    main()
