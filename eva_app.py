#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
📜 EVA'S THEORIE APP (V56 - PATH FIX)
-----------------------------------------------------
Reparaties:
- PATH FIX: We roepen edge-tts nu aan via 'python -m edge_tts' in plaats van
  alleen 'edge-tts'. Dit lost het probleem op dat de server het commando niet kan vinden.
- ERROR LOGGING: Als het nu mislukt, zie je de ECHTE foutmelding in beeld (niet alleen in de console).

Gebruik:
Start via terminal: streamlit run eva_app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import time
import base64
import os
import json
import tempfile
import re
import urllib.parse
import sys
import subprocess
from datetime import datetime, date

# ----------------------------------------------------------------------
# 1️⃣ CONFIGURATIE
# ----------------------------------------------------------------------

st.set_page_config(
    page_title="Eva's Theorie 🚗",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

if not st.runtime.exists():
    st.error("⚠️ Start via terminal: streamlit run eva_app.py")
    st.stop()

# --- CONSTANTEN ---
HISTORY_FILE = "progress.json"
EXAM_PASS_SCORE = 18

# Stemmen
VOICE_OPTIONS = {
    "Fenna (Vrouw - Standaard)": "nl-NL-FennaNeural",
    "Maarten (Man - Papa)": "nl-NL-MaartenNeural",
    "Colette (Vrouw - Extra)": "nl-NL-ColetteNeural"
}

REWARD_GIFS = [
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif", 
    "https://media.giphy.com/media/nNxT5qXR02FOM/giphy.gif",     
    "https://media.giphy.com/media/artj9zsVs8MFy/giphy.gif",     
    "https://media.giphy.com/media/3oz8xAFtqoOUUrsh7W/giphy.gif", 
    "https://media.giphy.com/media/Is1O1TWV0LEJi/giphy.gif",      
    "https://media.giphy.com/media/d31w24pskko8663a/giphy.gif"    
]

TTS_AVAILABLE = True 

# ----------------------------------------------------------------------
# 2️⃣ AUDIO ENGINE (FAIL-SAFE)
# ----------------------------------------------------------------------

def get_audio_player_html(speech_b64=None):
    """
    HTML/JS audiospeler V56.
    Strategie: Knop is standaard ZICHTBAAR. Javascript verbergt hem als autoplay lukt.
    """
    if not speech_b64:
        return ""

    music_url = "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3"
    speech_src = f"data:audio/mp3;base64,{speech_b64}"
    user_vol = st.session_state.music_volume
    uid = f"player_{random.randint(10000, 99999)}"

    # Styles
    btn_style = """
        display: inline-block; 
        margin: 5px auto; 
        background: #0095f6; 
        color: white; 
        border: none; 
        padding: 8px 16px; 
        border-radius: 20px; 
        font-family: sans-serif; 
        font-weight: bold; 
        font-size: 14px;
        cursor: pointer;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    """

    html = f"""
<div id="wrapper_{uid}" style="text-align:center; padding: 5px;">
    
    <audio id="music_{uid}" loop crossorigin="anonymous" playsinline preload="auto" style="display:none;">
        <source src="{music_url}" type="audio/mp3">
    </audio>
    <audio id="speech_{uid}" playsinline preload="auto" style="width: 200px; height: 30px; display:none;">
        <source src="{speech_src}" type="audio/mp3">
    </audio>

    <button id="btn_{uid}" onclick="forcePlay_{uid}()" style="{btn_style}">
        🔊 Tik voor geluid
    </button>
    <div id="status_{uid}" style="font-size:10px; color:#888; margin-top:2px;"></div>

</div>

<script>
(function() {{
    var music = document.getElementById('music_{uid}');
    var speech = document.getElementById('speech_{uid}');
    var btn = document.getElementById('btn_{uid}');
    var status = document.getElementById('status_{uid}');
    var vol = {user_vol};

    window.forcePlay_{uid} = function() {{
        btn.innerHTML = "Laden...";
        var AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {{
            var ctx = new AudioContext();
            ctx.resume();
        }}
        playSequence(true);
    }};

    function playSequence(isManual) {{
        if(music) {{
            music.volume = vol;
            var p = music.play();
            if(p !== undefined) {{ p.catch(e => {{}}); }}
        }}

        if(speech) {{
            if(music) music.volume = 0.05; 
            setTimeout(function() {{
                speech.volume = 1.0;
                var p2 = speech.play();
                if (p2 !== undefined) {{
                    p2.then(_ => {{
                        btn.style.display = 'none'; 
                        status.innerHTML = "Audio speelt...";
                        speech.onended = function() {{
                            if(music) {{
                                var fadeIn = setInterval(function() {{
                                    if (music.volume < vol) {{ music.volume += 0.05; }} 
                                    else {{ music.volume = vol; clearInterval(fadeIn); }}
                                }}, 100);
                            }}
                            status.innerHTML = "";
                        }};
                    }}).catch(error => {{
                        if(!isManual) {{
                            btn.style.display = 'inline-block';
                            status.innerHTML = "Tik op de knop (iOS)";
                        }}
                    }});
                }}
            }}, 300);
        }}
    }}
    playSequence(false);
}})();
</script>
"""
    return html

# ----------------------------------------------------------------------
# 3️⃣ TEKST LOGICA
# ----------------------------------------------------------------------

def clean_text_for_speech(text):
    if not text: return ""
    clean = re.sub(r'[\*\_#`]', '', text)
    clean = clean.replace(';', ',').replace(':', ',')
    clean = clean.replace("km/u", "kilometer per uur")
    clean = clean.replace("/", " of ")
    clean = re.sub(r'\bA\b', 'optie A', clean)
    clean = re.sub(r'\bB\b', 'optie B', clean)
    clean = re.sub(r'\bC\b', 'optie C', clean)
    return clean.strip()

def get_dad_feedback(is_correct, explanation):
    explanation = clean_text_for_speech(explanation)
    if is_correct:
        intros = ["Kijk, dat is mijn dochter! Goed.", "Lekker bezig Eef!", "Hoppa! In the pocket.", "Zie je wel dat je het kan? 😉", "De poesjes zijn trots!", "Gas erop Eef, dit is goed!", "Keurig."]
        return f"{random.choice(intros)} {explanation}"
    else:
        intros = ["Kom op frikandel, even dat koppie erbij!", "Hé Truus, zat je te slapen?", "Serieus Eef? Zelfs de poesjes wisten deze.", "Nee joh, dat meen je niet.", "Ai ai ai... dat gaat geld kosten.", "Je rijdt nu als een dweil, Eef. Focus!", "Niet gokken Truus, nadenken!", "Fout! Opletten jij."]
        return f"{random.choice(intros)} Het antwoord was fout. {explanation}"

def make_question_audio(row):
    q = clean_text_for_speech(row['question'])
    if "u " in q.lower(): q = q.replace("u ", "je ").replace("U ", "je ")
    opt1 = clean_text_for_speech(str(row['opt1']))
    opt2 = clean_text_for_speech(str(row['opt2']))
    opt3 = clean_text_for_speech(str(row['opt3'])) if str(row['opt3']).lower() != 'nan' else ""
    return f"Vraag: {q}. Is het: {opt1}? {opt2}? {opt3}"

# ----------------------------------------------------------------------
# 4️⃣ CACHED DATA & TTS (PATH FIX METHOD)
# ----------------------------------------------------------------------

@st.cache_data
def load_data():
    if not os.path.exists('vragen.csv'): return pd.DataFrame()
    try:
        df = pd.read_csv('vragen.csv', sep=';', dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

@st.cache_data(show_spinner=False)
def generate_audio_file(text, voice_key="Fenna (Vrouw - Standaard)"):
    """
    V56: Gebruikt sys.executable om edge-tts module direct aan te roepen.
    Dit voorkomt 'command not found' errors op servers.
    """
    if not text: return None
    
    voice = VOICE_OPTIONS.get(voice_key, "nl-NL-FennaNeural")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        output_file = f.name
    
    try:
        # HIER IS DE FIX: We gebruiken 'python -m edge_tts'
        # sys.executable is het pad naar de huidige python (bijv. /usr/bin/python3)
        command = [sys.executable, "-m", "edge_tts", "--text", text, "--write-media", output_file, "--voice", voice]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(output_file):
            with open(output_file, "rb") as f:
                data = f.read()
            os.remove(output_file)
            return base64.b64encode(data).decode()
        else:
            # Als het faalt, tonen we de ECHTE foutmelding in de app (handig voor debug)
            st.error(f"⚠️ Audio Server Fout: {result.stderr}")
            return None
            
    except Exception as e:
        st.error(f"⚠️ Audio Python Fout: {str(e)}")
        if os.path.exists(output_file): os.remove(output_file)
        return None
    
    return None

# ----------------------------------------------------------------------
# 5️⃣ OPSLAG & STATE
# ----------------------------------------------------------------------

def load_history():
    default = {"total_score": 0, "mistakes_list": [], "exams_history": [], "streak": 0}
    if os.path.exists(HISTORY_FILE):
        try: return {**default, **json.load(open(HISTORY_FILE, 'r'))}
        except: pass
    return default

def save_history(data):
    try: json.dump(data, open(HISTORY_FILE, 'w'))
    except: pass

if 'user_data' not in st.session_state: st.session_state.user_data = load_history()
if 'mode' not in st.session_state: st.session_state.mode = 'dashboard'
if 'streak' not in st.session_state: st.session_state.streak = st.session_state.user_data.get('streak', 0)
if 'current_index' not in st.session_state: st.session_state.current_index = 0
if 'music_volume' not in st.session_state: st.session_state.music_volume = 0.3
if 'answered_question' not in st.session_state: st.session_state.answered_question = False
if 'selected_answer' not in st.session_state: st.session_state.selected_answer = None
if 'trigger_balloons' not in st.session_state: st.session_state.trigger_balloons = False
if 'welcome_played' not in st.session_state: st.session_state.welcome_played = False
if 'exam_state' not in st.session_state: st.session_state.exam_state = {}
if 'dark_mode' not in st.session_state: st.session_state.dark_mode = False
if 'selected_categories' not in st.session_state: 
    st.session_state.selected_categories = ["Gevaarherkenning", "Kennis", "Inzicht"]
if 'voice_question' not in st.session_state: st.session_state.voice_question = "Fenna (Vrouw - Standaard)"
if 'voice_feedback' not in st.session_state: st.session_state.voice_feedback = "Maarten (Man - Papa)"
if 'practice_ids' not in st.session_state: st.session_state.practice_ids = []

# ----------------------------------------------------------------------
# 6️⃣ UI & CSS
# ----------------------------------------------------------------------

def inject_custom_css():
    dark = st.session_state.dark_mode
    bg_color = "#000000" if dark else "#fafafa"
    text_color = "#ffffff" if dark else "#262626"
    card_bg = "#121212" if dark else "#ffffff"
    card_border = "#363636" if dark else "#dbdbdb"
    btn_bg = "#262626" if dark else "#ffffff"
    btn_hover = "#333333" if dark else "#f0f0f0"
    
    st.markdown(f"""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>
.stApp {{ background-color: {bg_color}; font-family: 'Roboto', sans-serif; }}
#MainMenu, footer, header {{display: none !important;}}
.block-container {{ max-width: 600px !important; padding-top: 1rem !important; padding-left: 10px !important; padding-right: 10px !important; margin: 0 auto !important; }}
.insta-card {{ background: {card_bg}; border: 1px solid {card_border}; border-radius: 8px; margin-bottom: 12px; overflow: hidden; width: 100%; box-sizing: border-box; }}
.card-header {{ display: flex; align-items: center; padding: 14px; border-bottom: 1px solid {card_border}; }}
.avatar-small {{ width: 32px; height: 32px; border-radius: 50%; margin-right: 10px; background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888); padding: 2px; }}
.avatar-small img {{ border-radius: 50%; border: 2px solid {card_bg}; width: 100%; height: 100%; object-fit: cover; }}
.question-content {{ font-size: 22px !important; font-weight: 700 !important; color: {text_color} !important; margin-bottom: 10px; line-height: 1.4; display: block !important; opacity: 1 !important; text-align: left; }}
.question-label {{ font-size: 12px !important; color: #8e8e8e; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; display: block !important; }}
h1, h2, h3, p, label, span, div {{ color: {text_color}; }}
div.stButton {{ width: 100% !important; padding: 0 !important; }}
div.stButton > button {{ width: 100% !important; display: block !important; border-radius: 8px !important; background: {btn_bg} !important; border: 1px solid {card_border} !important; color: {text_color} !important; font-weight: 600 !important; padding: 16px 0px !important; margin-bottom: 8px !important; text-align: center !important; font-size: 16px !important; min-height: 54px !important; white-space: normal !important; box-shadow: none !important; transition: all 0.1s !important; }}
div.stButton > button:hover {{ background: {btn_hover} !important; border-color: #a8a8a8 !important; }}
div.stButton > button:active {{ transform: scale(0.98); background: #efefef !important; }}
.primary-btn > button {{ background: #0095f6 !important; color: white !important; border: none !important; }}
.primary-btn > button:hover {{ background: #0081d6 !important; }}
.profile-container {{ display: flex; padding: 20px 20px 0 20px; align-items: center; }}
.profile-pic-ring {{ width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888); padding: 2px; margin-right: 20px; flex-shrink: 0; }}
.profile-pic-img {{ width: 100%; height: 100%; border-radius: 50%; border: 3px solid {card_bg}; background: {btn_bg}; }}
.profile-stats {{ display: flex; justify-content: space-around; flex-grow: 1; text-align: center; }}
.stat-val {{ font-weight: 700; font-size: 18px; color: {text_color}; display: block; }}
.stat-lbl {{ font-size: 14px; color: {text_color}; }}
.profile-bio {{ padding: 10px 20px 20px 20px; font-size: 14px; color: {text_color}; line-height: 1.4; }}
.bio-name {{ font-weight: 700; }}
.highlights-scroll {{ display: flex; gap: 15px; padding: 0 20px 10px 20px; overflow-x: auto; scrollbar-width: none; }}
.highlight-item {{ text-align: center; width: 64px; flex-shrink: 0; }}
.highlight-circle {{ width: 62px; height: 62px; border-radius: 50%; border: 1px solid {card_border}; display: flex; align-items: center; justify-content: center; font-size: 24px; background: {btn_bg}; margin: 0 auto 5px auto; }}
.highlight-title {{ font-size: 12px; color: {text_color}; text-align: center; }}
.app-header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid {card_border}; background: {card_bg}; margin-bottom: 10px; }}
.logo-font {{ font-family: 'Grand Hotel', cursive; font-size: 28px; color: {text_color}; text-align: center; }}
.reward-overlay {{ text-align: center; margin: 20px 0; padding: 15px; background: {btn_bg}; border-radius: 8px; border: 2px solid #e1306c; animation: bounceIn 0.8s; }}
@keyframes bounceIn {{ 0% {{transform: scale(0.3);}} 50% {{transform: scale(1.05);}} 100% {{transform: scale(1);}} }}
.stExpander p, .stExpander label, .stExpander span, .stExpander div {{ color: {text_color} !important; }}
div[data-baseweb="select"] span {{ color: {text_color} !important; }}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 7️⃣ SCHERMEN
# ----------------------------------------------------------------------

def render_navbar():
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1:
        if st.button("🏠", key="nav_home"): 
            st.session_state.mode = 'dashboard'; st.session_state.answered_question = False; st.rerun()
    with c2: st.markdown(f"<div class='logo-font'>Eva's Theorie</div>", unsafe_allow_html=True)
    with c3:
        icon = "☀️" if st.session_state.dark_mode else "🌙"
        if st.button(icon, key="dark_toggle"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

def screen_dashboard():
    if st.session_state.trigger_balloons: st.session_state.trigger_balloons = False
    data = st.session_state.user_data
    
    # Geen inspringing in HTML string
    st.markdown(f"""
<div class="insta-card">
<div class="profile-container">
<div class="profile-pic-ring">
<img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Eva" class="profile-pic-img">
</div>
<div class="profile-stats">
<div><span class="stat-val">{data['total_score']}</span><span class="stat-lbl">posts</span></div>
<div><span class="stat-val">{st.session_state.streak}</span><span class="stat-lbl">volgers</span></div>
<div><span class="stat-val">{len([e for e in data['exams_history'] if e['passed']])}</span><span class="stat-lbl">volgend</span></div>
</div>
</div>
<div class="profile-bio">
<span style="font-weight:700;">Eefje 🚘</span><br>
Road to License ✨<br>
<i>"Niet als een frikandel rijden!"</i> - Papa<br>
<a href="#" style="color:#00376b; text-decoration:none;">www.cbr.nl</a>
</div>
</div>
""", unsafe_allow_html=True)
    
    # App Installatie Instructies (PWA)
    with st.expander("📲 Zet op je telefoon (App)"):
        st.markdown("""
        **iPhone (iOS):**
        1. Tik op de **Deel-knop** (vierkantje met pijl) onderin Safari.
        2. Scroll naar beneden en tik op **'Zet op beginscherm'**.
        3. Klik op **'Voeg toe'**.
        
        **Android:**
        1. Tik op de **3 puntjes** rechtsboven in Chrome.
        2. Tik op **'App installeren'** of **'Toevoegen aan startscherm'**.
        """)

    st.markdown("""
<div class="highlights-scroll">
<div class="highlight-item"><div class="highlight-circle">⚠️</div><div class="highlight-title">Gevaar</div></div>
<div class="highlight-item"><div class="highlight-circle">📚</div><div class="highlight-title">Kennis</div></div>
<div class="highlight-item"><div class="highlight-circle">🧠</div><div class="highlight-title">Inzicht</div></div>
<div class="highlight-item"><div class="highlight-circle">🏆</div><div class="highlight-title">Wins</div></div>
</div>
""", unsafe_allow_html=True)

    st.write("---") 
    st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
    if st.button("Start Oefenen"):
        df = load_data()
        valid_cats = st.session_state.get('selected_categories', ["Gevaarherkenning", "Kennis", "Inzicht"])
        mask = df['category'].apply(lambda x: any(c in str(x) for c in valid_cats))
        filtered_df = df[mask]
        if not filtered_df.empty:
            ids = filtered_df['id'].tolist()
            random.shuffle(ids)
            st.session_state.practice_ids = ids
            st.session_state.mode = 'practice'
            st.session_state.current_index = 0
            st.session_state.answered_question = False
            st.rerun()
        else:
            st.error("Geen vragen gevonden!")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Foutenbak Herkans"):
        st.session_state.mode = 'mistakes'; st.session_state.current_index = 0; st.session_state.answered_question = False; st.rerun()

    if st.button("Examen Simulatie"): st.session_state.mode = 'exam_init'; st.rerun()

    share_text = urllib.parse.quote(f"Hoi Papa! Ik heb al {data['total_score']} punten gehaald! 🚗💨")
    st.link_button("📱 Deel Score via WhatsApp", f"https://wa.me/?text={share_text}")

    with st.expander("⚙️ Instellingen"):
        st.caption("Geluid")
        st.session_state.music_volume = st.slider("Volume", 0.0, 1.0, 0.3)
        st.caption("Mix & Match Oefenen")
        cats = ["Gevaarherkenning", "Kennis", "Inzicht"]
        st.session_state.selected_categories = st.multiselect("Selecteer categorieën:", cats, default=st.session_state.selected_categories)
        st.caption("Stemmen")
        st.session_state.voice_question = st.selectbox("Vraag stem:", list(VOICE_OPTIONS.keys()), index=0)
        st.session_state.voice_feedback = st.selectbox("Feedback stem:", list(VOICE_OPTIONS.keys()), index=1)

    if not st.session_state.welcome_played:
        with st.empty():
            # Height 70 zorgt dat de knop zichtbaar is
            components.html(get_audio_player_html(generate_audio_file("Ha Eefje. Klaar om te knallen?", st.session_state.voice_question)), height=70)
        st.session_state.welcome_played = True
    else:
        with st.empty():
            components.html(get_audio_player_html(None), height=0)

def screen_practice(df):
    if st.session_state.trigger_balloons: st.balloons(); st.session_state.trigger_balloons = False
    is_mistakes = (st.session_state.mode == 'mistakes')
    
    if is_mistakes:
        q_ids = st.session_state.user_data['mistakes_list']
        valid_q_ids = [qid for qid in q_ids if not df[df['id'] == str(qid)].empty]
        if not valid_q_ids: 
            st.success("Foutenbak leeg! 🎉"); st.button("Terug", on_click=lambda: setattr(st.session_state, 'mode', 'dashboard')); return
        if st.session_state.current_index >= len(valid_q_ids): st.session_state.current_index = 0
        current_id = valid_q_ids[st.session_state.current_index]
    else:
        if 'practice_ids' not in st.session_state or not st.session_state.practice_ids:
             st.warning("Geen vragen geladen."); st.button("Terug", on_click=lambda: setattr(st.session_state, 'mode', 'dashboard')); return
        if st.session_state.current_index >= len(st.session_state.practice_ids): 
            st.balloons(); st.success("Klaar!"); st.button("Terug", on_click=lambda: setattr(st.session_state, 'mode', 'dashboard')); return
        current_id = st.session_state.practice_ids[st.session_state.current_index]

    row = df[df['id'] == str(current_id)].iloc[0]
    img_prompt = urllib.parse.quote(row.get('image_desc', 'traffic situation car netherlands'))
    ai_img_url = f"https://image.pollinations.ai/prompt/driver%20view%20inside%20car%20{img_prompt}?width=600&height=400&nologo=true"
    card_bg = '#121212' if st.session_state.dark_mode else '#ffffff'
    text_c = '#ffffff' if st.session_state.dark_mode else '#262626'

    # Geen inspringing om code-blokken te voorkomen!
    st.markdown(f"""
<div class="insta-card">
<div class="card-header">
<div class="avatar-small"><img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Papa"></div>
<div style="font-weight:600; font-size:14px; color:{text_c};">Papa & Fenna</div>
<div style="margin-left:auto; color:#8e8e8e; font-size:12px;">{row['category']}</div>
</div>
<img src="{ai_img_url}" style="width:100%; display:block; min-height:200px; background-color: #eee;">
<div style="padding:16px;">
<div style="margin-bottom:8px;">
<i class="far fa-heart" style="font-size:24px; margin-right:16px;"></i>
<i class="far fa-comment" style="font-size:24px; margin-right:16px;"></i>
<i class="far fa-paper-plane" style="font-size:24px;"></i>
</div>
<div class="question-content">{row['question']}</div>
</div>
</div>
""", unsafe_allow_html=True)

    audio_slot = st.empty()

    if not st.session_state.answered_question:
        with audio_slot:
            audio_data_b64 = generate_audio_file(make_question_audio(row), st.session_state.voice_question)
            components.html(get_audio_player_html(audio_data_b64), height=70)
            if audio_data_b64:
                st.audio(base64.b64decode(audio_data_b64), format='audio/mp3')

        for opt in [row['opt1'], row['opt2'], row['opt3']]:
            if str(opt).lower() != 'nan':
                if st.button(str(opt), key=f"btn_{current_id}_{opt}"):
                    st.session_state.answered_question = True
                    st.session_state.selected_answer = str(opt)
                    data = st.session_state.user_data
                    if str(opt) == str(row['answer']):
                        data['total_score'] += 1; st.session_state.streak += 1; st.session_state.trigger_balloons = True
                        if is_mistakes and str(current_id) in data['mistakes_list']: data['mistakes_list'].remove(str(current_id))
                    else:
                        st.session_state.streak = 0
                        if str(current_id) not in data['mistakes_list']: data['mistakes_list'].append(str(current_id))
                    save_history(data); st.rerun()
    else:
        is_correct = (st.session_state.selected_answer == str(row['answer']))
        fb_txt = get_dad_feedback(is_correct, row['explanation'])
        with audio_slot:
            audio_fb_b64 = generate_audio_file(fb_txt, st.session_state.voice_feedback)
            components.html(get_audio_player_html(audio_fb_b64), height=70)
            if audio_fb_b64:
                st.audio(base64.b64decode(audio_fb_b64), format='audio/mp3')

        if is_correct:
            st.success(f"✅ {fb_txt}")
            if st.session_state.streak > 0 and st.session_state.streak % 5 == 0:
                st.markdown(f"<div class='reward-overlay'><h2>🔥 5 OP EEN RIJ!</h2><img src='{random.choice(REWARD_GIFS)}' width='100%'></div>", unsafe_allow_html=True)
        else:
            st.error(f"❌ {fb_txt}"); st.info(f"Antwoord: {row['answer']}")
        st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
        if st.button("Volgende ➡️"):
            st.session_state.answered_question = False
            if not is_mistakes or not is_correct: st.session_state.current_index += 1
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def init_exam(df):
    q_pool = random.sample(df['id'].tolist(), min(len(df), 25))
    st.session_state.exam_state = {"ids": q_pool, "answers": {}, "idx": 0}
    st.session_state.mode = 'exam_active'; st.rerun()

def screen_exam(df):
    est = st.session_state.exam_state
    if est['idx'] >= len(est['ids']): st.session_state.mode = 'exam_result'; st.rerun(); return
    qid = est['ids'][est['idx']]
    row = df[df['id'] == str(qid)].iloc[0]
    
    st.markdown(f"**Examen Vraag {est['idx']+1}/{len(est['ids'])}**")
    st.progress(est['idx'] / len(est['ids']))
    img_prompt = urllib.parse.quote(row.get('image_desc', 'traffic situation car netherlands'))
    ai_img_url = f"https://image.pollinations.ai/prompt/driver%20view%20inside%20car%20{img_prompt}?width=600&height=400&nologo=true"
    st.image(ai_img_url, use_container_width=True)
    
    st.markdown(f"<div class='question-content'>{row['question']}</div>", unsafe_allow_html=True)
    
    with st.empty():
        audio_ex_b64 = generate_audio_file(clean_text_for_speech(row['question']), st.session_state.voice_question)
        components.html(get_audio_player_html(audio_ex_b64), height=70)
        if audio_ex_b64:
            st.audio(base64.b64decode(audio_ex_b64), format='audio/mp3')

    for opt in [row['opt1'], row['opt2'], row['opt3']]:
        if str(opt).lower() != 'nan':
            if st.button(str(opt), key=f"ex_{qid}_{opt}"):
                st.session_state.exam_state['answers'][qid] = (str(opt) == str(row['answer']))
                st.session_state.exam_state['idx'] += 1
                st.rerun()

def screen_exam_result(df):
    ans = st.session_state.exam_state['answers']
    score = sum(1 for v in ans.values() if v)
    passed = score >= EXAM_PASS_SCORE
    if 'last_exam_saved' not in st.session_state or st.session_state.last_exam_saved != len(ans):
        st.session_state.user_data['exams_history'].append({"date": datetime.now().strftime("%d-%m"), "score": f"{score}/{len(ans)}", "passed": passed})
        save_history(st.session_state.user_data); st.session_state.last_exam_saved = len(ans)

    st.markdown(f"<div class='insta-card' style='text-align:center; padding:30px;'><h1 style='color:{'green' if passed else 'red'}'>{'GESLAAGD! 🎓' if passed else 'GEZAKT 🛑'}</h1><h3>Score: {score}/{len(ans)}</h3></div>", unsafe_allow_html=True)
    if passed: st.balloons()
    
    msg = urllib.parse.quote(f"Ik ben {'GESLAAGD' if passed else 'gezakt'}! Score: {score}/{len(ans)} 🚗")
    st.link_button("📱 Deel uitslag", f"https://wa.me/?text={msg}")
    if st.button("Terug"): st.session_state.mode = 'dashboard'; st.rerun()

def screen_panic():
    st.markdown("<h2 style='text-align:center;'>Adem in... Adem uit... 🌿</h2>", unsafe_allow_html=True)
    st.markdown("""<div style="display:flex; justify-content:center; align-items:center; height:200px;"><div style="width:150px; height:150px; background:#a5d6a7; border-radius:50%; animation:breathe 8s infinite ease-in-out;"></div></div><style>@keyframes breathe {0%, 100% {transform:scale(1);} 50% {transform:scale(1.5);}}</style>""", unsafe_allow_html=True)
    with st.empty():
        components.html(get_audio_player_html(None), height=0)
    if st.button("Ik ben weer rustig"): st.session_state.mode = 'dashboard'; st.rerun()

def main():
    inject_custom_css()
    df = load_data()
    if df.empty: st.error("❌ 'vragen.csv' niet gevonden!"); return
    render_navbar()
    if st.session_state.mode == 'dashboard': screen_dashboard()
    elif st.session_state.mode == 'practice': screen_practice(df)
    elif st.session_state.mode == 'mistakes': screen_practice(df)
    elif st.session_state.mode == 'exam_init': init_exam(df)
    elif st.session_state.mode == 'exam_active': screen_exam(df)
    elif st.session_state.mode == 'exam_result': screen_exam_result(df)
    elif st.session_state.mode == 'panic': screen_panic()

if __name__ == "__main__":
    main()
