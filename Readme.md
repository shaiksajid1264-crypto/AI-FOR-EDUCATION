# 🎓 AI Smart Study Assistant

An AI-powered study tool that generates personalised lessons, quizzes, explanations, and recommendations for any topic.

---

## ✨ Features

- 📖 **Rich AI Lessons** — structured explanations with examples, analogies, and real-world applications
- 🧠 **20-Question Quiz** — auto-difficulty detection calibrated to each topic
- 💡 **Wrong Answer Explanations** — AI explains every mistake in detail
- 📊 **Accuracy Tracking** — progress chart, streak, and performance metrics
- 🧭 **Personalised Recommendations** — related topics, learning path, study tips
- ⚠️ **Weak Area Detection** — identifies topics where you score below 60%
- 🗂️ **Topic History** — grouped by subject, persisted across sessions
- 🔥 **Daily Streak** — tracks consecutive study days
- 💾 **SQLite Persistence** — all data saved locally across sessions
- 👤 **Multi-user** — each user has their own history and progress

---

## 🚀 Run Locally

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/ai-study-assistant.git
cd ai-study-assistant
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your Groq API key
Create the file `.streamlit/secrets.toml`:
```toml
GROQ_API_KEY = "your_groq_api_key_here"
```
Get a free API key at [console.groq.com](https://console.groq.com)

### 4. Run the app
```bash
streamlit run app.py
```

---

## ☁️ Deploy on Streamlit Cloud

1. Push this repo to GitHub (make sure `.streamlit/secrets.toml` is in `.gitignore`)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Under **Settings → Secrets**, add:
```toml
GROQ_API_KEY = "your_groq_api_key_here"
```
5. Deploy ✅

---

## 📁 Project Structure

```
ai-study-assistant/
├── app.py                  # Main application
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore rules
├── README.md               # This file
└── .streamlit/
    ├── config.toml         # Streamlit theme config
    └── secrets.toml        # API key (NOT committed to git)
```

---

## 🛠️ Tech Stack

| Tool | Purpose |
|------|---------|
| [Streamlit](https://streamlit.io) | Frontend & UI |
| [Groq](https://groq.com) | LLM API (llama-3.3-70b-versatile) |
| [SQLite](https://sqlite.org) | Local persistent database |
| [Pandas](https://pandas.pydata.org) | Progress chart data |

---

## 🔑 Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key from console.groq.com |

---

Built for the AI Hackathon 🏆
