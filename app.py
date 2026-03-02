import streamlit as st
from groq import Groq
import json, re, datetime, sqlite3, os, time
import streamlit.components.v1 as components

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="StudyMate AI — Powered by AMD",
    layout="wide",
    page_icon="🎓"
)

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=GROQ_API_KEY)

# FIX 7 — Expanded subject detection with more keywords
SUBJECT_TAGS = {
    "Math": [
        "algebra","calculus","trigonometry","geometry","statistics","probability",
        "matrices","vectors","arithmetic","number theory","differentiation",
        "integration","logarithm","quadratic","polynomial","equation","set theory",
        "combinatorics","permutation","sequence","series","complex number"
    ],
    "Science": [
        "physics","chemistry","biology","photosynthesis","genetics","evolution",
        "thermodynamics","quantum","organic","inorganic","cell","atom","molecule",
        "force","motion","gravity","electricity","magnetism","optics","waves",
        "nuclear","reaction","periodic table","enzyme","dna","protein","ecosystem",
        "chemical","biochemistry","anatomy","botany","zoology","microbiology"
    ],
    "History": [
        "war","revolution","empire","civilization","ancient","medieval","colonial",
        "world war","independence","dynasty","kingdom","republic","democracy",
        "french","american","industrial","renaissance","reformation","crusades",
        "ottoman","mughal","british","roman","greek","egyptian","chinese history"
    ],
    "Technology": [
        "programming","algorithm","machine learning","artificial intelligence","neural",
        "database","networking","cybersecurity","software","hardware","operating system",
        "data structure","cloud","devops","blockchain","cryptography","computer",
        "python","javascript","java","coding","web development","api","deep learning",
        "natural language","computer vision","robotics","iot","semiconductor"
    ],
    "Economics": [
        "supply","demand","inflation","gdp","microeconomics","macroeconomics",
        "market","fiscal","monetary","trade","investment","stock","bond","finance",
        "banking","currency","recession","capitalism","socialism","budget","tax",
        "unemployment","interest rate","opportunity cost","elasticity"
    ],
    "Literature": [
        "poetry","novel","shakespeare","metaphor","grammar","syntax","narrative",
        "prose","rhetoric","essay","fiction","drama","tragedy","comedy","sonnet",
        "symbolism","theme","character","plot","setting","genre","literary"
    ],
    "Geography": [
        "continent","ocean","climate","biome","tectonic","erosion","latitude",
        "longitude","map","country","capital","mountain","river","desert","rainforest",
        "population","migration","urbanization","geopolitics"
    ],
    "Philosophy": [
        "ethics","logic","epistemology","metaphysics","ontology","socrates","plato",
        "aristotle","kant","nietzsche","existentialism","utilitarianism","morality",
        "consciousness","free will","determinism","empiricism","rationalism"
    ],
}

DB_PATH = "study_assistant.db"

# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS study_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT, topic TEXT, subject TEXT, difficulty TEXT,
        score INTEGER, total INTEGER, accuracy INTEGER, studied_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS streak_log (
        username TEXT, date TEXT, PRIMARY KEY (username, date))""")
    conn.commit(); conn.close()

def db_get_or_create_user(username):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?)",
              (username, datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()

def db_save_result(username, topic, subject, difficulty, score, total):
    accuracy = round(score / total * 100)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""INSERT INTO study_history
        (username,topic,subject,difficulty,score,total,accuracy,studied_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (username, topic, subject, difficulty, score, total, accuracy,
         datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()

def db_record_streak(username):
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO streak_log VALUES (?,?)", (username, today))
    conn.commit(); conn.close()

def db_get_history(username):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""SELECT topic,subject,difficulty,score,total,accuracy,studied_at
        FROM study_history WHERE username=? ORDER BY studied_at DESC""", (username,))
    rows = c.fetchall(); conn.close()
    return [{"topic":r[0],"subject":r[1],"difficulty":r[2],"score":r[3],
             "total":r[4],"accuracy":r[5],"date":r[6][:16].replace("T"," ")} for r in rows]

def db_get_streak(username):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT date FROM streak_log WHERE username=? ORDER BY date DESC", (username,))
    dates = [r[0] for r in c.fetchall()]; conn.close()
    streak = 0; check = datetime.date.today()
    for d in dates:
        if datetime.date.fromisoformat(d) == check:
            streak += 1; check -= datetime.timedelta(days=1)
        else: break
    return streak

def db_get_stats(username):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT topic),COUNT(*),AVG(accuracy) FROM study_history WHERE username=?", (username,))
    row = c.fetchone(); conn.close()
    return {"topics": row[0] or 0, "quizzes": row[1] or 0, "avg_acc": round(row[2] or 0)}

def db_get_weak_areas(username):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""SELECT topic,difficulty,AVG(accuracy) as avg_acc
        FROM study_history WHERE username=?
        GROUP BY topic HAVING avg_acc < 60 ORDER BY avg_acc ASC LIMIT 5""", (username,))
    rows = c.fetchall(); conn.close()
    return [{"topic":r[0],"difficulty":r[1],"accuracy":round(r[2])} for r in rows]

def db_get_chart_data(username):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""SELECT topic,accuracy,studied_at FROM study_history
        WHERE username=? ORDER BY studied_at ASC LIMIT 20""", (username,))
    rows = c.fetchall(); conn.close()
    return rows

def detect_subject(topic):
    t = topic.lower()
    for subj, keywords in SUBJECT_TAGS.items():
        if any(k in t for k in keywords):
            return subj
    return "General"

init_db()

# ─────────────────────────────────────────────
#  FIX 4 — API CALL WRAPPER WITH RETRY
# ─────────────────────────────────────────────
def safe_api_call(messages, temperature=0.7, max_tokens=1000, retries=3):
    """Wraps Groq API calls with retry logic and user-friendly error handling."""
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return resp.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "rate_limit" in err or "429" in err:
                if attempt < retries - 1:
                    wait = 5 * (attempt + 1)
                    st.warning(f"⏳ API rate limit hit — retrying in {wait}s... (attempt {attempt+1}/{retries})")
                    time.sleep(wait)
                else:
                    st.error("🚫 API rate limit reached. Please wait a moment and try again.")
                    return None
            elif "timeout" in err or "connection" in err:
                if attempt < retries - 1:
                    st.warning(f"🌐 Connection issue — retrying... (attempt {attempt+1}/{retries})")
                    time.sleep(3)
                else:
                    st.error("🌐 Connection failed. Please check your internet and try again.")
                    return None
            else:
                st.error(f"❌ Unexpected error: {str(e)[:120]}. Please try again.")
                return None
    return None

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def scroll_to_top():
    components.html(
        "<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>",
        height=0
    )

def reset_for_new_topic():
    for k in ["explanation","quiz","user_answers","submitted","score",
              "recommendations","explanations","topic","difficulty","confirm_new"]:
        if k in st.session_state:
            del st.session_state[k]

def go_to_topic(topic):
    reset_for_new_topic()
    st.session_state.topic = topic
    st.session_state.phase = "input"
    scroll_to_top()
    st.rerun()

# ─────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Sora',sans-serif;}

.stApp{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);min-height:100vh;}

h1{font-size:2.6rem!important;font-weight:700!important;
   background:linear-gradient(90deg,#a78bfa,#60a5fa,#34d399);
   -webkit-background-clip:text;-webkit-text-fill-color:transparent;
   text-align:center;margin-bottom:0.2rem!important;}
h2,h3{color:#e2e8f0!important;font-weight:600!important;}

/* FIX 8 — polished login card */
.login-box{
  background:rgba(255,255,255,0.05);
  border:1px solid rgba(167,139,250,0.35);
  border-radius:20px; padding:36px 40px;
  box-shadow:0 8px 40px rgba(124,58,237,0.25);
}
.login-logo{font-size:3rem;text-align:center;margin-bottom:8px;}
.login-title{background:linear-gradient(90deg,#a78bfa,#60a5fa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  font-size:1.6rem;font-weight:700;text-align:center;margin-bottom:4px;}
.login-sub{color:#64748b;font-size:0.88rem;text-align:center;margin-bottom:24px;}
.login-features{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-bottom:24px;}
.login-feat{background:rgba(167,139,250,0.1);border:1px solid rgba(167,139,250,0.25);
  border-radius:999px;padding:4px 14px;color:#a78bfa;font-size:0.8rem;font-weight:600;}

/* AMD badge */
.amd-badge{
  background:linear-gradient(135deg,#ED1C24,#FF6B35);
  border-radius:10px;padding:10px 16px;
  display:flex;align-items:center;gap:10px;
  margin-bottom:16px;
}
.amd-badge-text{color:white;font-size:0.82rem;font-weight:600;line-height:1.4;}
.amd-badge-title{font-size:1rem;font-weight:700;}

/* cards */
.quiz-card{background:rgba(255,255,255,0.05);border-left:4px solid #a78bfa;
  border-radius:12px;padding:18px 22px;margin-bottom:18px;color:#e2e8f0;}
.score-badge{background:linear-gradient(135deg,#6d28d9,#2563eb);border-radius:16px;
  padding:24px;text-align:center;color:white;font-size:1.8rem;font-weight:700;
  margin:20px 0;box-shadow:0 8px 32px rgba(109,40,217,0.4);}
.answer-correct{color:#34d399;font-weight:600;}
.answer-wrong{color:#f87171;font-weight:600;}
.fancy-divider{height:2px;background:linear-gradient(90deg,transparent,#a78bfa,transparent);
  margin:32px 0;border:none;}

/* inputs */
.stTextInput>div>div>input,.stSelectbox>div>div{
  background:rgba(255,255,255,0.07)!important;
  border:1px solid rgba(167,139,250,0.3)!important;
  border-radius:10px!important;color:#e2e8f0!important;}

/* buttons */
.stButton>button{background:linear-gradient(135deg,#7c3aed,#2563eb)!important;
  color:white!important;border:none!important;border-radius:10px!important;
  padding:0.55rem 1.6rem!important;font-family:'Sora',sans-serif!important;
  font-weight:600!important;font-size:0.95rem!important;
  transition:all 0.2s ease!important;box-shadow:0 4px 15px rgba(124,58,237,0.4)!important;}
.stButton>button:hover{transform:translateY(-2px)!important;
  box-shadow:0 6px 20px rgba(124,58,237,0.6)!important;}

.stRadio>label{color:#cbd5e1!important;}
.stAlert{border-radius:10px!important;}
.subtitle{text-align:center;color:#94a3b8;font-size:0.95rem;margin-bottom:32px;}

/* pills */
.phase-pill{display:inline-block;padding:4px 14px;border-radius:999px;
  font-size:0.75rem;font-weight:600;letter-spacing:0.05em;
  text-transform:uppercase;margin-bottom:16px;}
.phase-learn{background:rgba(52,211,153,0.15);color:#34d399;border:1px solid #34d399;}
.phase-quiz{background:rgba(167,139,250,0.15);color:#a78bfa;border:1px solid #a78bfa;}
.phase-done{background:rgba(251,191,36,0.15);color:#fbbf24;border:1px solid #fbbf24;}

.diff-easy{display:inline-block;padding:3px 12px;border-radius:999px;font-size:0.78rem;font-weight:700;
  background:rgba(52,211,153,0.15);color:#34d399;border:1px solid #34d399;}
.diff-medium{display:inline-block;padding:3px 12px;border-radius:999px;font-size:0.78rem;font-weight:700;
  background:rgba(251,191,36,0.15);color:#fbbf24;border:1px solid #fbbf24;}
.diff-hard{display:inline-block;padding:3px 12px;border-radius:999px;font-size:0.78rem;font-weight:700;
  background:rgba(248,113,113,0.15);color:#f87171;border:1px solid #f87171;}

.subj-tag{display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.72rem;font-weight:700;
  background:rgba(96,165,250,0.15);color:#60a5fa;border:1px solid #60a5fa;margin-left:6px;}

/* sidebar */
.hist-card{background:rgba(255,255,255,0.05);border:1px solid rgba(167,139,250,0.2);
  border-radius:10px;padding:10px 14px;margin-bottom:10px;}
.hist-topic{color:#e2e8f0;font-weight:600;font-size:0.9rem;}
.hist-meta{color:#64748b;font-size:0.75rem;margin-top:2px;}
.hist-score{color:#a78bfa;font-size:0.8rem;font-weight:600;}
.streak-badge{background:linear-gradient(135deg,#f59e0b,#ef4444);border-radius:12px;
  padding:14px 18px;text-align:center;color:white;margin-bottom:12px;}
.streak-num{font-size:2rem;font-weight:700;}
.streak-text{font-size:0.8rem;opacity:0.85;margin-top:2px;}
.weak-card{background:rgba(248,113,113,0.06);border:1px solid rgba(248,113,113,0.25);
  border-radius:12px;padding:14px 18px;margin-bottom:10px;}
.weak-title{color:#f87171;font-weight:600;font-size:0.88rem;}
.weak-detail{color:#94a3b8;font-size:0.8rem;margin-top:4px;}

/* accuracy */
.accuracy-wrap{background:rgba(255,255,255,0.05);border:1px solid rgba(167,139,250,0.2);
  border-radius:16px;padding:20px 28px;margin:16px 0 24px 0;
  display:flex;align-items:center;gap:24px;}
.accuracy-pct{font-size:2.8rem;font-weight:700;
  background:linear-gradient(90deg,#a78bfa,#60a5fa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;min-width:100px;}
.accuracy-bar-bg{flex:1;height:14px;background:rgba(255,255,255,0.08);
  border-radius:999px;overflow:hidden;}
.accuracy-bar-fill{height:100%;border-radius:999px;
  background:linear-gradient(90deg,#7c3aed,#60a5fa);transition:width 0.6s ease;}
.accuracy-label{color:#94a3b8;font-size:0.85rem;margin-top:4px;}

/* explanation */
.explanation-box{background:rgba(96,165,250,0.08);border:1px solid rgba(96,165,250,0.3);
  border-radius:10px;padding:14px 18px;margin-top:12px;color:#bfdbfe;
  font-size:0.9rem;line-height:1.7;}
.explanation-label{color:#60a5fa;font-weight:700;font-size:0.8rem;
  text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;}

/* recommendations */
.rec-card{background:rgba(255,255,255,0.04);border:1px solid rgba(167,139,250,0.25);
  border-radius:14px;padding:16px 20px;margin-bottom:12px;
  transition:border-color 0.2s,background 0.2s;}
.rec-card:hover{border-color:#a78bfa;background:rgba(167,139,250,0.08);}
.rec-title{color:#e2e8f0;font-weight:600;font-size:0.95rem;margin-bottom:4px;}
.rec-reason{color:#94a3b8;font-size:0.82rem;line-height:1.5;}
.rec-tag{display:inline-block;padding:2px 10px;border-radius:999px;
  font-size:0.72rem;font-weight:700;margin-top:8px;}
.rec-next{background:rgba(96,165,250,0.15);color:#60a5fa;border:1px solid #60a5fa;}

/* learning path */
.path-step{display:flex;align-items:flex-start;gap:14px;padding:12px 0;
  border-bottom:1px solid rgba(255,255,255,0.06);}
.path-num{min-width:30px;height:30px;border-radius:50%;
  background:linear-gradient(135deg,#7c3aed,#2563eb);
  color:white;font-weight:700;font-size:0.85rem;
  display:flex;align-items:center;justify-content:center;}
.path-info{flex:1;}
.path-topic{color:#e2e8f0;font-weight:600;font-size:0.9rem;}
.path-why{color:#64748b;font-size:0.8rem;margin-top:2px;}

/* share card */
.share-card{background:linear-gradient(135deg,rgba(124,58,237,0.2),rgba(37,99,235,0.2));
  border:1px solid rgba(167,139,250,0.4);border-radius:16px;padding:24px;
  text-align:center;margin:16px 0;}
.share-title{color:#e2e8f0;font-size:1.1rem;font-weight:700;margin-bottom:8px;}
.share-body{color:#94a3b8;font-size:0.9rem;line-height:1.6;}

/* confirm dialog */
.confirm-box{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.3);
  border-radius:12px;padding:16px 20px;margin:12px 0;}
.confirm-text{color:#fca5a5;font-size:0.9rem;margin-bottom:12px;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SESSION STATE DEFAULTS
# ─────────────────────────────────────────────
for key, default in [
    ("logged_in",       False),
    ("username",        ""),
    ("phase",           "input"),
    ("explanation",     ""),
    ("quiz",            None),
    ("user_answers",    {}),
    ("submitted",       False),
    ("score",           0),
    ("topic",           ""),
    ("difficulty",      "Medium"),
    ("subject",         "General"),
    ("recommendations", None),
    ("confirm_new",     False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Auto-login from URL query param on refresh ──
if not st.session_state.logged_in:
    params = st.query_params
    if "user" in params and params["user"].strip():
        saved_name = params["user"].strip()
        db_get_or_create_user(saved_name)
        st.session_state.username  = saved_name
        st.session_state.logged_in = True


# ══════════════════════════════════════════════
#  FIX 8 — POLISHED LOGIN SCREEN
# ══════════════════════════════════════════════
if not st.session_state.logged_in:

    st.markdown("<h1>🎓 StudyMate AI</h1>", unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Powered by AMD Instinct MI300X via Groq · Learn · Quiz · Improve</p>',
        unsafe_allow_html=True
    )

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div class="login-box">
          <div class="login-logo">🎓</div>
          <div class="login-title">Welcome to StudyMate AI</div>
          <div class="login-sub">Your personal AI tutor — type any topic, get a lesson, take a quiz.</div>
          <div class="login-features">
            <span class="login-feat">📖 AI Lessons</span>
            <span class="login-feat">🧠 20-Q Quiz</span>
            <span class="login-feat">💡 Smart Explanations</span>
            <span class="login-feat">🗺️ Learning Path</span>
            <span class="login-feat">🔥 Streak Tracking</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")
        # FIX 3 — AMD badge prominently on login
        st.markdown("""
        <div class="amd-badge">
          <div style="font-size:1.8rem">⚡</div>
          <div class="amd-badge-text">
            <div class="amd-badge-title">Powered by AMD Instinct MI300X</div>
            Ultra-fast AI inference via Groq · &lt;2s response time · LLaMA 3.3 70B
          </div>
        </div>
        """, unsafe_allow_html=True)

        username_input = st.text_input(
            "Username", placeholder="Enter a username to save your progress…",
            label_visibility="collapsed"
        )
        if st.button("🚀 Start Learning", use_container_width=True):
            if username_input.strip():
                name = username_input.strip().lower().replace(" ", "_")
                db_get_or_create_user(name)
                st.session_state.username  = name
                st.session_state.logged_in = True
                st.query_params["user"]    = name
                st.rerun()
            else:
                st.warning("Please enter a username!")

    st.stop()


# ══════════════════════════════════════════════
#  LOGGED IN
# ══════════════════════════════════════════════
username = st.session_state.username
history  = db_get_history(username)
stats    = db_get_stats(username)
streak   = db_get_streak(username)
weak     = db_get_weak_areas(username)


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:

    st.markdown(f"### 👤 {username}")

    # FIX 3 — AMD badge in sidebar too
    st.markdown("""
    <div style="background:linear-gradient(135deg,#ED1C24,#FF6B35);border-radius:8px;
    padding:8px 12px;margin-bottom:12px;text-align:center;">
    <span style="color:white;font-size:0.78rem;font-weight:700;">
    ⚡ AMD Instinct MI300X · Groq API</span></div>
    """, unsafe_allow_html=True)

    st.markdown(
        f'<div class="streak-badge">'
        f'<div class="streak-num">🔥 {streak}</div>'
        f'<div class="streak-text">{"Day Streak!" if streak > 0 else "Complete a quiz to start your streak!"}</div>'
        f'</div>', unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("📚 Topics",  stats["topics"])
    c2.metric("🧪 Quizzes", stats["quizzes"])
    c3.metric("🎯 Avg",     f"{stats['avg_acc']}%")
    st.markdown("---")

    # Progress chart
    chart_data = db_get_chart_data(username)
    if len(chart_data) >= 2:
        st.markdown("### 📈 Accuracy Trend")
        import pandas as pd
        labels        = [r[0][:14] for r in chart_data]
        accuracy_vals = [r[1] for r in chart_data]
        df = pd.DataFrame({"Accuracy %": accuracy_vals}, index=labels)
        st.line_chart(df, use_container_width=True)
        st.markdown("---")

    if weak:
        st.markdown("### ⚠️ Weak Areas")
        for w in weak:
            dc = f"diff-{w['difficulty'].lower()}"
            st.markdown(
                f'<div class="weak-card">'
                f'<div class="weak-title">📉 {w["topic"]}</div>'
                f'<div class="weak-detail">Avg: {w["accuracy"]}% &nbsp;·&nbsp;'
                f'<span class="{dc}">{w["difficulty"]}</span></div>'
                f'</div>', unsafe_allow_html=True
            )
            if st.button(f"🔁 Re-quiz", key=f"weak_{w['topic']}"):
                go_to_topic(w["topic"])
        st.markdown("---")

    st.markdown("### 📚 Topic History")
    if not history:
        st.markdown('<p style="color:#64748b;font-size:0.85rem;">No topics yet. Start learning!</p>', unsafe_allow_html=True)
    else:
        subjects = {}
        for e in history:
            subjects.setdefault(e["subject"], []).append(e)
        for subj, entries in subjects.items():
            with st.expander(f"📂 {subj} ({len(entries)})"):
                for e in entries:
                    dc = f"diff-{e['difficulty'].lower()}"
                    st.markdown(
                        f'<div class="hist-card">'
                        f'<div class="hist-topic">📘 {e["topic"]}</div>'
                        f'<div class="hist-meta">{e["date"]}</div>'
                        f'<div style="display:flex;gap:8px;margin-top:6px;align-items:center;">'
                        f'<span class="{dc}">{e["difficulty"]}</span>'
                        f'<span class="hist-score">🎯 {e["score"]}/{e["total"]} ({e["accuracy"]}%)</span>'
                        f'</div></div>', unsafe_allow_html=True
                    )
                    if st.button("↩ Re-study", key=f"rs_{e['topic']}_{e['date']}"):
                        go_to_topic(e["topic"])

    st.markdown("---")
    if st.button("🚪 Log Out"):
        st.query_params.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ─────────────────────────────────────────────
#  MAIN HEADER — FIX 9 branding
# ─────────────────────────────────────────────
st.markdown("<h1>🎓 StudyMate AI</h1>", unsafe_allow_html=True)
st.markdown(
    f'<p class="subtitle">Welcome back, <strong style="color:#a78bfa">{username}</strong>! &nbsp;·&nbsp; '
    f'Powered by <strong style="color:#FF6B35;">AMD Instinct MI300X</strong> via Groq &nbsp;·&nbsp; '
    f'Learn · Quiz · Improve</p>',
    unsafe_allow_html=True
)


# ══════════════════════════════════════════════
#  PHASE 1 — INPUT
# ══════════════════════════════════════════════
if st.session_state.phase == "input":

    st.markdown('<div class="phase-pill phase-learn">Step 1 — Choose Your Topic</div>', unsafe_allow_html=True)

    st.markdown("**✨ Quick Start — try one of these:**")
    qcols = st.columns(6)
    samples = ["Photosynthesis","Trigonometry","Black Holes","World War II","Machine Learning","Supply & Demand"]
    for i, s in enumerate(samples):
        with qcols[i]:
            if st.button(s, key=f"sample_{s}"):
                st.session_state.topic = s
                st.rerun()

    st.markdown("")
    default_topic = st.session_state.get("topic", "")
    topic = st.text_input(
        "📚 Or type your own topic",
        value=default_topic,
        placeholder="e.g. Organic Chemistry, French Revolution, Neural Networks…"
    )
    st.info("🤖 **Difficulty is auto-detected** — the AI analyses your topic's complexity automatically.", icon="💡")

    if st.button("✨ Start Learning"):
        if topic.strip():
            progress_bar = st.progress(0, text="🔍 Analysing topic complexity…")

            # Step 1 — detect difficulty (with error handling)
            diff_content = safe_api_call(
                messages=[
                    {"role": "system", "content": "You are an academic difficulty classifier. Reply with exactly one word only."},
                    {"role": "user",   "content": f'Difficulty of "{topic}" for high school/first-year uni? Reply: Easy, Medium, or Hard'}
                ],
                temperature=0.1, max_tokens=5
            )
            if diff_content is None:
                st.stop()
            raw_diff   = diff_content.strip().capitalize()
            difficulty = raw_diff if raw_diff in ["Easy","Medium","Hard"] else "Medium"
            subject    = detect_subject(topic)
            progress_bar.progress(30, text="✍️ Generating your personalised lesson…")

            # Step 2 — generate lesson
            learn_prompt = f"""
You are a world-class teacher. Explain "{topic}" in a way that is UNFORGETTABLE, deeply clear, and packed with examples.

Structure with these EXACT markdown sections:

## 🌟 What Is {topic}?
Hook the student in 3-4 sentences. Why is this fascinating and important?

## 🧠 Core Concepts (Explained Simply)
Cover 4-5 key ideas. For EACH:
- **Concept name**: 1-2 sentence definition
- 💡 *Example*: A vivid everyday example
- 🔗 *Analogy*: Compare it to something familiar

## 🔬 3 Examples That Make It Click

### Example 1 — Step by Step (Beginner)
Fully worked example, every step shown.

### Example 2 — Real World Application
Where this appears in real life or technology. Be specific.

### Example 3 — The Wow Factor
Something surprising most students don't know.

## ⚠️ Common Mistakes Students Make
3 things students often get wrong — corrected clearly.

## ⚡ The 5 Things You Must Remember
Five bullet-point essentials.

Use **bold** for key terms. Keep language simple and encouraging.
"""
            lesson_content = safe_api_call(
                messages=[
                    {"role": "system", "content": "You are a brilliant engaging teacher who uses vivid examples and analogies."},
                    {"role": "user",   "content": learn_prompt}
                ],
                temperature=0.75, max_tokens=2800
            )
            if lesson_content is None:
                st.stop()

            progress_bar.progress(100, text="✅ Lesson ready!")

            st.session_state.explanation     = lesson_content
            st.session_state.topic           = topic
            st.session_state.difficulty      = difficulty
            st.session_state.subject         = subject
            st.session_state.recommendations = None
            st.session_state.confirm_new     = False
            if "explanations" in st.session_state:
                del st.session_state.explanations
            st.session_state.phase = "learning"
            scroll_to_top()
            st.rerun()
        else:
            st.warning("Please enter a topic first!")


# ══════════════════════════════════════════════
#  PHASE 2 — LEARNING
# ══════════════════════════════════════════════
elif st.session_state.phase == "learning":

    diff    = st.session_state.difficulty
    dc      = f"diff-{diff.lower()}"
    subject = st.session_state.get("subject", "General")

    st.markdown('<div class="phase-pill phase-learn">Step 2 — Learn the Topic</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;flex-wrap:wrap;">'
        f'<span style="color:#e2e8f0;font-size:1.3rem;font-weight:700;">📖 {st.session_state.topic}</span>'
        f'<span class="{dc}">{diff}</span>'
        f'<span class="subj-tag">{subject}</span>'
        f'<span style="color:#64748b;font-size:0.78rem;">• auto-detected</span>'
        f'</div>', unsafe_allow_html=True
    )

    st.markdown(st.session_state.explanation)
    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
    st.markdown("**Finished reading? Test yourself when you're ready! 👇**")

    col1, col2 = st.columns(2)
    with col1:
        # FIX 11 — confirmation before changing topic
        if st.button("🔄 Change Topic"):
            st.session_state.confirm_new = True
            st.rerun()

        if st.session_state.get("confirm_new"):
            st.markdown("""
            <div class="confirm-box">
              <div class="confirm-text">⚠️ Are you sure? Your current lesson will be lost.</div>
            </div>
            """, unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("✅ Yes, change topic"):
                    reset_for_new_topic()
                    st.session_state.phase = "input"
                    scroll_to_top()
                    st.rerun()
            with cc2:
                if st.button("❌ Cancel"):
                    st.session_state.confirm_new = False
                    st.rerun()

    with col2:
        if st.button("🧠 I'm Ready — Take the Quiz!"):
            progress_bar = st.progress(0, text=f"🧪 Generating {diff} quiz on {st.session_state.topic}…")

            quiz_prompt = f"""
Generate exactly 20 multiple choice questions about "{st.session_state.topic}".
Difficulty: {diff}.

Spread across tiers:
- Q1–7:   Basic recall and definitions
- Q8–14:  Application and reasoning
- Q15–20: Analysis, edge cases, real-world scenarios

Rules:
- Do NOT hint at the correct answer in the question or options.
- All 4 options must be plausible — no obviously wrong distractors.
- Return ONLY valid JSON — no text, no markdown fences.

Format:
[{{"question":"?","options":["A","B","C","D"],"answer_index":0}}]
"""
            quiz_content = safe_api_call(
                messages=[
                    {"role": "system", "content": "You are a strict quiz generator. Return only valid JSON."},
                    {"role": "user",   "content": quiz_prompt}
                ],
                temperature=0.6, max_tokens=4000
            )
            if quiz_content is None:
                st.stop()

            progress_bar.progress(100, text="✅ Quiz ready!")
            jm = re.search(r"\[.*\]", quiz_content, re.DOTALL)
            if jm:
                quiz = json.loads(jm.group())
                if len(quiz) < 20:
                    st.warning(f"⚠️ Only {len(quiz)} questions generated. Try again for a full 20-question set.")
                st.session_state.quiz         = quiz
                st.session_state.user_answers = {}
                st.session_state.submitted    = False
                st.session_state.phase        = "quiz"
                scroll_to_top()
                st.rerun()
            else:
                st.error("❌ Quiz generation failed — the AI returned unexpected output. Please try again.")


# ══════════════════════════════════════════════
#  PHASE 3 — QUIZ
#  FIX 5 — remove broken live progress bar,
#           show static count instead
# ══════════════════════════════════════════════
elif st.session_state.phase == "quiz":

    diff  = st.session_state.difficulty
    dc    = f"diff-{diff.lower()}"
    quiz  = st.session_state.quiz
    total = len(quiz)

    st.markdown('<div class="phase-pill phase-quiz">Step 3 — Quiz Time</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">'
        f'<span style="color:#e2e8f0;font-size:1.2rem;font-weight:700;">📝 {st.session_state.topic}</span>'
        f'<span class="{dc}">{diff}</span>'
        f'</div>', unsafe_allow_html=True
    )
    st.markdown(
        f'<p style="color:#64748b;font-size:0.88rem;">Answer all {total} questions then click Submit. '
        f'All questions must be answered before submitting.</p>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    with st.form("quiz_form"):
        for i, q in enumerate(quiz):
            st.markdown(
                f'<div class="quiz-card"><strong>Q{i+1}. {q["question"]}</strong></div>',
                unsafe_allow_html=True
            )
            sel = st.radio(
                f"Answer Q{i+1}", q["options"],
                index=None, key=f"q{i}", label_visibility="collapsed"
            )
            if sel is not None:
                st.session_state.user_answers[i] = sel
            st.markdown("")

        if st.form_submit_button("✅ Submit Answers", use_container_width=True):
            if len(st.session_state.user_answers) < total:
                remaining = total - len(st.session_state.user_answers)
                st.warning(f"⚠️ {remaining} question(s) unanswered. Please answer all {total} before submitting!")
            else:
                score = sum(
                    1 for i, q in enumerate(quiz)
                    if st.session_state.user_answers.get(i) == q["options"][q["answer_index"]]
                )
                st.session_state.score     = score
                st.session_state.submitted = True
                db_save_result(username, st.session_state.topic,
                               st.session_state.subject, diff, score, total)
                db_record_streak(username)
                st.session_state.phase = "results"
                scroll_to_top()
                st.rerun()

    st.markdown("")
    if st.button("← Back to Lesson"):
        st.session_state.phase = "learning"
        scroll_to_top()
        st.rerun()


# ══════════════════════════════════════════════
#  PHASE 4 — RESULTS
# ══════════════════════════════════════════════
elif st.session_state.phase == "results":

    diff  = st.session_state.difficulty
    dc    = f"diff-{diff.lower()}"
    score = st.session_state.score
    quiz  = st.session_state.quiz
    total = len(quiz)
    acc   = round(score / total * 100)

    st.markdown('<div class="phase-pill phase-done">Step 4 — Results</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;">'
        f'<span style="color:#e2e8f0;font-size:1.1rem;font-weight:700;">{st.session_state.topic}</span>'
        f'<span class="{dc}">{diff}</span>'
        f'<span class="subj-tag">{st.session_state.get("subject","General")}</span>'
        f'</div>', unsafe_allow_html=True
    )

    st.markdown(f'<div class="score-badge">🎯 {score} / {total}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="accuracy-wrap">'
        f'<div><div class="accuracy-pct">{acc}%</div>'
        f'<div class="accuracy-label">Accuracy</div></div>'
        f'<div style="flex:1;">'
        f'<div class="accuracy-bar-bg">'
        f'<div class="accuracy-bar-fill" style="width:{acc}%;"></div></div>'
        f'<div class="accuracy-label" style="margin-top:6px;">'
        f'{score} correct &nbsp;·&nbsp; {total-score} wrong &nbsp;·&nbsp; {total} total</div>'
        f'</div></div>', unsafe_allow_html=True
    )

    if acc == 100:   st.success("🚀 Perfect score! You've truly mastered this topic!")
    elif acc >= 80:  st.success("🌟 Excellent! Great understanding — just a few slip-ups.")
    elif acc >= 60:  st.info("👍 Good effort! Review the examples once more and you'll ace it.")
    elif acc >= 40:  st.warning("📚 Getting there. Re-read the lesson and try again.")
    else:            st.error("💡 Don't worry — revisit the examples carefully and retake the quiz!")

    ca, cb, cc = st.columns(3)
    ca.metric("✅ Correct",  score)
    cb.metric("❌ Wrong",    total - score)
    cc.metric("📊 Accuracy", f"{acc}%")

    streak_now = db_get_streak(username)
    st.markdown(
        f'<div class="share-card">'
        f'<div class="share-title">📤 Share Your Result</div>'
        f'<div class="share-body">'
        f'🎓 I scored <strong>{score}/{total} ({acc}%)</strong> on <strong>{st.session_state.topic}</strong> '
        f'using StudyMate AI!<br>'
        f'🔥 Streak: {streak_now} day(s) &nbsp;·&nbsp; Difficulty: {diff} &nbsp;·&nbsp; '
        f'Subject: {st.session_state.get("subject","General")}<br>'
        f'<em style="color:#64748b;font-size:0.8rem;">⚡ Powered by AMD Instinct MI300X via Groq</em>'
        f'</div></div>', unsafe_allow_html=True
    )

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    wrong_qs   = [(i,q) for i,q in enumerate(quiz)
                  if st.session_state.user_answers.get(i) != q["options"][q["answer_index"]]]
    correct_qs = [(i,q) for i,q in enumerate(quiz)
                  if st.session_state.user_answers.get(i) == q["options"][q["answer_index"]]]

    # ── Generate explanations for wrong answers ──
    if wrong_qs and "explanations" not in st.session_state:
        with st.spinner("🧠 Generating explanations for your wrong answers…"):
            wrong_list = "\n".join([
                f"{idx+1}. Q: {q['question']}\n"
                f"   Correct: {q['options'][q['answer_index']]}\n"
                f"   Student answered: {st.session_state.user_answers.get(idx,'—')}"
                for idx, q in wrong_qs
            ])
            exp_content = safe_api_call(
                messages=[
                    {"role": "system", "content": "You are a patient teacher. Return only valid JSON."},
                    {"role": "user",   "content": f"""
Student got these WRONG on a quiz about "{st.session_state.topic}".
For each, write a 2-4 sentence explanation:
1. Why the correct answer is right
2. Why their choice was wrong
3. The key concept to understand

{wrong_list}

Return ONLY JSON: {{"question_number": "explanation text"}}
"""}
                ],
                temperature=0.5, max_tokens=3000
            )
            try:
                if exp_content:
                    jm = re.search(r"\{.*\}", exp_content, re.DOTALL)
                    st.session_state.explanations = json.loads(jm.group()) if jm else {}
                else:
                    st.session_state.explanations = {}
            except Exception:
                st.session_state.explanations = {}
    elif "explanations" not in st.session_state:
        st.session_state.explanations = {}

    explanations = st.session_state.explanations

    st.markdown("### 📌 Answer Review")

    if wrong_qs:
        st.markdown(f"#### ❌ Questions You Got Wrong ({len(wrong_qs)})")
        for idx, q in wrong_qs:
            correct  = q["options"][q["answer_index"]]
            user_ans = st.session_state.user_answers.get(idx, "—")
            exp_text = explanations.get(str(idx+1), "")
            with st.expander(f"❌ Q{idx+1}. {q['question']}"):
                st.markdown(f'<span class="answer-wrong">❌ Your answer: {user_ans}</span>', unsafe_allow_html=True)
                st.markdown(f'<span class="answer-correct">✅ Correct answer: {correct}</span>', unsafe_allow_html=True)
                if exp_text:
                    st.markdown(
                        f'<div class="explanation-box">'
                        f'<div class="explanation-label">💡 Explanation</div>{exp_text}</div>',
                        unsafe_allow_html=True
                    )

    if correct_qs:
        st.markdown(f"#### ✅ Questions You Got Right ({len(correct_qs)})")
        for idx, q in correct_qs:
            correct = q["options"][q["answer_index"]]
            with st.expander(f"✅ Q{idx+1}. {q['question']}"):
                st.markdown(f'<span class="answer-correct">✅ {correct}</span>', unsafe_allow_html=True)

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    # ── Recommendations ──
    st.markdown("## 🧭 Personalised Recommendations")

    all_history    = db_get_history(username)
    studied_topics = list({e["topic"] for e in all_history})
    weak_topics    = [w["topic"] for w in db_get_weak_areas(username)]

    if st.session_state.recommendations is None:
        with st.spinner("🤖 Generating personalised recommendations…"):
            rec_content = safe_api_call(
                messages=[
                    {"role": "system", "content": "You are a personalised study advisor. Return only valid JSON."},
                    {"role": "user",   "content": f"""
Student studied "{st.session_state.topic}" ({diff}) and scored {acc}% ({score}/{total}).
Topics studied: {", ".join(studied_topics) if len(studied_topics)>1 else "only this topic"}.
Weak topics (<60%): {", ".join(weak_topics) if weak_topics else "none"}.

Return ONLY this JSON:
{{
  "related_topics":[
    {{"topic":"Name","reason":"1 sentence why","tag":"short tag"}},
    {{"topic":"Name","reason":"1 sentence","tag":"short tag"}},
    {{"topic":"Name","reason":"1 sentence","tag":"short tag"}}
  ],
  "learning_path":[
    {{"step":1,"topic":"Name","why":"short reason"}},
    {{"step":2,"topic":"Name","why":"short reason"}},
    {{"step":3,"topic":"Name","why":"short reason"}},
    {{"step":4,"topic":"Name","why":"short reason"}},
    {{"step":5,"topic":"Name","why":"short reason"}}
  ],
  "study_tip":"Specific actionable tip based on their score."
}}
"""}
                ],
                temperature=0.7, max_tokens=1500
            )
            try:
                if rec_content:
                    jm = re.search(r"\{.*\}", rec_content, re.DOTALL)
                    st.session_state.recommendations = json.loads(jm.group()) if jm else {}
                else:
                    st.session_state.recommendations = {}
            except Exception:
                st.session_state.recommendations = {}

    recs = st.session_state.recommendations or {}

    if recs.get("study_tip"):
        st.info(f"💡 **Study Tip:** {recs['study_tip']}")

    rec_col, path_col = st.columns(2)

    with rec_col:
        st.markdown("### 📖 Related Topics")
        for r in recs.get("related_topics", []):
            st.markdown(
                f'<div class="rec-card">'
                f'<div class="rec-title">📘 {r["topic"]}</div>'
                f'<div class="rec-reason">{r["reason"]}</div>'
                f'<span class="rec-tag rec-next">{r.get("tag","Next Step")}</span>'
                f'</div>', unsafe_allow_html=True
            )
            if st.button(f"Study {r['topic']} →", key=f"rec_{r['topic']}"):
                go_to_topic(r["topic"])

    with path_col:
        st.markdown("### 🗺️ Your Learning Path")
        for step in recs.get("learning_path", []):
            done = step["topic"] in studied_topics
            icon = "✅" if done else str(step["step"])
            st.markdown(
                f'<div class="path-step">'
                f'<div class="path-num">{icon}</div>'
                f'<div class="path-info">'
                f'<div class="path-topic">{step["topic"]}</div>'
                f'<div class="path-why">{step["why"]}</div>'
                f'</div></div>', unsafe_allow_html=True
            )

    if weak_topics:
        st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
        st.markdown("### 🎯 Targeted Practice — Improve Weak Areas")
        st.markdown(f"You scored below 60% on: **{', '.join(weak_topics)}**")
        w_cols = st.columns(min(len(weak_topics), 3))
        for idx, wt in enumerate(weak_topics[:3]):
            with w_cols[idx]:
                if st.button(f"🔁 Re-quiz: {wt}", key=f"rq_{wt}"):
                    go_to_topic(wt)

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔁 Retake Quiz"):
            st.session_state.user_answers = {}
            st.session_state.submitted    = False
            if "explanations" in st.session_state:
                del st.session_state.explanations
            st.session_state.phase = "quiz"
            scroll_to_top()
            st.rerun()
    with col2:
        if st.button("📖 Back to Lesson"):
            st.session_state.phase = "learning"
            scroll_to_top()
            st.rerun()

    # FIX 11 — confirmation before starting over
    if st.button("🏠 Study a New Topic"):
        st.session_state.confirm_new = True
        st.rerun()

    if st.session_state.get("confirm_new"):
        st.markdown("""
        <div class="confirm-box">
          <div class="confirm-text">⚠️ Start a new topic? Your current session will be cleared.</div>
        </div>
        """, unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Yes, new topic"):
                reset_for_new_topic()
                st.session_state.phase = "input"
                scroll_to_top()
                st.rerun()
        with cc2:
            if st.button("❌ Stay here"):
                st.session_state.confirm_new = False
                st.rerun()
