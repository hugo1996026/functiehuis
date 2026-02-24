# app.py
# Streamlit app: Medewerkerslijst + beoordeling -> standaardfunctie (basisframework)
# Start: streamlit run app.py

from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict, Any
import json
import os
import datetime as dt

import streamlit as st
import pandas as pd

# -----------------------------
# Data model
# -----------------------------
LEVELS = [3, 4, 5, 6, 7, 8, 9, 10]

@dataclass
class Role:
    code: str
    title: str
    family: str
    level: int
    keywords: List[str]

# Voorbeeldset (Montage). Later uitbreiden naar alle families/41 rollen.
ROLES = [

    # PROJECTLEIDING
    Role("UITV_8", "Uitvoerder (8)", "Projectleiding", 8, []),
    Role("PL_8", "Projectleider (8)", "Projectleiding", 8, []),
    Role("PL_9", "Projectleider (9)", "Projectleiding", 9, []),
    Role("PL_10", "Projectleider (10)", "Projectleiding", 10, []),

    # BEDRIJFSBUREAU
    Role("TEK_5", "Tekenaar (5)", "Bedrijfsbureau", 5, []),
    Role("TEK_6", "Tekenaar (6)", "Bedrijfsbureau", 6, []),
    Role("CALC_6", "Calculator (6)", "Bedrijfsbureau", 6, []),
    Role("CALC_7", "Calculator (7)", "Bedrijfsbureau", 7, []),
    Role("WV_6", "Werkvoorbereider (6)", "Bedrijfsbureau", 6, []),
    Role("WV_7", "Werkvoorbereider (7)", "Bedrijfsbureau", 7, []),
    Role("ENG_8", "Engineer (8)", "Bedrijfsbureau", 8, []),
    Role("ENG_9", "Engineer (9)", "Bedrijfsbureau", 9, []),
    Role("SW_8", "Software Engineer (8)", "Bedrijfsbureau", 8, []),
    Role("SW_9", "Software Engineer (9)", "Bedrijfsbureau", 9, []),
    Role("BIM_8", "BIM Modelleur (8)", "Bedrijfsbureau", 8, []),
    Role("BIM_10", "BIM Coördinator (10)", "Bedrijfsbureau", 10, []),

    # MONTAGE
    Role("ASM_3", "Assistent Monteur (3)", "Montage", 3, []),
    Role("MON_4", "Monteur (4)", "Montage", 4, []),
    Role("MON_5", "Monteur (5)", "Montage", 5, []),
    Role("MON_6", "Monteur (6)", "Montage", 6, []),
    Role("HM_6", "Hoofdmonteur (6)", "Montage", 6, []),
    Role("HM_7", "Hoofdmonteur (7)", "Montage", 7, []),
    Role("MS_7", "Montagespecialist (7)", "Montage", 7, []),
    Role("MS_8", "Montagespecialist (8)", "Montage", 8, []),

    # TECHNISCH BEHEER
    Role("SM_5", "Service Monteur (5)", "Technisch beheer", 5, []),
    Role("SM_6", "Service Monteur (6)", "Technisch beheer", 6, []),
    Role("SS_7", "Service Specialist (7)", "Technisch beheer", 7, []),
    Role("SS_8", "Service Specialist (8)", "Technisch beheer", 8, []),
    Role("SC_7", "Service Coördinator (7)", "Technisch beheer", 7, []),
    Role("SC_8", "Service Coördinator (8)", "Technisch beheer", 8, []),
    Role("SC_9", "Service Coördinator (9)", "Technisch beheer", 9, []),
    Role("IB_7", "Inbedrijfsteller (7)", "Technisch beheer", 7, []),
    Role("IB_8", "Inbedrijfsteller (8)", "Technisch beheer", 8, []),
    Role("CB_7", "Contractbeheerder (7)", "Technisch beheer", 7, []),
    Role("CB_8", "Contractbeheerder (8)", "Technisch beheer", 8, []),
    Role("TB_7", "Technisch Beheerder (7)", "Technisch beheer", 7, []),
    Role("TB_8", "Technisch Beheerder (8)", "Technisch beheer", 8, []),

    # ONDERSTEUNEND
    Role("MAG_5", "Magazijnmedewerker (5)", "Ondersteunend", 5, []),
    Role("ADM_6", "Administratief Medewerker (6)", "Ondersteunend", 6, []),
    Role("INS_9", "Inspecteur Installaties (9)", "Ondersteunend", 9, []),
    Role("ADV_9", "Adviseur (duurzame) techniek (9)", "Ondersteunend", 9, []),
]
FAMILIES = sorted(list({r.family for r in ROLES}))

DATA_FILE = "functieapp_data.json"


# -----------------------------
# Scoring helpers
# -----------------------------
def clamp_level(n: int) -> int:
    return max(min(n, max(LEVELS)), min(LEVELS))

def compute_characteristic_level(score: int) -> int:
    # score 0..12 -> niveau indicatie
    if score <= 2:  return 3
    if score <= 4:  return 4
    if score <= 6:  return 5
    if score <= 8:  return 6
    if score <= 10: return 7
    return 8

def decide_final_level(c_lvl: int, z_lvl: int, a_lvl: int, f_lvl: int) -> Tuple[int, str]:
    # 2 van 3 kernkarakteristieken (C/Z/A) is leidend; fysiek kan tie-breaken
    levels = [c_lvl, z_lvl, a_lvl]
    for candidate in set(levels):
        if levels.count(candidate) >= 2:
            return candidate, f"Doorslaggevend: 2 van 3 kernkarakteristieken wijzen naar niveau {candidate}."
    avg = clamp_level(round(sum(levels) / 3))
    if f_lvl >= avg + 2:
        return clamp_level(avg + 1), "Twijfelgeval: Fysieke aspecten duwen het niveau 1 stap omhoog."
    if f_lvl <= avg - 2:
        return clamp_level(avg - 1), "Twijfelgeval: Fysieke aspecten duwen het niveau 1 stap omlaag."
    return avg, "Geen duidelijke meerderheid: niveau bepaald op gemiddelde van kernkarakteristieken."

def pick_best_role(family: str, final_level: int) -> Tuple[Optional[Role], List[Role]]:
    candidates = [r for r in ROLES if r.family == family]
    if not candidates:
        return None, []
    candidates_sorted = sorted(candidates, key=lambda r: (abs(r.level - final_level), r.level))
    return candidates_sorted[0], candidates_sorted[:5]


# -----------------------------
# Persistence
# -----------------------------
def load_data() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"employees": []}

def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_state():
    if "data" not in st.session_state:
        st.session_state.data = load_data()
    if "selected_employee_id" not in st.session_state:
        st.session_state.selected_employee_id = None


# -----------------------------
# UI helpers
# -----------------------------
def question_block(prefix: str, title: str, questions: List[Tuple[str, int]], existing: Optional[Dict[str, int]] = None) -> Tuple[int, Dict[str, int]]:
    st.subheader(title)
    answers: Dict[str, int] = {}
    total = 0
    for i, (label, maxp) in enumerate(questions):
        key = f"{prefix}_{title}_{i}"
        default_val = 0
        if existing and key in existing:
            default_val = int(existing[key])
        val = st.slider(label, 0, maxp, default_val, key=key)
        answers[key] = val
        total += val
    st.caption(f"Subtotaal: {total}")
    return total, answers

def employees_df(employees: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for e in employees:
        assessment = e.get("assessment", {})
        rows.append({
            "ID": e.get("id"),
            "Naam": e.get("name"),
            "Afdeling": e.get("department", ""),
            "Functiefamilie": assessment.get("family", ""),
            "Niveau": assessment.get("final_level", ""),
            "Standaardfunctie": assessment.get("best_role_title", ""),
            "Laatste update": assessment.get("saved_at", ""),
            "Notities": e.get("notes", ""),
        })
    return pd.DataFrame(rows)

def make_employee_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d%H%M%S%f")


# -----------------------------
# App
# -----------------------------
st.set_page_config(page_title="Functieapp — medewerkers → standaardfunctie", layout="wide")
ensure_state()

st.title("Functieapp — medewerkerslijst → beoordeling → standaardfunctie")

with st.sidebar:
    st.header("Medewerkers")
    st.caption("Voeg medewerkers toe, selecteer iemand, beoordeel en sla op.")

    # Add employee form
    with st.expander("➕ Medewerker toevoegen", expanded=True):
        name = st.text_input("Naam*", value="")
        department = st.text_input("Afdeling", value="")
        notes = st.text_area("Notities", value="", height=80)
        if st.button("Toevoegen"):
            if not name.strip():
                st.warning("Vul minimaal een naam in.")
            else:
                new_emp = {
                    "id": make_employee_id(),
                    "name": name.strip(),
                    "department": department.strip(),
                    "notes": notes.strip(),
                    "assessment": {}
                }
                st.session_state.data["employees"].append(new_emp)
                save_data(st.session_state.data)
                st.success(f"Toegevoegd: {new_emp['name']}")
                st.session_state.selected_employee_id = new_emp["id"]
                st.rerun()

    employees = st.session_state.data["employees"]
    if employees:
        options = {f"{e['name']} ({e.get('department','')})".strip(): e["id"] for e in employees}
        label_list = list(options.keys())
        current_id = st.session_state.selected_employee_id
        # determine selected index
        selected_index = 0
        if current_id:
            for idx, lab in enumerate(label_list):
                if options[lab] == current_id:
                    selected_index = idx
                    break
        selected_label = st.selectbox("Selecteer medewerker", label_list, index=selected_index)
        st.session_state.selected_employee_id = options[selected_label]

        st.divider()
        st.subheader("Export / beheer")
        df = employees_df(employees)
        st.download_button(
            "⬇️ Download CSV (overzicht)",
            df.to_csv(index=False).encode("utf-8"),
            file_name="functieapp_overzicht.csv",
            mime="text/csv"
        )

        if st.button("💾 Handmatig opslaan"):
            save_data(st.session_state.data)
            st.success("Data opgeslagen.")

        if st.button("🧹 Verwijder geselecteerde medewerker"):
            sid = st.session_state.selected_employee_id
            st.session_state.data["employees"] = [e for e in employees if e["id"] != sid]
            st.session_state.selected_employee_id = None
            save_data(st.session_state.data)
            st.success("Medewerker verwijderd.")
            st.rerun()
    else:
        st.info("Nog geen medewerkers toegevoegd.")

# Main area
employees = st.session_state.data["employees"]
df = employees_df(employees)
st.subheader("Overzicht")
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Beoordeling")

sid = st.session_state.selected_employee_id
selected_emp = next((e for e in employees if e["id"] == sid), None)

if not selected_emp:
    st.info("Selecteer links een medewerker om te beoordelen.")
    st.stop()

st.write(f"**Medewerker:** {selected_emp['name']}  \n**Afdeling:** {selected_emp.get('department','')}")

# Family selection for this employee
assessment = selected_emp.get("assessment", {})
family = st.selectbox("Functiefamilie", FAMILIES, index=FAMILIES.index(assessment.get("family", FAMILIES[0])))

# Load previous answers if any
prev_answers = assessment.get("answers", {})

col1, col2 = st.columns(2)

with col1:
    complexity_score, complexity_answers = question_block(
        prefix="A",
        title="1) Complexiteit",
        questions=[
            ("Werk is vooral standaard (0) vs regelmatig maatwerk/variatie (2)", 2),
            ("Meerdere technieken/systemen combineren (2)", 2),
            ("Veel schakelen/onderbrekingen/druk (2)", 2),
            ("Problemen vragen analyse en afwegingen (3)", 3),
            ("Keuzes hebben commerciële/financiële impact (3)", 3),
        ],
        existing=prev_answers
    )

    independence_score, independence_answers = question_block(
        prefix="B",
        title="2) Zelfstandigheid",
        questions=[
            ("Instructies bepalen aanpak (0) vs veel eigen vrijheid (3)", 3),
            ("Plant eigen werk / bepaalt volgorde (3)", 3),
            ("Neemt beslissingen die project/anderen beïnvloeden (3)", 3),
            ("Geeft (functioneel) leiding aan anderen (3)", 3),
        ],
        existing=prev_answers
    )

with col2:
    risk_score, risk_answers = question_block(
        prefix="C",
        title="3) Afbreukrisico",
        questions=[
            ("Fouten: beperkt tijd/materiaalverlies (0) vs grotere schade (3)", 3),
            ("Fouten kunnen klantrelatie/imago beïnvloeden (3)", 3),
            ("Fouten kunnen forse financiële gevolgen/claims hebben (3)", 3),
            ("Discretie/vertrouwelijkheid vereist (3)", 3),
        ],
        existing=prev_answers
    )

    physical_score, physical_answers = question_block(
        prefix="D",
        title="4) Fysieke aspecten",
        questions=[
            ("Licht (0) vs regelmatig zwaar/onaangenaam (3)", 3),
            ("Risicovolle situaties (hoogte/val/chemie/etc.) (3)", 3),
            ("Structureel zwaar/risicovol werk (>25%) (3)", 3),
            ("PBM’s/onaangename factoren regelmatig nodig (3)", 3),
        ],
        existing=prev_answers
    )

# Convert to levels
c_lvl = compute_characteristic_level(complexity_score)
z_lvl = compute_characteristic_level(independence_score)
a_lvl = compute_characteristic_level(risk_score)
f_lvl = compute_characteristic_level(physical_score)

final_level, rationale = decide_final_level(c_lvl, z_lvl, a_lvl, f_lvl)
best_role, alternatives = pick_best_role(family, final_level)

st.divider()
st.write("**Indicatie per karakteristiek (niveau):**")
st.write(f"- Complexiteit: **{c_lvl}**")
st.write(f"- Zelfstandigheid: **{z_lvl}**")
st.write(f"- Afbreukrisico: **{a_lvl}**")
st.write(f"- Fysieke aspecten: **{f_lvl}**")

st.success(f"👉 Berekend functieniveau (functiegroep): **{final_level}**")
st.caption(rationale)

if best_role:
    st.write(f"**Voorgestelde standaardfunctie:** ✅ **{best_role.title}**")
    if alternatives:
        with st.expander("Alternatieven (dichtstbij)"):
            for r in alternatives:
                st.write(f"- {r.title} (afstand: {abs(r.level - final_level)})")
else:
    st.warning("Geen rollen gevonden in deze functiefamilie. Voeg rollen toe in ROLES in de code.")

extra_note = st.text_area("Beoordelaar-notitie (optioneel)", value=assessment.get("review_note", ""), height=90)

if st.button("✅ Opslaan bij medewerker"):
    # store answers + outcome in employee record
    merged_answers = {}
    merged_answers.update(complexity_answers)
    merged_answers.update(independence_answers)
    merged_answers.update(risk_answers)
    merged_answers.update(physical_answers)

    selected_emp["assessment"] = {
        "family": family,
        "scores": {
            "complexity_score": complexity_score,
            "independence_score": independence_score,
            "risk_score": risk_score,
            "physical_score": physical_score,
        },
        "levels": {
            "complexity_level": c_lvl,
            "independence_level": z_lvl,
            "risk_level": a_lvl,
            "physical_level": f_lvl,
        },
        "final_level": final_level,
        "rationale": rationale,
        "best_role_code": best_role.code if best_role else "",
        "best_role_title": best_role.title if best_role else "",
        "review_note": extra_note.strip(),
        "answers": merged_answers,
        "saved_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_data(st.session_state.data)
    st.success("Opgeslagen ✅ (wordt bewaard in functieapp_data.json naast app.py)")
    st.rerun()