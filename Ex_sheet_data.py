import streamlit as st
from datetime import datetime
import json
import os
import qrcode
import cv2
import numpy as np
from io import BytesIO
import sqlite3
import hashlib

st.set_page_config(page_title="Exercise Prescription System", layout="wide")

# --- Custom CSS ---
st.markdown(
    """
    <style>
    html, body, [class*="css"]  { font-size: 14px !important; }
    h1 { font-size: 22px !important; font-weight:700 !important; margin-bottom: 0.5rem !important;}
    .cat-header {
        font-size: 15px; font-weight: 800; text-decoration: underline;
        background-color: #e1f5fe; color: #01579b; padding: 5px;
        border-radius: 4px; margin-bottom: 10px; margin-top: 10px;
    }
    .config-box {
        padding-left: 15px; border-left: 3px solid #1f77b4;
        background-color: #f0f2f6; margin-bottom: 15px;
        padding-top: 8px; padding-bottom: 8px; border-radius: 0 5px 5px 0;
    }
    .label-box {
        border: 2px dashed #999; width: 280px; height: 100px;
        display: flex; align-items: center; justify-content: center;
        color: #666; font-size: 12px; text-align: center; margin-bottom: 10px;
    }
    @media print {
        @page { size: A5 portrait; margin: 5mm; }
        .stButton, .stSelectbox, .stTextInput, [data-testid="stSidebar"], 
        header, [data-testid="stHeader"], .no-print, [data-testid="stCameraInput"], 
        .stMultiSelect, .stCheckbox, .stDateInput, .stRadio { display: none !important; }
        .main .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
        body { -webkit-print-color-adjust: exact; zoom: 0.85; }
        .print-text { font-size: 14px !important; color: black !important; line-height: 1.3 !important; margin-bottom: 5px !important; }
        .print-item { font-size: 14px !important; font-weight: 600 !important; margin-bottom: 6px !important; }
        hr { margin: 5px 0 !important; border: 0.5px solid black !important; }
        .label-box { border: 1px dashed black !important; width: 220px !important; height: 80px !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Database Setup ---
DB_FILE = "prescription_history.db"


def init_db():
    conn = sqlite3.connect(DB_FILE);
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, hashed_id TEXT NOT NULL, timestamp TEXT NOT NULL,
        op_details TEXT, op_date TEXT, p_class TEXT, p_precautions TEXT, prescription_json TEXT NOT NULL)''')
    conn.commit();
    conn.close()


init_db()


def hash_c(c): return hashlib.sha256(c.encode('utf-8')).hexdigest()


def save_h(c_no, presc, op_text, o_date, p_class, p_pre):
    conn = sqlite3.connect(DB_FILE);
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO history 
        (hashed_id, timestamp, op_details, op_date, p_class, p_precautions, prescription_json) 
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                   (hash_c(c_no), datetime.now().strftime('%m/%d/%Y %H:%M'), op_text, o_date.strftime('%Y-%m-%d'),
                    p_class, p_pre, json.dumps(presc, ensure_ascii=False)))
    conn.commit();
    conn.close()


# --- Exercise Config ---
EXERCISE_DB = {
    "Electrotherapy": [{"id": "e1", "name": "Ice + Magnetopulse"}, {"id": "e2", "name": "Gameready"},
                       {"id": "e3", "name": "EMS"}, {"id": "e4", "name": "Lymphapress"},
                       {"id": "e5", "name": "Hot Pack"}],
    "Mobilization": [{"id": "s3", "name": "Knee to chest mob"}, {"id": "s4", "name": "Static bike"},
                     {"id": "s5", "name": "Nustep"}, {"id": "s7", "name": "Sling suspension"},
                     {"id": "s8", "name": "Reciprocal pulley"}, {"id": "s9", "name": "RT300"},
                     {"id": "s10", "name": "Cybercycle"}],
    "Strengthening": [{"id": "st1", "name": "Quad exercise"}, {"id": "st2", "name": "Standing + Ham curl"},
                      {"id": "st3", "name": "Wall slides"}, {"id": "st4", "name": "企 Hip strengthening"},
                      {"id": "st7", "name": "Bridging"}, {"id": "st8", "name": "Minipress"},
                      {"id": "st9", "name": "Sitting + Hip abd"}],
    "Functional training": [{"id": "f4", "name": "Stepping on box"}, {"id": "f6", "name": "Hurdles"},
                            {"id": "f7", "name": "Foam step"}, {"id": "f11", "name": "海棉單腳企"},
                            {"id": "f8", "name": "踩磅"}, {"id": "f9", "name": "Arjo"},
                            {"id": "f10", "name": "Wall bar: 坐>企"}],
    "Walking exercise": [{"id": "w1", "name": "Stick walking"}, {"id": "w2", "name": "Quadripod walk"},
                         {"id": "w3", "name": "Stairs"}],
    "Assessment": [{"id": "a1", "name": "Assessment"}, {"id": "a2", "name": "KOOS"}],
    "Others": [{"id": "o1", "name": "Massage roller"}, {"id": "o2", "name": "網球"}, {"id": "o3", "name": "斜板"}]
}

# --- State Init ---
if "master_registry" not in st.session_state:
    st.session_state.master_registry = {}
    for cat, items in EXERCISE_DB.items():
        for ex in items:
            st.session_state.master_registry[ex["id"]] = {
                "selected": False, "mins": "15" if ex["id"].startswith("e") else "10",
                "side": "Right knee", "press": "Low pressure", "deg": "1",
                "e3_side": "Right quads", "e3_mode": "Static Quads",
                "e4_side": "Right leg", "e5_target": "Quad", "e5_other": "",
                "bike_range": "Full Circle", "seat": "", "s3_ball": "紅波", "s9_res": "", "s10_level": "Easy",
                "st1_weight": "", "st2_weight": "", "st3_ball": "紅波",
                "st4_modes": [], "st4_res": "Red",
                "st7_ball": "紅波", "st7_pos": "於膝下", "st8_side": "Right leg", "st8_red": "", "st8_black": "",
                "st9_band": "Red",
                "box_height": "4\"", "downstairs": False, "box_ems": False, "hurdle_height": "4\"", "f11_sec": "30",
                "f7_bars": False, "f7_family": False, "f8_tw": "",
                "target_muscle": "ITB", "slant_lvl": "兩格", "lymph_press": "40 mmHg"
            }

for key in ["show_sheet", "case_no_input", "final_class", "final_precautions", "final_op_text", "prescription"]:
    if key not in st.session_state: st.session_state[
        key] = False if key == "show_sheet" else "" if key != "prescription" else []
if "final_op_date" not in st.session_state: st.session_state.final_op_date = datetime.now()


def upd(e, f, v): st.session_state.master_registry[e][f] = v


def safe_index(options, value):
    try:
        return options.index(value)
    except:
        return 0


# --- Sidebar (History & QR Scanner) ---
with st.sidebar:
    st.header("🔍 Retrieval")
    with st.expander("📷 Scan Patient QR"):
        cam_img = st.camera_input("Scan QR from prescription")
        if cam_img:
            file_bytes = np.asarray(bytearray(cam_img.read()), dtype=np.uint8)
            opencv_img = cv2.imdecode(file_bytes, 1)
            qr_data, _, _ = cv2.QRCodeDetector().detectAndDecode(opencv_img)
            if qr_data: st.session_state.search_query = qr_data

    lookup_code = st.text_input("Enter Case No.", key="search_query")
    if lookup_code:
        conn = sqlite3.connect(DB_FILE);
        cursor = conn.cursor()
        cursor.execute(
            'SELECT prescription_json, op_details, op_date, p_class, p_precautions FROM history WHERE hashed_id = ? ORDER BY id DESC LIMIT 1',
            (hash_c(lookup_code),))
        res = cursor.fetchone();
        conn.close()
        if res:
            if st.button("Load Recent Record", use_container_width=True):
                st.session_state.case_no_input = lookup_code
                st.session_state.final_op_text, st.session_state.final_op_date = res[1], datetime.strptime(res[2],
                                                                                                           '%Y-%m-%d')
                st.session_state.final_class, st.session_state.final_precautions = res[3], res[4]
                last_presc = json.loads(res[0])
                for eid in st.session_state.master_registry: st.session_state.master_registry[eid]["selected"] = False
                for item in last_presc:
                    if item["id"] in st.session_state.master_registry:
                        st.session_state.master_registry[item["id"]].update(item);
                        st.session_state.master_registry[item["id"]]["selected"] = True
                st.rerun()

# --- Selection Panel ---
if not st.session_state.get("show_sheet"):
    st.title("Exercise Prescription")
    l, r = st.columns([1.2, 3.5])
    with l:
        st.subheader("Patient Info")
        c_no = st.text_input("Case No.", key="case_no_input")
        p_cl = st.radio("Patient Class", ["Class I", "Class II", "Class III"], horizontal=True)
        st.markdown("**Precautions:**")
        p_att, p_fing = st.checkbox("多注目"), st.checkbox("夾手指做運動")
        st.markdown("**Operation:**")
        r_on = st.checkbox("Right Side", value=True)
        r_ty = st.selectbox("Type (R)", ["TKR", "UKA", "THR", "HTO"], key="r_op") if r_on else ""
        l_on = st.checkbox("Left Side")
        l_ty = st.selectbox("Type (L)", ["TKR", "UKA", "THR", "HTO"], key="l_op") if l_on else ""
        op_d = st.date_input("Op Date", value=datetime.now())

        if st.button("Generate Prescription", type="primary", use_container_width=True):
            if not st.session_state.case_no_input:
                st.error("Missing Case No.")
            else:
                pre = [x for x, y in zip(["多注目", "夾手指做運動"], [p_att, p_fing]) if y]
                st.session_state.final_precautions = ", ".join(pre) if pre else "None"
                ops = [f"Right {r_ty}" if r_on else None, f"Left {l_ty}" if l_on else None]
                st.session_state.final_op_text = ", ".join(filter(None, ops)) or "N/A"
                st.session_state.final_class, st.session_state.final_op_date = p_cl, op_d
                sel = [
                    {"id": eid, "name": next(x["name"] for c in EXERCISE_DB.values() for x in c if x["id"] == eid), **d}
                    for eid, d in st.session_state.master_registry.items() if d["selected"]]
                save_h(st.session_state.case_no_input, sel, st.session_state.final_op_text, op_d, p_cl,
                       st.session_state.final_precautions)
                st.session_state.prescription = sel;
                st.session_state.show_sheet = True;
                st.rerun()

    with r:
        cols = st.columns(3)
        for idx, (cat_name, items) in enumerate(EXERCISE_DB.items()):
            with cols[idx % 3]:
                st.markdown(f'<div class="cat-header">{cat_name}</div>', unsafe_allow_html=True)
                for ex in items:
                    eid = ex["id"]
                    reg = st.session_state.master_registry[eid]
                    is_checked = st.checkbox(ex["name"], value=reg["selected"], key=f"cb_{eid}",
                                             on_change=lambda e=eid: upd(e, "selected", st.session_state[f"cb_{e}"]))

                    if is_checked:
                        st.markdown('<div class="config-box">', unsafe_allow_html=True)
                        if not (eid.startswith("w") or eid.startswith("a")):
                            st.text_input("Mins", value=reg["mins"], key=f"m_{eid}",
                                          on_change=lambda e=eid: upd(e, "mins", st.session_state[f"m_{e}"]))

                        if eid == "e1":
                            opts = ["Right knee", "Left knee", "Bilateral"]
                            st.selectbox("Side", opts, index=safe_index(opts, reg["side"]), key=f"s_{eid}",
                                         on_change=lambda e=eid: upd(e, "side", st.session_state[f"s_{e}"]))
                        elif eid == "e2":
                            opts = ["Right knee", "Left knee", "Bilateral"]
                            st.selectbox("Side", opts, index=safe_index(opts, reg["side"]), key=f"s_{eid}",
                                         on_change=lambda e=eid: upd(e, "side", st.session_state[f"s_{e}"]))
                            st.text_input("Temp (°C)", value=reg["deg"], key=f"temp_{eid}",
                                          on_change=lambda e=eid: upd(e, "deg", st.session_state[f"temp_{e}"]))
                        elif eid == "e3":
                            opts_s = ["Right quads", "Left quads", "Bilateral"]
                            st.selectbox("Side", opts_s, index=safe_index(opts_s, reg["e3_side"]), key=f"s_{eid}",
                                         on_change=lambda e=eid: upd(e, "e3_side", st.session_state[f"s_{e}"]))
                            opts_m = ["Static Quads", "Quad Board 踢腳", "沙包壓腳"]
                            st.selectbox("Mode", opts_m, index=safe_index(opts_m, reg["e3_mode"]), key=f"md_{eid}",
                                         on_change=lambda e=eid: upd(e, "e3_mode", st.session_state[f"md_{e}"]))
                        elif eid == "e4":
                            opts = ["40 mmHg", "50 mmHg", "60 mmHg"]
                            st.selectbox("Press", opts, index=safe_index(opts, reg["lymph_press"]), key=f"p_{eid}",
                                         on_change=lambda e=eid: upd(e, "lymph_press", st.session_state[f"p_{e}"]))
                        elif eid == "e5":
                            opts = ["Quad", "ITB", "Calf", "Hamstring", "Others"]
                            st.selectbox("Area", opts, index=safe_index(opts, reg["e5_target"]), key=f"t_{eid}",
                                         on_change=lambda e=eid: upd(e, "e5_target", st.session_state[f"t_{e}"]))
                            if reg["e5_target"] == "Others": st.text_input("Spec", value=reg["e5_other"],
                                                                           key=f"o_{eid}",
                                                                           on_change=lambda e=eid: upd(e, "e5_other",
                                                                                                       st.session_state[
                                                                                                           f"o_{e}"]))

                        elif eid == "st1" or eid == "st2":
                            st.text_input("Sandbag (lbs)", value=reg[f"{eid}_weight"], key=f"w_{eid}",
                                          on_change=lambda e=eid: upd(e, f"{e}_weight", st.session_state[f"w_{e}"]))
                        elif eid == "st4":
                            st.multiselect("Dirs", ["側 (Abd)", "前 (Flex)", "後 (Ext)"], default=reg["st4_modes"],
                                           key=f"sm_{eid}",
                                           on_change=lambda e=eid: upd(e, "st4_modes", st.session_state[f"sm_{e}"]))
                            opts = ["Yellow", "Red", "Green", "Blue"]
                            st.selectbox("Resist", opts, index=safe_index(opts, reg["st4_res"]), key=f"sr_{eid}",
                                         on_change=lambda e=eid: upd(e, "st4_res", st.session_state[f"sr_{e}"]))

                        elif eid == "f4":
                            opts = ["4\"", "6\"", "8\""]
                            st.selectbox("Box", opts, index=safe_index(opts, reg["box_height"]), key=f"bh_{eid}",
                                         on_change=lambda e=eid: upd(e, "box_height", st.session_state[f"bh_{e}"]))
                            st.checkbox("Downstairs", value=reg["downstairs"], key=f"ds_{eid}",
                                        on_change=lambda e=eid: upd(e, "downstairs", st.session_state[f"ds_{e}"]))
                        elif eid == "f6":
                            opts = ["4\"", "6\""]
                            st.selectbox("Hurdle", opts, index=safe_index(opts, reg["hurdle_height"]), key=f"hh_{eid}",
                                         on_change=lambda e=eid: upd(e, "hurdle_height", st.session_state[f"hh_{e}"]))
                        elif eid == "f11":
                            st.text_input("Seconds", value=reg["f11_sec"], key=f"sec_{eid}",
                                          on_change=lambda e=eid: upd(e, "f11_sec", st.session_state[f"sec_{e}"]))

                        elif eid == "o1" or eid == "o2":
                            opts = ["ITB", "Quad", "Calf", "Hamstring"]
                            st.selectbox("Target", opts, index=safe_index(opts, reg["target_muscle"]), key=f"tm_{eid}",
                                         on_change=lambda e=eid: upd(e, "target_muscle", st.session_state[f"tm_{e}"]))
                        elif eid == "o3":
                            opts = ["兩格", "三格", "四格"]
                            st.selectbox("Lvl", opts, index=safe_index(opts, reg["slant_lvl"]), key=f"sl_{eid}",
                                         on_change=lambda e=eid: upd(e, "slant_lvl", st.session_state[f"sl_{e}"]))

                        st.markdown('</div>', unsafe_allow_html=True)
else:
    # --- Print View ---
    st.markdown('<div class="spread-container">', unsafe_allow_html=True)
    h1, h2 = st.columns([2.5, 1])
    with h1:
        st.header("Exercise Prescription")
        st.markdown('<div class="label-box">STAMP PATIENT LABEL HERE</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="print-text"><b>Case:</b> {st.session_state.case_no_input} | <b>{st.session_state.get("final_class", "")}</b></div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div class="print-text"><b>Precautions:</b> {st.session_state.get("final_precautions", "None")}</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div class="print-text"><b>Op:</b> {st.session_state.get("final_op_text", "N/A")} ({st.session_state.final_op_date.strftime("%m/%d/%Y")})</div>',
            unsafe_allow_html=True)
    with h2:
        qr = qrcode.QRCode(box_size=10);
        qr.add_data(st.session_state.case_no_input);
        buf = BytesIO();
        qr.make_image().save(buf, format="PNG");
        st.image(buf, width=80)
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="exercise-list">', unsafe_allow_html=True)
    for item in st.session_state.prescription:
        eid, name, mins, d = item['id'], item['name'], item.get('mins', '15'), []
        if eid == "e1":
            d.append(item.get("side"))
        elif eid == "e2":
            d.append(f"{item.get('side')} ({item.get('deg')}°C)")
        elif eid == "e3":
            d.append(f"{item.get('e3_side')} - {item.get('e3_mode')}")
        elif eid == "e5":
            d.append(item.get("e5_other") if item.get("e5_target") == "Others" else item.get("e5_target"))
        elif eid == "st1":
            d.append(f"{item.get('st1_weight')} lbs")
        elif eid == "st2":
            d.append(f"{item.get('st2_weight')} lbs")
        elif eid == "st4":
            d.append(f"{', '.join(item.get('st4_modes', []))} ({item.get('st4_res')})")
        elif eid == "f4":
            d.append(f"Box: {item.get('box_height')}")
            if item.get("downstairs"): d.append("Downstairs")
        elif eid == "f6":
            d.append(f"Hurdle: {item.get('hurdle_height')}")
        elif eid == "f11":
            d.append(f"{item.get('f11_sec')}s")
        elif eid in ["o1", "o2"]:
            d.append(f"Target: {item.get('target_muscle')}")
        elif eid == "o3":
            d.append(f"Level: {item.get('slant_lvl')}")

        d_str = f" ({', '.join(filter(None, d))})" if d else ""
        st.markdown(f'<div class="print-item">- {name}{d_str}' + (
            f' x {mins}m' if not (eid.startswith("w") or eid.startswith("a")) else "") + '</div>',
                    unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="print-text" style="text-align: right; border-top: 0.5px solid #000; padding-top: 5px;"><b>Date:</b> {datetime.now().strftime("%m/%d/%Y")}</div>',
        unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("Back to Selection"): st.session_state.show_sheet = False; st.rerun()