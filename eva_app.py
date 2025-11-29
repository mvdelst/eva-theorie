#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
📜 EVA'S THEORIE APP (V66 - SESSIES & BELONINGEN)
-----------------------------------------------------
Nieuw in V66:
- SESSIE LENGTE: Kies vooraf hoeveel vragen je wilt doen (5, 10, 20 of Alles).
- VOORTGANG: Een balkje laat zien hoe ver je bent in je sessie.
- BELONINGEN: Werken nog steeds! Bij elke 5 goede antwoorden op rij (streak) komt er een GIF.
- EINDSCORE: Na de sessie zie je direct je resultaat.

Gebruik:
Start via terminal: streamlit run eva_app.py
"""

import streamlit as st
import pandas as pd
import random
import time
import os
import json
import tempfile
import re
import urllib.parse
from datetime import datetime

# --- LIBRARY SETUP ---
try:
    from gtts import gTTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# ----------------------------------------------------------------------
# 1️⃣ CONFIGURATIE
# ----------------------------------------------------------------------

st.set_page_config(
    page_title="Eva's Theorie 🚗",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CONSTANTEN ---
HISTORY_FILE = "progress.json"
APP_VERSION = "V66 (Sessies & Beloningen)"
EXAM_PASS_SCORE = 18

REWARD_GIFS = [
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif", 
    "https://media.giphy.com/media/nNxT5qXR02FOM/giphy.gif",     
    "https://media.giphy.com/media/artj9zsVs8MFy/giphy.gif",     
    "https://media.giphy.com/media/3oz8xAFtqoOUUrsh7W/giphy.gif", 
    "https://media.giphy.com/media/Is1O1TWV0LEJi/giphy.gif",      
    "https://media.giphy.com/media/d31w24pskko8663a/giphy.gif"    
]

# ----------------------------------------------------------------------
# 2️⃣ TEKST LOGICA
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
# 3️⃣ AUDIO ENGINE (GOOGLE TTS)
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
def generate_audio_bytes(text):
    if not TTS_AVAILABLE: return None
    if not text: return None
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        output_file = f.name
    
    try:
        tts = gTTS(text=text, lang='nl')
        tts.save(output_file)
        if os.path.exists(output_file):
            with open(output_file, "rb") as f: data = f.read()
            os.remove(output_file)
            return data
    except:
        if os.path.exists(output_file): os.remove(output_file)
        return None
    return None

# ----------------------------------------------------------------------
# 4️⃣ OPSLAG & STATE
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

# Init Session State
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

# Nieuwe variabelen voor sessie beheer
if 'session_limit_setting' not in st.session_state: st.session_state.session_limit_setting = "10"
if 'current_session_score' not in st.session_state: st.session_state.current_session_score = 0

# ----------------------------------------------------------------------
# 5️⃣ UI & CSS
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
# 6️⃣ SCHERMEN
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
    
    with st.expander("📲 Zet op je telefoon (App)"):
        st.markdown("""
        **iPhone (iOS):**
        1. Tik op de **Deel-knop** (vierkantje met pijl) onderin Safari.
        2. Scroll naar beneden en tik op **'Zet op beginscherm'**.
        
        **Android:**
        1. Tik op de **3 puntjes** rechtsboven in Chrome.
        2. Tik op **'App installeren'**.
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
    
    # --- SESSIE KIEZER ---
    st.caption("Hoeveel vragen wil je oefenen?")
    session_choice = st.select_slider("", options=["5", "10", "20", "Alles"], value=st.session_state.session_limit_setting)
    st.session_state.session_limit_setting = session_choice
    
    st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
    if st.button("Start Oefenen"):
        df = load_data()
        valid_cats = st.session_state.get('selected_categories', ["Gevaarherkenning", "Kennis", "Inzicht"])
        mask = df['category'].apply(lambda x: any(c in str(x) for c in valid_cats))
        filtered_df = df[mask]
        
        if not filtered_df.empty:
            ids = filtered_df['id'].tolist()
            random.shuffle(ids)
            
            # Limiet toepassen op de lijst met IDs
            if session_choice != "Alles":
                limit = int(session_choice)
                ids = ids[:limit]
            
            st.session_state.practice_ids = ids
            st.session_state.current_session_score = 0
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

    with st.expander("⚙️ Instellingen"):
        st.caption("Geluid")
        st.session_state.music_volume = st.slider("Volume", 0.0, 1.0, 0.3)
        st.caption("Mix & Match Oefenen")
        cats = ["Gevaarherkenning", "Kennis", "Inzicht"]
        st.session_state.selected_categories = st.multiselect("Selecteer categorieën:", cats, default=st.session_state.selected_categories)
        # Diagnosetest
        if st.button("🔊 Test Audio"):
             data = generate_audio_bytes("Test 1 2 3.")
             if data: st.audio(data, format="audio/mp3")
             else: st.error("Audio motor niet beschikbaar.")
    
    st.caption(f"App Versie: {APP_VERSION} | © 2025 Papa & Eva")

    if not st.session_state.welcome_played:
        welkom_text = "Ha Eefje. Klaar om te knallen?"
        audio_welkom = generate_audio_bytes(welkom_text)
        if audio_welkom:
            st.audio(audio_welkom, format='audio/mp3', start_time=0, autoplay=True)
        st.session_state.welcome_played = True

def screen_practice(df):
    if st.session_state.trigger_balloons: st.balloons(); st.session_state.trigger_balloons = False
    is_mistakes = (st.session_state.mode == 'mistakes')
    
    # ID Lijst ophalen
    if is_mistakes:
        q_ids = st.session_state.user_data['mistakes_list']
        # Filter ongeldige IDs eruit
        valid_q_ids = [qid for qid in q_ids if not df[df['id'] == str(qid)].empty]
        if not valid_q_ids: 
            st.success("Foutenbak leeg! 🎉"); st.button("Terug", on_click=lambda: setattr(st.session_state, 'mode', 'dashboard')); return
        practice_list = valid_q_ids
    else:
        practice_list = st.session_state.practice_ids

    # Check of we klaar zijn
    if st.session_state.current_index >= len(practice_list):
        # Sessie is klaar, toon resultaat
        screen_session_done(len(practice_list))
        return

    current_id = practice_list[st.session_state.current_index]
    row = df[df['id'] == str(current_id)].iloc[0]
    
    # Voortgangsbalk en teller
    total_q = len(practice_list)
    curr_q = st.session_state.current_index + 1
    progress = curr_q / total_q
    
    st.markdown(f"**Vraag {curr_q} van {total_q}**")
    st.progress(progress)

    img_prompt = urllib.parse.quote(row.get('image_desc', 'traffic situation car netherlands'))
    ai_img_url = f"https://image.pollinations.ai/prompt/driver%20view%20inside%20car%20{img_prompt}?width=600&height=400&nologo=true"
    card_bg = '#121212' if st.session_state.dark_mode else '#ffffff'
    text_c = '#ffffff' if st.session_state.dark_mode else '#262626'

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
            audio_bytes = generate_audio_bytes(make_question_audio(row))
            if audio_bytes:
                st.audio(audio_bytes, format='audio/mp3', start_time=0, autoplay=True)

        for opt in [row['opt1'], row['opt2'], row['opt3']]:
            if str(opt).lower() != 'nan':
                if st.button(str(opt), key=f"btn_{current_id}_{opt}"):
                    st.session_state.answered_question = True
                    st.session_state.selected_answer = str(opt)
                    data = st.session_state.user_data
                    
                    if str(opt) == str(row['answer']):
                        # GOED ANTWOORD
                        data['total_score'] += 1
                        st.session_state.streak += 1
                        st.session_state.current_session_score += 1
                        st.session_state.trigger_balloons = True
                        if is_mistakes and str(current_id) in data['mistakes_list']: 
                            data['mistakes_list'].remove(str(current_id))
                    else:
                        # FOUT ANTWOORD
                        st.session_state.streak = 0
                        if str(current_id) not in data['mistakes_list']: 
                            data['mistakes_list'].append(str(current_id))
                    
                    save_history(data)
                    st.rerun()
    else:
        is_correct = (st.session_state.selected_answer == str(row['answer']))
        fb_txt = get_dad_feedback(is_correct, row['explanation'])
        with audio_slot:
            audio_fb_bytes = generate_audio_bytes(fb_txt)
            if audio_fb_bytes:
                st.audio(audio_fb_bytes, format='audio/mp3', start_time=0, autoplay=True)

        if is_correct:
            st.success(f"✅ {fb_txt}")
            # --- BELONING SYSTEEM ---
            if st.session_state.streak > 0 and st.session_state.streak % 5 == 0:
                st.markdown(f"<div class='reward-overlay'><h2>🔥 {st.session_state.streak} OP EEN RIJ!</h2><img src='{random.choice(REWARD_GIFS)}' width='100%'></div>", unsafe_allow_html=True)
                st.balloons()
        else:
            st.error(f"❌ {fb_txt}"); st.info(f"Antwoord: {row['answer']}")
        
        st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
        if st.button("Volgende ➡️"):
            st.session_state.answered_question = False
            # Als we in de foutenbak modus zitten en het was goed, is de vraag nu weg uit de lijst
            # Dus we hoeven de index niet te verhogen als de lijst korter is geworden
            # Tenzij het antwoord fout was, dan blijft hij staan.
            # Simpelste logica: Altijd volgende index in gewone modus.
            if not is_mistakes:
                st.session_state.current_index += 1
            else:
                # In foutenbak: als goed, is item weg, dus index wijst al naar volgende.
                # Als fout, item blijft, dus index verhogen om volgende te pakken.
                if not is_correct:
                    st.session_state.current_index += 1
                    
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def screen_session_done(total_questions):
    score = st.session_state.current_session_score
    st.markdown(f"""
    <div class="insta-card" style="text-align:center; padding: 40px;">
        <h1>Sessie Klaar! 🎉</h1>
        <h3>Je score: {score} van de {total_questions}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    if score == total_questions:
        st.balloons()
        st.success("Foutloos! Wat een baas. 🏆")
    elif score > total_questions / 2:
        st.info("Lekker bezig! Op naar de 100%.")
    else:
        st.warning("Oefening baart kunst. Nog een keertje?")

    st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
    if st.button("Terug naar Dashboard"):
        st.session_state.mode = 'dashboard'
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
        audio_ex_bytes = generate_audio_bytes(clean_text_for_speech(row['question']))
        if audio_ex_bytes:
            st.audio(audio_ex_bytes, format='audio/mp3', start_time=0, autoplay=True)

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
