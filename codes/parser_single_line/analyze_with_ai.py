#!/usr/bin/env python3
"""
Analyze Single Line Diagram images using AI Vision API.
This is Step 2 of the OCR pipeline for electrical schematics.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: google-genai library is not installed.")
    print("Please install it using: pip install google-genai")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


# The analysis prompt for the AI
#ANALYSIS_PROMPT = """You are an expert Electrical Engineer analyzing a Single Line Diagram (SLD).
#
#Your Goal:
#
#Extract accurate cable specifications for every circuit column AND classify the direction of electricity flow.
#
#Visual Guide:
#
#Locate the Circuit Column: Identified by the number at the bottom (e.g., 1, 2, 3).
#
#Locate the Terminal Block: This is the horizontal row labeled "X..." (e.g., X03, X101) located just above the bottom text descriptions.
#
#Locate the Cable Size: A number like "1,5" or "2,5" usually found below the terminals.
#
#Locate the Description: Read the text at the very bottom of the column to understand the circuit's function.
#
#Classification Rules for "connection_type":
#
#Analyze the text description to determine the direction of power:
#
#SUPPLY: Text contains "Zuleitung", "Einspeisung", "Supply", "Incoming" (Power entering the panel).
#
#INTERNAL: Text contains "Überspannungsschutz", "SPD", "Potentialausgleich", "Surge" (Wiring that stays inside the panel/room).
#
#LOAD: Text contains "Steckdosen", "Beleuchtung", "Licht", "Motor", "Reserve", "Trafo", "Heizung", or specific device names.
#
#Note: If a circuit leaves the panel to connect to an external control/monitoring device (e.g., "Phasenausfallrelais", "Remote Control", "BMS"), classify it as LOAD because the wiring leaves the enclosure.
#
#Extraction Rules for "cable_spec":
#
#To determine the full cable string, analyze the terminals and text.
#
#Step A (Find Cross-Section): Extract the number (e.g., "1,5" = 1.5mm²).
#
#Step B (Count Cores): Count the terminals in the block for that specific circuit.
#
#3x: (L, N, PE) or (1, N, PE).
#
#5x: (L1, L2, L3, N, PE) or (1, 2, 3, N, PE).
#
#Other: Exact count of terminals (e.g., 4 slots = "4x").
#
#Step C (Check for Multiple Cables):
#
#Split Cables: If a single circuit (column) has multiple separate terminal blocks (e.g., one block labeled X101 with 5 pins and another adjacent block labeled X1 with 5 pins), verify if they represent separate cables. If yes, sum them (e.g., "2x(5x1.5mm²)").
#
#Complex Control: If a device (like a relay or monitor) has wires going to terminals X... and separate wires going to a different external destination, account for all outgoing cables.
#
#Step D (Exceptions):
#
#Text Override: If the text explicitly states a cable type (e.g., "NAYCWY 4x240"), use the text description instead of counting terminals.
#
#Output Format:
#
#Return ONLY a valid JSON array. Do not include any markdown formatting, code blocks, or explanatory text. Just the raw JSON array.
#
#Example format:
#
#[
#  {
#    "circuit": "1",
#    "connection_type": "SUPPLY",
#    "breaker": "1S1",
#    "cable_spec": "4x240/120mm²",
#    "destination": "Zuleitung NAYCWY..."
#  },
#  {
#    "circuit": "3",
#    "connection_type": "LOAD",
#    "breaker": "1F3",
#    "cable_spec": "2x(5x1.5mm²)",
#    "destination": "Phasenausfallrelais (Control & Sense)"
#  },
#  {
#    "circuit": "18",
#    "connection_type": "LOAD",
#    "breaker": "03F01",
#    "cable_spec": "7x2.5",
#    "destination": "Lichtschiene..."
#  }
#]"""


##version 2
#ANALYSIS_PROMPT = """You are an expert Electrical Engineer and Quantity Surveyor analyzing a Single Line Diagram (SLD).
#
#Your Goal:
#Extract detailed circuit specifications for a Bill of Quantities (BoQ). You must preserve the existing JSON structure but enrich it with precise component data (Fuses, RCDs, Control Modules).
#
#Visual Scanning Strategy (Top-Down Method):
#For every circuit column (identified by the number at the bottom):
#1.  **Scan the Top (Protection):** Identify the breaker ID (e.g., 1F3), the Fuse/MCB Type (e.g., D02, B10), and the Rating (e.g., 35A, 6A, 40A/0,03A).
#2.  **Scan the Middle (Control):** Look for boxes or relays (e.g., "Gessler", "Zumtobel", "Phasenausfallrelais").
#3.  **Scan the Bottom (Terminals/Cable):** Identify terminal blocks (X...) and cable cross-sections.
#4.  **Scan the Description:** Read the text at the very bottom.
#
#Extraction Rules by Field:
#
#1.  "circuit":
#    * Extract the circuit number from the bottom row.
#
#2.  "connection_type":
#    * **SUPPLY:** Text has "Zuleitung", "Einspeisung".
#    * **INTERNAL:** Text has "Überspannungsschutz", "SPD".
#    * **LOAD:** Text has "Steckdosen", "Licht", "Motor", "Reserve", "Trafo".
#    * **DISTRIBUTION:** Feeder circuits (e.g., "FI Schalter Gruppe 02").
#
#3.  "breaker":
#    * Extract the component ID Tag ONLY (e.g., "1S1", "02F0", "1F3").
#
#4.  "protection_detail" (NEW - CRITICAL FOR QS):
#    * Extract the technical specs usually found near the breaker symbol.
#    * **Fuses:** Look for "D02", "D01", "Feins" combined with Amps (e.g., "D02 35A", "Feins 6A").
#    * **MCBs:** Look for curve and rating (e.g., "B10", "C16", "B16").
#    * **RCDs:** Look for sensitivity ratings (e.g., "40A/0,03A").
#    * *Example:* If a circuit has a Fuse and an RCD, combine them: "D02 35A + RCD 40A/0,03A".
#
#5.  "control_device" (NEW - CRITICAL FOR QS):
#    * Identify manufacturers or device types inside rectangular boxes in the circuit line.
#    * Look for: "Gessler DNÜ", "ZUMTOBEL", "Phasenausfallrelais".
#    * Include the ID if present (e.g., "02P1 Gessler DNÜ").
#    * If none, return "None".
#
#6.  "cable_spec":
#    * **Count Terminals:** 3 pins = "3x", 5 pins = "5x".
#    * **Find Cross-Section:** Look for numbers like "1,5", "2,5" near the terminals.
#    * **Override:** If text explicitly says "NAYCWY 4x240", use that.
#
#7.  "destination":
#    * The descriptive text at the very bottom of the column.
#
#Output Format:
#Return ONLY a valid JSON array.
#
#Example JSON:
#[
#  {
#    "circuit": "9",
#    "connection_type": "DISTRIBUTION",
#    "breaker": "02F0",
#    "protection_detail": "D02 35A + RCD 40A/0,03A",
#    "control_device": "None",
#    "cable_spec": "Internal Busbar",
#    "destination": "FI Schalter Gruppe 02 Beleuchtung"
#  },
#  {
#    "circuit": "16",
#    "connection_type": "LOAD",
#    "breaker": "02F1",
#    "protection_detail": "Feins 6A",
#    "control_device": "02P1 Gessler DNÜ",
#    "cable_spec": "5x1.5mm²",
#    "destination": "Steckdosenkombi Typ 1 Achse 43-44/G4"
#  },
#  {
#    "circuit": "10",
#    "connection_type": "LOAD",
#    "breaker": "B10",
#    "protection_detail": "MCB B10 1-Pole",
#    "control_device": "02Q01 (DALI Control)",
#    "cable_spec": "3x2.5",
#    "destination": "Beleuchtung BT5.1..."
#  }
#]
#"""

#ANALYSIS_PROMPT = """You are an expert Electrical Engineer and Quantity Surveyor. Analyze the provided Single Line Diagram (SLD) image.
#
#**GOAL:**
#Extract a structured JSON array of EVERY electrical circuit column, including "Feeder/Supply" columns (usually on the left) and "Load" columns.
#
#**STRICT DATA ENTRY RULES:**
#1. **NO TRANSLATION:** Extract text EXACTLY as written in the diagram (German). Do not translate "Reserve" to "Spare" or "Beleuchtung" to "Lighting".
#2. **VISUAL VERIFICATION:** Do not trust text labels alone. verify pole counts visually (1 vertical line = 1P, 3 lines = 3P).
#3. **GROUPING-READY SPECS:** The `specs` field must be a clean identifier for the device model to allow grouping by part type.
#
#**EXTRACTION LOGIC:**
#
#**1. Circuit ID & "Feeder" Columns (Crucial)**
#   - Scan the top and bottom of every vertical grid section.
#   - **Branch Circuits:** Standard loads (e.g., 10, 11, 12). ID is usually at the bottom.
#   - **Feeder Columns:** Look at the LEFTMOST column of a group (e.g., Column 9). This often contains the Main Fuse (D02) and RCD (FI-Schalter).
#     - *Trigger:* If you see a Fuse AND an RCD in the same vertical line, capture this as a distinct circuit.
#     - *ID:* Use the number at the top/bottom of that column (e.g., "9").
#
#**2. Destination / Description**
#   - Extract the German text at the very bottom of the column.
#   - Example: "FI Schalter Gruppe 02 Beleuchtung" or "Reserve".
#
#**3. Components (The Protection Devices)**
#   - **Tag:** Component Label (e.g., 02F0, 02Q01, 02F01).
#   - **Type:** [MCB, RCD, RCBO, FUSE_NEOZED_D02, FUSE_NH, CONTACTOR, TERMINAL_ONLY].
#   - **Poles:** Count vertical lines crossing the device symbol (1, 3, or 4).
#   - **Specs (Model Code):** This is for grouping.
#     - If a model number is visible (e.g., "S201-B10"), use THAT.
#     - If only rating is visible (e.g., "B10"), use "B10".
#     - Do NOT write "10A" here if "10" is already in the Model Code.
#   - **Amps:** Just the number (e.g., "10", "35", "40").
#   - **Sensitivity:** For RCDs, extract "0,03A" or "30mA".
#
#   *Special Rule for Feeders (Multiple Components):*
#   If a column (like 9) has TWO main devices (e.g., Fuse 02F0 + RCD 02Q01), create ONE JSON entry for the column, but use an array for "components" OR pick the primary protection device and note the second in "secondary_component". *Preferred: Use an array of components if multiple exist in series.*
#
#**4. Cable & Terminals**
#   - **Terminal Tag:** Label of the terminal block (e.g., X02).
#   - **Cable String:** Combine core count + cross-section (e.g., "5x2.5mm²").
#
#**OUTPUT FORMAT:**
#Return ONLY a valid JSON array.
#
#Example Output:
#[
#  {
#    "circuit_id": "9",
#    "destination": "FI Schalter Gruppe 02 Beleuchtung",
#    "connection_type": "SUPPLY_FEEDER",
#    "components": [
#      {
#        "tag": "02F0",
#        "type": "FUSE_NEOZED_D02",
#        "poles": 3,
#        "specs": "D02 gG",
#        "amps": "35"
#      },
#      {
#        "tag": "02Q01",
#        "type": "RCD",
#        "poles": 4,
#        "specs": "RCCB 40A",
#        "amps": "40",
#        "sensitivity": "0.03A"
#      }
#    ],
#    "cable": {
#      "terminal_tag": "BUSBAR",
#      "spec_string": "Internal Busbar"
#    }
#  },
#  {
#    "circuit_id": "10",
#    "destination": "Beleuchtung / BT5.1.E0.1090 Trafo 5.2",
#    "connection_type": "LOAD",
#    "components": [
#      {
#        "tag": "02F01",
#        "type": "MCB",
#        "poles": 1,
#        "specs": "S201-B10",
#        "amps": "10"
#      }
#    ],
#    "cable": {
#      "terminal_tag": "X02",
#      "spec_string": "5x2.5mm²"
#    }
#  }
#]"""
#ANALYSIS_PROMPT = """You are an expert Electrical Engineer and Quantity Surveyor. Analyze the provided Single Line Diagram (SLD) image.
#
#**GOAL:**
#Extract a structured JSON array of EVERY electrical circuit column, including "Feeder/Supply" columns (usually on the left) and "Load" columns.
#
#**STRICT DATA ENTRY RULES:**
#1. **NO TRANSLATION:** Extract text EXACTLY as written in the diagram (German). Do not translate "Reserve" to "Spare" or "Beleuchtung" to "Lighting".
#2. **VISUAL VERIFICATION:** Do not trust text labels alone. Verify pole counts visually (1 vertical line = 1P, 3 lines = 3P).
#3. **GROUPING-READY SPECS:** The `specs` field must be a clean identifier for the device model to allow grouping by part type.
#
#**EXTRACTION LOGIC:**
#
#**1. Circuit ID & "Feeder" Columns (Crucial)**
#   - Scan the top and bottom of every vertical grid section.
#   - **Branch Circuits:** Standard loads (e.g., 10, 11, 16). ID is usually at the bottom.
#   - **Feeder Columns:** Look at the LEFTMOST column of a group (e.g., Column 9). This often contains the Main Fuse (D02) and RCD (FI-Schalter).
#     - *Trigger:* If you see a Fuse AND an RCD in the same vertical line, capture this as a distinct circuit.
#     - *ID:* Use the number at the top/bottom of that column (e.g., "9").
#
#**2. Destination / Description (UPDATED LOGIC)**
#   - **Primary Source:** Extract the German text at the very bottom of the column (e.g., "Beleuchtung").
#   - **Fallback Source:** IF the bottom text is empty (common for controls like Circuit 16), look **INSIDE the main component symbol** for a description (e.g., "Gessler DNÜ", "USV", "Steuerung"). Use this text as the destination.
#
#**3. Components (The Protection Devices)**
#   - **Tag:** Component Label (e.g., 02F0, 02Q01, 02P1).
#   - **Type:** Choose from: [MCB, RCD, RCBO, FUSE_NEOZED_D02, FUSE_MINIATURE, RELAY_MONITOR, CONTACTOR, TERMINAL_ONLY].
#   - **Poles:** Count vertical lines crossing the device symbol (1, 3, or 4).
#   - **Specs (Model Code):** This is for grouping.
#     - *Breakers:* If model is visible ("S201-B10"), use it. If only rating ("B10"), use "B10".
#     - *Fuses:* If label says "Feins", use "Feins". If "D02", use "D02 gG".
#     - *Monitors:* If device is a relay/monitor (like Gessler), use the text description as the spec.
#   - **Amps:** Just the number (e.g., "10", "35", "6").
#   - **Sensitivity:** For RCDs, extract "0,03A" or "30mA".
#
#   *Special Rule for Multiple Components:*
#   If a column has multiple devices in series (e.g., Fuse + Relay, or Fuse + RCD), capture ALL of them in the `components` array.
#
#**4. Cable & Terminals**
#   - **Terminal Tag:** Label of the terminal block (e.g., X02, 02P1).
#   - **Cable String:** Combine core count + cross-section (e.g., "5x2.5mm²").
#   - If no external cable exists (internal wiring only), set spec_string to "Internal Wiring".
#
#**OUTPUT FORMAT:**
#Return ONLY a valid JSON array.
#
#Example Output:
#[
#  {
#    "circuit_id": "9",
#    "destination": "FI Schalter Gruppe 02 Beleuchtung",
#    "connection_type": "SUPPLY_FEEDER",
#    "components": [
#      {
#        "tag": "02F0",
#        "type": "FUSE_NEOZED_D02",
#        "poles": 3,
#        "specs": "D02 gG",
#        "amps": "35"
#      },
#      {
#        "tag": "02Q01",
#        "type": "RCD",
#        "poles": 4,
#        "specs": "RCCB 40A",
#        "amps": "40",
#        "sensitivity": "0.03A"
#      }
#    ],
#    "cable": {
#      "terminal_tag": "BUSBAR",
#      "spec_string": "Internal Busbar"
#    }
#  },
#  {
#    "circuit_id": "16",
#    "destination": "Gessler DNÜ",
#    "connection_type": "LOAD",
#    "components": [
#      {
#        "tag": "02F1",
#        "type": "FUSE_MINIATURE",
#        "poles": 3,
#        "specs": "Feins",
#        "amps": "6"
#      },
#      {
#        "tag": "02P1",
#        "type": "RELAY_MONITOR",
#        "poles": 4,
#        "specs": "Gessler DNÜ",
#        "amps": null
#      }
#    ],
#    "cable": {
#      "terminal_tag": "INTERNAL",
#      "spec_string": "Internal Wiring"
#    }
#  }
#]"""

#version 1
#ANALYSIS_PROMPT = """You are an expert Electrical Engineer and Quantity Surveyor. Analyze the provided Multi-Line Electrical Schematic image.
#
#**GOAL:**
#Extract a structured JSON array representing **EVERY VERTICAL GRID COLUMN** in the drawing.
#
#**CORE PRINCIPLE:**
#The drawing is a grid. You must iterate through every vertical strip (Column) that contains electrical symbols.
#- Do NOT group multiple columns into one entry.
#- Do NOT translate German text (extract exact strings).
#- Do NOT hallucinate components (e.g., do not see a breaker where there is only a wire).
#
#**VISUAL DICTIONARY (Strict Symbol Rules):**
#1. **FUSE:** Represented by a **Rectangular Box**.
#   - Large Box = `FUSE_NEOZED_D02` or `FUSE_NH` (Main power).
#   - Small/Thin Box = `FUSE_MINIATURE` (often labeled "Feins").
#2. **BREAKER (MCB/Switch):** Represented by a **Diagonal Lever/Switch Line**.
#   - If it has an "X" or ">" on the lever -> MCB.
#   - If it has a loop/oval next to it -> RCD or RCBO.
#3. **CONTACTOR / RELAY:** Represented by a **Square** containing a Coil symbol (diagonal line) or text.
#4. **TERMINAL / WIRE:** A simple vertical line connecting to a block (e.g., "X...").
#   - **Crucial:** If a line goes straight to a terminal with NO symbol on it, classify type as `TERMINAL_ONLY`.
#
#**EXTRACTION LOGIC (Apply to EACH Column):**
#
#**1. Circuit ID (The Anchor)**
#   - Locate the grid number at the top or bottom of the vertical strip (e.g., "1", "2", "9", "91").
#   - This is your `circuit_id`.
#
#**2. Destination / Description**
#   - **Step A:** Read the vertical text at the very bottom of the column. (e.g., "Steckdosen", "DALI Leitung").
#   - **Step B (Fallback):** If the bottom text is EMPTY (common for controls), read the text **inside the main component box** (e.g., "Gessler DNÜ", "ZUMTOBEL", "Fremdspannung").
#   - **Step C (Feeders):** If it is a Supply column, read the text describing the group (e.g., "FI Schalter Gruppe 02").
#
#**3. Connection Type**
#   - **SUPPLY:** Column contains Main Fuses/Switches protecting a downstream group. Text often contains "Zuleitung".
#   - **LOAD:** Standard outgoing circuits (Lights, Sockets).
#   - **CONTROL:** Internal panel wiring (Relays, Monitors, SPDs).
#   - **TERMINAL:** Direct connections without protection (e.g., DALI).
#
#**4. Components (Array)**
#   - Extract ALL devices in the vertical line (from top to bottom).
#   - **Tag:** Component Label (e.g., 02F0, K1, 1S1).
#   - **Type:** [MCB, RCD, RCBO, FUSE_NEOZED_D02, FUSE_MINIATURE, SWITCH_DISCONNECTOR, CONTACTOR, RELAY_MONITOR, TERMINAL_ONLY].
#   - **Poles:** Visually count the vertical lines crossing the symbol (1, 3, or 4).
#   - **Specs (Model Identifier):**
#     - *Breakers:* Extract "B16", "C16", "B10".
#     - *Fuses:* Extract "D02", "35A", "Feins 6A".
#     - *Relays/Contactors:* Extract model (e.g., "ESB25-40N", "VPU AC II").
#   - **Amps:** Just the numeric rating (e.g., "16", "35", "25").
#   - **Sensitivity:** For RCDs only (e.g., "0.03A").
#   - **Attributes:**
#     - `external_voltage`: true if labeled "Fremdspannung".
#     - `red_marked`: true if boxed in "ROT".
#
#**5. Cable & Terminals**
#   - **Terminal Tag:** Label of the terminal block (e.g., "X02", "XDALI", "X40").
#   - **Cable String:** Combine core count + cross-section found at the bottom (e.g., "5x1,5", "4x240/120mm²").
#   - *If no external cable is shown (internal wiring only), set spec_string to "Internal".*
#
#**OUTPUT FORMAT:**
#Return ONLY a valid JSON array.
#
#Example Output Structure:
#[
#  {
#    "circuit_id": "9",
#    "destination": "FI Schalter Gruppe 02 Beleuchtung",
#    "connection_type": "SUPPLY",
#    "components": [
#      {
#        "tag": "02F0",
#        "type": "FUSE_NEOZED_D02",
#        "poles": 3,
#        "specs": "D02 gG",
#        "amps": "35"
#      },
#      {
#        "tag": "02Q01",
#        "type": "RCD",
#        "poles": 4,
#        "specs": "RCCB 40A",
#        "amps": "40",
#        "sensitivity": "0.03A"
#      }
#    ],
#    "cable": {
#      "terminal_tag": "BUSBAR",
#      "spec_string": "Internal"
#    }
#  },
#  {
#    "circuit_id": "16",
#    "destination": "Gessler DNÜ",
#    "connection_type": "CONTROL",
#    "components": [
#      {
#        "tag": "02F1",
#        "type": "FUSE_MINIATURE",
#        "poles": 3,
#        "specs": "Feins",
#        "amps": "6"
#      },
#      {
#        "tag": "02P1",
#        "type": "RELAY_MONITOR",
#        "poles": 4,
#        "specs": "Gessler DNÜ",
#        "amps": null
#      }
#    ],
#    "cable": {
#      "terminal_tag": "INTERNAL",
#      "spec_string": "Internal"
#    }
#  },
#  {
#    "circuit_id": "91",
#    "destination": "DALI Leitung",
#    "connection_type": "TERMINAL",
#    "components": [
#      {
#        "tag": "XDALI",
#        "type": "TERMINAL_ONLY",
#        "poles": 0,
#        "specs": "Terminal Block",
#        "amps": null
#      }
#    ],
#    "cable": {
#      "terminal_tag": "XDALI",
#      "spec_string": "5x1,5"
#    }
#  }
#]"""


#version 3
#ANALYSIS_PROMPT = """You are an expert Electrical Engineer and Quantity Surveyor. Analyze the provided Multi-Line Electrical Schematic image.
#
#**GOAL:**
#Extract a structured JSON array representing **EVERY VERTICAL GRID COLUMN** in the drawing.
#
#**CORE PRINCIPLE:**
#The drawing is a grid. You must iterate through every vertical strip (Column) that contains electrical symbols.
#- Do NOT group multiple columns into one entry.
#- Do NOT translate German text (extract exact strings).
#- Do NOT hallucinate components (e.g., do not see a breaker where there is only a wire).
#
#**VISUAL DICTIONARY (Strict Symbol Rules):**
#1. **FUSE:** Represented by a **Rectangular Box**.
#   - Large Box = `FUSE_NEOZED_D02` or `FUSE_NH` (Main power).
#   - Small/Thin Box = `FUSE_MINIATURE` (often labeled "Feins").
#2. **BREAKER (MCB/Switch):** Represented by a **Diagonal Lever/Switch Line**.
#   - If it has an "X" or ">" on the lever -> MCB.
#   - If it has a loop/oval next to it -> RCD or RCBO.
#3. **CONTACTOR / RELAY:** Represented by a **Square** containing a Coil symbol (diagonal line) or text.
#4. **TERMINAL / WIRE:** A simple vertical line connecting to a block (e.g., "X...").
#   - **Crucial:** If a line goes straight to a terminal with NO symbol on it, classify type as `TERMINAL_ONLY`.
#
#**EXTRACTION LOGIC (Apply to EACH Column):**
#
#**1. Circuit ID (The Anchor)**
#   - Locate the grid number at the top or bottom of the vertical strip (e.g., "1", "2", "9", "91").
#   - This is your `circuit_id`.
#
#**2. Destination / Description**
#   - **Step A:** Read the vertical text at the very bottom of the column. (e.g., "Steckdosen", "DALI Leitung").
#   - **Step B (Fallback):** If the bottom text is EMPTY (common for controls), read the text **inside the main component box** (e.g., "Gessler DNÜ", "ZUMTOBEL", "Fremdspannung").
#   - **Step C (Feeders):** If it is a Supply column, read the text describing the group (e.g., "FI Schalter Gruppe 02").
#
#**3. Connection Type**
#   - **SUPPLY:** Column contains Main Fuses/Switches protecting a downstream group. Text often contains "Zuleitung".
#   - **LOAD:** Standard outgoing circuits (Lights, Sockets).
#   - **CONTROL:** Internal panel wiring (Relays, Monitors, SPDs).
#   - **TERMINAL:** Direct connections without protection (e.g., DALI).
#
#**4. Components (Array)**
#   - Extract ALL devices in the vertical line (from top to bottom).
#   - **Tag:** Component Label (e.g., 02F0, K1, 1S1).
#   - **Type:** [MCB, RCD, RCBO, FUSE_NEOZED_D02, FUSE_MINIATURE, SWITCH_DISCONNECTOR, CONTACTOR, RELAY_MONITOR, TERMINAL_ONLY].
#   - **Poles:** Visually count the vertical lines crossing the symbol (1, 3, or 4).
#   - **Specs (Model Identifier):**
#     - *Breakers:* Extract "B16", "C16", "B10".
#     - *Fuses:* Extract "D02", "35A", "Feins 6A".
#     - *Relays/Contactors:* Extract model (e.g., "ESB25-40N", "VPU AC II").
#   - **Amps:** Just the numeric rating (e.g., "16", "35", "25").
#   - **Sensitivity:** For RCDs only (e.g., "0.03A").
#   - **Attributes:**
#     - `external_voltage`: true if labeled "Fremdspannung".
#     - `red_marked`: true if boxed in "ROT".
#
#**5. Cable & Terminals (STRICT FORMATTING RULE)**
#   - **Terminal Tag:** Label of the terminal block (e.g., "X02", "XDALI", "X40").
#   - **spec_string Enforcement:** You must ALWAYS combine the core count with the cross-section.
#     1. **Find the number:** Locate the cross-section value (e.g., "16", "1.5", "2.5").
#     2. **Count the Cores:** Count the vertical lines/terminals in that specific column (e.g., L1, L2, L3, N, PE = 5 cores).
#     3. **Format:** Output MUST be `[Cores]x[Size]mm²`.
#     4. **Examples:**
#        - Visual: "16" on a line with 5 terminals -> Output: "5x16mm²"
#        - Visual: "2.5" on a line with 3 terminals -> Output: "3x2.5mm²"
#        - Visual: "1.5" on a single line -> Output: "1x1.5mm²"
#   - *Exception:* If no external cable is shown (internal wiring only), set spec_string to "Internal".
#
#**OUTPUT FORMAT:**
#Return ONLY a valid JSON array.
#
#Example Output Structure:
#[
#  {
#    "circuit_id": "9",
#    "destination": "FI Schalter Gruppe 02 Beleuchtung",
#    "connection_type": "SUPPLY",
#    "components": [
#      {
#        "tag": "02F0",
#        "type": "FUSE_NEOZED_D02",
#        "poles": 3,
#        "specs": "D02 gG",
#        "amps": "35"
#      },
#      {
#        "tag": "02Q01",
#        "type": "RCD",
#        "poles": 4,
#        "specs": "RCCB 40A",
#        "amps": "40",
#        "sensitivity": "0.03A"
#      }
#    ],
#    "cable": {
#      "terminal_tag": "BUSBAR",
#      "spec_string": "Internal"
#    }
#  },
#  {
#    "circuit_id": "1",
#    "destination": "Main Supply",
#    "connection_type": "SUPPLY",
#    "components": [],
#    "cable": {
#      "terminal_tag": "X1",
#      "spec_string": "5x16mm²"
#    }
#  }
#]"""

#version 4
ANALYSIS_PROMPT = """You are an expert Electrical Engineer and Quantity Surveyor. Analyze the provided Multi-Line Electrical Schematic image.

**GOAL:**
Extract a structured JSON array representing **EVERY VERTICAL GRID COLUMN** in the drawing.

**CORE PRINCIPLE:**
The drawing is a grid. You must iterate through every vertical strip (Column) that contains electrical symbols.
- Do NOT group multiple columns into one entry.
- Do NOT translate German text (extract exact strings).
- Do NOT hallucinate components (e.g., do not see a breaker where there is only a wire).
- **Circuit ID Accuracy:** Scan both the TOP margin and the BOTTOM row for the circuit number. Do NOT default to "1". If the column is labeled "28" at the top, the ID is "28".

- **Strict "Connection Type" Rules:** "Steckdosen" (Sockets) are ALWAYS `LOAD`. "Zuleitung" is `SUPPLY`. Never confuse them.

- **Cable Core Precision:** You must count the vertical wires precisely. If there are 7 lines going to the terminals, the cable is "7x...".

- **Text Formatting:** Do NOT use `\n` in strings. Use a single space or `\t` (tab) if you need to separate lines of text.

**VISUAL DICTIONARY (Strict Symbol Rules):**
1. **FUSE:** Represented by a **Rectangular Box**.
   - Large Box = `FUSE_NEOZED_D02` or `FUSE_NH` (Main power).
   - Small/Thin Box = `FUSE_MINIATURE` (often labeled "Feins").
2. **BREAKER (MCB/Switch):** Represented by a **Diagonal Lever/Switch Line**.
   - If it has an "X" or ">" on the lever -> MCB.
   - If it has a loop/oval next to it -> RCD or RCBO.
3. **CONTACTOR / RELAY:** Represented by a **Square** containing a Coil symbol (diagonal line) or text.
4. **TERMINAL / WIRE:** A simple vertical line connecting to a block (e.g., "X...").
   - **Crucial:** If a line goes straight to a terminal with NO symbol on it, classify type as `TERMINAL_ONLY`.

**EXTRACTION LOGIC (Apply to EACH Column):**

**1. Circuit ID (The Anchor) - CRITICAL**
   - Locate the grid number at the top or bottom of the vertical strip (e.g., "1", "2", "9", "91").
   - **STRICT ALIGNMENT RULE:** You must ensure the Circuit ID matches the components directly below it. Do NOT mix up IDs between adjacent columns.
   - *Verification:* Trace the vertical line from the grid number down to the components. If the grid number is "9", all extracted data (breaker 02F0, cable, etc.) MUST physically align with column 9.

**2. Destination / Description**
   - **Step A:** Read the vertical text at the very bottom of the column. (e.g., "Steckdosen", "DALI Leitung").
   - **Step B (Fallback):** If the bottom text is EMPTY (common for controls), read the text **inside the main component box** (e.g., "Gessler DNÜ", "ZUMTOBEL", "Fremdspannung").
   - **Step C (Feeders):** If it is a Supply column, read the text describing the group (e.g., "FI Schalter Gruppe 02").

**3. Connection Type**
   - **SUPPLY:** Column contains Main Fuses/Switches protecting a downstream group. Text often contains "Zuleitung".
   - **LOAD:** Standard outgoing circuits (Lights, Sockets).
   - **CONTROL:** Internal panel wiring (Relays, Monitors, SPDs).
   - **TERMINAL:** Direct connections without protection (e.g., DALI).

**4. Components (Array)**
   - Extract ALL devices in the vertical line (from top to bottom).
   - **Tag:** Component Label (e.g., 02F0, K1, 1S1).
   - **Type:** [MCB, RCD, RCBO, FUSE_NEOZED_D02, FUSE_MINIATURE, SWITCH_DISCONNECTOR, CONTACTOR, RELAY_MONITOR, TERMINAL_ONLY].
   - **Poles:** Visually count the vertical lines crossing the symbol (eg. 1, 2, 3, 4, etc.).
   - **Specs (Model Identifier):**
     - *Breakers:* Extract "B16", "C16", "B10" (don't hallucinate and don't add/read extra suffix writtin in the bottom e.g. S203-B13, S201-B10)
     - *Fuses:* Extract "D02", "35A", "Feins 6A".
     - *Relays/Contactors:* Extract model (e.g., "ESB25-40N", "VPU AC II").
   - **Amps:** Just the numeric rating (e.g., "16", "35", "25").
   - **Sensitivity:** For RCDs only (e.g., "0.03A").
   - **Attributes:**
     - `external_voltage`: true if labeled "Fremdspannung".
     - `red_marked`: true if boxed in "ROT".

**5. Cable & Terminals (STRICT FORMATTING RULE)**
   - **Terminal Tag:** Label of the terminal block (e.g., "X02", "XDALI", "X40").
   - **spec_string Enforcement:** You must ALWAYS combine the core count with the cross-section.
     1. **Find the number:** Locate the cross-section value (e.g., "16", "1.5", "2.5").
     2. **Count the Cores:** Count the vertical lines/terminals in that specific column (e.g., L1, L2, L3, N, PE = 5 cores).
     3. **Format:** Output MUST be `[Cores]x[Size]mm²`.
     4. **Examples:**
        - Visual: "16" on a line with 5 terminals -> Output: "5x16mm²"
        - Visual: "2.5" on a line with 3 terminals -> Output: "3x2.5mm²"
        - Visual: "2.5" on a line with 7 terminals -> Output: "7x2.5mm²"
        - Visual: "5" on a line with 9 terminals -> Output: "9x5mm²"
        - Visual: "1.5" on a single line -> Output: "1x1.5mm²"
   - *Exception:* If no external cable is shown (internal wiring only), set spec_string to "Internal".

**OUTPUT FORMAT:**
Return ONLY a valid JSON array.

Example Output Structure:
[
  {
    "circuit_id": "982",
    "destination": "FI Schalter Gruppe 02 Beleuchtung",
    "connection_type": "SUPPLY",
    "components": [
      {
        "tag": "02F0",
        "type": "FUSE_NEOZED_D02",
        "poles": 3,
        "specs": "D02 gG",
        "amps": "35"
      },
      {
        "tag": "02Q01",
        "type": "RCD",
        "poles": 4,
        "specs": "RCCB 40A",
        "amps": "40",
        "sensitivity": "0.03A"
      }
    ],
    "cable": {
      "terminal_tag": "BUSBAR",
      "spec_string": "Internal"
    }
  },
  {
    "circuit_id": "1",
    "destination": "Main Supply",
    "connection_type": "SUPPLY",
    "components": [],
    "cable": {
      "terminal_tag": "X1",
      "spec_string": "5x16mm²"
    }
  }
]"""

def extract_json_from_response(response_text: str) -> List[Dict[str, Any]]:
    """
    Extract JSON from AI response, handling markdown code blocks if present.
    """
    # Remove markdown code blocks if present
    response_text = response_text.strip()
    
    # Try to find JSON array
    if response_text.startswith("```"):
        # Remove markdown code block markers
        lines = response_text.split("\n")
        # Remove first and last line if they are code block markers
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response_text = "\n".join(lines)
    
    # Try to find JSON array boundaries
    start_idx = response_text.find("[")
    end_idx = response_text.rfind("]")
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = response_text[start_idx:end_idx + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse JSON, trying full response: {e}")
    
    # Fallback: try parsing the whole response
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not parse JSON from response: {e}")
        print(f"Response preview: {response_text[:500]}")
        return []


def analyze_image_with_ai(
    client: genai.Client,
    model_name: str,
    image_path: Path,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Analyze a single image using Google Gemini Vision API.
    
    Args:
        client: Gemini client instance
        model_name: Name of the model to use
        image_path: Path to the image file
        max_retries: Maximum number of retry attempts
        
    Returns:
        List of extracted circuit data dictionaries
    """
    # Read image file
    with open(image_path, "rb") as f:
        image_content = f.read()
    
    # Prepare the API call
    for attempt in range(max_retries):
        try:
            # Use the same API format as test.py
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    # Pass the detailed analysis prompt
                    ANALYSIS_PROMPT,
                    # Pass the image using from_bytes (same as test.py)
                    types.Part.from_bytes(
                        data=image_content,
                        mime_type="image/png"
                    ),
                ]
            )
            
            # Extract response text
            response_text = response.text
            
            # Parse JSON from response
            results = extract_json_from_response(response_text)
            
            return results
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff
                print(f"  ⚠ Attempt {attempt + 1} failed: {e}")
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ Failed after {max_retries} attempts: {e}")
                return []


def process_single_image(
    api_key: str,
    model_name: str,
    image_path: Path,
    page_num: int,
    total_pages: int
) -> tuple[int, Path, List[Dict[str, Any]]]:
    """
    Helper function to process a single image (for parallel execution).
    Creates its own client instance to ensure thread safety.
    
    Returns:
        Tuple of (page_num, image_path, results)
    """
    print(f"[STARTING] Processing page {page_num}/{total_pages}: {image_path.name}")
    
    # Create a new client instance for this thread to ensure thread safety
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"  ❌ Page {page_num}: Failed to create client: {e}")
        return (page_num, image_path, [])
    
    results = analyze_image_with_ai(client, model_name, image_path)
    
    if results:
        # Add page number to each result for tracking
        for result in results:
            result["page"] = page_num
            result["source_image"] = image_path.name
        print(f"  ✓ Page {page_num}: Extracted {len(results)} circuit(s)")
    else:
        print(f"  ⚠ Page {page_num}: No circuits extracted")
    
    print(f"[COMPLETED] Page {page_num}/{total_pages}: {image_path.name}")
    return (page_num, image_path, results)


def process_all_images(
    input_dir: Path = Path("input_images"),
    output_file: Path = Path("results.json"),
    api_key: str = None,
    model_name: str = "gemini-2.0-flash",
    max_workers: int = 5
) -> List[Dict[str, Any]]:
    """
    Process all images in the input directory and save to a single results.json file.
    Uses parallel processing to speed up API calls.
    
    Args:
        input_dir: Directory containing input images
        output_file: Path to save the combined results JSON file
        api_key: Google API key (if None, reads from GOOGLE_API_KEY env var)
        model_name: Model to use (default: gemini-2.0-flash). Options: gemini-2.0-flash, gemini-3-pro-preview
        max_workers: Maximum number of concurrent API requests (default: 5)
        
    Returns:
        List of all extracted circuit data dictionaries
    """
    # Initialize Google Gemini client
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("ERROR: Google API key not found.")
            print("Please set GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable or pass it as argument.")
            print("You can get an API key from: https://aistudio.google.com/app/apikey")
            sys.exit(1)
    
    # Initialize the client (new API: pass api_key directly to Client)
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"ERROR: Failed to initialize Gemini client: {e}")
        sys.exit(1)
    
    # Get all image files
    image_files = sorted(input_dir.glob("page_*.png"))
    
    if not image_files:
        print(f"ERROR: No images found in {input_dir}")
        sys.exit(1)
    
    print(f"Found {len(image_files)} image(s) to process")
    print(f"Using model: {model_name}")
    print(f"Parallel workers: {max_workers}")
    print(f"Output file: {output_file}")
    print("="*60)
    
    all_results = []
    start_time = time.time()
    
    # Process images in parallel using ThreadPoolExecutor
    # Each thread will create its own client instance for thread safety
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks - pass api_key instead of client
        print(f"Submitting {len(image_files)} task(s) to thread pool (max {max_workers} concurrent)...")
        future_to_image = {}
        for i, image_path in enumerate(image_files):
            future = executor.submit(
                process_single_image,
                api_key,
                model_name,
                image_path,
                i + 1,
                len(image_files)
            )
            future_to_image[future] = (i + 1, image_path)
        
        print(f"✓ All {len(future_to_image)} task(s) queued. Up to {max_workers} will run concurrently.\n")
        print("Tasks will start as workers become available...\n")
        
        # Collect results as they complete
        page_results = {}
        completed_count = 0
        for future in as_completed(future_to_image):
            try:
                page_num, image_path, results = future.result()
                page_results[page_num] = results
                completed_count += 1
                print(f"  [Progress: {completed_count}/{len(image_files)} pages completed]")
            except Exception as e:
                page_num, image_path = future_to_image[future]
                print(f"  ❌ Page {page_num} ({image_path.name}) failed: {e}")
                page_results[page_num] = []
                completed_count += 1
    
    # Sort results by page number to maintain order
    for page_num in sorted(page_results.keys()):
        all_results.extend(page_results[page_num])
    
    elapsed_time = time.time() - start_time
    
    # Save all results to a single JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*60)
    print(f"SUCCESS: Processed {len(image_files)} page(s) in {elapsed_time:.1f} seconds")
    print(f"Total circuits extracted: {len(all_results)}")
    print(f"Results saved to: {output_file}")
    print("="*60)
    
    return all_results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze Single Line Diagram images using AI Vision"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="input_images",
        help="Directory containing input images (default: input_images)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results.json",
        help="Output JSON file path (default: results.json)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Google API key (or set GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.0-flash",
        choices=["gemini-2.0-flash", "gemini-3-pro-preview"],
        help="Model to use (default: gemini-2.0-flash)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Maximum number of concurrent API requests (default: 5). Increase for faster processing, but be mindful of API rate limits."
    )
    
    args = parser.parse_args()
    
    process_all_images(
        input_dir=Path(args.input_dir),
        output_file=Path(args.output),
        api_key=args.api_key,
        model_name=args.model,
        max_workers=args.max_workers
    )

