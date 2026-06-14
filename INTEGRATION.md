# Frontend Integration & Build Script

To build and integrate this React frontend with the Python backend:

1. **Install Node dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Build the production assets**:
   This will automatically output the files to the `../static` folder used by the FastAPI backend.
   ```bash
   npm run build
   ```

3. **Start the Backend**:
   ```bash
   cd ..
   # On Windows
   .\.venv\Scripts\python.exe main.face.py.py
   # On Linux/Mac
   python3 main.face.py.py
   ```

The backend is configured to serve the built React app from the `static` directory.
