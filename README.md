# Hospital Kiosk

This is the backend and frontend for the Hospital Kiosk application. It features face recognition, voice transcription, and conversational AI for patient registration and triage.

The system is optimized for **edge deployment** on devices like the **Raspberry Pi 5 (8GB RAM)**, utilizing local LLM inference via Ollama and the Gemma 3 model.

---

## 🚀 How to Setup (Raspberry Pi 5 / Ubuntu)

### 1. Prerequisites

First, ensure your system is up to date and you have Python 3 and Node.js installed.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl
```

For the frontend, you'll need Node.js (v18+ recommended):
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. Install and Setup Local AI (Ollama & Gemma 3)

We use **Ollama** to run the LLM locally on the Raspberry Pi without needing cloud services like Groq. 
For an 8GB Raspberry Pi 5, the `gemma3:4b` model is recommended.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start the Ollama service (if it doesn't start automatically)
sudo systemctl enable ollama
sudo systemctl start ollama

# Pull the Gemma 3 (4B) model
ollama pull gemma3:4b

# Verify it works
curl http://localhost:11434
# Should output: "Ollama is running"
```

### 3. Setup the Backend

Clone the repository and set up the Python environment.

```bash
git clone https://github.com/v1k111-29/medKiosk.git
cd medKiosk

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
# Note: On Raspberry Pi, some packages (like opencv-python, numpy) might take time to build.
pip install -r requirements.txt
```

### 4. Environment Variables

Create your `.env` file based on the example:

```bash
cp .env.example .env
```

Open `.env` and configure your keys:
- Ensure `OLLAMA_URL=http://localhost:11434` and `OLLAMA_MODEL=gemma3:4b` are set.
- Add your **Sarvam AI API Key** for voice transcription (`SARVAM_API_KEY`). Get it from [dashboard.sarvam.ai](https://dashboard.sarvam.ai).

### 5. Setup the Frontend

Build the React frontend. The backend FastAPI server is configured to serve the built static files.

```bash
cd frontend
npm install
npm run build
cd ..
```

### 6. Run the Application

You can start the backend and serve the application using the provided scripts:

**Linux / Raspberry Pi:**
```bash
./start.sh
```

**Windows:**
```cmd
start.bat
```

The application will be available at: **http://localhost:8000**

---

## 🏗️ Architecture

- **Backend**: FastAPI (Python)
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Local LLM**: Ollama (`gemma3:4b`) for privacy-preserving, edge-computed triage and conversational registration.
- **Voice Transcription**: Sarvam AI STT API (specifically optimized for Indian languages and accents).
- **Face Recognition**: DeepFace (ArcFace model) for patient identification.
- **Database**: SQLite (`patients.db`)

## ⚡ Performance on Raspberry Pi 5
- **Face Recognition**: ~1-2 seconds per scan.
- **Voice STT**: ~1-2 seconds via Sarvam Cloud API.
- **LLM Inference**: ~5-15 seconds per response using `gemma3:4b` (quantized) via CPU. The `OLLAMA_TIMEOUT` is set to 120s by default to accommodate this.
