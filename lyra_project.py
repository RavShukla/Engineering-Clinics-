import os
import json
import threading
import datetime
import webbrowser
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext
import requests
import speech_recognition as sr
import pyttsx3
from PIL import Image, ImageTk
import io

# ========================= CONFIG =========================
GEMINI_API_KEY = "hghfh"  #Generate your API Key
# CORRECT API ENDPOINT
GEMINI_MODEL = "gemini-2.5-flash"  # Updated to available model
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

MEMORY_FILE = "lyra_memory.json"
HISTORY_LIMIT = 8

# ======================== MEMORY ==========================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"name": None, "facts": [], "history": []}

def save_memory(mem):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)

memory = load_memory()

# ====================== TEXT TO SPEECH =====================
tts_engine = None

def init_tts():
    global tts_engine
    try:
        tts_engine = pyttsx3.init()
        tts_engine.setProperty("rate", 160)
        tts_engine.setProperty("volume", 0.9)
        voices = tts_engine.getProperty("voices")
        # Try to find English voice
        for v in voices:
            if "english" in v.name.lower() or "india" in v.name.lower():
                tts_engine.setProperty("voice", v.id)
                break
    except Exception as e:
        print(f"TTS Error: {e}")

# def speak(text: str):
#     def _speak():
#         try:
#             # Reinitialize TTS engine for each speak to ensure it works
#             engine = pyttsx3.init()
#             engine.setProperty("rate", 160)
#             engine.setProperty("volume", 0.9)
#             voices = engine.getProperty("voices")
#             # Try to find Hindi voice first, then English
#             for v in voices:
#                 if "hindi" in v.name.lower() or "india" in v.name.lower() or "english" in v.name.lower():
#                     engine.setProperty("voice", v.id)
#                     break
#             engine.say(text)
#             engine.runAndWait()
#             engine.stop()
#         except Exception as e:
#             print(f"TTS Error: {e}")
#     threading.Thread(target=_speak, daemon=True).start()
def speak(text: str):
    def _speak():
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.setProperty("volume", 1.0)

            voices = engine.getProperty("voices")

            # Try to pick a female Indian or English voice
            selected_voice = None
            for v in voices:
                if "female" in v.name.lower() and ("india" in v.name.lower() or "english" in v.name.lower()):
                    selected_voice = v.id
                    break
            if not selected_voice:
                # fallback to any English or Indian voice
                for v in voices:
                    if "india" in v.name.lower() or "english" in v.name.lower():
                        selected_voice = v.id
                        break

            if selected_voice:
                engine.setProperty("voice", selected_voice)

            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"TTS Error: {e}")
    threading.Thread(target=_speak, daemon=True).start()


# ===================== SPEECH RECOGNITION ==================
recognizer = sr.Recognizer()
recognizer.energy_threshold = 3000
recognizer.dynamic_energy_threshold = True

def listen_voice(timeout=8, phrase_limit=12):
    """Listen and recognize speech in both Hindi and English"""
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        
        # Try English first
        try:
            text = recognizer.recognize_google(audio, language="en-IN")
            return text
        except:
            # Fallback to Hindi
            try:
                text = recognizer.recognize_google(audio, language="hi-IN")
                return text
            except:
                raise sr.UnknownValueError()
    except Exception as e:
        raise e

# ===================== GEMINI API =====================
def call_gemini(user_message: str, system_context: str = "") -> str:
    """Call Google Gemini API - Super Fast & Free!"""
    
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return "⚠️ Please add your Gemini API key in the code!"
    
    # Build context with memory
    context_parts = []
    if system_context:
        context_parts.append(system_context)
    
    if memory.get("name"):
        context_parts.append(f"User's name: {memory['name']}")
    
    if memory.get("facts"):
        context_parts.append("Important facts: " + "; ".join(memory["facts"][-5:]))
    
    # Add recent history for context
    for msg in memory.get("history", [])[-6:]:
        role = "User" if msg["role"] == "user" else "Lyra"
        context_parts.append(f"{role}: {msg['content']}")
    
    context_parts.append(f"User: {user_message}")
    
    full_prompt = "\n".join(context_parts)
    
    # FIXED: API key goes in HEADER, not URL!
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }
    
    payload = {
        "contents": [{
            "parts": [{"text": full_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 200,
            "topP": 0.9,
            "topK": 40
        }
    }
    
    try:
        # Call Gemini API - key is in header!
        response = requests.post(
            GEMINI_API_URL,
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
        else:
            return "Sorry, I couldn't generate a response."
            
    except requests.exceptions.Timeout:
        return "⏱️ Response timeout. Please try again."
    except requests.exceptions.RequestException as e:
        return f"❌ API Error: {str(e)}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ====================== COMMAND HANDLERS ===================
def handle_command(text: str) -> tuple:
    """Handle various commands - returns (handled: bool, response: str)"""
    text_lower = text.lower()
    
    # Name commands
    if "my name is" in text_lower or "mera naam" in text_lower:
        name = text.split("is")[-1].strip() if "is" in text else text.split("naam")[-1].strip()
        name = name.strip(" .,:;!?")
        if name:
            memory["name"] = name
            save_memory(memory)
            return True, f"Nice to meet you, {name}! 😊 I'll remember your name."
    
    if "your name" in text_lower or "tumhara naam" in text_lower:
        return True, "I'm Lyra, your AI assistant! 💖"
    
    if ("my name" in text_lower or "mera naam" in text_lower) and ("what" in text_lower or "kya" in text_lower):
        if memory.get("name"):
            return True, f"Your name is {memory['name']}! 😊"
        return True, "You haven't told me your name yet."
    
    # Memory commands
    if text_lower.startswith("remember ") or text_lower.startswith("yaad rakh"):
        fact = text.replace("remember", "").replace("yaad rakh", "").strip()
        if fact:
            memory.setdefault("facts", []).append(fact)
            save_memory(memory)
            return True, f"✅ Remembered: {fact}"
    
    if "show memories" in text_lower or "yaadein dikha" in text_lower or "what do you remember" in text_lower:
        facts = memory.get("facts", [])
        if not facts:
            return True, "I don't have any saved memories yet."
        return True, "Your memories:\n" + "\n".join([f"• {f}" for f in facts])
    
    # Time & Date
    if "time" in text_lower or "samay" in text_lower or "kitna baj" in text_lower:
        now = datetime.datetime.now().strftime("%I:%M %p")
        return True, f"🕒 Current time: {now}"
    
    if "date" in text_lower or "tareekh" in text_lower or "aaj ki" in text_lower:
        today = datetime.date.today().strftime("%B %d, %Y")
        return True, f"📅 Today's date: {today}"
    
    # Open apps
    if text_lower.startswith(("open ", "khol ", "launch ", "start ")):
        app = text_lower.split(" ", 1)[1].strip()
        return True, open_application(app)
    
    # Play song
    if "play song" in text_lower or "play" in text_lower and "song" in text_lower:
        query = text.split("song")[-1].strip() if "song" in text else ""
        if query:
            webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
            return True, f"🎵 Playing: {query}"
        return True, "Which song should I play?"
    
    # Search
    if text_lower.startswith(("search ", "google ", "find ")):
        query = text.split(" ", 1)[1].strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return True, f"🔍 Searching: {query}"
    
    # Screenshot
    if "screenshot" in text_lower or "screen capture" in text_lower:
        return True, take_screenshot()
    
    return False, ""

def open_application(app_name: str) -> str:
    """Open various applications"""
    apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "terminal": "cmd.exe",
        "word": "winword.exe",
        "excel": "excel.exe",
        "powerpoint": "powerpnt.exe",
        "vlc": "vlc.exe",
    }
    
    if app_name in apps:
        try:
            subprocess.Popen([apps[app_name]], shell=True)
            return f"✅ Opened {app_name.title()}"
        except Exception as e:
            return f"❌ Couldn't open {app_name}: {str(e)}"
    
    return f"❌ App '{app_name}' not found"

def take_screenshot() -> str:
    """Take a screenshot"""
    try:
        import pyautogui
        filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        pyautogui.screenshot(filename)
        return f"📸 Screenshot saved: {filename}"
    except ImportError:
        return "❌ Please install: pip install pyautogui"
    except Exception as e:
        return f"❌ Screenshot failed: {e}"

# ========================= UI APP =========================
class LyraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Lyra AI - Fast & Smart Assistant")
        self.root.geometry("700x600")
        self.root.configure(bg="#0d1117")
        self.voice_enabled = True
        self.listening = False
        
        # Title Frame
        title_frame = tk.Frame(root, bg="#0d1117")
        title_frame.pack(fill="x", pady=(10, 5))
        
        tk.Label(
            title_frame, text="✨ LYRA AI ✨",
            fg="#58a6ff", bg="#0d1117", 
            font=("Segoe UI", 20, "bold")
        ).pack()
        
        tk.Label(
            title_frame, text="Powered by Google Gemini • Lightning Fast",
            fg="#8b949e", bg="#0d1117", 
            font=("Segoe UI", 9)
        ).pack()
        
        # Chat Area
        chat_frame = tk.Frame(root, bg="#0d1117")
        chat_frame.pack(padx=15, pady=10, fill="both", expand=True)
        
        self.chat = scrolledtext.ScrolledText(
            chat_frame,
            bg="#161b22", fg="#c9d1d9",
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=10, pady=10
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.config(state="disabled")
        
        # Configure text tags
        self.chat.tag_config("user", foreground="#58a6ff", font=("Consolas", 10, "bold"))
        self.chat.tag_config("bot", foreground="#3fb950", font=("Consolas", 10, "bold"))
        self.chat.tag_config("system", foreground="#f85149", font=("Consolas", 10, "italic"))
        
        # Status Bar
        self.status = tk.Label(
            root, text="🟢 Ready to chat",
            bg="#0d1117", fg="#58a6ff",
            font=("Segoe UI", 9), anchor="w"
        )
        self.status.pack(fill="x", padx=15, pady=(0, 5))
        
        # Input Frame
        input_frame = tk.Frame(root, bg="#0d1117")
        input_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.entry = tk.Entry(
            input_frame,
            bg="#161b22", fg="white",
            font=("Segoe UI", 11),
            relief="flat",
            insertbackground="white"
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.send_message())
        self.entry.focus()
        
        # Buttons
        tk.Button(
            input_frame, text="Send",
            bg="#238636", fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", padx=20, pady=8,
            cursor="hand2",
            command=self.send_message
        ).pack(side="left", padx=(0, 5))
        
        tk.Button(
            input_frame, text="🎤",
            bg="#1f6feb", fg="white",
            font=("Segoe UI", 12, "bold"),
            relief="flat", padx=15, pady=8,
            cursor="hand2",
            command=self.toggle_voice_input
        ).pack(side="left", padx=(0, 5))
        
        self.voice_btn = tk.Button(
            input_frame, text="🔊",
            bg="#58a6ff", fg="white",
            font=("Segoe UI", 12, "bold"),
            relief="flat", padx=15, pady=8,
            cursor="hand2",
            command=self.toggle_voice_output
        )
        self.voice_btn.pack(side="left")
        
        # Welcome message
        self.add_message("bot", "Hello! I'm Lyra, your super-fast AI assistant powered by Google Gemini! 🚀\n\n"
                         "Try these commands:\n"
                         "• 'Open notepad' / 'Notepad kholo'\n"
                         "• 'Play song [name]'\n"
                         "• 'Remember [something]'\n"
                         "• 'What time is it?'\n"
                         "• 'Search for [query]'\n"
                         "• Or just chat with me in Hindi or English! 😊")
        
        # Load history
        for msg in memory.get("history", [])[-4:]:
            role = "user" if msg["role"] == "user" else "bot"
            self.add_message(role, msg["content"], save=False)
        
        # Initialize TTS
        init_tts()
    
    def add_message(self, role: str, text: str, save=True):
        """Add message to chat"""
        self.chat.config(state="normal")
        
        if role == "user":
            self.chat.insert("end", "👤 You: ", "user")
            self.chat.insert("end", f"{text}\n\n")
        elif role == "bot":
            self.chat.insert("end", "🤖 Lyra: ", "bot")
            self.chat.insert("end", f"{text}\n\n")
        else:
            self.chat.insert("end", f"⚠️ {text}\n\n", "system")
        
        self.chat.see("end")
        self.chat.config(state="disabled")
        
        if save:
            memory["history"].append({"role": role if role == "user" else "assistant", "content": text})
            memory["history"] = memory["history"][-(HISTORY_LIMIT * 2):]
            save_memory(memory)
    
    def set_status(self, text: str, color="#58a6ff"):
        """Update status bar"""
        self.status.config(text=text, fg=color)
        self.root.update()
    
    def send_message(self):
        """Send text message"""
        text = self.entry.get().strip()
        if not text:
            return
        
        self.entry.delete(0, "end")
        self.process_input(text)
    
    def toggle_voice_input(self):
        """Start voice input"""
        if self.listening:
            return
        
        threading.Thread(target=self._voice_input_thread, daemon=True).start()
    
    def _voice_input_thread(self):
        """Voice input thread"""
        self.listening = True
        self.set_status("🎤 Listening... (speak now)", "#f85149")
        
        try:
            text = listen_voice()
            self.set_status(f"✓ Heard: {text}", "#3fb950")
            self.process_input(text)
        except sr.WaitTimeoutError:
            self.set_status("❌ No speech detected", "#f85149")
        except sr.UnknownValueError:
            self.set_status("❌ Couldn't understand", "#f85149")
        except Exception as e:
            self.set_status(f"❌ Error: {e}", "#f85149")
        finally:
            self.listening = False
    
    def toggle_voice_output(self):
        """Toggle voice output"""
        self.voice_enabled = not self.voice_enabled
        color = "#3fb950" if self.voice_enabled else "#8b949e"
        self.voice_btn.config(bg=color)
        self.set_status(f"🔊 Voice {'ON' if self.voice_enabled else 'OFF'}", color)
    
    def process_input(self, text: str):
        """Process user input"""
        self.add_message("user", text)
        
        # Check for commands first
        handled, response = handle_command(text)
        if handled:
            self.add_message("bot", response)
            if self.voice_enabled:
                speak(response)
            self.set_status("🟢 Ready", "#3fb950")
            return
        
        # Use AI for conversation
        threading.Thread(target=self._ai_response_thread, args=(text,), daemon=True).start()
    
    def _ai_response_thread(self, user_text: str):
        """Get AI response"""
        self.set_status("🤖 Thinking...", "#f85149")
        
        system_context = (
            "You are Lyra, a friendly AI assistant. "
            "Respond in the same language the user uses (Hindi or English). "
            "Keep responses brief (2-3 sentences) unless asked for detail. "
            "Be warm, helpful, and conversational."
        )
        
        try:
            response = call_gemini(user_text, system_context)
            self.add_message("bot", response)
            
            if self.voice_enabled:
                speak(response)
            
            self.set_status("🟢 Ready", "#3fb950")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.add_message("system", error_msg)
            self.set_status("❌ Error occurred", "#f85149")

# ========================= MAIN =========================
if __name__ == "__main__":
    root = tk.Tk()
    app = LyraApp(root)

    root.mainloop()
